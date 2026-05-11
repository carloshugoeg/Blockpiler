import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// --- Blockly mock ---
// Must be hoisted before importing the module under test.
vi.mock('blockly', () => {
  const serializationMock = {
    workspaces: {
      save: vi.fn((ws) => ws._state ?? {}),
      load: vi.fn((state, ws) => { ws._state = state; }),
    },
  };
  return {
    default: { serialization: serializationMock },
    serialization: serializationMock,
  };
});

import { SyncManager } from '../../frontend/features/sync.js';
import Blockly from 'blockly';

// --- Editor / workspace helpers ---

function makeMockEditor() {
  const listeners = [];
  const editor = {
    _value: 'int main() { return 0; }',
    getValue: vi.fn(() => editor._value),
    // setValue simulates Monaco: fires onDidChangeModelContent listeners
    setValue: vi.fn((v) => {
      editor._value = v;
      listeners.forEach((cb) => cb());
    }),
    onDidChangeModelContent: vi.fn((cb) => {
      listeners.push(cb);
      return {
        dispose: () => {
          const i = listeners.indexOf(cb);
          if (i >= 0) listeners.splice(i, 1);
        },
      };
    }),
    _triggerChange: () => listeners.forEach((cb) => cb()),
  };
  return editor;
}

function makeMockWorkspace() {
  const listeners = [];
  const ws = {
    _state: {},
    addChangeListener: vi.fn((cb) => listeners.push(cb)),
    removeChangeListener: vi.fn((cb) => {
      const i = listeners.indexOf(cb);
      if (i >= 0) listeners.splice(i, 1);
    }),
    _triggerChange: (event = {}) => listeners.forEach((cb) => cb(event)),
  };
  return ws;
}

// Flush N microtask ticks (each await fetch / await res.json is one tick)
const flush = (n = 4) =>
  Array.from({ length: n }).reduce((p) => p.then(() => Promise.resolve()), Promise.resolve());

// -------------------------------------------------------------------

describe('T19 · SyncManager', () => {
  let editor, workspace, sync;

  beforeEach(() => {
    vi.useFakeTimers();
    editor = makeMockEditor();
    workspace = makeMockWorkspace();
    sync = new SyncManager(editor, workspace, '');
    vi.clearAllMocks();
    Blockly.serialization.workspaces.save.mockClear();
    Blockly.serialization.workspaces.load.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── Test 1: instantiation ──────────────────────────────────────────
  it('instantiates without throwing', () => {
    expect(() => new SyncManager(editor, workspace, '')).not.toThrow();
  });

  // ── Test 2: 600ms debounce — no sync before 600ms ──────────────────
  it('IDE→Blocks: does NOT sync before 600ms', () => {
    global.fetch = vi.fn();
    sync.enableSync();
    editor._triggerChange();
    vi.advanceTimersByTime(599);
    expect(fetch).not.toHaveBeenCalled();
  });

  // ── Test 3: 600ms debounce — syncs after 600ms ────────────────────
  it('IDE→Blocks: syncs after 600ms with c_to_blocks', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: true, data: { workspace: { blocks: [] } } }),
    });
    sync.enableSync();
    editor._triggerChange();
    vi.advanceTimersByTime(600);
    await flush();

    expect(fetch).toHaveBeenCalledOnce();
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain('/api/convert');
    expect(JSON.parse(opts.body)).toMatchObject({ direction: 'c_to_blocks' });
    expect(Blockly.serialization.workspaces.load).toHaveBeenCalledOnce();
  });

  // ── Test 4: guard prevents re-entrancy ────────────────────────────
  it('guard: Blocks→IDE sync does not loop back through IDE→Blocks', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: true, data: { source: 'int x = 1;' } }),
    });
    sync.enableSync();

    // Trigger blocks change (immediate, no debounce)
    workspace._triggerChange({ isUiEvent: false });
    await flush();

    // editor.setValue was called (Blocks→IDE)
    expect(editor.setValue).toHaveBeenCalledWith('int x = 1;');
    // setValue fired onDidChangeModelContent internally, but _guard was true → no debounce
    vi.advanceTimersByTime(600);
    await flush();

    // Only one fetch (blocks_to_c). No second fetch for c_to_blocks.
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ direction: 'blocks_to_c' });
  });

  // ── Test 5: API error — Blockly not modified ──────────────────────
  it('IDE→Blocks: Blockly not loaded when API returns error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: false, errors: [{ code: 'PAR001', message: 'parse error' }] }),
    });
    sync.enableSync();
    editor._triggerChange();
    vi.advanceTimersByTime(600);
    await flush();

    expect(fetch).toHaveBeenCalledOnce();
    expect(Blockly.serialization.workspaces.load).not.toHaveBeenCalled();
  });

  // ── Test 6: API error — IDE not modified ──────────────────────────
  it('Blocks→IDE: editor not updated when API returns error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({ ok: false, errors: [{ code: 'SEM001', message: 'type error' }] }),
    });
    sync.enableSync();
    workspace._triggerChange({ isUiEvent: false });
    await flush();

    expect(editor.setValue).not.toHaveBeenCalled();
  });

  // ── Test 7: disableSync removes listeners ────────────────────────
  it('disableSync: no sync after disabling', () => {
    global.fetch = vi.fn();
    sync.enableSync();
    sync.disableSync();
    editor._triggerChange();
    vi.advanceTimersByTime(600);
    workspace._triggerChange({ isUiEvent: false });
    expect(fetch).not.toHaveBeenCalled();
  });
});
