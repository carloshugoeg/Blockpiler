import { describe, it, expect, vi, beforeAll } from 'vitest';

// --- Blockly mock ---
// Blockly requires a real browser (SVG, DOM event system). We mock its API
// surface so blockly_setup.js can import and execute cleanly in jsdom.

const registeredBlocks = {};
const registeredGenerators = {};
const mockWorkspace = {
  _state: {},
  addChangeListener: vi.fn(),
  dispose: vi.fn(),
};

vi.mock('blockly', () => {
  const Blocks = new Proxy({}, {
    set(target, key, value) { registeredBlocks[key] = value; target[key] = value; return true; },
    get(target, key) { return target[key]; },
  });
  const JavaScript = new Proxy({}, {
    set(target, key, value) { registeredGenerators[key] = value; target[key] = value; return true; },
  });
  return {
    default: {
      Blocks,
      JavaScript,
      inject: vi.fn(() => mockWorkspace),
      serialization: {
        workspaces: {
          save: vi.fn((ws) => ws._state),
          load: vi.fn((state, ws) => { ws._state = state; }),
        },
      },
    },
    Blocks,
    JavaScript,
    inject: vi.fn(() => mockWorkspace),
    serialization: {
      workspaces: {
        save: vi.fn((ws) => ws._state),
        load: vi.fn((state, ws) => { ws._state = state; }),
      },
    },
  };
});

import {
  setupBlockly,
  getWorkspace,
  getWorkspaceJSON,
  loadWorkspaceJSON,
} from '../../frontend/blocks/blockly_setup.js';

// -------------------------------------------------------------------

describe('T18 · blockly_setup', () => {
  beforeAll(() => {
    const container = document.createElement('div');
    setupBlockly(container);
  });

  // Test 1 — setupBlockly mounts without throwing
  it('setupBlockly mounts without throwing', () => {
    const container = document.createElement('div');
    expect(() => setupBlockly(container)).not.toThrow();
    expect(getWorkspace()).toBeTruthy();
  });

  // Test 2 — c_func_call_expr has output, c_func_call_stmt does not
  it('c_func_call_expr has output; c_func_call_stmt has previousStatement', () => {
    expect(registeredBlocks['c_func_call_expr']).toBeDefined();
    expect(registeredBlocks['c_func_call_stmt']).toBeDefined();

    // Each block definition stores its JSON config for inspection
    const exprDef = registeredBlocks['c_func_call_expr']._def;
    const stmtDef = registeredBlocks['c_func_call_stmt']._def;

    expect(exprDef).toHaveProperty('output');
    expect(stmtDef).not.toHaveProperty('output');
    expect(stmtDef).toHaveProperty('previousStatement');
  });

  // Test 3 — all §14.2 block types are defined
  it('defines all required block types', () => {
    const required = [
      'c_var_decl', 'c_array_decl',
      'c_if', 'c_while', 'c_for', 'c_dowhile',
      'c_return', 'c_break', 'c_continue',
      'c_print', 'c_println',
      'c_binary_arith', 'c_binary_cmp', 'c_binary_logic',
      'c_unary_not', 'c_unary_neg',
      'c_prefix_inc', 'c_prefix_dec', 'c_postfix_inc', 'c_postfix_dec',
      'c_assign', 'c_compound_assign', 'c_array_assign',
      'c_func_decl', 'c_param', 'c_func_call_expr', 'c_func_call_stmt',
      'c_lit_int', 'c_lit_float', 'c_lit_bool', 'c_lit_string', 'c_lit_char',
      'c_identifier', 'c_index_expr',
      'c_input', 'c_input_int', 'c_input_float',
      'c_cast',
    ];
    for (const name of required) {
      expect(registeredBlocks[name], `block "${name}" not registered`).toBeDefined();
    }
  });

  // Test 4 — Blockly visual types are correct (§14.1)
  it('c_binary_arith outputs Number; c_binary_cmp outputs Boolean; c_binary_logic outputs Boolean', () => {
    expect(registeredBlocks['c_binary_arith']._def.output).toBe('Number');
    expect(registeredBlocks['c_binary_cmp']._def.output).toBe('Boolean');
    expect(registeredBlocks['c_binary_logic']._def.output).toBe('Boolean');
  });

  // Test 5 — literal blocks have correct output types (§14.1)
  it('literal blocks carry correct Blockly output types', () => {
    expect(registeredBlocks['c_lit_int']._def.output).toBe('Number');
    expect(registeredBlocks['c_lit_float']._def.output).toBe('Number');
    expect(registeredBlocks['c_lit_char']._def.output).toBe('Number');
    expect(registeredBlocks['c_lit_bool']._def.output).toBe('Boolean');
    expect(registeredBlocks['c_lit_string']._def.output).toBe('String');
  });

  // Test 6 — getWorkspaceJSON / loadWorkspaceJSON roundtrip
  it('getWorkspaceJSON / loadWorkspaceJSON roundtrip', () => {
    const state = { blocks: { blocks: [] } };
    loadWorkspaceJSON(state);
    const saved = getWorkspaceJSON();
    expect(saved).toEqual(state);
  });
});
