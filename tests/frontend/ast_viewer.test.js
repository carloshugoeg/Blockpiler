import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── D3 mock ────────────────────────────────────────────────────────��─
// D3 requires Canvas/SVG features unavailable in jsdom. We mock its API
// surface so ast_viewer.js imports cleanly and we can assert on calls.
vi.mock('d3', () => {
  const makeChain = () => {
    const sel = {};
    [
      'attr', 'style', 'text', 'append', 'select', 'selectAll',
      'data', 'join', 'enter', 'on', 'call', 'remove', 'classed', 'filter',
    ].forEach((m) => { sel[m] = vi.fn(() => sel); });
    return sel;
  };

  const makeHierNode = (data) => {
    const node = { data, x: 0, y: 0, id: null };
    node.descendants = vi.fn(() => [node]);
    node.links      = vi.fn(() => []);
    node.each       = vi.fn((fn) => { fn(node); return node; });
    return node;
  };

  const linkFn = vi.fn(() => '');
  linkFn.x = vi.fn(() => linkFn);
  linkFn.y = vi.fn(() => linkFn);

  const treeFn = vi.fn((root) => root);
  treeFn.size = vi.fn(() => treeFn);

  const zoomBeh = vi.fn();
  zoomBeh.scaleExtent = vi.fn(() => zoomBeh);
  zoomBeh.on          = vi.fn(() => zoomBeh);

  return {
    select:       vi.fn(() => makeChain()),
    hierarchy:    vi.fn((data) => makeHierNode(data)),
    tree:         vi.fn(() => treeFn),
    zoom:         vi.fn(() => zoomBeh),
    linkVertical: vi.fn(() => linkFn),
  };
});

import { ASTViewer } from '../../frontend/features/ast_viewer.js';
import * as d3 from 'd3';

// ── AST fixture ──────────────────────────��────────────────────────────
const simpleAst = {
  type: 'Program',
  pos:  { line: 1, col: 0 },
  declarations: [
    {
      type:          'FunctionDecl',
      name:          'main',
      return_type:   'int',
      inferred_type: 'int',
      pos:           { line: 1, col: 4 },
      params:        [],
      body: {
        type: 'Block',
        pos:  { line: 1, col: 16 },
        stmts: [
          {
            type: 'ReturnStmt',
            pos:  { line: 2, col: 2 },
            value: {
              type:          'IntLiteral',
              value:         0,
              inferred_type: 'int',
              pos:           { line: 2, col: 9 },
            },
          },
        ],
      },
    },
  ],
};

// ───────────────────��─────────────────────────────────────────────────

describe('T20 · ASTViewer', () => {
  let container, viewer;

  beforeEach(() => {
    container = document.createElement('div');
    viewer    = new ASTViewer(container);
    vi.clearAllMocks();
  });

  // Test 1 — instantiation
  it('instantiates without throwing', () => {
    expect(() => new ASTViewer(container)).not.toThrow();
  });

  // Test 2 — render does not throw for a well-formed AST
  it('render(simpleAst) does not throw', () => {
    expect(() => viewer.render(simpleAst)).not.toThrow();
  });

  // Test 3 — render null is a no-op, does not throw
  it('render(null) does not throw', () => {
    expect(() => viewer.render(null)).not.toThrow();
  });

  // Test 4 — render calls d3.hierarchy and d3.tree (uses D3 for layout)
  it('render calls d3.hierarchy and d3.tree', () => {
    viewer.render(simpleAst);
    expect(d3.hierarchy).toHaveBeenCalledOnce();
    expect(d3.tree).toHaveBeenCalledOnce();
  });

  // Test 5 — click callback receives {line, col} from node pos
  it('_onNodeClick: callback fires with {line, col}', () => {
    const cb = vi.fn();
    viewer._onNodeClick(cb);
    viewer._handleNodeClick({
      data: { type: 'IntLiteral', inferred_type: 'int', pos: { line: 5, col: 3 } },
    });
    expect(cb).toHaveBeenCalledOnce();
    expect(cb).toHaveBeenCalledWith({ line: 5, col: 3 });
  });

  // Test 6 — no callback when pos is absent
  it('_handleNodeClick: no callback when pos is absent', () => {
    const cb = vi.fn();
    viewer._onNodeClick(cb);
    viewer._handleNodeClick({ data: { type: 'Program' } });
    expect(cb).not.toHaveBeenCalled();
  });

  // Test 7 — _buildD3Tree passes astData to d3.hierarchy
  it('_buildD3Tree passes root AST to d3.hierarchy', () => {
    const ast = { type: 'IntLiteral', value: 42, inferred_type: 'int', pos: { line: 1, col: 0 } };
    viewer._buildD3Tree(ast);
    expect(d3.hierarchy).toHaveBeenCalledWith(ast, expect.any(Function));
  });

  // Test 8 — children extractor picks up a single nested AST node
  it('_buildD3Tree children fn: extracts single nested AST node', () => {
    const ast = { type: 'Program', pos: { line: 1, col: 0 }, declarations: [] };
    viewer._buildD3Tree(ast);
    const childrenFn = d3.hierarchy.mock.calls[0][1];

    const node = {
      type: 'FunctionDecl',
      body: { type: 'Block', pos: { line: 1, col: 10 } },
    };
    const children = childrenFn(node);
    expect(children).toHaveLength(1);
    expect(children[0].type).toBe('Block');
  });

  // Test 9 — children extractor picks up an array of AST nodes
  it('_buildD3Tree children fn: extracts array of AST nodes', () => {
    const ast = { type: 'Program', pos: { line: 1, col: 0 }, declarations: [] };
    viewer._buildD3Tree(ast);
    const childrenFn = d3.hierarchy.mock.calls[0][1];

    const node = {
      type: 'Program',
      declarations: [
        { type: 'FunctionDecl', pos: { line: 1, col: 4 } },
        { type: 'VarDecl',      pos: { line: 5, col: 0 } },
      ],
    };
    const children = childrenFn(node);
    expect(children).toHaveLength(2);
    expect(children[0].type).toBe('FunctionDecl');
    expect(children[1].type).toBe('VarDecl');
  });
});
