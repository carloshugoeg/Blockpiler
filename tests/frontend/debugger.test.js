import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── socket.io-client mock ─────────────────────────────────────────────
// Must be hoisted before the module under test is imported.
vi.mock('socket.io-client', () => {
  const makeSocket = () => {
    const handlers = {};
    const socket = {
      emit:       vi.fn(),
      disconnect: vi.fn(),
      on: vi.fn((event, cb) => {
        handlers[event] = cb;
        return socket;
      }),
      _trigger: (event, data) => {
        if (handlers[event]) handlers[event](data);
      },
    };
    return socket;
  };

  const io = vi.fn(() => makeSocket());
  return { io };
});

import { Debugger } from '../../frontend/features/debugger.js';
import { io } from 'socket.io-client';

// ── helpers ───────────────────────────────────────────────────────────

function makeMockEditor() {
  return {
    deltaDecorations: vi.fn(() => ['dec-id-1']),
  };
}

function makeMockWorkspace() {
  const blocks = [];
  return {
    getAllBlocks: vi.fn(() => blocks),
    highlightBlock: vi.fn(),
    _addBlock: (id, srcLine) => {
      blocks.push({
        id,
        data: JSON.stringify({ srcLine }),
      });
    },
  };
}

function makeDebugger() {
  const editor    = makeMockEditor();
  const workspace = makeMockWorkspace();
  const dbg       = new Debugger(editor, workspace, 'http://localhost:5000');
  return { editor, workspace, dbg };
}

// Returns the socket that io() most recently returned
function lastSocket() {
  return io.mock.results[io.mock.results.length - 1].value;
}

// ─────────────────────────────────────────────────────────────────────

describe('T22 · Debugger', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Test 1 — instantiation
  it('instantiates without throwing', () => {
    expect(() => new Debugger(null, null, 'http://localhost:5000')).not.toThrow();
  });

  // Test 2 — start() creates socket and emits debug:start
  it('start() connects to socketURL and emits debug:start', () => {
    const { dbg } = makeDebugger();
    dbg.start('int main() { return 0; }');

    expect(io).toHaveBeenCalledWith('http://localhost:5000');
    const sock = lastSocket();
    expect(sock.emit).toHaveBeenCalledWith(
      'debug:start',
      { source: 'int main() { return 0; }' },
    );
  });

  // Test 3 — step() emits debug:step
  it('step() emits debug:step', () => {
    const { dbg } = makeDebugger();
    dbg.start('int main() {}');
    const sock = lastSocket();
    sock.emit.mockClear();

    dbg.step();
    expect(sock.emit).toHaveBeenCalledWith('debug:step');
  });

  // Test 4 — continue() emits debug:continue with serialized breakpoints
  it('continue(Set) emits debug:continue with breakpoints array', () => {
    const { dbg } = makeDebugger();
    dbg.start('int main() {}');
    const sock = lastSocket();
    sock.emit.mockClear();

    dbg.continue(new Set([3, 7]));
    expect(sock.emit).toHaveBeenCalledWith('debug:continue', {
      breakpoints: expect.arrayContaining([3, 7]),
    });
    expect(sock.emit.mock.calls[0][1].breakpoints).toHaveLength(2);
  });

  // Test 5 — stop() emits debug:stop and disconnects
  it('stop() emits debug:stop and disconnects socket', () => {
    const { dbg } = makeDebugger();
    dbg.start('int main() {}');
    const sock = lastSocket();
    sock.emit.mockClear();

    dbg.stop();
    expect(sock.emit).toHaveBeenCalledWith('debug:stop');
    expect(sock.disconnect).toHaveBeenCalledOnce();
  });

  // Test 6 — _onState calls _highlightLine with state.line
  it('_onState() calls _highlightLine with state.line', () => {
    const { dbg } = makeDebugger();
    const spy = vi.spyOn(dbg, '_highlightLine');
    dbg._onState({ line: 5, variables: {}, call_stack: [] });
    expect(spy).toHaveBeenCalledWith(5);
  });

  // Test 7 — _onState null is a no-op
  it('_onState(null) does not throw', () => {
    const { dbg } = makeDebugger();
    expect(() => dbg._onState(null)).not.toThrow();
  });

  // Test 8 — _onState calls _updateVariablesPanel
  it('_onState() calls _updateVariablesPanel with variables', () => {
    const { dbg } = makeDebugger();
    const spy = vi.spyOn(dbg, '_updateVariablesPanel');
    dbg._onState({ line: 1, variables: { x: 42, y: 'hello' }, call_stack: [] });
    expect(spy).toHaveBeenCalledWith({ x: 42, y: 'hello' });
  });

  // Test 9 — _onState calls _updateCallStack
  it('_onState() calls _updateCallStack with call_stack', () => {
    const { dbg } = makeDebugger();
    const spy = vi.spyOn(dbg, '_updateCallStack');
    dbg._onState({ line: 1, variables: {}, call_stack: ['main', 'fib'] });
    expect(spy).toHaveBeenCalledWith(['main', 'fib']);
  });

  // Test 10 — _highlightLine calls editor.deltaDecorations
  it('_highlightLine() calls editor.deltaDecorations with correct line', () => {
    const { dbg, editor } = makeDebugger();
    dbg._highlightLine(7);
    expect(editor.deltaDecorations).toHaveBeenCalledOnce();
    const [, newDecs] = editor.deltaDecorations.mock.calls[0];
    expect(newDecs[0].range.startLineNumber).toBe(7);
    expect(newDecs[0].options.isWholeLine).toBe(true);
  });

  // Test 11 — _highlightLine highlights correct Blockly block
  it('_highlightLine() highlights the Blockly block with matching srcLine', () => {
    const { dbg, workspace } = makeDebugger();
    workspace._addBlock('block-a', 3);
    workspace._addBlock('block-b', 7);
    dbg._highlightLine(7);
    expect(workspace.highlightBlock).toHaveBeenCalledWith('block-b');
  });

  // Test 12 — _highlightLine with no matching block highlights null
  it('_highlightLine() calls highlightBlock(null) when no block matches', () => {
    const { dbg, workspace } = makeDebugger();
    workspace._addBlock('block-a', 3);
    dbg._highlightLine(99);
    expect(workspace.highlightBlock).toHaveBeenCalledWith(null);
  });

  // Test 13 — _updateVariablesPanel renders rows in the mounted panel
  it('_updateVariablesPanel renders one row per variable', () => {
    const { dbg } = makeDebugger();
    const container = document.createElement('div');
    dbg.mountUI(container);

    dbg._updateVariablesPanel({ x: 10, y: 'hello' });
    const rows = container.querySelectorAll('.dbg-var-row');
    expect(rows.length).toBe(2);
  });

  // Test 14 — _updateCallStack renders stack frames
  it('_updateCallStack renders one frame per entry', () => {
    const { dbg } = makeDebugger();
    const container = document.createElement('div');
    dbg.mountUI(container);

    dbg._updateCallStack(['main', 'factorial']);
    const frames = container.querySelectorAll('.dbg-stack-frame');
    expect(frames.length).toBe(2);
    expect(frames[0].textContent).toBe('main');
    expect(frames[1].textContent).toBe('factorial');
  });

  // Test 15 — mountUI creates Step, Continue, Stop buttons
  it('mountUI() creates Step, Continue, Stop buttons', () => {
    const { dbg } = makeDebugger();
    const container = document.createElement('div');
    dbg.mountUI(container);

    const buttons = container.querySelectorAll('button');
    const labels  = [...buttons].map((b) => b.textContent);
    expect(labels).toContain('Step');
    expect(labels).toContain('Continue');
    expect(labels).toContain('Stop');
  });

  // Test 16 — socket receives debug:state and routes to _onState
  it('socket debug:state event triggers _onState', () => {
    const { dbg } = makeDebugger();
    const spy = vi.spyOn(dbg, '_onState');
    dbg.start('int main() {}');

    const sock  = lastSocket();
    const state = { line: 3, variables: { i: 0 }, call_stack: ['main'], finished: false };
    sock._trigger('debug:state', state);

    expect(spy).toHaveBeenCalledWith(state);
  });
});
