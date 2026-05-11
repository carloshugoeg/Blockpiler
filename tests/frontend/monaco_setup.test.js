import { describe, it, expect, vi, beforeEach } from 'vitest';

// --- Monaco mock ---
// Monaco requires a real browser environment (Canvas, Web Workers, etc.).
// We replicate its API surface so monaco_setup.js imports cleanly and
// so we can inspect what was registered.

const registeredProviders = {
  monarch: null,
  completion: null,
  hover: null,
  signatureHelp: null,
  formatter: null,
};

const mockEditor = {
  getValue:   vi.fn(() => ''),
  setValue:   vi.fn((v) => { mockEditor._value = v; }),
  _value:     '',
  getModel:   vi.fn(() => ({ getFullModelRange: vi.fn() })),
  addCommand: vi.fn(),
  onDidChangeModelContent: vi.fn(),
  getAction:  vi.fn(() => ({ run: vi.fn() })),
};

// Keep getValue in sync with setValue
mockEditor.getValue.mockImplementation(() => mockEditor._value);

vi.mock('monaco-editor', () => ({
  languages: {
    register:                          vi.fn(),
    setMonarchTokensProvider:          vi.fn((_, provider) => { registeredProviders.monarch = provider; }),
    registerCompletionItemProvider:    vi.fn((_, provider) => { registeredProviders.completion = provider; }),
    registerHoverProvider:             vi.fn((_, provider) => { registeredProviders.hover = provider; }),
    registerSignatureHelpProvider:     vi.fn((_, provider) => { registeredProviders.signatureHelp = provider; }),
    registerDocumentFormattingEditProvider: vi.fn((_, provider) => { registeredProviders.formatter = provider; }),
    CompletionItemKind: {
      Keyword: 'Keyword', Function: 'Function', Variable: 'Variable', Snippet: 'Snippet',
    },
    CompletionItemInsertTextRule: { InsertAsSnippet: 4 },
  },
  editor: {
    create:           vi.fn(() => mockEditor),
    setModelMarkers:  vi.fn(),
  },
  KeyMod:    { CtrlCmd: 2048 },
  KeyCode:   { KeyS: 83 },
  MarkerSeverity: { Error: 8, Warning: 4, Info: 2 },
}));

// Import AFTER mock is set up
import {
  setupMonaco,
  getEditorValue,
  setEditorValue,
  getEditor,
} from '../../frontend/ide/monaco_setup.js';

// -------------------------------------------------------------------

describe('T17 · monaco_setup', () => {
  beforeEach(() => {
    mockEditor._value = '';
    mockEditor.getValue.mockClear();
    mockEditor.setValue.mockClear();
    delete window.__symbolTable;
  });

  // Test 1 — setupMonaco does not throw when mounted in a DOM container
  it('setupMonaco mounts without throwing', () => {
    const container = document.createElement('div');
    expect(() => setupMonaco(container)).not.toThrow();
    const ed = getEditor();
    expect(ed).toBeTruthy();
  });

  // Test 2 — Monarch tokenizer recognises correct token types for §3.3 tokens
  it('tokenizer classifies int, float, for, println correctly', () => {
    // The Monarch provider was registered during setupMonaco above.
    const provider = registeredProviders.monarch;
    expect(provider).not.toBeNull();

    // Verify keyword sets are present and correct
    expect(provider.keywords).toContain('for');
    expect(provider.keywords).toContain('if');
    expect(provider.keywords).not.toContain('int');   // int is type_keyword
    expect(provider.keywords).not.toContain('println'); // println is builtin

    expect(provider.type_keywords).toContain('int');
    expect(provider.type_keywords).toContain('float');
    expect(provider.type_keywords).not.toContain('for');

    expect(provider.builtins).toContain('println');
    expect(provider.builtins).toContain('printf');
    expect(provider.builtins).toContain('input_int');
    expect(provider.builtins).toContain('input_float');
    expect(provider.builtins).not.toContain('for');

    // Verify the identifier rule dispatches to the right token categories
    const identifierRule = provider.tokenizer.root.find(r => Array.isArray(r) && String(r[0]) === '/[a-zA-Z_]\\w*/');
    expect(identifierRule).toBeTruthy();
    const cases = identifierRule[1].cases;
    expect(cases['@keywords']).toBe('keyword');
    expect(cases['@type_keywords']).toBe('keyword.type');
    expect(cases['@builtins']).toBe('keyword.builtin');
  });

  // Test 3 — setEditorValue / getEditorValue roundtrip
  it('setEditorValue / getEditorValue roundtrip', () => {
    const code = 'int x = 1;';
    setEditorValue(code);
    expect(getEditorValue()).toBe(code);
  });

  // Bonus — completion provider works without __symbolTable
  it('completion provider returns suggestions without __symbolTable', () => {
    const provider = registeredProviders.completion;
    expect(provider).not.toBeNull();
    const model = {
      getWordUntilPosition: vi.fn(() => ({ startColumn: 1, endColumn: 1 })),
    };
    const result = provider.provideCompletionItems(model, { lineNumber: 1, column: 1 });
    expect(result.suggestions.length).toBeGreaterThan(0);
  });

  // Bonus — completion provider adds symbol table entries when present
  it('completion provider includes __symbolTable symbols', () => {
    window.__symbolTable = { myVar: { kind: 'variable', type: 'int' } };
    const provider = registeredProviders.completion;
    const model = {
      getWordUntilPosition: vi.fn(() => ({ startColumn: 1, endColumn: 1 })),
    };
    const result = provider.provideCompletionItems(model, { lineNumber: 1, column: 1 });
    const labels = result.suggestions.map(s => s.label);
    expect(labels).toContain('myVar');
  });
});
