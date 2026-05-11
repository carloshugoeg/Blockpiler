# CompileFlow — Especificación Técnica Auditada v1.1

> **Fuente de verdad para implementación.** Documento consolidado y auditado a partir de `SPEC_TECNICA_AGENTES.md` y `PROYECTO_FINAL.md`.
>
> **Audiencia:** agentes de IA que implementarán el proyecto por módulos.
>
> **Regla de oro:** los agentes NO toman decisiones de diseño. Toda arquitectura está decidida. Si algo es ambiguo, se resuelve en favor de la opción **más conservadora y defensiva**.

---

## 1. CONVENCIONES GLOBALES

### 1.1 Formato de respuesta JSON (backend)

**Error:**

```json
{
  "ok": false,
  "errors": [
    {
      "code": "LEX002",
      "message": "String literal no cerrado",
      "line": 5,
      "column": 12,
      "length": 1,
      "suggestion": "Agrega un cierre de comillas \" al final del string",
      "severity": "error"
    }
  ],
  "warnings": []
}
```

**Éxito:**

```json
{ "ok": true, "data": { ... }, "warnings": [] }
```

`severity ∈ {"error", "warning", "info"}`. `suggestion` es opcional. `length` cuenta caracteres a subrayar desde `column` (1-indexado).

### 1.2 Límites globales

```python
# compiler/limits.py
MAX_SOURCE_SIZE     = 524_288      # 512 KB
MAX_BLOCKS_SIZE     = 2_097_152    # 2 MB
MAX_ERRORS          = 50           # umbral de panic abort
MAX_IDENTIFIER_LEN  = 255
MAX_STRING_LEN      = 4_096
MAX_ARRAY_SIZE      = 65_535
MAX_PARAMS          = 255
MAX_NESTING_DEPTH   = 255
MAX_OUTPUT_SIZE     = 1_048_576    # 1 MB stdout
EXEC_TIMEOUT_SEC    = 10
INTERP_MAX_DEPTH    = 500
INTERP_MAX_ITERS    = 1_000_000
INTERP_TIMEOUT_SEC  = 30
OPTIMIZER_MAX_PASS  = 20
INT64_MIN           = -9_223_372_036_854_775_808
INT64_MAX           =  9_223_372_036_854_775_807
```

### 1.3 Índice de módulos

```
compiler/
  01 ast_nodes.py        Tipos del AST (dataclasses)
  02 error_reporter.py   Acumulador de errores
  03 lexer.py            Tokenizador
  04 parser.py           Recursive descent parser
  05 semantic.py         Análisis semántico + tabla de símbolos
  06 optimizer.py        Passes de optimización
  07 codegen.py          Generador ARM64
  08 interpreter.py      Intérprete (debugger)
  09 blocks_to_ast.py    JSON Blockly → AST
  10 ast_to_blocks.py    AST → JSON Blockly
  11 ast_to_c.py         AST → código C
  12 explainer.py        AST → explicación en español
  13 executor.py         Ensamblar y ejecutar
server/
  14 validators.py       Pydantic models
  15 app.py + routes/    API Flask
frontend/
  16 ide/                Monaco Editor
  17 blocks/             Google Blockly
  18 features/sync.js    Sync bidireccional
  19 features/debugger.js
  20 features/ast_viewer.js
  21 features/asm_panel.js
  22 features/file_io.js
  23 features/gallery.js
  24 features/share.js
  25 features/explainer.js
tests/
  26 tests/              Suite completa
```

---

## 2. LENGUAJE SOPORTADO

### 2.1 Gramática BNF (auditada)

```ebnf
program         → top_decl*
top_decl        → function_decl | var_decl | array_decl

function_decl   → type IDENT '(' param_list? ')' block
param_list      → parameter (',' parameter)*
parameter       → type IDENT

var_decl        → type IDENT ('=' expression)? ';'
array_decl      → type IDENT '[' INT_LIT ']' ('=' '{' expr_list? '}')? ';'

block           → '{' statement* '}'

statement       → if_stmt | while_stmt | for_stmt | dowhile_stmt
                | return_stmt | break_stmt | continue_stmt
                | print_stmt | var_decl | array_decl
                | expression ';' | block

if_stmt         → 'if' '(' expression ')' block
                  ( 'else' 'if' '(' expression ')' block )*
                  ( 'else' block )?

while_stmt      → 'while' '(' expression ')' block
for_stmt        → 'for' '(' for_init ';' expression? ';' expression? ')' block
for_init        → var_decl_inline | expression | /* empty */
var_decl_inline → type IDENT ('=' expression)?   /* sin ';' porque for lo añade */

dowhile_stmt    → 'do' block 'while' '(' expression ')' ';'
return_stmt     → 'return' expression? ';'
break_stmt      → 'break' ';'
continue_stmt   → 'continue' ';'

print_stmt      → ('print' | 'println') '(' expression ')' ';'

expression      → assignment
assignment      → lvalue assign_op assignment | logical_or
assign_op       → '=' | '+=' | '-=' | '*=' | '/=' | '%='
lvalue          → IDENT | IDENT '[' expression ']'

logical_or      → logical_and ('||' logical_and)*
logical_and     → equality ('&&' equality)*
equality        → relational (('==' | '!=') relational)*
relational      → additive (('<' | '>' | '<=' | '>=') additive)*
additive        → multiplicative (('+' | '-') multiplicative)*
multiplicative  → unary (('*' | '/' | '%') unary)*
unary           → ('!' | '-' | '++' | '--') unary | cast
cast            → '(' type ')' cast | postfix
postfix         → primary ('++' | '--')?

primary         → literal | IDENT
                | IDENT '[' expression ']'
                | IDENT '(' arg_list? ')'
                | '(' expression ')'
                | 'input' '(' ')'
                | 'input_int' '(' ')'
                | 'input_float' '(' ')'

literal         → INT_LIT | FLOAT_LIT | STRING_LIT | CHAR_LIT | 'true' | 'false'
arg_list        → expression (',' expression)*
expr_list       → expression (',' expression)*
type            → 'int' | 'float' | 'char' | 'bool' | 'void' | 'string'
```

**Cambios respecto al original:**

- `for_init` permite vacío o solo expresión (no solo declaración).
- `cast` se incorpora a la cadena de precedencia.
- `print_stmt` se desambigua con `'print' | 'println'`.
- Se añade `input_int`, `input_float` como builtins.
- `lvalue` se formaliza (solo IDENT o IDENT[expr] pueden ser target de asignación).

### 2.2 Builtins

| Builtin | Firma | Notas |
|---------|-------|-------|
| `print(x)` | `void(any)` | imprime sin `\n`. Acepta cualquier tipo primitivo. |
| `println(x)` | `void(any)` | imprime con `\n`. |
| `input()` | `() -> string` | lee una línea de stdin (sin `\n` final). |
| `input_int()` | `() -> int` | lee una línea y parsea a int. Error en runtime si falla. |
| `input_float()` | `() -> float` | lee una línea y parsea a float. |

En el AST se representan como `CallExpr` con `name ∈ {"print", "println", ...}`, pero el parser produce `PrintStmt` para `print`/`println` cuando aparecen en posición de statement. `input*` siempre son expresiones.

### 2.3 Tabla de tipos

| Tipo | Tamaño | Representación ARM64 | Registro param |
|------|--------|----------------------|----------------|
| `int` | 8 bytes (int64) | `x0`..`x27` | `x0`..`x7` |
| `float` | 8 bytes (IEEE 754 double) | `d0`..`d15` | `d0`..`d7` |
| `char` | 1 byte | `w0`..`w27` (usar `strb`/`ldrb`) | `w0`..`w7` |
| `bool` | 1 byte (0 ó 1) | `w0`..`w27` | `w0`..`w7` |
| `string` | 8 bytes (puntero) | `x0`..`x27` | `x0`..`x7` |
| `void` | — | — | — |

**Nota:** `string` es un puntero a buffer null-terminated en `.rodata` (literales) o heap (resultado de `input()`). Los strings **son inmutables** en este subset — no hay concatenación con `+` ni modificación.

> **Excepción literal:** el pretty-printer y codegen permiten `StringLiteral + StringLiteral` como azúcar sintáctico que se resuelve en tiempo de compilación (constant folding). En runtime, `string + string` es error SEM011.

---

## 3. MÓDULO 01–03 — AST, ErrorReporter, Lexer

### 3.1 AST (`compiler/ast_nodes.py`)

Dataclasses idénticas al doc original. Se **añade** el campo `is_tail_call: bool = False` en `CallExpr` desde la definición (no solo cuando el optimizer lo marca), para evitar mutación de schema.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

CType = Literal['int', 'float', 'char', 'bool', 'string', 'void', 'unknown']

@dataclass
class SourcePos:
    line: int
    col: int
    length: int = 1

# ─── Top-level ─────────────────────────────────────────────────────────
@dataclass
class Program:
    declarations: list[Any]   # FunctionDecl | VarDecl | ArrayDecl
    pos: SourcePos

# ─── Declaraciones ─────────────────────────────────────────────────────
@dataclass
class FunctionDecl:
    name: str
    return_type: CType
    params: list['Parameter']
    body: 'Block'
    pos: SourcePos

@dataclass
class Parameter:
    name: str
    type: CType
    pos: SourcePos

@dataclass
class VarDecl:
    name: str
    type: CType
    init_expr: Optional[Any]
    pos: SourcePos

@dataclass
class ArrayDecl:
    name: str
    element_type: CType
    size: int
    init_list: list[Any]
    pos: SourcePos

# ─── Statements ────────────────────────────────────────────────────────
@dataclass
class Block:
    stmts: list[Any]
    pos: SourcePos

@dataclass
class IfStmt:
    condition: Any
    then_body: Block
    elif_clauses: list[tuple[Any, Block]]
    else_body: Optional[Block]
    pos: SourcePos

@dataclass
class WhileStmt:
    condition: Any
    body: Block
    pos: SourcePos

@dataclass
class ForStmt:
    init: Optional[Any]        # VarDecl | AssignOp | ExprStmt | None
    condition: Optional[Any]
    update: Optional[Any]
    body: Block
    pos: SourcePos

@dataclass
class DoWhileStmt:
    body: Block
    condition: Any
    pos: SourcePos

@dataclass
class ReturnStmt:
    value: Optional[Any]
    pos: SourcePos

@dataclass
class BreakStmt:
    pos: SourcePos

@dataclass
class ContinueStmt:
    pos: SourcePos

@dataclass
class PrintStmt:
    expr: Any
    newline: bool
    pos: SourcePos

@dataclass
class ExprStmt:
    expr: Any
    pos: SourcePos

# ─── Expresiones ───────────────────────────────────────────────────────
@dataclass
class BinaryOp:
    op: str   # '+','-','*','/','%','==','!=','<','>','<=','>=','&&','||'
             # Internos del optimizador: '<<','>>','&'
    left: Any
    right: Any
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class UnaryOp:
    op: str          # '!','-','++','--'
    operand: Any
    prefix: bool
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class AssignOp:
    op: str          # '=','+=','-=','*=','/=','%='
    target: Any      # Identifier | IndexExpr
    value: Any
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class CallExpr:
    name: str
    args: list[Any]
    inferred_type: CType = 'unknown'
    is_tail_call: bool = False
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class IndexExpr:
    name: str
    index: Any
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class Identifier:
    name: str
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class IntLiteral:
    value: int
    inferred_type: CType = 'int'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class FloatLiteral:
    value: float
    inferred_type: CType = 'float'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class StringLiteral:
    value: str
    inferred_type: CType = 'string'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class CharLiteral:
    value: str       # exactamente 1 carácter
    inferred_type: CType = 'char'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class BoolLiteral:
    value: bool
    inferred_type: CType = 'bool'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class InputExpr:
    variant: Literal['string', 'int', 'float'] = 'string'
    inferred_type: CType = 'string'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))

@dataclass
class CastExpr:
    target_type: CType
    expr: Any
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))
```

**Utilitarios requeridos** (`ast_nodes.py`):

```python
EXPR_TYPES = (BinaryOp, UnaryOp, AssignOp, CallExpr, IndexExpr, Identifier,
              IntLiteral, FloatLiteral, StringLiteral, CharLiteral,
              BoolLiteral, InputExpr, CastExpr)

def is_expression(node: Any) -> bool:
    return isinstance(node, EXPR_TYPES)

def get_pos(node: Any) -> SourcePos:
    return getattr(node, 'pos', SourcePos(0, 0))

def node_type_name(node: Any) -> str:
    return type(node).__name__

def is_lvalue(node: Any) -> bool:
    return isinstance(node, (Identifier, IndexExpr))

def is_pure_expr(node: Any) -> bool:
    """True si evaluar `node` no tiene side effects.

    Literales y Identifiers son puros. BinaryOp/UnaryOp son puros si sus
    hijos lo son, EXCEPTO UnaryOp con '++' o '--'. CallExpr e InputExpr
    NUNCA son puros (asumimos peor caso). AssignOp nunca es puro.
    """
    if isinstance(node, (IntLiteral, FloatLiteral, StringLiteral,
                         CharLiteral, BoolLiteral, Identifier)):
        return True
    if isinstance(node, UnaryOp):
        if node.op in ('++', '--'):
            return False
        return is_pure_expr(node.operand)
    if isinstance(node, BinaryOp):
        return is_pure_expr(node.left) and is_pure_expr(node.right)
    if isinstance(node, CastExpr):
        return is_pure_expr(node.expr)
    if isinstance(node, IndexExpr):
        return is_pure_expr(node.index)
    # CallExpr, InputExpr, AssignOp: impuros
    return False
```

### 3.2 ErrorReporter (`compiler/error_reporter.py`)

Idéntico al doc original. Sin cambios.

### 3.3 Lexer — tipos de token

Idéntico al doc original. Recordatorio: `KEYWORDS` ≠ `TYPE_KEYWORDS` ≠ `BUILTINS`, cada uno produce su `TokenType` respectivo.

```python
KEYWORDS         = {'if','else','for','while','do','return','break','continue'}
TYPE_KEYWORDS    = {'int','float','char','bool','void','string'}
BUILTINS         = {'print','println','input','input_int','input_float','true','false'}
```

### 3.4 Lexer — comportamiento requerido

Validaciones de entrada, comentarios, strings, chars, números, identificadores: como el doc original.

**Correcciones:**

- Un input que solo contiene whitespace/comentarios produce `[Token(EOF,'',1,1,0)]` **sin errores** (es programa vacío válido).
- Input vacío (string `""`): mismo caso anterior, **no es error**.
- Al encontrar un caracter inválido: emitir `Token(ERROR, char, ...)`, reportar `LEX001`, avanzar **exactamente un caracter** (prevención de loop).

### 3.5 Códigos de error del lexer (unificados)

```python
LEXER_ERRORS = {
    'LEX001': "Caracter ilegal '{char}'",
    'LEX002': "String literal no cerrado",
    'LEX003': "Char literal inválido ({reason})",
    'LEX004': "Comentario de bloque '/*' sin cerrar",
    'LEX005': "Número mal formado: '{text}'",
    'LEX006': "Identificador excede {MAX_IDENTIFIER_LEN} caracteres",
    'LEX007': "Secuencia de escape inválida: '\\{ch}'",
    'LEX008': "String literal excede {MAX_STRING_LEN} caracteres",
    'LEX009': "Input no es texto UTF-8 válido",
    'LEX010': "Archivo fuente excede {MAX_SOURCE_SIZE} bytes",
    'LEX011': "Literal entero fuera de rango int64 ({INT64_MIN}..{INT64_MAX})",
    'LEX012': "Literal float fuera de rango o produce Inf/NaN",
}
```

---

## 4. MÓDULO 04 — Parser

### 4.1 Interfaz

```python
class Parser:
    def __init__(self, tokens: list[Token], reporter: ErrorReporter): ...
    def parse(self) -> Program: ...
```

### 4.2 Panic-mode recovery

Tokens de sincronización: `SEMICOLON`, `RBRACE`, `LBRACE`, `EOF`, y **el inicio de una declaración de top-level** (un `TYPE_KW` en columna 1 después de un `RBRACE`).

Si `reporter.error_limit_reached`: retornar el `Program` parcialmente construido inmediatamente.

### 4.3 Rastreo de contexto

```python
self._loop_depth: int = 0
self._func_depth: int = 0
self._nesting_depth: int = 0
self._open_braces: list[SourcePos] = []
self._current_func_type: Optional[CType] = None
self._current_func_name: Optional[str] = None
```

Al terminar el parse, si `self._open_braces` no está vacío: por cada `SourcePos` restante, emitir `PAR003`.

### 4.4 Precedencia de operadores (de menor a mayor)

```
 1. = += -= *= /= %=          (right-associative)
 2. ||                         (left)
 3. &&                         (left)
 4. == !=                      (left)
 5. < > <= >=                  (left)
 6. + -                        (left)
 7. * / %                      (left)
 8. unary !, unary -, ++x, --x, (type)x   (right)
 9. postfix x++, x--, x[i], f(args)
```

### 4.5 Códigos de error

```python
PARSER_ERRORS = {
    'PAR001': "Se esperaba {expected}, se encontró '{found}'",
    'PAR002': "Fin de archivo inesperado dentro de {context}",
    'PAR003': "'{char}' sin cerrar abierto en línea {open_line}",
    'PAR004': "No se permiten funciones anidadas",
    'PAR005': "Se esperaba ';' al final de la declaración",
    'PAR006': "'else' sin 'if' correspondiente",
    'PAR007': "'{stmt}' fuera de un bloque de loop",
    'PAR008': "'return' con valor en función de tipo 'void'",
    'PAR009': "Profundidad de anidamiento excede el máximo ({MAX_NESTING_DEPTH})",
    'PAR010': "Número de argumentos/parámetros excede el máximo ({MAX_PARAMS})",
    'PAR011': "Target de asignación debe ser una variable o acceso a array",
    'PAR012': "Declaración de tipo 'void' solo permitida para funciones",
}
```

---

## 5. MÓDULO 05 — Semántico + Tabla de símbolos

### 5.1 Interfaces (idénticas al original excepto lo anotado)

```python
@dataclass
class Symbol:
    name: str
    type: CType
    kind: Literal['variable', 'parameter', 'function', 'array']
    scope_level: int
    line_declared: int
    col_declared: int
    initial_value: Any = None
    use_count: int = 0
    is_initialized: bool = False
    is_mutated: bool = False
    array_size: int = 0
    # Solo si kind='function':
    return_type: CType = 'void'
    param_types: list[CType] = field(default_factory=list)
    call_count: int = 0

    def to_dict(self) -> dict: ...
```

### 5.2 Estructura del analizador

```python
class SemanticAnalyzer:
    def __init__(self, reporter: ErrorReporter):
        self._scopes: list[dict[str, Symbol]] = [{}]
        self._current_func: Optional[FunctionDecl] = None
        self._loop_depth: int = 0
        self._table = SymbolTable()

    def analyze(self, program: Program) -> SymbolTable: ...
```

**Pasos del análisis en orden:**

1. **Pass 1 — collect functions**: recorre `program.declarations`, registra todas las `FunctionDecl` en `self._table.functions` **sin** analizar sus cuerpos. Esto permite recursión mutua (forward references implícitas).
2. **Pass 2 — globals**: analiza `VarDecl`/`ArrayDecl` de nivel global.
3. **Pass 3 — function bodies**: analiza cada cuerpo de función.
4. **Pass 4 — unused checks**: al final, por cada símbolo con `use_count == 0`, emitir `SEM004` (warning).

### 5.3 Reglas de coerción

```python
# Coerciones seguras: se aplican sin warning
SAFE_WIDENING = {
    # (from, to)
    ('int',  'float'),
    ('char', 'int'),
    ('bool', 'int'),
}

# Coerciones con pérdida potencial: warning SEM012
LOSSY_NARROWING = {
    ('float', 'int'),
    ('int',   'bool'),
    ('int',   'char'),
    ('float', 'bool'),
    ('float', 'char'),
}

def resolve_binary_type(left: CType, right: CType, op: str) -> tuple[CType, bool]:
    """Retorna (tipo_resultado, needs_lossy_warning).

    Si los tipos no pueden combinarse para `op`, retorna ('unknown', False)
    y el caller debe emitir SEM011.

    Es conmutativa para operadores conmutativos (+, *, ==, !=, &&, ||).
    Para - y /, preserva el tipo más amplio de los operandos.
    Para operadores de comparación, el resultado es siempre 'bool'.
    Para && y ||, los operandos deben ser 'bool'; si no, error SEM011.
    """
    # Comparación
    if op in ('==', '!=', '<', '>', '<=', '>='):
        if left == right:
            return ('bool', False)
        if (left, right) in SAFE_WIDENING or (right, left) in SAFE_WIDENING:
            return ('bool', False)
        if left in ('int', 'float', 'char') and right in ('int', 'float', 'char'):
            return ('bool', True)
        return ('unknown', False)

    # Lógico
    if op in ('&&', '||'):
        if left == 'bool' and right == 'bool':
            return ('bool', False)
        return ('unknown', False)

    # Aritmético
    if op in ('+', '-', '*', '/', '%'):
        # String concatenation solo para '+' con ambos strings (azúcar, fold en compile-time)
        if op == '+' and left == 'string' and right == 'string':
            return ('string', False)
        # Tipos numéricos
        if left in ('int', 'float', 'char', 'bool') and right in ('int', 'float', 'char', 'bool'):
            # '%' no permite float
            if op == '%' and ('float' in (left, right)):
                return ('unknown', False)
            if 'float' in (left, right):
                return ('float', False)
            return ('int', False)
        return ('unknown', False)

    return ('unknown', False)
```

### 5.4 Checks semánticos (códigos unificados)

```python
SEMANTIC_ERRORS = {
    # Scope
    'SEM001': "Variable '{name}' usada antes de ser declarada",
    'SEM002': "'{name}' ya fue declarado en este scope (línea {prev_line})",
    'SEM003': "Variable '{name}' usada sin haber sido inicializada",            # warning
    'SEM004': "Variable '{name}' declarada pero nunca usada",                   # warning
    'SEM005': "Función '{name}' llamada pero no declarada",
    'SEM006': "Función '{name}' declarada más de una vez",
    # Tipos
    'SEM010': "Tipo incompatible en asignación: esperaba '{expected}', encontró '{found}'",
    'SEM011': "Operador '{op}' no puede aplicarse a tipos '{left}' y '{right}'",
    'SEM012': "Posible pérdida de datos: conversión de '{from}' a '{to}'",      # warning
    'SEM013': "División por cero en tiempo de compilación",
    'SEM014': "Literal entero fuera de rango int64",
    'SEM015': "Índice {index} fuera del rango válido [0, {size_minus_1}] para el array '{name}'",
    'SEM016': "Función '{name}' debe retornar '{type}', retorna '{found}'",
    'SEM017': "Condición de 'if'/'while'/'for'/'do-while' debe ser de tipo 'bool'",
    # Funciones
    'SEM020': "Función '{name}' espera {expected} argumentos, se encontraron {found}",
    'SEM021': "Argumento {n} de '{name}': tipo '{found}', se esperaba '{expected}'",
    'SEM022': "Función '{name}' no retorna un valor en todos los caminos",
    'SEM023': "Código inalcanzable después de '{stmt}'",                        # warning
    'SEM024': "Función '{name}' parece no tener caso base (heurística)",        # warning
    'SEM025': "'main' debe tener signatura 'int main()' sin parámetros",
    # Arrays
    'SEM030': "'{name}' no es un array",
    'SEM031': "'{name}' no es una función",
    'SEM032': "Lista de inicialización tiene {found} elementos, array tiene tamaño {size}",
    'SEM033': "Tamaño de array debe ser mayor que 0",
    'SEM034': "Tamaño de array no puede ser negativo",
    'SEM035': "Tamaño de array excede el máximo ({MAX_ARRAY_SIZE})",
    # Builtins
    'SEM036': "'{name}' es un identificador reservado (builtin)",
    'SEM037': "'break'/'continue' fuera de un loop",    # duplicate-safety vs PAR007
}
```

**SEM022 — análisis de retorno:** implementar como función `all_paths_return(block: Block) -> bool`:

- `return` → True
- `IfStmt` con `else_body` presente → True si **todas** las ramas retornan (then, cada elif, else)
- `IfStmt` sin `else_body` → False (puede caer al final del bloque)
- `while`/`for`/`do-while` → False (puede no ejecutarse)
- Para un `Block`: True si **algún** stmt en la lista tiene `all_paths_return == True` (corta el camino)

**SEM024 — heurística de base case:** `maybe_infinite_recursion(fn: FunctionDecl) -> bool`:

- Recolectar todos los `ReturnStmt` dentro del cuerpo.
- Si **todos** los returns tienen `value` que es un `CallExpr(name=fn.name, ...)`: warning.
- Si la función recursiva **no tiene ningún `ReturnStmt` sin llamada a sí misma**: warning.
- No es completo (problema de la halting); solo es heurística razonable.

### 5.5 Ejemplo crítico — declaración de `main`

Si existe una función `main`:

- Si `main.return_type != 'int'` o `main.params != []`: emitir `SEM025`.
- Si **no existe** `main`: es error `SEM026 "Programa sin función 'main'"` **solo** si el modo es `compile` (para `check` es warning).

Añadir:

```python
'SEM026': "Programa sin función 'main' — requerido para ejecutar",
```

---

## 6. MÓDULO 06 — Optimizer

### 6.1 Interfaz

```python
class Optimizer:
    def __init__(self, level: int = 1, symbol_table: Optional[SymbolTable] = None):
        """
        level 0: sin optimizaciones
        level 1: constant folding + propagation + dead code
        level 2: nivel 1 + algebraic + strength reduction (solo seguras)
                 + LICM + CSE
        level 3: nivel 2 + inlining + TCO + array access opt
                 + strength reduction agresiva con análisis de rango
        """
    def optimize(self, program: Program) -> Program: ...
```

**Invariante crítico:** el programa optimizado **debe producir el mismo stdout** que el no optimizado para todos los programas bien formados. Los tests de `test_optimizer.py` verifican esto explícitamente comparando niveles 0 y 3.

### 6.2 Constant Folding (nivel 1)

Post-order. Pliega `BinaryOp` y `UnaryOp` con operandos literales. **No pliega** si:

- Algún operando tiene side effects (`is_pure_expr` retorna False).
- División/módulo con divisor == 0.
- Operación float que produce NaN o ±Inf.
- Resultado int excede int64.

### 6.3 Constant Propagation (nivel 1) — política conservadora

```python
def _propagate_in_block(self, stmts: list[Any], env: dict[str, Any]) -> list[Any]:
    """
    env: nombre → nodo literal (o None si la variable ya no es constante).

    Política conservadora:
      - VarDecl con init literal y variable nunca mutada en el resto del scope
        → añadir al env.
      - Entrar a IfStmt/WhileStmt/ForStmt/DoWhileStmt: hacer snapshot del env.
        Analizar qué variables son asignadas dentro (visitar todos los AssignOp,
        UnaryOp ++/--). Remover esas del env para el resto del scope.
        NO propagar dentro de cuerpos de control (pass separado lo hace).
      - CallExpr: si alguna variable global podría ser mutada, ser conservador
        (en este subset no hay globales mutables desde funciones, pero
        documentarlo explícitamente).
    """
```

Nota: este pass NO intenta hacer value analysis cross-branch (merge de abstractos). Una variable **mutada en cualquier rama** deja de ser constante desde ese punto.

### 6.4 Dead Code Elimination (nivel 1)

Dado un `Block.stmts`:

1. Encontrar el primer `stmt` que sea `ReturnStmt | BreakStmt | ContinueStmt`.
2. Eliminar todo lo que viene después (emitir `SEM023` warning para el **primer** stmt eliminado, mencionando cuántos más hay).
3. Para `IfStmt` con condición literal `True`: reemplazar por `then_body.stmts` (concatenados al stmt actual).
4. Para `IfStmt` con condición literal `False`: reemplazar por `else_body.stmts` (o lista vacía).
5. Para `WhileStmt` con condición literal `False`: eliminar completo.
6. **Eliminar `VarDecl`** con `use_count == 0` **solo si** `init_expr is None` **o** `is_pure_expr(init_expr)`. Si no es puro (ej. `int x = input_int();`), mantener pero convertir a `ExprStmt(init_expr)`.

### 6.5 Algebraic Simplification (nivel 2)

Tabla completa, solo se aplica si los lados correspondientes son puros:

| Patrón | Resultado | Condición extra |
|--------|-----------|-----------------|
| `x + 0`, `0 + x` | `x` | — |
| `x - 0` | `x` | — |
| `0 - x` | `-x` (UnaryOp) | — |
| `x * 1`, `1 * x` | `x` | — |
| `x * 0`, `0 * x` | `0` (IntLiteral) | x debe ser puro |
| `x / 1` | `x` | — |
| `x - x` | `0` | x debe ser Identifier puro (no solo "puro", porque `f()-f()` no es 0 con floats IEEE) |
| `x \|\| true`, `true \|\| x` | `true` | — |
| `x \|\| false` | `x` | — |
| `false \|\| x` | `x` | — |
| `x && false`, `false && x` | `false` | — |
| `x && true` | `x` | — |
| `true && x` | `x` | — |
| `!!x` | `x` | — |
| `!true` | `false` | — |
| `!false` | `true` | — |

> **Nota semántica:** `x - x` no es 0 para floats cuando `x` es NaN. Por eso solo aplicamos si `x` es un `Identifier` de tipo `int` (no `float`).

### 6.6 Strength Reduction (nivel 2/3)

```python
# Nivel 2: solo seguras (no cambian semántica de signo).
STRENGTH_MUL = {   # x * N donde N es potencia de 2 → x << log2(N)
    2:  1, 4:  2, 8:  3, 16: 4, 32: 5, 64: 6, 128: 7, 256: 8,
}

# DIVISIÓN Y MÓDULO: reservados para nivel 3 con análisis de rango.
#  x / 2 → x >> 1 SOLO si x >= 0 (probado por análisis).
#  x % 2 → x & 1 SOLO si x >= 0.
# Si no se puede probar x >= 0, NO aplicar la transformación.
```

**Por qué:** en C, `-5 / 2 == -2` (truncación hacia 0), pero `-5 >> 1 == -3` (shift aritmético hacia -∞). La transformación es incorrecta para signed sin guardas. El codegen a nivel 3 puede emitir la secuencia correcta con signo:

```
asr x_tmp, x_n, #63      ; sign mask
add x_n,   x_n, x_tmp, lsr #(64-k)
asr x_res, x_n, #k
```

Pero para simplicidad académica del proyecto, **recomendamos dejar la división SIN strength reduction** (siempre emitir `sdiv`). Es la decisión por defecto del spec.

### 6.7 LICM, CSE, Inlining, TCO

Como en el doc original. Puntos a reforzar:

- **LICM**: solo mover expresiones `is_pure_expr == True`. Variables introducidas: nombre `_licm_{N}`.
- **CSE**: hash canónico debe ignorar `pos`. Solo sobre expresiones `is_pure_expr`.
- **Inlining**: función inlineable si:
  - Cuerpo es `[ReturnStmt(expr)]` con `expr` de ≤ 5 nodos.
  - `is_pure_expr(expr)` del return.
  - No recursiva (hacer análisis de grafo de llamadas).
  - Parámetros se renombran con prefijo `_inline_{funcname}_` para evitar captura.
- **TCO**: solo marcar. El codegen reemplaza `ReturnStmt(CallExpr(f=self, ..., is_tail_call=True))` por sobrescribir parámetros en los slots correspondientes + `b .L_func_start`.

---

## 7. MÓDULO 07 — Codegen ARM64

### 7.1 Estrategia general

**Linkeamos contra libc.** No se usan syscalls crudas. Esto resuelve:

- Formateo de enteros/floats (`printf`).
- Lectura de stdin (`fgets`, `scanf`).
- `malloc`/`free` si se necesitan strings dinámicos para `input()`.

El código ensamblado se enlaza con `gcc` (tanto en Linux como en macOS) → se encarga de `crt0`, `main`, libc.

**Entry point:** el compilador emite la función `main` con nombre:

- Linux: `main` (sin underscore)
- macOS: `_main`

El runtime de libc llama a `main`, que **es la función `main` del usuario**. Su valor de retorno (int) se convierte en exit code.

### 7.2 Estructura del assembly

```asm
; ───────────────────────────────────────────────────────────────────
; macOS:
    .section __TEXT,__text,regular,pure_instructions
    .build_version macos, 11, 0
    .globl _main
; Linux:
    .text
    .globl main

; ─── Sección de datos de solo lectura (string literals y formats) ──
; macOS:
    .section __TEXT,__cstring,cstring_literals
; Linux:
    .section .rodata
.Lstr_0:
    .asciz "Hola mundo\n"
.Lfmt_int_nl:
    .asciz "%ld\n"
.Lfmt_int:
    .asciz "%ld"
.Lfmt_float_nl:
    .asciz "%f\n"
.Lfmt_float:
    .asciz "%f"
.Lfmt_str_nl:
    .asciz "%s\n"
.Lfmt_str:
    .asciz "%s"
.Lfmt_char_nl:
    .asciz "%c\n"
.Lfmt_char:
    .asciz "%c"
.Lerr_div_zero:
    .asciz "Error: división por cero\n"
.Lerr_oob:
    .asciz "Error: índice fuera de rango en array '%s'\n"

    .section __TEXT,__text       ; o .text en Linux
    .p2align 2

_main:                           ; o main:
    ; prologue
    stp x29, x30, [sp, #-FRAME]! ; FRAME múltiplo de 16
    mov x29, sp
    ; cuerpo
    ; epilogue:
    mov w0, #0                   ; return 0 implícito si no hubo return
    ldp x29, x30, [sp], #FRAME
    ret
```

### 7.3 Frame size (corregido)

```python
def _compute_frame(self, func: FunctionDecl) -> None:
    """
    Calcula offsets para cada variable local y parámetro.

    Reserva:
      - 16 bytes arriba para stp x29, x30
      - Espacio para cada local según su tipo:
          int, float, string: 8 bytes
          char, bool: 1 byte, pero se alinea a 8 para simplicidad del subset
          array: element_size * size, alineado a 8
      - Alinear total a 16 bytes (requerido por AArch64 PCS)

    Ejemplo: 3 int locals → 24 + 16 = 40 → round_up(40, 16) = 48
    """
    size = 16   # para fp/lr
    for local in collect_locals(func):
        size += aligned_size_of(local.type, local.array_size)
        self._local_offsets[local.name] = -size + 0   # offset desde fp al inicio del slot
    size = (size + 15) & ~15   # round up to 16
    self._frame_size = size
```

**Importante:** al emitir `stp x29, x30, [sp, #-FRAME]!` con FRAME calculado así, el frame queda correctamente alineado para llamar a `printf` (que requiere SP alineado a 16 en el call site).

### 7.4 Emitir `print` / `println`

Mapeo directo a `printf` de libc según tipo inferido del argumento:

```asm
; println(int_expr)
; 1) evaluar int_expr → x1
; 2) cargar format string
    adrp x0, .Lfmt_int_nl@PAGE            ; macOS
    add  x0, x0, .Lfmt_int_nl@PAGEOFF
;   Linux:
;   adrp x0, .Lfmt_int_nl
;   add  x0, x0, :lo12:.Lfmt_int_nl
; 3) printf
    bl   _printf                           ; macOS (o 'bl printf' en Linux)
```

Para `float`: pasar el valor en `d0` y `x0 = puntero a formato`. **Variadic ABI de AArch64:** floats van en registros `d0..d7` en macOS, pero en Linux **también** van en `d0..d7` para variadic (es consistente con printf).

> **Nota sutil:** macOS AArch64 varargs pasa **todos** los argumentos variádicos por stack (no por registro), mientras que Linux los pasa por registros. Esto afecta el código generado. Para portabilidad, el codegen **debe** detectar la plataforma en runtime y emitir secuencias distintas. Alternativa más simple: generar solo para la plataforma actual (`sys.platform`) y documentar que los binarios no son cross-platform.

### 7.5 Control de flujo — labels

```asm
; if (cond) { then } else { else }
    ; evaluar cond → x0 (0 o 1)
    cbz  x0, .Lelse_N
    ; then
    b    .Lendif_N
.Lelse_N:
    ; else
.Lendif_N:

; while (cond) { body }
.Lwhile_start_N:
    ; evaluar cond → x0
    cbz  x0, .Lwhile_end_N
    ; body
    b    .Lwhile_start_N
.Lwhile_end_N:

; for (init; cond; update) { body }
    ; init
.Lfor_cond_N:
    ; cond → x0
    cbz  x0, .Lfor_end_N
    ; body
.Lfor_update_N:                  ; destino de 'continue'
    ; update
    b    .Lfor_cond_N
.Lfor_end_N:
```

**Stacks de etiquetas** en el codegen:

```python
self._break_labels: list[str]      # push/pop con cada loop
self._continue_labels: list[str]   # destino de continue:
                                   # - for:     .Lfor_update_N
                                   # - while:   .Lwhile_start_N
                                   # - do-while: .Ldowhile_cond_N
```

### 7.6 Guards de runtime

```asm
; Guard: división por cero (antes de sdiv x0, xA, xB)
    cbz  xB, .Ldiv_zero
    sdiv xDST, xA, xB
    b    .Ldiv_ok_N
.Ldiv_zero:
    adrp x0, .Lerr_div_zero@PAGE
    add  x0, x0, .Lerr_div_zero@PAGEOFF
    bl   _printf
    mov  w0, #1
    bl   _exit
.Ldiv_ok_N:

; Guard: array out of bounds (antes de acceso arr[i], size = N)
    cmp  xI, #N
    b.hs .Loob_N             ; unsigned >= abarca también negativos con signo
    ; acceso seguro
    b    .Loob_ok_N
.Loob_N:
    adrp x0, .Lfmt_oob@PAGE
    add  x0, x0, .Lfmt_oob@PAGEOFF
    adrp x1, .Lstr_arrname@PAGE
    add  x1, x1, .Lstr_arrname@PAGEOFF
    bl   _printf
    mov  w0, #1
    bl   _exit
.Loob_ok_N:
```

### 7.7 Mapa de líneas (para panel split C↔ASM)

Cada línea generada se emite con un prefijo de comentario `; src:LINE:COL` en el cuerpo (no en prologue/epilogue). El codegen mantiene:

```python
self._line_map: dict[int, int] = {}   # asm_line → c_line
```

Se popula cada vez que se llama a `_emit(line, c_line)` con `c_line >= 0`.

---

## 8. MÓDULO 08 — Intérprete

Idéntico al doc original, con estas correcciones:

- El intérprete **también** valida `main() -> int` y usa su return como exit code.
- Al llamar a `input()` / `input_int()` / `input_float()`, solicitar input mediante el callback `input_fn`. Si no hay callback y el programa intenta leer: `InterpreterError("input() requiere input_fn configurado")`.
- El límite de iteraciones se incrementa en **cada entrada** a un loop body, no en cada statement dentro del loop.

---

## 9. MÓDULOS 09–13 — Conversiones, Explainer, Executor

### 9.1 Módulos 09, 10, 11, 12 — sin cambios de diseño

Mantener interfaces como en el doc original. Se refuerza:

- **`ast_to_c.py`**: siempre parentiza `BinaryOp` y `UnaryOp` para evitar ambigüedades de precedencia al re-parsear. El roundtrip C → AST → C debe ser idempotente para programas bien formados.
- **`ast_to_blocks.py`**: debe inyectar `block.data = {"srcLine": node.pos.line}` en cada bloque generado para que el debugger pueda resaltar el bloque correcto.

### 9.2 Módulo 13 — Executor (corregido)

```python
class Executor:
    def __init__(self, work_dir: str = '/tmp/compileflow'):
        self._work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    def assemble_and_run(self, assembly: str, session_id: str,
                         stdin_data: str = '') -> ExecutionResult:
        asm_path = f'{self._work_dir}/{session_id}.s'
        bin_path = f'{self._work_dir}/{session_id}'
        with open(asm_path, 'w') as f:
            f.write(assembly)

        # Un solo paso con gcc: ensambla, linkea libc, genera binario.
        # Funciona en macOS y Linux nativo. En x86 emular con qemu-aarch64.
        cmd = self._gcc_cmd(asm_path, bin_path)
        as_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if as_proc.returncode != 0:
            return ExecutionResult(
                stdout='', stderr=as_proc.stderr, returncode=-1,
                timed_out=False, assembly_path=asm_path, binary_path=None,
                error=f'Error al ensamblar:\n{as_proc.stderr}')

        # Ejecutar binario
        run_cmd = self._run_cmd(bin_path)
        try:
            proc = subprocess.run(
                run_cmd, input=stdin_data, capture_output=True,
                text=True, timeout=EXEC_TIMEOUT_SEC)
            stdout = proc.stdout[:MAX_OUTPUT_SIZE]
            truncated = len(proc.stdout) > MAX_OUTPUT_SIZE
            if truncated:
                stdout += '\n[Output truncado — máximo 1MB]'
            return ExecutionResult(
                stdout=stdout, stderr=proc.stderr,
                returncode=proc.returncode, timed_out=False,
                assembly_path=asm_path, binary_path=bin_path, error=None)
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout='', stderr='', returncode=-1, timed_out=True,
                assembly_path=asm_path, binary_path=bin_path,
                error=f'Tiempo de ejecución excedido ({EXEC_TIMEOUT_SEC}s)')
        finally:
            # Limpiar binario (el .s se conserva para mostrar al usuario)
            if os.path.exists(bin_path):
                os.remove(bin_path)

    def _is_native_arm64(self) -> bool:
        import platform
        return platform.machine().lower() in ('arm64', 'aarch64')

    def _gcc_cmd(self, asm: str, out: str) -> list[str]:
        if self._is_native_arm64():
            return ['gcc', '-o', out, asm]
        # Cross-compile con toolchain AArch64 (debe estar instalado)
        return ['aarch64-linux-gnu-gcc', '-static', '-o', out, asm]

    def _run_cmd(self, bin_path: str) -> list[str]:
        if self._is_native_arm64():
            return [bin_path]
        # Emular con qemu-aarch64
        return ['qemu-aarch64', bin_path]
```

**Dependencias de sistema** (documentar en README):

- macOS Apple Silicon / Linux ARM64: `gcc` y `libc` (standard).
- Linux x86_64: `gcc-aarch64-linux-gnu` + `qemu-user-static`.

---

## 10. MÓDULO 26 — Tests

### 10.1 Estructura

```
tests/
├── conftest.py
├── unit/
│   ├── test_lexer.py
│   ├── test_parser.py
│   ├── test_semantic.py
│   ├── test_optimizer.py
│   └── test_codegen.py
├── integration/
│   ├── test_pipeline.py
│   └── test_api.py
├── robustness/
│   ├── test_bad_inputs.py
│   └── test_stress.py
├── roundtrip/
│   └── test_roundtrip.py
└── interpreter/
    └── test_interpreter.py
```

### 10.2 conftest.py (corregido)

```python
import pytest
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from compiler.optimizer import Optimizer
from compiler.codegen import CodeGenerator
from compiler.error_reporter import ErrorReporter
from compiler.executor import Executor

class CompileResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.ast = None
        self.exception = None
        self.assembly = None
        self.stdout = ''
        self.returncode = 0

def compile_safe(source: str, opt_level: int = 0) -> CompileResult:
    """Corre lex+parse+sema sin lanzar excepciones. Para testing."""
    r = CompileResult()
    try:
        rep = ErrorReporter()
        tokens = Lexer(source, rep).tokenize()
        ast = Parser(tokens, rep).parse()
        SemanticAnalyzer(rep).analyze(ast)
        r.errors = rep.errors
        r.warnings = rep.warnings
        r.ast = ast
    except Exception as e:
        import traceback
        r.exception = (e, traceback.format_exc())
    return r

def compile_and_run(source: str, opt_level: int = 1,
                     stdin_data: str = '') -> CompileResult:
    """Pipeline completo: source → ejecución. Lanza si hay errores."""
    r = CompileResult()
    rep = ErrorReporter()
    tokens = Lexer(source, rep).tokenize()
    ast = Parser(tokens, rep).parse()
    SemanticAnalyzer(rep).analyze(ast)
    r.errors = rep.errors
    r.warnings = rep.warnings
    if rep.has_errors:
        r.exception = ValueError(f'Errores: {rep.errors}')
        return r
    opt_ast = Optimizer(level=opt_level).optimize(ast)
    asm, line_map = CodeGenerator().generate(opt_ast)
    r.assembly = asm
    exec_result = Executor().assemble_and_run(asm, 'test', stdin_data)
    r.stdout = exec_result.stdout
    r.returncode = exec_result.returncode
    return r

@pytest.fixture
def reporter():
    return ErrorReporter()

@pytest.fixture
def safe_compile():
    return compile_safe

@pytest.fixture
def run():
    return compile_and_run
```

### 10.3 Robustness (auditado)

```python
# Inputs malformados: DEBEN producir al menos un error, NUNCA crash
MALFORMED_INPUTS = [
    "\x00\x01\x02\x03",               # null bytes
    "/* comentario sin cerrar",       # LEX004
    '"string sin cerrar',             # LEX002
    "'",                              # LEX003
    "'ab'",                           # LEX003
    "{{{{{{" + "}" * 3,               # braces desbalanceados
    "if if if if if",                 # PAR001
    "int x = 1/0;",                   # SEM013
    "else { }",                       # PAR006
    "int outer(){ int inner(){return 1;} return 0;}",  # PAR004
    "int arr[-1];",                   # SEM034
    "int arr[0];",                    # SEM033
    "int arr[999999999];",            # SEM035
    "true = 5;",                      # PAR011
    "5 = x;",                         # PAR011
    "int print = 5;",                 # SEM036
    "return; break; continue;",       # PAR007 (fuera de función)
    "int main() { break; return 0; }",# PAR007
    "int f(){} int f(){}",            # SEM006
    "int x = \"hello\";",             # SEM010
]

# Inputs edge-case: DEBEN parsear sin errores (o con solo warnings)
EDGE_CASE_INPUTS = [
    "",                               # programa vacío
    "   ",                            # solo whitespace
    "\n" * 100,                       # solo newlines
    "// solo un comentario",          # solo comentario
    "/* comentario\nmultilinea */",   # comentario multilinea cerrado
    "int x;",                         # declaración sin inicializar
]

# Inputs "bomb": pueden producir errores o no, pero NUNCA deben crashear
BOMB_INPUTS = [
    "a" * 600_000,                    # excede tamaño → LEX010
    "a" * 500,                        # identificador largo → LEX006
    "int x = " + "1 + " * 200 + "1;", # expresión muy anidada
    "int " + "f(" * 300 + ")" * 300 + ";",  # tokens balanceados pero raros
    "#@$%",                           # puros caracteres ilegales
    '{"blocks":null}',                # parece JSON
]

@pytest.mark.parametrize("src", MALFORMED_INPUTS)
def test_malformed_produces_errors(src, safe_compile):
    r = safe_compile(src)
    assert r.exception is None, \
        f"Compiler crashed on:\n{src!r}\n{r.exception}"
    assert len(r.errors) > 0, f"Esperaba errores para: {src!r}"
    for err in r.errors:
        assert isinstance(err.code, str) and err.code
        assert isinstance(err.message, str) and err.message
        assert err.line >= 0 and err.column >= 0

@pytest.mark.parametrize("src", EDGE_CASE_INPUTS)
def test_edge_cases_no_errors(src, safe_compile):
    r = safe_compile(src)
    assert r.exception is None
    assert len(r.errors) == 0, f"Error inesperado en: {src!r}: {r.errors}"

@pytest.mark.parametrize("src", BOMB_INPUTS)
def test_bombs_do_not_crash(src, safe_compile):
    r = safe_compile(src)
    assert r.exception is None, \
        f"Compiler crashed on bomb input:\n{src[:80]!r}\n{r.exception}"
    # No assertion sobre errors: algunos bombs pueden parsear OK.
```

### 10.4 Optimizer invariance test (crítico)

```python
# El test MÁS importante del optimizer
OPT_INVARIANCE_PROGRAMS = [
    # fibonacci, factorial, bubble_sort, collatz, etc. — los 8 de la galería.
]

@pytest.mark.parametrize("source", OPT_INVARIANCE_PROGRAMS)
def test_optimization_preserves_semantics(source, run):
    """Ningún nivel de optimización debe cambiar el output del programa."""
    r0 = run(source, opt_level=0)
    r1 = run(source, opt_level=1)
    r2 = run(source, opt_level=2)
    r3 = run(source, opt_level=3)
    assert r0.stdout == r1.stdout == r2.stdout == r3.stdout
    assert r0.returncode == r1.returncode == r2.returncode == r3.returncode
```

---

## 11. MÓDULO 14 — Validators

```python
# server/validators.py
from pydantic import BaseModel, Field
from typing import Literal, Optional

class CompileRequest(BaseModel):
    source: str = Field(..., max_length=524_288)
    optimization_level: int = Field(default=1, ge=0, le=3)
    stdin: Optional[str] = Field(default='', max_length=65_536)
    include_explanation: bool = False

class CheckRequest(BaseModel):
    source: str = Field(..., max_length=524_288)

class ConvertRequest(BaseModel):
    direction: Literal['c_to_blocks', 'blocks_to_c']
    source: str = Field(default='', max_length=524_288)
    workspace: dict = Field(default_factory=dict)

class DebugStartRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=524_288)

class ValidateFileRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content: str = Field(..., max_length=2_097_152)
    file_type: Literal['c', 'asm', 'scratch', 'cfproj']

class ExplainRequest(BaseModel):
    source: str = Field(..., max_length=524_288)
```

---

## 12. MÓDULO 15 — API Flask

### 12.1 Setup

```python
# server/app.py
from flask import Flask, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    from .routes.compile import compile_bp
    from .routes.check import check_bp
    from .routes.convert import convert_bp
    from .routes.files import files_bp
    from .routes.explain import explain_bp   # añadido
    from .routes.debug import register_debug_events

    app.register_blueprint(compile_bp, url_prefix='/api')
    app.register_blueprint(check_bp, url_prefix='/api')
    app.register_blueprint(convert_bp, url_prefix='/api')
    app.register_blueprint(files_bp, url_prefix='/api')
    app.register_blueprint(explain_bp, url_prefix='/api')
    register_debug_events(socketio)

    @app.errorhandler(Exception)
    def global_error_handler(e):
        import traceback
        # En dev puede incluir traceback; en prod, ocultar
        return jsonify({
            'ok': False,
            'errors': [{
                'code': 'SRV001', 'message': str(e),
                'line': 0, 'column': 0, 'severity': 'error'
            }]
        }), 500

    return app, socketio
```

### 12.2 Endpoints (referencia)

- `POST /api/compile` — body `CompileRequest`. Pipeline completo + ejecución. Response como doc original.
- `POST /api/check` — body `CheckRequest`. Solo lex+parse+sema. Response siempre 200.
- `POST /api/convert` — body `ConvertRequest`. Una dirección a la vez.
- `POST /api/validate-file` — body `ValidateFileRequest`. Ver módulo file_io.
- `POST /api/explain` — body `ExplainRequest`. Retorna `{explanation: str}` en Markdown.
- `WebSocket /ws/debug` — eventos `debug:start`, `debug:step`, `debug:continue`, `debug:stop`; respuestas `debug:state`, `debug:error`.

---

## 13. MÓDULO 16 — Monaco (IDE)

Configuración del lenguaje, completion provider, hover provider: **idénticos al doc original**, con estos ajustes:

- Añadir `'input_int'` y `'input_float'` a la lista `builtins` del monarch tokenizer.
- El completion provider debe usar `window.__symbolTable` que es inyectado por el cliente después de cada `/api/check` exitoso. Si no hay `__symbolTable`, solo muestra keywords y snippets.
- Debounce del `/api/check`: **300ms** desde el último cambio.

---

## 14. MÓDULO 17 — Blockly (canvas) — CORRECCIONES

### 14.1 Reglas de tipado visual

Blockly usa `check` (en `output` del bloque y en `input_value`) para validar conexiones. Nuestros tipos visuales:

```javascript
const TYPE_NUMBER  = ["Number"];
const TYPE_BOOLEAN = ["Boolean"];
const TYPE_STRING  = ["String"];
const TYPE_ANY     = null;   // acepta cualquier tipo
```

**Mapeo de tipos del lenguaje a tipos Blockly:**

- `int`, `float`, `char` → `"Number"`
- `bool` → `"Boolean"`
- `string` → `"String"`
- `void` → no se conecta como expresión

### 14.2 Bloques corregidos (los que cambian respecto al doc original)

**Operador binario — dividido en tres bloques para tipado correcto:**

```javascript
{
    "type": "c_binary_arith",          // +, -, *, /, %
    "message0": "%1 %2 %3",
    "args0": [
        { "type": "input_value", "name": "LEFT",  "check": "Number" },
        { "type": "field_dropdown", "name": "OP",
          "options": [["+","+"],["-","-"],["*","*"],["/","/"],["%","%"]] },
        { "type": "input_value", "name": "RIGHT", "check": "Number" }
    ],
    "output": "Number",
    "inputsInline": true,
    "colour": 230
},
{
    "type": "c_binary_cmp",            // ==, !=, <, >, <=, >=
    "message0": "%1 %2 %3",
    "args0": [
        { "type": "input_value", "name": "LEFT"  },   // acepta cualquier tipo
        { "type": "field_dropdown", "name": "OP",
          "options": [["==","=="],["!=","!="],["<","<"],
                      ["<=","<="],[">",">"],[">=",">="]] },
        { "type": "input_value", "name": "RIGHT" }
    ],
    "output": "Boolean",
    "inputsInline": true,
    "colour": 230
},
{
    "type": "c_binary_logic",          // &&, ||
    "message0": "%1 %2 %3",
    "args0": [
        { "type": "input_value", "name": "LEFT",  "check": "Boolean" },
        { "type": "field_dropdown", "name": "OP",
          "options": [["&&","&&"],["||","||"]] },
        { "type": "input_value", "name": "RIGHT", "check": "Boolean" }
    ],
    "output": "Boolean",
    "inputsInline": true,
    "colour": 230
},
```

**Llamada a función — dividida en dos bloques:**

```javascript
{
    "type": "c_func_call_expr",
    "message0": "llamar %1 ( %2 )",
    "args0": [
        { "type": "field_input", "name": "NAME", "text": "miFuncion" },
        { "type": "input_value", "name": "ARGS" }
    ],
    "output": null,          // tipo de retorno se valida en el backend
    "inputsInline": true,
    "colour": 290
},
{
    "type": "c_func_call_stmt",
    "message0": "llamar %1 ( %2 )",
    "args0": [
        { "type": "field_input", "name": "NAME", "text": "miFuncion" },
        { "type": "input_value", "name": "ARGS" }
    ],
    "previousStatement": null,
    "nextStatement": null,
    "inputsInline": true,
    "colour": 290
},
```

**`ast_to_blocks.py`** debe usar `c_func_call_expr` cuando el `CallExpr` está en posición de expresión, y `c_func_call_stmt` cuando está en `ExprStmt`.

**Literales con `output` correcto** (solo cambio: ya estaban bien con `"Number"`, `"Boolean"`, `"String"`).

El resto de bloques (control, variables, I/O, funciones de definición, arrays, literales) se mantienen como en el doc original.

---

## 15. MÓDULOS 18–25 — Frontend features

### 15.1 Módulo 18 (sync) — sin cambios

### 15.2 Módulo 19 (debugger) — sin cambios

### 15.3 Módulo 20 (ast_viewer) — sin cambios

### 15.4 Módulo 21 (asm_panel) — tabla ARM64 corregida

Se mantiene la tabla original. Se añade esta nota: la columna `example` debe mostrar **pseudocódigo claro**, nunca código Python. Los tooltips son para estudiantes de C — no de Python.

### 15.5 Módulo 22 (file_io) — sin cambios de diseño

### 15.6 Módulo 23 (gallery) — sin cambios

### 15.7 Módulo 24 (share) — CORREGIDO

```javascript
// features/share.js
export class ShareManager {
    constructor() {
        this._PARAM = 'p';
        this._SCHEMA_VERSION = 1;
    }

    _encodeUtf8Base64(str) {
        const bytes = new TextEncoder().encode(str);
        // btoa espera string; construimos binary string desde bytes
        let binary = '';
        for (const b of bytes) binary += String.fromCharCode(b);
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    _decodeUtf8Base64(encoded) {
        // Restaurar padding y base64 estándar
        let b64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
        while (b64.length % 4) b64 += '=';
        const binary = atob(b64);
        const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
        return new TextDecoder().decode(bytes);
    }

    encode(state) {
        const payload = { v: this._SCHEMA_VERSION, ...state };
        return this._encodeUtf8Base64(JSON.stringify(payload));
    }

    decode(encoded) {
        try {
            const json = this._decodeUtf8Base64(encoded);
            const payload = JSON.parse(json);
            if (payload.v !== this._SCHEMA_VERSION)
                throw new Error(`Versión incompatible: ${payload.v}`);
            return payload;
        } catch (e) {
            throw new Error(`No se pudo decodificar el estado: ${e.message}`);
        }
    }

    share(state) {
        const encoded = this.encode(state);
        const url = `${location.origin}${location.pathname}?${this._PARAM}=${encoded}`;
        history.pushState(null, '', url);
        if (navigator.clipboard) navigator.clipboard.writeText(url);
        return url;
    }

    loadFromURL() {
        const params = new URLSearchParams(location.search);
        const encoded = params.get(this._PARAM);
        if (!encoded) return null;
        return this.decode(encoded);
    }
}
```

### 15.8 Módulo 25 (explainer) — sin cambios

---

## 16. APÉNDICE — Programas de demostración

Idénticos al doc original (fibonacci, factorial, bubble_sort, collatz). Se conservan tal cual.

**Nota crítica:** los programas deben **compilar y ejecutar** con el pipeline completo en el entorno objetivo antes de publicarlos como `.cfproj`. La prueba se hace ejecutando `test_roundtrip.py` antes de cada release.

---

## 17. APÉNDICE — Dependencias

```
# requirements.txt
flask==3.0.3
flask-cors==4.0.1
flask-socketio==5.3.6
pydantic==2.7.1
pytest==8.2.0
pytest-cov==5.0.0
eventlet==0.36.1
```

**Dependencias del sistema (no Python):**

- `gcc` (nativo o `gcc-aarch64-linux-gnu` para cross)
- `qemu-user-static` (solo si el host es x86)
- Node.js 18+ y `npm` o `pnpm` para el frontend
- Vite como bundler

---

## 18. APÉNDICE — Orden de implementación recomendado

Los agentes deben implementar en este orden estricto por dependencias:

```
Etapa A — fundamentos compilador (no dependen de nada):
  1. ast_nodes.py             ← NO MODIFICAR después
  2. error_reporter.py
  3. lexer.py                 (depende de 2)

Etapa B — análisis:
  4. parser.py                (depende de 1,2,3)
  5. semantic.py              (depende de 1,2)

Etapa C — transformaciones:
  6. ast_to_c.py              (depende de 1) — facilita debugging
  7. optimizer.py             (depende de 1)

Etapa D — codegen y ejecución:
  8. codegen.py               (depende de 1)
  9. executor.py              (sin deps del compiler)
 10. interpreter.py           (depende de 1,2)

Etapa E — conversiones bidireccionales:
 11. blocks_to_ast.py         (depende de 1,2)
 12. ast_to_blocks.py         (depende de 1)
 13. explainer.py             (depende de 1)

Etapa F — API:
 14. validators.py
 15. app.py + routes/         (depende de todo el compiler)

Etapa G — frontend:
 16. Monaco setup
 17. Blockly setup
 18. sync.js                  (depende de 11, 12, 15)
 19. debugger.js              (depende de 10, 15)
 20–25. resto de features
 26. tests (en paralelo desde etapa A)
```

**Regla cardinal:** NUNCA modificar `ast_nodes.py` después de la etapa A. Si se descubre una falla, se añaden campos con `default_factory`, nunca se cambian los existentes.

---

## 19. APÉNDICE — Checklist de revisión antes de commit

Cada agente, antes de hacer commit de un módulo, verifica:

1. [ ] El módulo no lanza excepciones no manejadas para ningún input de `MALFORMED_INPUTS` ni `BOMB_INPUTS`.
2. [ ] Todos los códigos de error que emite están en las tablas de este documento.
3. [ ] Las firmas públicas coinciden exactamente con este documento.
4. [ ] Los tests de su módulo pasan al 100%.
5. [ ] El linter (`ruff` + `mypy` en modo strict) no reporta errores.
6. [ ] No hay llamadas a `print()` fuera de código de debugging (usar el reporter).
7. [ ] No hay `time.sleep`, `os.system`, ni `subprocess` salvo en `executor.py`.

---

## 20. CIERRE

Cualquier ambigüedad que se descubra durante la implementación se resuelve en favor de:

1. La opción que **no crashea** el sistema.
2. La opción que **produce un mensaje de error más informativo**.
3. La opción **más simple** y alineada con los tests.

Los tests son la autoridad última. Si un agente encuentra contradicción entre este documento y un test, el test gana (después de verificar que el test no tenga un bug documentado en esta auditoría).

**Fin del documento.**
