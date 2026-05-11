import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AsmPanel } from '../../frontend/features/asm_panel.js';

// ── fixtures ──────────────────────────────────────────────────────────

const SIMPLE_ASM = [
  '_main:',
  '    stp x29, x30, [sp, #-16]!',
  '    mov x29, sp',
  '    mov w0, #42',
  '    ldp x29, x30, [sp], #16',
  '    ret',
].join('\n');

// lineMap: asm_line_number → c_line_number  (1-indexed)
const SIMPLE_LINE_MAP = { 2: 1, 3: 1, 4: 2, 5: 3, 6: 3 };

// ─────────────────────────────────────────────────────────────────────

describe('T21 · AsmPanel', () => {
  let container, panel;

  beforeEach(() => {
    container = document.createElement('div');
    panel     = new AsmPanel(container, null);
    vi.clearAllMocks();
  });

  // Test 1 — instantiation
  it('instantiates without throwing', () => {
    expect(() => new AsmPanel(document.createElement('div'), null)).not.toThrow();
  });

  // Test 2 — render well-formed assembly does not throw
  it('render(assembly, lineMap) does not throw for well-formed input', () => {
    expect(() => panel.render(SIMPLE_ASM, SIMPLE_LINE_MAP)).not.toThrow();
  });

  // Test 3 — render empty string does not throw
  it('render("") does not throw', () => {
    expect(() => panel.render('', {})).not.toThrow();
  });

  // Test 4 — container has child divs after render
  it('render populates container with one div per line', () => {
    panel.render(SIMPLE_ASM, SIMPLE_LINE_MAP);
    const lineCount = SIMPLE_ASM.split('\n').length;
    expect(container.querySelectorAll('.asm-line').length).toBe(lineCount);
  });

  // Test 5 — _buildReverseMap inverts the lineMap
  it('_buildReverseMap inverts lineMap: c_line → first asm_line', () => {
    const rev = panel._buildReverseMap({ 2: 1, 3: 1, 4: 2 });
    expect(rev[1]).toBe(2);  // first asm line for c-line 1 is 2
    expect(rev[2]).toBe(4);
  });

  // Test 6 — _buildReverseMap returns empty object for empty input
  it('_buildReverseMap({}) returns empty object', () => {
    expect(panel._buildReverseMap({})).toEqual({});
  });

  // Test 7 — syncWithEditor calls _highlightAsmLine with correct line
  it('syncWithEditor(cLine) highlights the correct asm line', () => {
    panel.render(SIMPLE_ASM, SIMPLE_LINE_MAP);
    const spy = vi.spyOn(panel, '_highlightAsmLine');
    panel.syncWithEditor(2);           // c-line 2 maps to asm-line 4
    expect(spy).toHaveBeenCalledWith(4);
  });

  // Test 8 — syncWithEditor with unmapped line does not throw
  it('syncWithEditor with unmapped c-line does not throw', () => {
    panel.render(SIMPLE_ASM, SIMPLE_LINE_MAP);
    expect(() => panel.syncWithEditor(999)).not.toThrow();
  });

  // Test 9 — _highlightAsmLine adds asm-active class to correct div
  it('_highlightAsmLine adds asm-active to the target line div', () => {
    panel.render(SIMPLE_ASM, SIMPLE_LINE_MAP);
    panel._highlightAsmLine(3);   // 1-indexed → third line div
    const divs = container.querySelectorAll('.asm-line');
    expect(divs[2].classList.contains('asm-active')).toBe(true);
    // other lines must not be active
    expect(divs[0].classList.contains('asm-active')).toBe(false);
    expect(divs[1].classList.contains('asm-active')).toBe(false);
  });

  // Test 10 — _highlightAsmLine with out-of-range index does not throw
  it('_highlightAsmLine out-of-range does not throw', () => {
    panel.render(SIMPLE_ASM, SIMPLE_LINE_MAP);
    expect(() => panel._highlightAsmLine(9999)).not.toThrow();
    expect(() => panel._highlightAsmLine(0)).not.toThrow();
  });
});
