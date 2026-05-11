import * as Blockly from 'blockly';

let workspace = null;

// -------------------------------------------------------------------
// Block definitions
// Each entry exposes ._def so the test suite can inspect JSON config.
// -------------------------------------------------------------------

const BLOCK_DEFS = [
  // ── Variables ──────────────────────────────────────────────────
  {
    type: 'c_var_decl',
    message0: '%1 %2 = %3',
    args0: [
      { type: 'field_dropdown', name: 'TYPE',
        options: [['int','int'],['float','float'],['char','char'],['bool','bool'],['string','string']] },
      { type: 'field_input', name: 'NAME', text: 'x' },
      { type: 'input_value', name: 'VALUE' },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: 330,
  },
  {
    type: 'c_array_decl',
    message0: '%1 %2 [ %3 ]',
    args0: [
      { type: 'field_dropdown', name: 'TYPE',
        options: [['int','int'],['float','float'],['char','char'],['bool','bool'],['string','string']] },
      { type: 'field_input', name: 'NAME', text: 'arr' },
      { type: 'input_value', name: 'SIZE', check: 'Number' },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: 330,
  },
  // ── Assign ─────────────────────────────────────────────────────
  {
    type: 'c_assign',
    message0: '%1 = %2',
    args0: [
      { type: 'field_input', name: 'NAME', text: 'x' },
      { type: 'input_value', name: 'VALUE' },
    ],
    previousStatement: null,
    nextStatement: null,
    inputsInline: true,
    colour: 330,
  },
  {
    type: 'c_compound_assign',
    message0: '%1 %2 %3',
    args0: [
      { type: 'field_input', name: 'NAME', text: 'x' },
      { type: 'field_dropdown', name: 'OP',
        options: [['+=','+='],[ '-=','-='],['*=','*='],[ '/=','/='],[ '%=','%='] ] },
      { type: 'input_value', name: 'VALUE' },
    ],
    previousStatement: null,
    nextStatement: null,
    inputsInline: true,
    colour: 330,
  },
  // ── Control ────────────────────────────────────────────────────
  {
    type: 'c_array_assign',
    message0: '%1 [ %2 ] = %3',
    args0: [
      { type: 'field_input', name: 'NAME', text: 'arr' },
      { type: 'input_value', name: 'INDEX', check: 'Number' },
      { type: 'input_value', name: 'VALUE' },
    ],
    previousStatement: null,
    nextStatement: null,
    inputsInline: true,
    colour: 330,
  },
  // c_if is registered programmatically below (supports dynamic elif)
  {
    type: 'c_while',
    message0: 'mientras %1',
    args0: [{ type: 'input_value', name: 'COND', check: 'Boolean' }],
    message1: '%1',
    args1: [{ type: 'input_statement', name: 'BODY' }],
    previousStatement: null,
    nextStatement: null,
    colour: 210,
  },
  {
    type: 'c_for',
    message0: 'para %1 ; %2 ; %3',
    args0: [
      { type: 'input_value', name: 'INIT' },
      { type: 'input_value', name: 'COND', check: 'Boolean' },
      { type: 'input_value', name: 'UPDATE' },
    ],
    message1: '%1',
    args1: [{ type: 'input_statement', name: 'BODY' }],
    previousStatement: null,
    nextStatement: null,
    colour: 210,
  },
  {
    type: 'c_dowhile',
    message0: 'hacer %1 mientras %2',
    args0: [
      { type: 'input_statement', name: 'BODY' },
      { type: 'input_value', name: 'COND', check: 'Boolean' },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: 210,
  },
  {
    type: 'c_return',
    message0: 'retornar %1',
    args0: [{ type: 'input_value', name: 'VALUE' }],
    previousStatement: null,
    colour: 210,
  },
  {
    type: 'c_break',
    message0: 'salir',
    previousStatement: null,
    nextStatement: null,
    colour: 210,
  },
  {
    type: 'c_continue',
    message0: 'continuar',
    previousStatement: null,
    nextStatement: null,
    colour: 210,
  },
  // ── I/O ────────────────────────────────────────────────────────
  {
    type: 'c_print',
    message0: 'print %1',
    args0: [{ type: 'input_value', name: 'VALUE' }],
    previousStatement: null,
    nextStatement: null,
    inputsInline: true,
    colour: 160,
  },
  {
    type: 'c_println',
    message0: 'println %1',
    args0: [{ type: 'input_value', name: 'VALUE' }],
    previousStatement: null,
    nextStatement: null,
    inputsInline: true,
    colour: 160,
  },
  {
    type: 'c_input',
    message0: 'input',
    output: 'String',
    colour: 160,
  },
  {
    type: 'c_input_int',
    message0: 'input_int',
    output: 'Number',
    colour: 160,
  },
  {
    type: 'c_input_float',
    message0: 'input_float',
    output: 'Number',
    colour: 160,
  },
  // ── Operators ──────────────────────────────────────────────────
  {
    type: 'c_binary_arith',
    message0: '%1 %2 %3',
    args0: [
      { type: 'input_value', name: 'LEFT',  check: 'Number' },
      { type: 'field_dropdown', name: 'OP',
        options: [['+','+'],['-','-'],['*','*'],['/','/'],[  '%','%']] },
      { type: 'input_value', name: 'RIGHT', check: 'Number' },
    ],
    output: 'Number',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_binary_cmp',
    message0: '%1 %2 %3',
    args0: [
      { type: 'input_value', name: 'LEFT' },
      { type: 'field_dropdown', name: 'OP',
        options: [['==','=='],['!=','!='],['<','<'],['<=','<='],[ '>','>'],[  '>=','>='] ] },
      { type: 'input_value', name: 'RIGHT' },
    ],
    output: 'Boolean',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_binary_logic',
    message0: '%1 %2 %3',
    args0: [
      { type: 'input_value', name: 'LEFT',  check: 'Boolean' },
      { type: 'field_dropdown', name: 'OP',
        options: [['&&','&&'],['||','||']] },
      { type: 'input_value', name: 'RIGHT', check: 'Boolean' },
    ],
    output: 'Boolean',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_unary_not',
    message0: '! %1',
    args0: [{ type: 'input_value', name: 'OPERAND', check: 'Boolean' }],
    output: 'Boolean',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_unary_neg',
    message0: '- %1',
    args0: [{ type: 'input_value', name: 'OPERAND', check: 'Number' }],
    output: 'Number',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_prefix_inc',
    message0: '++ %1',
    args0: [{ type: 'field_input', name: 'NAME', text: 'x' }],
    output: 'Number',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_prefix_dec',
    message0: '-- %1',
    args0: [{ type: 'field_input', name: 'NAME', text: 'x' }],
    output: 'Number',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_postfix_inc',
    message0: '%1 ++',
    args0: [{ type: 'field_input', name: 'NAME', text: 'x' }],
    output: 'Number',
    inputsInline: true,
    colour: 230,
  },
  {
    type: 'c_postfix_dec',
    message0: '%1 --',
    args0: [{ type: 'field_input', name: 'NAME', text: 'x' }],
    output: 'Number',
    inputsInline: true,
    colour: 230,
  },
  // ── Functions ──────────────────────────────────────────────────
  {
    type: 'c_func_decl',
    message0: '%1 función %2 ( %3 ) %4',
    args0: [
      { type: 'field_dropdown', name: 'TYPE',
        options: [['void','void'],['int','int'],['float','float'],['bool','bool'],['string','string']] },
      { type: 'field_input', name: 'NAME', text: 'miFuncion' },
      { type: 'input_value', name: 'PARAMS' },
      { type: 'input_statement', name: 'BODY' },
    ],
    colour: 290,
  },
  {
    type: 'c_param',
    message0: '%1 %2',
    args0: [
      { type: 'field_dropdown', name: 'TYPE',
        options: [['int','int'],['float','float'],['char','char'],['bool','bool'],['string','string']] },
      { type: 'field_input', name: 'NAME', text: 'n' },
    ],
    previousStatement: null,
    nextStatement: null,
    inputsInline: true,
    colour: 290,
  },
  {
    type: 'c_func_call_expr',
    message0: 'llamar %1 ( %2 )',
    args0: [
      { type: 'field_input', name: 'NAME', text: 'miFuncion' },
      { type: 'input_value', name: 'ARGS' },
    ],
    output: null,
    inputsInline: true,
    colour: 290,
  },
  {
    type: 'c_func_call_stmt',
    message0: 'llamar %1 ( %2 )',
    args0: [
      { type: 'field_input', name: 'NAME', text: 'miFuncion' },
      { type: 'input_value', name: 'ARGS' },
    ],
    previousStatement: null,
    nextStatement: null,
    inputsInline: true,
    colour: 290,
  },
  // ── Literals ───────────────────────────────────────────────────
  {
    type: 'c_lit_int',
    message0: '%1',
    args0: [{ type: 'field_number', name: 'VALUE', value: 0, precision: 1 }],
    output: 'Number',
    colour: 60,
  },
  {
    type: 'c_lit_float',
    message0: '%1',
    args0: [{ type: 'field_number', name: 'VALUE', value: 0.0 }],
    output: 'Number',
    colour: 60,
  },
  {
    type: 'c_lit_bool',
    message0: '%1',
    args0: [{ type: 'field_dropdown', name: 'VALUE',
              options: [['true','true'],['false','false']] }],
    output: 'Boolean',
    colour: 60,
  },
  {
    type: 'c_lit_string',
    message0: '"%1"',
    args0: [{ type: 'field_input', name: 'VALUE', text: '' }],
    output: 'String',
    colour: 60,
  },
  {
    type: 'c_lit_char',
    message0: "\'%1\'",
    args0: [{ type: 'field_input', name: 'VALUE', text: 'a' }],
    output: 'Number',
    colour: 60,
  },
  // ── Identifiers / arrays ───────────────────────────────────────
  {
    type: 'c_identifier',
    message0: '%1',
    args0: [{ type: 'field_input', name: 'NAME', text: 'x' }],
    output: null,
    colour: 330,
  },
  {
    type: 'c_index_expr',
    message0: '%1 [ %2 ]',
    args0: [
      { type: 'field_input', name: 'NAME', text: 'arr' },
      { type: 'input_value', name: 'INDEX', check: 'Number' },
    ],
    output: null,
    inputsInline: true,
    colour: 330,
  },
  // ── Cast ───────────────────────────────────────────────────────
  {
    type: 'c_cast',
    message0: '( %1 ) %2',
    args0: [
      { type: 'field_dropdown', name: 'TYPE',
        options: [['int','int'],['float','float'],['char','char'],['bool','bool'],['string','string']] },
      { type: 'input_value', name: 'VALUE' },
    ],
    output: null,
    inputsInline: true,
    colour: 230,
  },
];

// -------------------------------------------------------------------
// Toolbox
// -------------------------------------------------------------------

const TOOLBOX = {
  kind: 'categoryToolbox',
  contents: [
    {
      kind: 'category', name: 'Variables', colour: '330',
      contents: [
        { kind: 'block', type: 'c_var_decl' },
        { kind: 'block', type: 'c_assign' },
        { kind: 'block', type: 'c_compound_assign' },
        { kind: 'block', type: 'c_array_assign' },
        { kind: 'block', type: 'c_identifier' },
      ],
    },
    {
      kind: 'category', name: 'Control', colour: '210',
      contents: [
        { kind: 'block', type: 'c_if' },
        { kind: 'block', type: 'c_while' },
        { kind: 'block', type: 'c_for' },
        { kind: 'block', type: 'c_dowhile' },
        { kind: 'block', type: 'c_return' },
        { kind: 'block', type: 'c_break' },
        { kind: 'block', type: 'c_continue' },
      ],
    },
    {
      kind: 'category', name: 'Funciones', colour: '290',
      contents: [
        { kind: 'block', type: 'c_func_decl' },
        { kind: 'block', type: 'c_param' },
        { kind: 'block', type: 'c_func_call_stmt' },
        { kind: 'block', type: 'c_func_call_expr' },
      ],
    },
    {
      kind: 'category', name: 'I/O', colour: '160',
      contents: [
        { kind: 'block', type: 'c_print' },
        { kind: 'block', type: 'c_println' },
        { kind: 'block', type: 'c_input' },
        { kind: 'block', type: 'c_input_int' },
        { kind: 'block', type: 'c_input_float' },
      ],
    },
    {
      kind: 'category', name: 'Operadores', colour: '230',
      contents: [
        { kind: 'block', type: 'c_binary_arith' },
        { kind: 'block', type: 'c_binary_cmp' },
        { kind: 'block', type: 'c_binary_logic' },
        { kind: 'block', type: 'c_unary_not' },
        { kind: 'block', type: 'c_unary_neg' },
        { kind: 'block', type: 'c_prefix_inc' },
        { kind: 'block', type: 'c_prefix_dec' },
        { kind: 'block', type: 'c_postfix_inc' },
        { kind: 'block', type: 'c_postfix_dec' },
        { kind: 'block', type: 'c_cast' },
      ],
    },
    {
      kind: 'category', name: 'Arrays', colour: '330',
      contents: [
        { kind: 'block', type: 'c_array_decl' },
        { kind: 'block', type: 'c_index_expr' },
      ],
    },
    {
      kind: 'category', name: 'Tipos', colour: '60',
      contents: [
        { kind: 'block', type: 'c_lit_int' },
        { kind: 'block', type: 'c_lit_float' },
        { kind: 'block', type: 'c_lit_bool' },
        { kind: 'block', type: 'c_lit_string' },
        { kind: 'block', type: 'c_lit_char' },
      ],
    },
  ],
};

function getCompileFlowTheme() {
  const themeApi = Object.prototype.hasOwnProperty.call(Blockly, 'Theme') ? Blockly.Theme : null;
  const themesApi = Object.prototype.hasOwnProperty.call(Blockly, 'Themes') ? Blockly.Themes : null;
  if (!themeApi || typeof themeApi.defineTheme !== 'function') {
    return undefined;
  }

  return themeApi.defineTheme('compileflow-modern', {
    base: themesApi?.Classic,
    blockStyles: {
      variable_blocks: { colourPrimary: '#db2777', colourSecondary: '#f9a8d4', colourTertiary: '#9d174d' },
      control_blocks: { colourPrimary: '#0891b2', colourSecondary: '#67e8f9', colourTertiary: '#155e75' },
      function_blocks: { colourPrimary: '#7c3aed', colourSecondary: '#c4b5fd', colourTertiary: '#5b21b6' },
      io_blocks: { colourPrimary: '#059669', colourSecondary: '#86efac', colourTertiary: '#047857' },
      operator_blocks: { colourPrimary: '#4f46e5', colourSecondary: '#a5b4fc', colourTertiary: '#3730a3' },
      type_blocks: { colourPrimary: '#d97706', colourSecondary: '#fcd34d', colourTertiary: '#92400e' },
    },
    categoryStyles: {
      variable_category: { colour: '#db2777' },
      control_category: { colour: '#0891b2' },
      function_category: { colour: '#7c3aed' },
      io_category: { colour: '#059669' },
      operator_category: { colour: '#4f46e5' },
      array_category: { colour: '#0f766e' },
      type_category: { colour: '#d97706' },
    },
    componentStyles: {
      workspaceBackgroundColour: '#f6f9fd',
      toolboxBackgroundColour: '#ffffff',
      toolboxForegroundColour: '#253247',
      flyoutBackgroundColour: '#ffffff',
      flyoutForegroundColour: '#253247',
      flyoutOpacity: 0.98,
      scrollbarColour: '#94a3b8',
      scrollbarOpacity: 0.7,
      insertionMarkerColour: '#2563eb',
      insertionMarkerOpacity: 0.35,
      markerColour: '#2563eb',
      cursorColour: '#db2777',
      selectedGlowColour: '#2563eb',
      selectedGlowOpacity: 0.28,
    },
    fontStyle: {
      family: 'Inter, "Segoe UI", Arial, sans-serif',
      weight: '700',
      size: 12,
    },
    startHats: false,
  });
}

// -------------------------------------------------------------------
// Registration
// -------------------------------------------------------------------

let blocksRegistered = false;

function registerBlocks() {
  for (const def of BLOCK_DEFS) {
    Blockly.Blocks[def.type] = {
      _def: def,
      init() { this.jsonInit(def); },
    };
    // Stub JavaScript generator — guarded because blockly/javascript is a separate package
    if (Blockly.JavaScript) Blockly.JavaScript[def.type] = () => '';
  }

  // c_if: programmatic block with dynamic elif support via saveExtraState/loadExtraState
  Blockly.Blocks['c_if'] = {
    elseIfCount_: 0,

    init() {
      this.appendValueInput('COND').setCheck('Boolean').appendField('si');
      this.appendStatementInput('THEN');
      this.appendStatementInput('ELSE').appendField('si no');
      this.setColour(210);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
    },

    saveExtraState() {
      return this.elseIfCount_ ? { elseIfCount: this.elseIfCount_ } : null;
    },

    loadExtraState(state) {
      const target = (state && state.elseIfCount) || 0;
      while (this.elseIfCount_ > 0) {
        if (this.getInput(`ELIF_COND${this.elseIfCount_ - 1}`))
          this.removeInput(`ELIF_COND${this.elseIfCount_ - 1}`);
        if (this.getInput(`ELIF${this.elseIfCount_ - 1}`))
          this.removeInput(`ELIF${this.elseIfCount_ - 1}`);
        this.elseIfCount_--;
      }
      if (this.getInput('ELSE')) this.removeInput('ELSE');
      for (let i = 0; i < target; i++) {
        this.appendValueInput(`ELIF_COND${i}`).setCheck('Boolean').appendField('si no si');
        this.appendStatementInput(`ELIF${i}`);
        this.elseIfCount_++;
      }
      this.appendStatementInput('ELSE').appendField('si no');
    },
  };
  if (Blockly.JavaScript) Blockly.JavaScript['c_if'] = () => '';
}

// -------------------------------------------------------------------
// Public API
// -------------------------------------------------------------------

export function setupBlockly(container, options = {}) {
  if (!blocksRegistered) {
    registerBlocks();
    blocksRegistered = true;
  }

  const theme = getCompileFlowTheme();

  workspace = Blockly.inject(container, {
    toolbox: TOOLBOX,
    theme,
    renderer: 'zelos',
    move: { scrollbars: true, drag: true, wheel: true },
    zoom: { controls: true, wheel: true, startScale: 0.92 },
    grid: { spacing: 28, length: 3, colour: '#d6e1ef', snap: true },
    trashcan: true,
    ...options,
  });

  // Inject srcLine into block.data on block creation (for debugger T21)
  workspace.addChangeListener((event) => {
    if (event.type === Blockly.Events?.CREATE || event.type === 'create') {
      const block = workspace.getBlockById?.(event.blockId);
      if (block && !block.data) {
        block.data = JSON.stringify({ srcLine: null });
      }
    }
  });

  return workspace;
}

export function getWorkspace() {
  return workspace;
}

export function getWorkspaceJSON() {
  if (!workspace) return {};
  return Blockly.serialization.workspaces.save(workspace);
}

export function loadWorkspaceJSON(json) {
  if (!workspace) return;
  Blockly.serialization.workspaces.load(json, workspace);
}
