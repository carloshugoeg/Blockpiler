import * as monaco from 'monaco-editor';

// Vite worker setup for Monaco
self.MonacoEnvironment = {
  getWorkerUrl: (_moduleId, label) => {
    if (label === 'json')
      return new URL('monaco-editor/esm/vs/language/json/json.worker', import.meta.url).href;
    if (label === 'css' || label === 'scss' || label === 'less')
      return new URL('monaco-editor/esm/vs/language/css/css.worker', import.meta.url).href;
    if (label === 'html' || label === 'handlebars' || label === 'razor')
      return new URL('monaco-editor/esm/vs/language/html/html.worker', import.meta.url).href;
    if (label === 'typescript' || label === 'javascript')
      return new URL('monaco-editor/esm/vs/language/typescript/ts.worker', import.meta.url).href;
    return new URL('monaco-editor/esm/vs/editor/editor.worker', import.meta.url).href;
  },
};

const LANG_ID = 'c-compileflow';

// Token sets from spec §3.3
const KEYWORDS      = ['if', 'else', 'for', 'while', 'do', 'return', 'break', 'continue'];
const TYPE_KEYWORDS  = ['int', 'float', 'char', 'bool', 'void', 'string'];
const BUILTINS      = ['print', 'println', 'printf', 'input', 'input_int', 'input_float', 'true', 'false'];

let languageRegistered = false;
let editor = null;
let checkTimer = null;

function registerLanguage() {
  monaco.languages.register({ id: LANG_ID });

  monaco.languages.setMonarchTokensProvider(LANG_ID, {
    keywords: KEYWORDS,
    type_keywords: TYPE_KEYWORDS,
    builtins: BUILTINS,
    operators: [
      '=', '>', '<', '!', '~', '?', ':',
      '==', '<=', '>=', '!=', '&&', '||', '++', '--',
      '+', '-', '*', '/', '&', '|', '^', '%', '<<', '>>',
      '+=', '-=', '*=', '/=', '&=', '|=', '^=', '%=', '<<=', '>>=',
    ],
    symbols: /[=><!~?:&|+\-*\/^%]+/,
    tokenizer: {
      root: [
        [/[a-zA-Z_]\w*/, {
          cases: {
            '@keywords':     'keyword',
            '@type_keywords': 'keyword.type',
            '@builtins':     'keyword.builtin',
            '@default':      'identifier',
          },
        }],
        { include: '@whitespace' },
        [/[{}()\[\]]/, '@brackets'],
        [/[<>](?!@symbols)/, '@brackets'],
        [/@symbols/, { cases: { '@operators': 'operator', '@default': '' } }],
        [/\d*\.\d+([eE][\-+]?\d+)?/, 'number.float'],
        [/\d+/, 'number'],
        [/"([^"\\]|\\.)*$/, 'string.invalid'],
        [/"/, 'string', '@string_double'],
        [/'[^\\']'/, 'string'],
        [/'/, 'string.invalid'],
      ],
      whitespace: [
        [/[ \t\r\n]+/, ''],
        [/\/\*/, 'comment', '@comment'],
        [/\/\/.*$/, 'comment'],
      ],
      comment: [
        [/[^\/*]+/, 'comment'],
        [/\*\//, 'comment', '@pop'],
        [/[\/*]/, 'comment'],
      ],
      string_double: [
        [/[^\\"]+/, 'string'],
        [/\\./, 'string.escape'],
        [/"/, 'string', '@pop'],
      ],
    },
  });
}

function registerCompletionProvider() {
  monaco.languages.registerCompletionItemProvider(LANG_ID, {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber:   position.lineNumber,
        startColumn:     word.startColumn,
        endColumn:       word.endColumn,
      };

      const suggestions = [
        ...KEYWORDS.map(kw => ({
          label: kw,
          kind: monaco.languages.CompletionItemKind.Keyword,
          insertText: kw,
          range,
        })),
        ...TYPE_KEYWORDS.map(kw => ({
          label: kw,
          kind: monaco.languages.CompletionItemKind.Keyword,
          insertText: kw,
          range,
        })),
        ...BUILTINS.filter(b => b !== 'true' && b !== 'false').map(b => ({
          label: b,
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: b,
          range,
        })),
        {
          label: 'if (snippet)',
          kind: monaco.languages.CompletionItemKind.Snippet,
          insertText: 'if (${1:condición}) {\n\t${2}\n}',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Instrucción condicional',
          range,
        },
        {
          label: 'for (snippet)',
          kind: monaco.languages.CompletionItemKind.Snippet,
          insertText: 'for (${1:init}; ${2:condición}; ${3:actualización}) {\n\t${4}\n}',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Bucle for',
          range,
        },
        {
          label: 'while (snippet)',
          kind: monaco.languages.CompletionItemKind.Snippet,
          insertText: 'while (${1:condición}) {\n\t${2}\n}',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: 'Bucle while',
          range,
        },
      ];

      if (window.__symbolTable) {
        for (const [name, info] of Object.entries(window.__symbolTable)) {
          suggestions.push({
            label: name,
            kind: info.kind === 'function'
              ? monaco.languages.CompletionItemKind.Function
              : monaco.languages.CompletionItemKind.Variable,
            insertText: name,
            documentation: info.type ? `${info.type} ${name}` : name,
            range,
          });
        }
      }

      return { suggestions };
    },
  });
}

function registerHoverProvider() {
  const docs = {
    print:       'Imprime texto en la salida estándar sin salto de línea.',
    println:     'Imprime texto en la salida estándar con salto de línea.',
    printf:      'Imprime texto usando formato estilo C.',
    input:       'Lee una línea de texto del usuario.',
    input_int:   'Lee un número entero del usuario.',
    input_float: 'Lee un número flotante del usuario.',
    if:          'Instrucción condicional.',
    else:        'Rama alternativa de una instrucción if.',
    for:         'Bucle for con inicialización, condición y actualización.',
    while:       'Bucle while — repite mientras la condición sea verdadera.',
    do:          'Bucle do-while — ejecuta el cuerpo al menos una vez.',
    return:      'Retorna un valor desde la función actual.',
    break:       'Sale del bucle o switch más cercano.',
    continue:    'Salta a la siguiente iteración del bucle.',
    int:         'Tipo entero de 32 bits.',
    float:       'Tipo punto flotante de 64 bits.',
    char:        'Tipo carácter de un byte.',
    bool:        'Tipo booleano (true / false).',
    void:        'Tipo vacío — sin valor de retorno.',
    string:      'Tipo cadena de texto.',
    true:        'Valor booleano verdadero.',
    false:       'Valor booleano falso.',
  };

  monaco.languages.registerHoverProvider(LANG_ID, {
    provideHover: (model, position) => {
      const word = model.getWordAtPosition(position);
      if (!word) return null;
      const doc = docs[word.word];
      if (!doc) return null;
      return { contents: [{ value: `**${word.word}**: ${doc}` }] };
    },
  });
}

function registerSignatureHelpProvider() {
  monaco.languages.registerSignatureHelpProvider(LANG_ID, {
    signatureHelpTriggerCharacters: ['(', ','],
    provideSignatureHelp: (model, position) => {
      if (!window.__symbolTable) return null;
      const textBefore = model.getValueInRange({
        startLineNumber: 1,
        startColumn:     1,
        endLineNumber:   position.lineNumber,
        endColumn:       position.column,
      });
      const match = textBefore.match(/(\w+)\s*\([^)]*$/);
      if (!match) return null;
      const fnInfo = window.__symbolTable[match[1]];
      if (!fnInfo || fnInfo.kind !== 'function') return null;
      const params = fnInfo.params || [];
      return {
        value: {
          signatures: [{
            label:      `${fnInfo.type || 'void'} ${match[1]}(${params.join(', ')})`,
            parameters: params.map(p => ({ label: p })),
          }],
          activeSignature: 0,
          activeParameter: (textBefore.match(/,/g) || []).length,
        },
        dispose: () => {},
      };
    },
  });
}

function registerFormatter() {
  monaco.languages.registerDocumentFormattingEditProvider(LANG_ID, {
    provideDocumentFormattingEdits: (model) => {
      const lines = model.getValue().split('\n');
      let indent = 0;
      const formatted = lines.map(line => {
        const trimmed = line.trim();
        if (trimmed.startsWith('}')) indent = Math.max(0, indent - 1);
        const result = '\t'.repeat(indent) + trimmed;
        if (trimmed.endsWith('{')) indent++;
        return result;
      });
      return [{ range: model.getFullModelRange(), text: formatted.join('\n') }];
    },
  });
}

export function setupMonaco(container, options = {}) {
  if (!languageRegistered) {
    registerLanguage();
    registerCompletionProvider();
    registerHoverProvider();
    registerSignatureHelpProvider();
    registerFormatter();
    languageRegistered = true;
  }

  editor = monaco.editor.create(container, {
    language:          LANG_ID,
    theme:             options.theme || 'vs-dark',
    automaticLayout:   true,
    formatOnSave:      true,
    minimap:           { enabled: options.minimap !== false },
    fontSize:          options.fontSize || 14,
    ...options,
  });

  editor.addCommand(
    monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
    () => editor.getAction('editor.action.formatDocument').run(),
  );

  editor.onDidChangeModelContent(() => {
    clearTimeout(checkTimer);
    checkTimer = setTimeout(runCheck, 300);
  });

  return editor;
}

async function runCheck() {
  if (!editor) return;
  const code = editor.getValue();
  try {
    const response = await fetch('/api/check', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ source: code }),
    });
    const data = await response.json();
    const model = editor.getModel();
    if (!model) return;

    const markers = [];
    for (const err of [...(data.errors || []), ...(data.warnings || [])]) {
      markers.push({
        severity:        err.severity === 'warning' ? monaco.MarkerSeverity.Warning
                       : err.severity === 'info'    ? monaco.MarkerSeverity.Info
                       :                              monaco.MarkerSeverity.Error,
        startLineNumber: err.line,
        startColumn:     err.column,
        endLineNumber:   err.line,
        endColumn:       err.column + (err.length || 1),
        message:         err.message,
        code:            err.code,
      });
    }

    monaco.editor.setModelMarkers(model, LANG_ID, markers);

    if (data.ok && data.symbol_table) {
      window.__symbolTable = data.symbol_table;
    }
  } catch (_) {
    // Silently ignore network errors
  }
}

export function getEditorValue() {
  return editor ? editor.getValue() : '';
}

export function setEditorValue(code) {
  if (editor) editor.setValue(code);
}

export function getEditor() {
  return editor;
}
