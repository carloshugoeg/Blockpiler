const ARM64_TOOLTIPS = {
  mov:     'Copia un valor a un registro. mov x0, x1 → x0 = x1',
  ldr:     'Carga desde memoria a registro. ldr x0, [x29, #-8] → x0 = *(fp-8)',
  str:     'Almacena registro en memoria. str x0, [x29, #-8] → *(fp-8) = x0',
  ldp:     'Carga par de registros desde memoria. ldp x29, x30, [sp] → restaura fp y lr',
  stp:     'Almacena par de registros en memoria. stp x29, x30, [sp, #-16]! → guarda fp y lr',
  add:     'Suma. add x0, x1, x2 → x0 = x1 + x2',
  sub:     'Resta. sub x0, x1, x2 → x0 = x1 - x2',
  mul:     'Multiplica. mul x0, x1, x2 → x0 = x1 * x2',
  sdiv:    'División entera con signo. sdiv x0, x1, x2 → x0 = x1 / x2',
  msub:    'Multiplica y resta (para calcular resto). msub x0, x2, x0, x1 → x0 = x1 - x2*x0',
  neg:     'Niega un registro. neg x0, x1 → x0 = -x1',
  cmp:     'Compara dos operandos actualizando flags. cmp x0, x1 → flags para x0 - x1',
  b:       'Salto incondicional. b .Lend → ir a la etiqueta .Lend',
  bl:      'Llamada a función (salto con enlace). bl printf → llama a printf',
  ret:     'Retorna de función al llamador. ret → vuelve a la dirección guardada en lr',
  cbz:     'Salta si el registro es cero. cbz x0, .Lelse → si x0 == 0, ir a .Lelse',
  cbnz:    'Salta si el registro no es cero. cbnz x0, .Lloop → si x0 != 0, ir a .Lloop',
  'b.eq':  'Salta si igual (flag Z=1). b.eq .L → si igual, ir a .L',
  'b.ne':  'Salta si no igual (Z=0). b.ne .L → si no igual, ir a .L',
  'b.lt':  'Salta si menor (signed). b.lt .L → si menor, ir a .L',
  'b.le':  'Salta si menor o igual (signed). b.le .L → si menor o igual, ir a .L',
  'b.gt':  'Salta si mayor (signed). b.gt .L → si mayor, ir a .L',
  'b.ge':  'Salta si mayor o igual (signed). b.ge .L → si mayor o igual, ir a .L',
  adrp:   'Carga dirección base de página. adrp x0, .Lstr@PAGE → x0 = dirección de página de .Lstr',
  and:     'AND bit a bit. and x0, x1, x2 → x0 = x1 & x2',
  orr:     'OR bit a bit. orr x0, x1, x2 → x0 = x1 | x2',
  eor:     'XOR bit a bit. eor x0, x1, x2 → x0 = x1 ^ x2',
  lsl:     'Desplazamiento lógico a la izquierda. lsl x0, x1, #2 → x0 = x1 << 2',
  lsr:     'Desplazamiento lógico a la derecha. lsr x0, x1, #2 → x0 = x1 >> 2',
  asr:     'Desplazamiento aritmético a la derecha (conserva signo). asr x0, x1, #1 → x0 = x1 >> 1',
  cset:    'Fija registro según flag. cset x0, eq → x0 = (iguales) ? 1 : 0',
  fmov:    'Mueve valor entre registros de punto flotante y enteros. fmov d0, x0',
  fadd:    'Suma en punto flotante. fadd d0, d1, d2 → d0 = d1 + d2',
  fsub:    'Resta en punto flotante. fsub d0, d1, d2 → d0 = d1 - d2',
  fmul:    'Multiplicación en punto flotante. fmul d0, d1, d2 → d0 = d1 * d2',
  fdiv:    'División en punto flotante. fdiv d0, d1, d2 → d0 = d1 / d2',
  fcmp:    'Compara dos valores de punto flotante. fcmp d0, d1 → flags para d0 - d1',
  scvtf:   'Convierte entero con signo a punto flotante. scvtf d0, x0 → d0 = (float)x0',
  fcvtzs:  'Convierte punto flotante a entero con signo (trunca). fcvtzs x0, d0 → x0 = (int)d0',
  // assembler directives
  '.p2align': 'Directiva: alinea el código a 2^N bytes',
  '.globl':   'Directiva: hace un símbolo visible al enlazador',
  '.global':  'Directiva: hace un símbolo visible al enlazador',
  '.asciz':   'Directiva: define una cadena terminada en null',
  '.text':    'Directiva: marca el inicio de la sección de código ejecutable',
  '.section': 'Directiva: cambia a la sección indicada',
  '.build_version': 'Directiva macOS: especifica la versión del SO objetivo',
};

const _REG = /\b(x(?:[12]?\d|30)|w(?:[12]?\d|30)|sp|fp|lr|xzr|wzr|d(?:[12]?\d|30)|s(?:[12]?\d|30))\b/g;
const _IMM = /(#-?\d+)/g;
const _STR = /("(?:[^"\\]|\\.)*")/g;

function _escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function _tokenizeLine(raw) {
  const trimmed = raw.trimStart();

  // comment
  if (trimmed.startsWith(';')) {
    return `<span class="asm-comment">${_escHtml(raw)}</span>`;
  }

  // label  (e.g.  "_main:"  or  ".Lloop_start:")
  const labelMatch = trimmed.match(/^([._\w][\w.]*:)(.*)/s);
  if (labelMatch) {
    const label  = _escHtml(raw.slice(0, raw.indexOf(':') + 1));
    const rest   = raw.slice(raw.indexOf(':') + 1);
    return `<span class="asm-label">${label}</span>${_tokenizeBody(rest)}`;
  }

  // directive line (.section, .globl, .asciz …)
  if (trimmed.startsWith('.')) {
    const spaceIdx = trimmed.indexOf(' ');
    const dir  = spaceIdx === -1 ? trimmed : trimmed.slice(0, spaceIdx);
    const tip  = ARM64_TOOLTIPS[dir] ?? '';
    const rest = spaceIdx === -1 ? '' : trimmed.slice(spaceIdx);
    const indent = raw.slice(0, raw.length - trimmed.length);
    const tipAttr = tip ? ` title="${_escHtml(tip)}"` : '';
    return (
      _escHtml(indent) +
      `<span class="asm-directive"${tipAttr}>${_escHtml(dir)}</span>` +
      _tokenizeBody(rest)
    );
  }

  return _tokenizeBody(raw);
}

function _tokenizeBody(raw) {
  // strip inline comment first
  const semiIdx = raw.indexOf(';');
  const code    = semiIdx === -1 ? raw : raw.slice(0, semiIdx);
  const comment = semiIdx === -1 ? '' : raw.slice(semiIdx);

  // find mnemonic (first non-whitespace word in `code`)
  const mnemonicMatch = code.match(/^(\s*)(\S+)(.*)/s);
  if (!mnemonicMatch) {
    return _escHtml(raw);
  }

  const [, leading, mnemonic, operands] = mnemonicMatch;
  const tip     = ARM64_TOOLTIPS[mnemonic.toLowerCase()] ?? '';
  const tipAttr = tip ? ` title="${_escHtml(tip)}"` : '';
  const cls     = tip ? 'asm-mnemonic' : 'asm-token';

  const operandsHtml = _decorateOperands(operands);
  const commentHtml  = comment
    ? `<span class="asm-comment">${_escHtml(comment)}</span>`
    : '';

  return (
    _escHtml(leading) +
    `<span class="${cls}"${tipAttr}>${_escHtml(mnemonic)}</span>` +
    operandsHtml +
    commentHtml
  );
}

function _decorateOperands(raw) {
  // Replace strings first (to avoid messing with their content)
  const stringSlots = [];
  let s = raw.replace(_STR, (m) => {
    stringSlots.push(m);
    return `\x00STR${stringSlots.length - 1}\x00`;
  });

  // Escape HTML
  s = _escHtml(s);

  // Registers
  s = s.replace(_REG, '<span class="asm-register">$1</span>');

  // Immediates
  s = s.replace(_IMM, '<span class="asm-immediate">$1</span>');

  // Restore strings
  s = s.replace(/\x00STR(\d+)\x00/g, (_, i) =>
    `<span class="asm-string">${_escHtml(stringSlots[Number(i)])}</span>`,
  );

  return s;
}

export class AsmPanel {
  constructor(container, monacoEditor) {
    this._container  = container;
    this._editor     = monacoEditor;
    this._lines      = [];
    this._reverseMap = {};
  }

  render(assembly, lineMap) {
    this._container.innerHTML = '';
    this._lines = [];

    const lines = typeof assembly === 'string' ? assembly.split('\n') : [];
    for (const [i, line] of lines.entries()) {
      const div = document.createElement('div');
      div.className   = 'asm-line';
      div.dataset.asm = String(i + 1);
      div.innerHTML   = _tokenizeLine(line);
      this._container.appendChild(div);
      this._lines.push(div);
    }

    this._reverseMap = this._buildReverseMap(lineMap ?? {});
  }

  syncWithEditor(cLine) {
    const asmLine = this._reverseMap[cLine];
    if (asmLine != null) {
      this._highlightAsmLine(asmLine);
    }
  }

  _buildReverseMap(lineMap) {
    const result = {};
    for (const [asmLine, cLine] of Object.entries(lineMap)) {
      const c = Number(cLine);
      if (result[c] == null) {
        result[c] = Number(asmLine);
      }
    }
    return result;
  }

  _highlightAsmLine(asmLine) {
    for (const div of this._lines) {
      div.classList.remove('asm-active');
    }
    const target = this._lines[asmLine - 1];
    if (target) {
      target.classList.add('asm-active');
      if (typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ block: 'nearest' });
      }
    }
  }
}
