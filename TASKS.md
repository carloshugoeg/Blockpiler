# CompileFlow — TASKS.md

> **Fuente de verdad para la ejecución del proyecto.**
> Cada tarea se completa en una sola sesión de Claude Code.
> **Ninguna tarea se marca como hecha hasta que pase todos los criterios de Done.**

---

## Protocolo obligatorio para todo agente

Antes de comenzar una tarea:

1. Lee `compileflow.specs.md` completo.
2. Lee esta sección entera.
3. Lee la tarea asignada en detalle.
4. Implementa **exactamente** lo que dice el spec — sin inventar, sin simplificar.
5. Completa todo el 'done criteria' antes de pasar a la siguiente tarea.
6. Completa el checklist general y deja bien documentado para proximos agentes

Al terminar una tarea, ejecuta el checklist de Done de esa tarea.
**Solo si todos los ítems pasan**, cambia `[ ]` a `[x]` en esta línea:

```
- [ ] T0N completa
```

Si algún ítem falla, sigue trabajando. No marques la tarea hasta que todos pasen.

---

## Checklist universal de pre-commit (spec §19)

Todo módulo debe pasar esto antes de considerarse completo:

- No lanza excepciones para ningún input de `MALFORMED_INPUTS` ni `BOMB_INPUTS`
- Todos los códigos de error que emite están en las tablas del spec
- Las firmas públicas coinciden exactamente con el spec
- Los tests del módulo pasan al 100% (`pytest`)
- `ruff` + `mypy --strict` no reportan errores
- No hay `print()` fuera de código de debugging
- No hay `time.sleep`, `os.system`, ni `subprocess` salvo en `executor.py`

---

## Estado de tareas

```
[x] T01  ast_nodes.py
[x] T02  error_reporter.py
[x] T03  lexer.py
[x] T04  parser.py
[x] T05  semantic.py
[x] T06  ast_to_c.py
[x] T07  optimizer.py
[x] T08  codegen.py
[x] T09  executor.py
[x] T10  interpreter.py
[x] T11  blocks_to_ast.py
[x] T12  ast_to_blocks.py
[x] T13  explainer.py
[x] T14  validators.py
[x] T15  app.py + routes/
[x] T16  scaffolding frontend
[x] T17  monaco_setup.js
[x] T18  blockly_setup.js
[x] T19  sync.js
[x] T20  ast_viewer.js
[x] T21  asm_panel.js
[x] T22  debugger.js
[x] T23  explainer.js (frontend)
[x] T24  gallery.js
[x] T25  share.js + file_io.js
[x] T26  tests suite
```

---

## ETAPA A — Fundamentos del compilador

---

### T01 · `compiler/ast_nodes.py`

- [x] T01 completa

**Archivo:** `compiler/ast_nodes.py`
**Depende de:** nada
**Spec:** §3.1

#### Scope

Implementar exactamente las siguientes clases (dataclasses) y utilitarios, sin añadir ni quitar:

**Tipo base:**

- `CType` — Literal alias: `'int' | 'float' | 'char' | 'bool' | 'string' | 'void' | 'unknown'`
- `SourcePos(line, col, length=1)`

**Top-level:**

- `Program(declarations, pos)`
- `FunctionDecl(name, return_type, params, body, pos)`
- `Parameter(name, type, pos)`
- `VarDecl(name, type, init_expr, pos)`
- `ArrayDecl(name, element_type, size, init_list, pos)`

**Statements:**

- `Block(stmts, pos)`
- `IfStmt(condition, then_body, elif_clauses, else_body, pos)`
- `WhileStmt(condition, body, pos)`
- `ForStmt(init, condition, update, body, pos)`
- `DoWhileStmt(body, condition, pos)`
- `ReturnStmt(value, pos)`
- `BreakStmt(pos)`
- `ContinueStmt(pos)`
- `PrintStmt(expr, newline, pos)`
- `ExprStmt(expr, pos)`

**Expresiones:**

- `BinaryOp(op, left, right, inferred_type='unknown', pos)`
- `UnaryOp(op, operand, prefix, inferred_type='unknown', pos)`
- `AssignOp(op, target, value, pos)`
- `CallExpr(name, args, inferred_type='unknown', is_tail_call=False, pos)`
- `IndexExpr(name, index, inferred_type='unknown', pos)`
- `Identifier(name, inferred_type='unknown', pos)`
- `IntLiteral(value, inferred_type='int', pos)`
- `FloatLiteral(value, inferred_type='float', pos)`
- `StringLiteral(value, inferred_type='string', pos)`
- `CharLiteral(value, inferred_type='char', pos)`
- `BoolLiteral(value, inferred_type='bool', pos)`
- `InputExpr(variant='string', inferred_type='string', pos)`
- `CastExpr(target_type, expr, inferred_type='unknown', pos)`

**Utilitarios (funciones module-level):**

- `EXPR_TYPES` — tupla con todas las clases de expresión
- `is_expression(node) -> bool`
- `get_pos(node) -> SourcePos`
- `node_type_name(node) -> str`
- `is_lvalue(node) -> bool`
- `is_pure_expr(node) -> bool` — implementar lógica exacta del spec §3.1

**Constraints:**

- Usar `from __future__ import annotations`
- Usar `@dataclass` para todas las clases
- `pos` con `field(default_factory=lambda: SourcePos(0,0))` en expresiones
- `is_tail_call: bool = False` en `CallExpr` desde la definición

#### Tests requeridos (`tests/unit/test_ast_nodes.py`)

- Instanciar cada dataclass con valores válidos → no falla
- `is_expression` retorna True para expresiones, False para statements
- `is_lvalue` retorna True solo para `Identifier` y `IndexExpr`
- `is_pure_expr`: literals → True; `CallExpr` → False; `UnaryOp('++', ...)` → False; `BinaryOp` con literals → True
- `get_pos` en nodo sin `pos` retorna `SourcePos(0,0)`

#### Done Criteria

- [ ] Todas las clases del spec están implementadas con exactamente los campos especificados
- [ ] `is_pure_expr` sigue la lógica exacta del spec (recursión, casos especiales `++`/`--`)
- [ ] Tests en `tests/unit/test_ast_nodes.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Sin TODOs, sin `pass` en métodos de lógica, sin prints
- [ ] Checklist universal de pre-commit ✓

---

### T02 · `compiler/error_reporter.py`

- [x] T02 completa

**Archivo:** `compiler/error_reporter.py`
**Depende de:** T01
**Spec:** §3.2, §1.1, §1.2

#### Scope

Implementar:

**Dataclass `CompileError`:**

- `code: str`
- `message: str`
- `line: int`
- `column: int`
- `length: int`
- `severity: Literal['error', 'warning', 'info']`
- `suggestion: Optional[str] = None`
- `to_dict() -> dict` — produce el formato JSON del spec §1.1

**Clase `ErrorReporter`:**

- `__init__(self)` — inicializa `errors: list[CompileError]`, `warnings: list[CompileError]`
- `add(code, message, line, col, length=1, severity='error', suggestion=None)` — acumula error. Si `severity == 'error'`: añadir a `self.errors`. Si `warning`/`info`: a `self.warnings`. Si `len(self.errors) >= MAX_ERRORS`: no añadir más errors (pero sí warnings).
- `has_errors -> bool` (property)
- `error_limit_reached -> bool` (property) — True si `len(self.errors) >= MAX_ERRORS`
- `all_issues -> list[CompileError]` — `errors + warnings`, ordenados por `(line, column)`
- `to_response(ok=None) -> dict` — produce `{"ok": bool, "errors": [...], "warnings": [...]}`. Si `ok` es None, inferir `ok = not has_errors`.

**También crear `compiler/limits.py`** con todas las constantes del spec §1.2.

#### Tests requeridos (`tests/unit/test_error_reporter.py`)

- `add` con severity `'error'` añade a `errors`
- `add` con severity `'warning'` añade a `warnings`
- Después de `MAX_ERRORS` errores, `error_limit_reached` == True y no se añaden más errors
- Warnings siguen acumulándose incluso con limit reached
- `to_response()` produce JSON con `ok=False` cuando hay errores
- `all_issues` ordenado por línea/columna
- `to_dict()` en `CompileError` incluye `suggestion` solo si no es None

#### Done Criteria

- [ ] `CompileError.to_dict()` produce el formato exacto del spec §1.1
- [ ] `MAX_ERRORS` respetado: no acepta más de 50 errores
- [ ] `error_limit_reached` funciona correctamente
- [ ] `compiler/limits.py` existe con todas las constantes del spec §1.2
- [ ] Tests en `tests/unit/test_error_reporter.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T03 · `compiler/lexer.py`

- [x] T03 completa

**Archivo:** `compiler/lexer.py`
**Depende de:** T01, T02
**Spec:** §3.3, §3.4, §3.5

#### Scope

**Enum `TokenType`** con todos los tipos de token:

- Literales: `INT_LIT`, `FLOAT_LIT`, `STRING_LIT`, `CHAR_LIT`, `BOOL_LIT`
- Identificadores: `IDENT`
- Keywords: `IF`, `ELSE`, `FOR`, `WHILE`, `DO`, `RETURN`, `BREAK`, `CONTINUE`
- Type keywords: `TYPE_KW` (para `int`, `float`, `char`, `bool`, `void`, `string`)
- Builtins: `BUILTIN` (para `print`, `println`, `input`, `input_int`, `input_float`, `true`, `false`)
- Operadores: `PLUS`, `MINUS`, `STAR`, `SLASH`, `PERCENT`, `EQ`, `NEQ`, `LT`, `GT`, `LE`, `GE`, `ASSIGN`, `PLUS_ASSIGN`, `MINUS_ASSIGN`, `STAR_ASSIGN`, `SLASH_ASSIGN`, `PERCENT_ASSIGN`, `AND`, `OR`, `NOT`, `INC`, `DEC`
- Delimitadores: `LPAREN`, `RPAREN`, `LBRACE`, `RBRACE`, `LBRACKET`, `RBRACKET`, `SEMICOLON`, `COMMA`
- Especiales: `EOF`, `ERROR`

**Dataclass `Token`:**

- `type: TokenType`
- `value: str`
- `line: int`
- `column: int`
- `length: int`

**Conjuntos de lookup:**

```python
KEYWORDS      = {'if','else','for','while','do','return','break','continue'}
TYPE_KEYWORDS = {'int','float','char','bool','void','string'}
BUILTINS      = {'print','println','input','input_int','input_float','true','false'}
```

**Clase `Lexer`:**

- `__init__(self, source: str, reporter: ErrorReporter)`
- `tokenize(self) -> list[Token]`

**Comportamiento requerido (spec §3.4):**

- Validar UTF-8, tamaño máximo (`LEX009`, `LEX010`)
- Saltar whitespace y comentarios (`//` y `/* */`, `LEX004` si bloque no cerrado)
- Strings: soporte secuencias escape (`\n`,`\t`,`\r`,`\\`,`\"`,`\'`,`\0`), `LEX007` para secuencias inválidas, `LEX002` si no cerrado, `LEX008` si excede `MAX_STRING_LEN`
- Chars: exactamente 1 caracter entre comillas simples, `LEX003` si vacío o >1 caracter
- Números: enteros decimales y floats (`123`, `1.5`, `.5`, `1e3`, `1.5e-2`), `LEX005` si malformado, `LEX011` si int fuera de rango, `LEX012` si float produce Inf/NaN
- Identificadores: `[a-zA-Z_][a-zA-Z0-9_]*`, `LEX006` si excede `MAX_IDENTIFIER_LEN`
- Operadores de 2 caracteres antes de 1 (ej: `==` antes de `=`)
- Input vacío o solo whitespace/comentarios: produce `[Token(EOF, '', 1, 1, 0)]` sin errores
- Carácter ilegal: emitir `Token(ERROR, char)`, reportar `LEX001`, avanzar exactamente 1 char

#### Tests requeridos (`tests/unit/test_lexer.py`)

- Input vacío → `[EOF]` sin errores
- Solo whitespace → `[EOF]` sin errores
- Keywords reconocidos correctamente (tipo `IF`, `WHILE`, etc.)
- Type keywords → `TYPE_KW` con value correcto
- Builtins → `BUILTIN`
- Integer literals con valores edge: 0, MAX_INT64, MIN_INT64, overflow → `LEX011`
- Float literals: `1.0`, `1e3`, `.5`; `1e999` → `LEX012`
- Strings con escapes válidos e inválidos (`LEX007`)
- Char literal de 1 char → ok; vacío o múltiple → `LEX003`
- Comentario de bloque abierto → `LEX004`
- String sin cerrar → `LEX002`
- Caracter ilegal `@` → `ERROR` token + `LEX001`
- Secuencia de tokens: `int x = 5;` → tipos correctos en orden

#### Done Criteria

- [ ] Todos los `TokenType` del scope implementados
- [ ] Los 12 errores LEX001-LEX012 están implementados con mensajes exactos del spec §3.5
- [ ] Input vacío produce `[EOF]` sin errores (no crash)
- [ ] Caracter ilegal avanza exactamente 1 char (sin loop infinito)
- [ ] Tests en `tests/unit/test_lexer.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T04 · `compiler/parser.py`

- [x] T04 completa

**Archivo:** `compiler/parser.py`
**Depende de:** T01, T02, T03
**Spec:** §4, §2.1

#### Scope

**Clase `Parser`:**

- `__init__(self, tokens: list[Token], reporter: ErrorReporter)`
- `parse(self) -> Program`

**Estado interno requerido (spec §4.3):**

```python
self._loop_depth: int = 0
self._func_depth: int = 0
self._nesting_depth: int = 0
self._open_braces: list[SourcePos] = []
self._current_func_type: Optional[CType] = None
self._current_func_name: Optional[str] = None
```

**Métodos privados (recursive descent — uno por regla gramatical):**

- `_parse_program() -> Program`
- `_parse_top_decl() -> FunctionDecl | VarDecl | ArrayDecl`
- `_parse_function_decl() -> FunctionDecl`
- `_parse_param_list() -> list[Parameter]`
- `_parse_var_decl() -> VarDecl`
- `_parse_array_decl() -> ArrayDecl`
- `_parse_block() -> Block`
- `_parse_statement() -> Any`
- `_parse_if_stmt() -> IfStmt`
- `_parse_while_stmt() -> WhileStmt`
- `_parse_for_stmt() -> ForStmt`
- `_parse_dowhile_stmt() -> DoWhileStmt`
- `_parse_return_stmt() -> ReturnStmt`
- `_parse_expression() -> Any` — entry point para expresiones
- `_parse_assignment() -> Any`
- `_parse_logical_or() -> Any`
- `_parse_logical_and() -> Any`
- `_parse_equality() -> Any`
- `_parse_relational() -> Any`
- `_parse_additive() -> Any`
- `_parse_multiplicative() -> Any`
- `_parse_unary() -> Any`
- `_parse_cast() -> Any`
- `_parse_postfix() -> Any`
- `_parse_primary() -> Any`
- `_synchronize()` — panic-mode recovery hasta token de sincronización
- `_expect(token_type) -> Token` — consume o emite PAR001
- `_check(token_type) -> bool`
- `_advance() -> Token`
- `_peek() -> Token`

**Errores PAR001-PAR012** implementados con mensajes exactos del spec §4.5.

**Comportamiento panic-mode (spec §4.2):**

- Tokens de sincronización: `SEMICOLON`, `RBRACE`, `LBRACE`, `EOF`
- Si `reporter.error_limit_reached`: retornar `Program` parcial inmediatamente
- Al terminar: si `self._open_braces` no vacío → emitir `PAR003` por cada uno

#### Tests requeridos (`tests/unit/test_parser.py`)

- Programa válido mínimo: `int main() { return 0; }` → `Program` con 1 `FunctionDecl`
- Declaración de variable global: `int x = 5;` → `VarDecl`
- Array con inicialización: `int arr[3] = {1, 2, 3};` → `ArrayDecl` con `init_list`
- `if`/`else if`/`else` → `IfStmt` con `elif_clauses` correctos
- `while`, `for`, `do-while` → nodos correctos
- `for` con init vacío: `for (;;)` → `ForStmt(init=None, condition=None, update=None)`
- Función anidada → `PAR004`
- `break` fuera de loop → `PAR007`
- `{` sin cerrar → `PAR003`
- Operadores con precedencia correcta: `1 + 2 * 3` → `BinaryOp(+, 1, BinaryOp(*, 2, 3))`
- `(int)x` → `CastExpr`
- Postfix `x++` y prefix `++x` → `UnaryOp` con `prefix` correcto
- `void` en variable: `void x;` → `PAR012`

#### Done Criteria

- [ ] Toda la gramática BNF del spec §2.1 está implementada
- [ ] Los 12 errores PAR001-PAR012 implementados con mensajes exactos
- [ ] Panic-mode recovery funciona: parser no crashea ante inputs malformados
- [ ] `_open_braces` tracking correcto → `PAR003` al final si quedan abiertas
- [ ] Precedencia de operadores correcta (tabla spec §4.4)
- [ ] Tests en `tests/unit/test_parser.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T05 · `compiler/semantic.py`

- [x] T05 completa

**Archivo:** `compiler/semantic.py`
**Depende de:** T01, T02, T04
**Spec:** §5

#### Scope

**Dataclass `Symbol`** con todos los campos del spec §5.1:

- `name, type, kind, scope_level, line_declared, col_declared`
- `initial_value=None, use_count=0, is_initialized=False, is_mutated=False`
- `array_size=0, return_type='void', param_types=[], call_count=0`
- `to_dict() -> dict`

**Clase `SymbolTable`:**

- `variables: dict[str, Symbol]`
- `functions: dict[str, Symbol]`
- `lookup(name) -> Optional[Symbol]`
- `to_dict() -> dict`

**Clase `SemanticAnalyzer`:**

- `__init__(self, reporter: ErrorReporter)`
- `analyze(self, program: Program) -> SymbolTable`

**4 passes en orden (spec §5.2):**

1. `_pass1_collect_functions(program)` — registra todas las `FunctionDecl` sin analizar bodies
2. `_pass2_globals(program)` — analiza `VarDecl`/`ArrayDecl` globales
3. `_pass3_function_bodies(program)` — analiza cada cuerpo
4. `_pass4_unused_checks()` — emite `SEM004` para `use_count == 0`

**Funciones auxiliares:**

- `_push_scope()`, `_pop_scope()`
- `_declare(name, symbol)` — verifica `SEM002`
- `_resolve(name) -> Optional[Symbol]` — busca desde scope actual hacia global
- `_analyze_block(block)`, `_analyze_stmt(stmt)`, `_analyze_expr(expr) -> CType`
- `resolve_binary_type(left, right, op) -> tuple[CType, bool]` — implementación exacta del spec §5.3
- `all_paths_return(block: Block) -> bool` — spec §5.4 (SEM022)
- `maybe_infinite_recursion(fn: FunctionDecl) -> bool` — spec §5.4 (SEM024)

**Todos los errores SEM001-SEM037** implementados con mensajes exactos del spec §5.4.

**Coerciones** (spec §5.3): `SAFE_WIDENING` y `LOSSY_NARROWING` como conjuntos.

**Regla main (spec §5.5):** `SEM025` si main tiene params o tipo incorrecto; `SEM026` si no existe main (solo en modo compile).

#### Tests requeridos (`tests/unit/test_semantic.py`)

- Variable no declarada → `SEM001`
- Variable duplicada → `SEM002`
- Variable no inicializada → `SEM003` (warning)
- Variable no usada → `SEM004` (warning)
- Función no declarada → `SEM005`
- Función duplicada → `SEM006`
- Tipos incompatibles en asignación → `SEM010`
- `int` + `string` → `SEM011`
- `float` a `int` en asignación → `SEM012` (warning)
- División por cero estática → `SEM013`
- Array con `size=0` → `SEM033`; `size<0` → `SEM034`; `size>65535` → `SEM035`
- `all_paths_return`: if con else → True; if sin else → False
- `SEM022` para función que puede no retornar
- Recursión mutua: `f` llama a `g`, `g` llama a `f` → sin error (forward decls)
- `main` con parámetros → `SEM025`
- `print` como nombre de variable → `SEM036`

#### Done Criteria

- [ ] Los 4 passes implementados en orden correcto
- [ ] Todos los SEM001-SEM037 (+SEM026) implementados con mensajes exactos
- [ ] `resolve_binary_type` sigue exactamente la lógica del spec §5.3
- [ ] `all_paths_return` correcto para if/else, if sin else, while, for
- [ ] Recursión mutua funciona sin error (forward refs via pass 1)
- [ ] Tests en `tests/unit/test_semantic.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

## ETAPA B — Transformaciones del AST

---

### T06 · `compiler/ast_to_c.py`

- [x] T06 completa

**Archivo:** `compiler/ast_to_c.py`
**Depende de:** T01
**Spec:** §9.1

#### Scope

**Clase `ASTtoC`:**

- `__init__(self)`
- `generate(self, program: Program) -> str` — retorna código C válido

**Visitor methods (uno por tipo de nodo):**

- `_visit(node) -> str` — dispatcher
- `_visit_program`, `_visit_function_decl`, `_visit_var_decl`, `_visit_array_decl`
- `_visit_block(block, indent=0) -> str`
- `_visit_if_stmt`, `_visit_while_stmt`, `_visit_for_stmt`, `_visit_dowhile_stmt`
- `_visit_return_stmt`, `_visit_break_stmt`, `_visit_continue_stmt`
- `_visit_print_stmt`, `_visit_expr_stmt`
- `_visit_binary_op` — **siempre parentizar**: `(left op right)`
- `_visit_unary_op` — parentizar: `(op operand)` o `(operand op)` según prefix
- `_visit_assign_op`, `_visit_call_expr`, `_visit_index_expr`
- `_visit_identifier`, `_visit_int_literal`, `_visit_float_literal`
- `_visit_string_literal`, `_visit_char_literal`, `_visit_bool_literal`
- `_visit_input_expr`, `_visit_cast_expr`

**Requisito crítico (spec §9.1):** siempre parentizar `BinaryOp` y `UnaryOp` para que el roundtrip C → AST → C sea idempotente.

**Función module-level:**

- `ast_to_c(program: Program) -> str`

#### Tests requeridos (`tests/unit/test_ast_to_c.py`)

- `int main() { return 0; }` → roundtrip: parse → ast_to_c → resultado válido
- BinaryOp siempre parentizado en output
- `println(x)` → `printf("%...\n", x)` o equivalente en C
- Indentación correcta (4 espacios por nivel)
- Programa completo (fibonacci) → C válido que compila con gcc

#### Done Criteria

- [ ] Todo tipo de nodo AST genera C sintácticamente válido
- [ ] BinaryOp y UnaryOp siempre parentizados
- [ ] Roundtrip idempotente: `parse(ast_to_c(parse(src)))` == `parse(src)` para programas bien formados
- [ ] Tests en `tests/unit/test_ast_to_c.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T07 · `compiler/optimizer.py`

- [x] T07 completa

**Archivo:** `compiler/optimizer.py`
**Depende de:** T01, T05
**Spec:** §6

#### Scope

**Clase `Optimizer`:**

- `__init__(self, level: int = 1, symbol_table: Optional[SymbolTable] = None)`
- `optimize(self, program: Program) -> Program` — ejecuta passes de nivel 1..level en fixed-point hasta OPTIMIZER_MAX_PASS iteraciones

**Passes (métodos privados):**

Nivel 1:

- `_constant_fold(node) -> Any` — post-order, spec §6.2. No plegar si: side effects, div/0, float NaN/Inf, overflow int64
- `_propagate_constants(program) -> Program` — política conservadora spec §6.3
- `_dead_code(program) -> Program` — spec §6.4. Incluye: eliminar después de return/break/continue, fold if literal, fold while-false, eliminar VarDecl con use_count==0 si puro

Nivel 2 (adicionales):

- `_algebraic_simplify(node) -> Any` — tabla completa spec §6.5
- `_strength_reduce(node) -> Any` — spec §6.6 (solo multiplicación por potencias de 2 para nivel 2)
- `_licm(program) -> Program` — spec §6.7. Variables introducidas: `_licm_N`
- `_cse(program) -> Program` — spec §6.7. Hash canónico ignora `pos`

Nivel 3 (adicionales):

- `_inline_functions(program) -> Program` — spec §6.7. Solo si: cuerpo `[ReturnStmt(expr)]`, ≤5 nodos, `is_pure_expr`, no recursiva. Prefijo `_inline_{funcname}_`
- `_tco(program) -> Program` — marcar `is_tail_call=True` en `CallExpr` que son tail calls

**Invariante crítico:** programas optimizados producen el mismo stdout que sin optimizar.

#### Tests requeridos (`tests/unit/test_optimizer.py`)

- Constant folding: `2 + 3` → `IntLiteral(5)`
- No fold: `f() + 3` (side effects)
- No fold: `x / 0` (div zero)
- Algebraic: `x * 1` → `x`; `x + 0` → `x`; `!!x` → `x`
- Strength: `x * 4` → `BinaryOp('<<', x, IntLiteral(2))`
- Dead code: después de `return 1;` los statements siguientes se eliminan
- Dead code: `if (true) { ... }` → solo el cuerpo del then
- Optimizer level 0: no cambia nada en el AST
- **Optimizer invariance**: para todos los programas de demo, `opt_level 0` y `opt_level 3` producen el mismo stdout

#### Done Criteria

- [ ] Los 9 passes implementados (constant fold, propagation, dead code, algebraic, strength, LICM, CSE, inlining, TCO)
- [ ] Fixed-point loop con máximo `OPTIMIZER_MAX_PASS` iteraciones
- [ ] Invariante semántica: outputs iguales en todos los niveles para programas válidos
- [ ] No modifica nodos del AST original (crea nuevos nodos)
- [ ] Tests en `tests/unit/test_optimizer.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

## ETAPA C — Generación de código y ejecución

---

### T08 · `compiler/codegen.py`

- [x] T08 completa

**Archivo:** `compiler/codegen.py`
**Depende de:** T01, T05
**Spec:** §7

#### Scope

**Clase `CodeGenerator`:**

- `__init__(self)`
- `generate(self, program: Program) -> tuple[str, dict[int, int]]` — retorna `(assembly_str, line_map)` donde `line_map[asm_line] = c_line`

**Estado interno:**

```python
self._output: list[str]
self._label_counter: int
self._local_offsets: dict[str, int]   # var_name → offset from fp
self._frame_size: int
self._string_literals: dict[str, str] # value → label
self._line_map: dict[int, int]
self._break_labels: list[str]
self._continue_labels: list[str]
```

**Métodos privados:**

- `_emit(line: str, c_line: int = -1)` — añade a `_output`, popula `_line_map` si `c_line >= 0`
- `_new_label(prefix: str) -> str`
- `_compute_frame(func: FunctionDecl)` — spec §7.3
- `_collect_locals(func: FunctionDecl) -> list[VarDecl | ArrayDecl | Parameter]`
- `_aligned_size_of(ctype: CType, array_size: int = 0) -> int`
- `_gen_function(func: FunctionDecl)` — prologue + body + epilogue
- `_gen_block(block: Block)`
- `_gen_stmt(stmt: Any)`
- `_gen_if`, `_gen_while`, `_gen_for`, `_gen_dowhile`
- `_gen_return`, `_gen_break`, `_gen_continue`
- `_gen_print(stmt: PrintStmt)` — spec §7.4
- `_gen_expr(expr: Any) -> str` — retorna el registro que contiene el resultado
- `_gen_binary`, `_gen_unary`, `_gen_assign`, `_gen_call`, `_gen_index`
- `_gen_literal_int`, `_gen_literal_float`, `_gen_literal_string`, etc.
- `_gen_input(expr: InputExpr)` — usa fgets/scanf
- `_gen_div_zero_guard(reg_divisor: str, label_n: int)`
- `_gen_oob_guard(reg_index: str, size: int, arr_name: str, label_n: int)`
- `_is_macos() -> bool`
- `_emit_rodata_section()` — emite todos los string literals
- `_emit_prologue(func_name: str)`
- `_emit_epilogue()`

**Estructura del assembly emitido:** exactamente como spec §7.2 (secciones, directivas macOS/Linux, formato de labels).

**Guards:** división por cero y array OOB tal como spec §7.6.

**Mapa de líneas:** comentarios `; src:LINE:COL` + `self._line_map` tal como spec §7.7.

**TCO:** si `stmt` es `ReturnStmt` con `CallExpr(is_tail_call=True)`: sobrescribir parámetros y `b .L_{funcname}_start` en lugar de call normal.

#### Tests requeridos (`tests/unit/test_codegen.py`)

- `int main() { return 42; }` → assembly que al ejecutar retorna código 42
- `println(5)` → assembly que imprime "5\n"
- `if`/`else` → labels `.Lelse_N`, `.Lendif_N`
- `while` loop → labels `.Lwhile_start_N`, `.Lwhile_end_N`
- `for` → label `.Lfor_update_N` para continue
- División por cero guard presente cuando no se puede probar estáticamente
- Array OOB guard presente en accesos
- `line_map` no vacío para programa con múltiples líneas

#### Done Criteria

- [ ] Estructura del assembly sigue exactamente spec §7.2
- [ ] `_compute_frame` alinea a 16 bytes (requerido por AArch64 PCS)
- [ ] Guards de división por cero y OOB implementados (spec §7.6)
- [ ] `_line_map` poblado correctamente
- [ ] `_break_labels` y `_continue_labels` con push/pop correcto
- [ ] Detección macOS vs Linux para directivas de sección y nombres de funciones
- [ ] Tests en `tests/unit/test_codegen.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T09 · `compiler/executor.py`

- [x] T09 completa

**Archivo:** `compiler/executor.py`
**Depende de:** T08
**Spec:** §9.2

#### Scope

**Dataclass `ExecutionResult`:**

- `stdout: str`
- `stderr: str`
- `returncode: int`
- `timed_out: bool`
- `assembly_path: str`
- `binary_path: Optional[str]`
- `error: Optional[str]`

**Clase `Executor`:**

- `__init__(self, work_dir: str = '/tmp/compileflow')`
- `assemble_and_run(self, assembly: str, session_id: str, stdin_data: str = '') -> ExecutionResult`
- `_is_native_arm64(self) -> bool`
- `_gcc_cmd(self, asm: str, out: str) -> list[str]`
- `_run_cmd(self, bin_path: str) -> list[str]`

**Comportamiento (spec §9.2):**

- `assemble_and_run`: escribir `.s`, invocar gcc, ejecutar binario
- Si gcc falla: retornar `ExecutionResult` con `error` y `returncode=-1`
- Ejecución con timeout `EXEC_TIMEOUT_SEC` (10s)
- Truncar stdout a `MAX_OUTPUT_SIZE` con mensaje `'[Output truncado — máximo 1MB]'`
- Limpiar binario en `finally`, conservar `.s`
- Native ARM64: `gcc -o out asm`
- Cross (x86): `aarch64-linux-gnu-gcc -static -o out asm`; run con `qemu-aarch64`

#### Tests requeridos (`tests/unit/test_executor.py`)

- Assembly ARM64 válido (retorna 0) → `ExecutionResult.returncode == 0`
- Assembly inválido → `returncode == -1` y `error` no vacío
- Timeout: assembly con loop infinito → `timed_out == True`
- Output truncado: stdout > 1MB → stdout termina con mensaje de truncado

#### Done Criteria

- [ ] `assemble_and_run` sigue exactamente la lógica del spec §9.2
- [ ] `_gcc_cmd` diferencia correctamente entre native ARM64 y cross-compile
- [ ] Timeout funciona: proceso se mata a los `EXEC_TIMEOUT_SEC` segundos
- [ ] Output truncado a `MAX_OUTPUT_SIZE`
- [ ] Binario se limpia en `finally` aunque haya excepción
- [ ] Tests en `tests/unit/test_executor.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T10 · `compiler/interpreter.py`

- [x] T10 completa

**Archivo:** `compiler/interpreter.py`
**Depende de:** T01, T02
**Spec:** §8

#### Scope

**Clase `InterpreterError(Exception)`**

**Dataclass `DebugState`:**

- `line: int`
- `col: int`
- `variables: dict[str, Any]` — snapshot del scope actual
- `call_stack: list[str]` — nombres de funciones
- `stdout: str` — output acumulado hasta este punto
- `finished: bool`
- `return_code: Optional[int]`

**Clase `Interpreter`:**

- `__init__(self, program: Program, input_fn: Optional[Callable[[], str]] = None)`
- `run(self) -> tuple[str, int]` — ejecuta main(), retorna `(stdout, returncode)`
- `start_debug(self)` — prepara estado para step-through
- `step(self) -> DebugState` — ejecuta un statement, retorna estado
- `continue_to_breakpoint(self, breakpoints: set[int]) -> DebugState`
- `get_state(self) -> DebugState`
- `_execute_function(self, func: FunctionDecl, args: list[Any]) -> Any`
- `_execute_block(self, block: Block) -> Any`
- `_execute_stmt(self, stmt: Any) -> Any`
- `_eval_expr(self, expr: Any) -> Any`

**Límites (spec §8):**

- `INTERP_MAX_DEPTH = 500` — profundidad de call stack
- `INTERP_MAX_ITERS = 1_000_000` — iteraciones de loop (incrementar por cada *entrada* al body del loop)
- `INTERP_TIMEOUT_SEC = 30`
- `input()` sin `input_fn` → `InterpreterError("input() requiere input_fn configurado")`

**Semántica de tipos:** int como Python int (con límites int64), float como Python float, bool como Python bool, string como Python str, arrays como Python lists.

#### Tests requeridos (`tests/interpreter/test_interpreter.py`)

- `int main() { return 42; }` → returncode 42
- `println(1 + 2)` → stdout "3\n"
- Variables, asignaciones, scoping correcto
- Recursión: fibonacci(10) → stdout correcto
- Límite de recursión: función recursiva infinita → `InterpreterError`
- Límite de iteraciones: while true → `InterpreterError`
- `input()` sin callback → `InterpreterError`
- Step-through: `start_debug()` + `step()` avanza statement a statement

#### Done Criteria

- [ ] `run()` ejecuta main y retorna `(stdout, returncode)` correcto
- [ ] Todos los límites (`INTERP_MAX_DEPTH`, `INTERP_MAX_ITERS`) respetados
- [ ] `start_debug` + `step` funciona para step-through
- [ ] `DebugState` refleja variables y call stack correctamente
- [ ] `input()` sin callback lanza `InterpreterError` con mensaje exacto
- [ ] Tests en `tests/interpreter/test_interpreter.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

## ETAPA D — Conversiones bidireccionales

---

### T11 · `compiler/blocks_to_ast.py`

- [x] T11 completa

**Archivo:** `compiler/blocks_to_ast.py`
**Depende de:** T01, T02
**Spec:** §9.1

#### Scope

**Clase `BlocksToAST`:**

- `__init__(self, reporter: ErrorReporter)`
- `convert(self, workspace: dict) -> Program` — workspace es el JSON de Blockly

**Métodos privados por tipo de bloque:**

- `_convert_workspace(ws: dict) -> Program`
- `_convert_function_def(block: dict) -> FunctionDecl`
- `_convert_var_decl(block: dict) -> VarDecl`
- `_convert_array_decl(block: dict) -> ArrayDecl`
- `_convert_statement(block: dict) -> Any`
- `_convert_if(block: dict) -> IfStmt`
- `_convert_while(block: dict) -> WhileStmt`
- `_convert_for(block: dict) -> ForStmt`
- `_convert_dowhile(block: dict) -> DoWhileStmt`
- `_convert_return(block: dict) -> ReturnStmt`
- `_convert_print(block: dict) -> PrintStmt`
- `_convert_assign(block: dict) -> ExprStmt`
- `_convert_expr(block: dict) -> Any`
- `_convert_binary_arith`, `_convert_binary_cmp`, `_convert_binary_logic`
- `_convert_unary`, `_convert_call_expr`, `_convert_call_stmt`
- `_convert_literal_int`, `_convert_literal_float`, `_convert_literal_bool`, `_convert_literal_string`, `_convert_literal_char`
- `_convert_identifier`, `_convert_index_expr`, `_convert_input`
- `_get_pos_from_block(block: dict) -> SourcePos`

**Manejo de JSON inválido:** nunca lanzar excepción; usar `reporter.add(...)` para cada bloque no reconocido.

**Función module-level:**

- `blocks_to_ast(workspace: dict, reporter: ErrorReporter) -> Program`

#### Tests requeridos (`tests/unit/test_blocks_to_ast.py`)

- Workspace vacío → `Program(declarations=[], ...)`
- Bloque de función → `FunctionDecl` con params correctos
- Bloque de if con else → `IfStmt` con `else_body`
- Bloque de expresión aritmética → `BinaryOp` con tipos correctos
- Bloque desconocido → error en reporter, sin crash
- JSON malformado (None values) → sin crash

#### Done Criteria

- [ ] Todos los tipos de bloque del spec §14 implementados
- [ ] JSON inválido/desconocido → error en reporter, sin crash
- [ ] `_get_pos_from_block` extrae `srcLine` correctamente
- [ ] Tests en `tests/unit/test_blocks_to_ast.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T12 · `compiler/ast_to_blocks.py`

- [x] T12 completa

**Archivo:** `compiler/ast_to_blocks.py`
**Depende de:** T01, T11
**Spec:** §9.1, §14

#### Scope

**Clase `ASTtoBlocks`:**

- `__init__(self)`
- `convert(self, program: Program) -> dict` — retorna workspace JSON para Blockly

**Métodos privados por tipo de nodo:**

- `_visit(node) -> dict | list[dict]`
- `_visit_program(program) -> dict`
- `_visit_function_decl(func) -> dict`
- `_visit_var_decl`, `_visit_array_decl`
- `_visit_block(block) -> list[dict]` — lista de statement blocks encadenados
- `_visit_if_stmt`, `_visit_while_stmt`, `_visit_for_stmt`, `_visit_dowhile_stmt`
- `_visit_return_stmt`, `_visit_break_stmt`, `_visit_continue_stmt`
- `_visit_print_stmt`, `_visit_expr_stmt`
- `_visit_binary_op` — selecciona `c_binary_arith`, `c_binary_cmp`, o `c_binary_logic` (spec §14.2)
- `_visit_unary_op`, `_visit_assign_op`
- `_visit_call_expr` → `c_func_call_expr` (spec §14.2)
- `_visit_call_stmt` (cuando `CallExpr` está en `ExprStmt`) → `c_func_call_stmt`
- `_visit_index_expr`, `_visit_identifier`
- `_visit_int_literal`, `_visit_float_literal`, `_visit_bool_literal`, `_visit_string_literal`, `_visit_char_literal`
- `_visit_input_expr`, `_visit_cast_expr`
- `_inject_src_line(block: dict, pos: SourcePos) -> dict` — inyecta `block.data = {"srcLine": pos.line}` (spec §9.1)

**Función module-level:**

- `ast_to_blocks(program: Program) -> dict`

#### Tests requeridos (`tests/unit/test_ast_to_blocks.py`)

- Roundtrip: `blocks_to_ast(ast_to_blocks(ast))` produce AST equivalente al original
- `CallExpr` en `ExprStmt` → `c_func_call_stmt`; en expresión → `c_func_call_expr`
- BinaryOp aritmético → `c_binary_arith`; comparación → `c_binary_cmp`; lógico → `c_binary_logic`
- `srcLine` inyectado en cada bloque

#### Done Criteria

- [ ] Todos los tipos de nodo AST convertidos al tipo de bloque correcto del spec §14.2
- [ ] `c_func_call_expr` vs `c_func_call_stmt` diferenciados por posición
- [ ] `srcLine` inyectado en `block.data` para todos los bloques
- [ ] Roundtrip AST → Blocks → AST produce AST equivalente
- [ ] Tests en `tests/unit/test_ast_to_blocks.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T13 · `compiler/explainer.py`

- [x] T13 completa

**Archivo:** `compiler/explainer.py`
**Depende de:** T01
**Spec:** §9.1

#### Scope

**Clase `Explainer`:**

- `__init__(self)`
- `explain(self, program: Program) -> str` — retorna Markdown en español

**Métodos privados:**

- `_explain_program(program) -> str`
- `_explain_function(func: FunctionDecl) -> str`
- `_explain_block(block: Block, indent: int = 0) -> str`
- `_explain_stmt(stmt: Any, indent: int = 0) -> str`
- `_explain_expr(expr: Any) -> str` — descripción legible de la expresión
- `_explain_if(stmt: IfStmt, indent: int) -> str`
- `_explain_while(stmt: WhileStmt, indent: int) -> str`
- `_explain_for(stmt: ForStmt, indent: int) -> str`
- `_explain_var_decl(decl: VarDecl, indent: int) -> str`
- `_explain_return(stmt: ReturnStmt, indent: int) -> str`
- `_explain_call(expr: CallExpr) -> str`
- `_explain_binary(expr: BinaryOp) -> str`
- `_ctype_name(ctype: CType) -> str` — `'int'` → `'entero'`, `'float'` → `'decimal'`, etc.

**Output esperado:** Markdown legible en español. Ejemplo:

```
## Programa CompileFlow

### Función `main` (retorna entero)
1. Declara variable entera `x` con valor inicial **5**
2. Si `x` es mayor que **3**:
   - Imprime `"mayor"` con salto de línea
3. Retorna **0**
```

**Función module-level:**

- `explain(program: Program) -> str`

#### Tests requeridos (`tests/unit/test_explainer.py`)

- `int main() { return 0; }` → output contiene "función" y "retorna"
- `println(5)` → output menciona "imprime"
- `if (x > 0) { ... }` → output menciona condición
- `for` loop → output menciona "repite" o "itera"
- Output es Markdown válido (contiene `#` headers)
- Sin crash para programas vacíos

#### Done Criteria

- [ ] Todos los tipos de nodo generan descripción en español
- [ ] Output es Markdown con headers `##` y `###`
- [ ] `_ctype_name` mapea todos los 6 tipos de CType
- [ ] Sin crash para AST de cualquier estructura
- [ ] Tests en `tests/unit/test_explainer.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

## ETAPA E — API Flask

---

### T14 · `server/validators.py`

- [x] T14 completa

**Archivo:** `server/validators.py`
**Depende de:** T01, T02
**Spec:** §11

#### Scope

Implementar exactamente los siguientes modelos Pydantic v2 del spec §11:

- `CompileRequest(source, optimization_level=1, stdin='', include_explanation=False)`
- `CheckRequest(source)`
- `ConvertRequest(direction, source='', workspace={})`
- `DebugStartRequest(source)`
- `ValidateFileRequest(filename, content, file_type)`
- `ExplainRequest(source)`

Constraints de cada campo:

- `source: str = Field(..., max_length=524_288)`
- `optimization_level: int = Field(default=1, ge=0, le=3)`
- `stdin: Optional[str] = Field(default='', max_length=65_536)`
- `direction: Literal['c_to_blocks', 'blocks_to_c']`
- `filename: str = Field(..., max_length=255)`
- `content: str = Field(..., max_length=2_097_152)`
- `file_type: Literal['c', 'asm', 'scratch', 'cfproj']`

#### Tests requeridos (`tests/unit/test_validators.py`)

- `CompileRequest` válido → sin error
- `source` vacío en `CompileRequest` → sin error (Pydantic no requiere min_length aquí)
- `source` > 512KB → `ValidationError`
- `optimization_level` fuera de `[0,3]` → `ValidationError`
- `direction` inválido en `ConvertRequest` → `ValidationError`
- `file_type` inválido → `ValidationError`

#### Done Criteria

- [ ] Todos los 6 modelos del spec §11 implementados con constraints exactos
- [ ] Tests en `tests/unit/test_validators.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

### T15 · `server/app.py` + `server/routes/`

- [x] T15 completa

**Archivos:**

- `server/app.py`
- `server/routes/compile.py`
- `server/routes/check.py`
- `server/routes/convert.py`
- `server/routes/files.py`
- `server/routes/explain.py`
- `server/routes/debug.py`

**Depende de:** T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13, T14
**Spec:** §12

#### Scope

**`server/app.py`** (spec §12.1):

- `create_app() -> tuple[Flask, SocketIO]`
- CORS habilitado para `/api/*`
- SocketIO con `async_mode='threading'`
- Blueprints registrados en `/api`
- `@app.errorhandler(Exception)` → JSON `{'ok': False, 'errors': [{'code': 'SRV001', ...}]}`

**`routes/compile.py`:**

- `POST /api/compile` — corre pipeline completo: lex → parse → sema → optimize → codegen → execute
- Body: `CompileRequest`; response: `{"ok": true, "data": {"assembly": str, "stdout": str, "stderr": str, "returncode": int, "line_map": dict, "warnings": [...], "explanation": str | null}}`
- Si hay errores semánticos: no compilar, retornar errores
- Manejo de `include_explanation`: si True, llamar a `explainer.explain(ast)` y añadir al response

**`routes/check.py`:**

- `POST /api/check` — solo lex + parse + sema
- Body: `CheckRequest`; response siempre HTTP 200 con `{"ok": bool, "errors": [...], "warnings": [...], "symbol_table": dict}`

**`routes/convert.py`:**

- `POST /api/convert` — `c_to_blocks` o `blocks_to_c`
- Body: `ConvertRequest`

**`routes/files.py`:**

- `POST /api/validate-file` — valida formato de archivo subido
- Body: `ValidateFileRequest`; response `{"ok": true, "content": str}`

**`routes/explain.py`:**

- `POST /api/explain` — Body: `ExplainRequest`; response `{"ok": true, "data": {"explanation": str}}`

**`routes/debug.py` (SocketIO):**

- Evento `debug:start` — inicia intérprete, emite `debug:state`
- Evento `debug:step` — ejecuta un step, emite `debug:state`
- Evento `debug:continue` — continúa hasta breakpoint, emite `debug:state`
- Evento `debug:stop` — termina sesión

#### Tests requeridos (`tests/integration/test_api.py`)

- `POST /api/check` con `int main() { return 0; }` → `{"ok": true}`
- `POST /api/check` con `int x = "hello";` → `{"ok": false, "errors": [...]}`
- `POST /api/compile` con programa simple → `{"ok": true, "data": {"stdout": ...}}`
- `POST /api/convert` direction `c_to_blocks` → workspace dict
- `POST /api/explain` → markdown string
- Error 500 cualquier ruta → `{"ok": false, "errors": [{"code": "SRV001"}]}`

#### Done Criteria

- [ ] Todos los endpoints del spec §12.2 implementados
- [ ] `create_app()` retorna `(Flask, SocketIO)` con CORS y blueprints correctos
- [ ] `global_error_handler` captura todas las excepciones → JSON `SRV001`
- [ ] SocketIO debug events implementados
- [ ] Tests en `tests/integration/test_api.py` pasan al 100%
- [ ] `ruff` y `mypy --strict` limpios
- [ ] Checklist universal de pre-commit ✓

---

## ETAPA F — Frontend

---

### T16 · Scaffolding frontend (Vite + estructura)

- [x] T16 completa

**Archivos creados:**

- `package.json`
- `vite.config.js`
- `index.html`
- `frontend/main.js`
- `frontend/ide/` (directorio vacío con `.gitkeep`)
- `frontend/blocks/` (directorio vacío con `.gitkeep`)
- `frontend/features/` (directorio vacío con `.gitkeep`)
- `requirements.txt` — dependencias Python del spec §17

**Depende de:** nada
**Spec:** §17

#### Scope

`package.json`:

```json
{
  "scripts": { "dev": "vite", "build": "vite build", "preview": "vite preview" },
  "dependencies": { "monaco-editor": "latest", "blockly": "latest", "d3": "latest" },
  "devDependencies": { "vite": "latest" }
}
```

`requirements.txt` exactamente como spec §17:

```
flask==3.0.3
flask-cors==4.0.1
flask-socketio==5.3.6
pydantic==2.7.1
pytest==8.2.0
pytest-cov==5.0.0
eventlet==0.36.1
```

`index.html`: estructura HTML base con `<div id="app">`, importa `main.js`.

`vite.config.js`: configuración básica de Vite con proxy a `localhost:5000` para `/api` y `/ws`.

#### Done Criteria

- [ ] `npm install` termina sin errores
- [ ] `npm run dev` arranca sin errores
- [ ] `requirements.txt` tiene exactamente las versiones del spec §17
- [ ] Estructura de directorios completa
- [ ] Checklist universal de pre-commit ✓

---

### T17 · `frontend/ide/monaco_setup.js`

- [x] T17 completa

**Archivo:** `frontend/ide/monaco_setup.js`
**Depende de:** T16
**Spec:** §13

#### Scope

**Función exportada `setupMonaco(container, options)`:**

- Crea editor Monaco con lenguaje `'c-compileflow'`
- Registra monarch tokenizer con: keywords, type_keywords, builtins (incluye `input_int`, `input_float`), operadores, comentarios `//` y `/* */`, strings, chars, números
- Registra completion provider: keywords + snippets + símbolos de `window.__symbolTable` si existe
- Registra hover provider: doc strings para builtins y keywords
- Registra signature help provider para funciones definidas por el usuario
- Configura `formatOnSave: true` (usando formatter básico)
- Debounce de `/api/check` a **300ms** (spec §13)
- Al recibir respuesta de `/api/check`: marcar errores con `editor.setModelMarkers(...)`
- Setter `window.__symbolTable` actualizado después de cada check exitoso

**Función exportada `getEditorValue() -> string`**
**Función exportada `setEditorValue(code: string)`**
**Función exportada `getEditor() -> monaco.editor`**

#### Tests requeridos

- `setupMonaco` no lanza al montar en DOM
- Tokenizer reconoce `int`, `float`, `for`, `println` como tokens correctos
- `setEditorValue` / `getEditorValue` roundtrip

#### Done Criteria

- [x] Monarch tokenizer reconoce todos los tokens del lenguaje (spec §3.3)
- [x] Completion provider funciona con y sin `window.__symbolTable`
- [x] Debounce de check a 300ms
- [x] Marcadores de error se muestran en el editor
- [x] Tests pasan
- [x] Checklist universal de pre-commit ✓

---

### T18 · `frontend/blocks/blockly_setup.js`

- [x] T18 completa

**Archivo:** `frontend/blocks/blockly_setup.js`
**Depende de:** T16
**Spec:** §14

#### Scope

**Función exportada `setupBlockly(container, options)`:**

- Define todos los bloques custom con `Blockly.Blocks[...]` y `Blockly.JavaScript[...]` (para toolbox):
  - `c_var_decl`, `c_array_decl`
  - `c_if`, `c_while`, `c_for`, `c_dowhile`
  - `c_return`, `c_break`, `c_continue`
  - `c_print`, `c_println`
  - `c_binary_arith`, `c_binary_cmp`, `c_binary_logic` — tipos Blockly del spec §14.1
  - `c_unary_not`, `c_unary_neg`, `c_prefix_inc`, `c_prefix_dec`, `c_postfix_inc`, `c_postfix_dec`
  - `c_assign`, `c_compound_assign`
  - `c_func_decl`, `c_func_call_expr`, `c_func_call_stmt` — split del spec §14.2
  - `c_lit_int`, `c_lit_float`, `c_lit_bool`, `c_lit_string`, `c_lit_char`
  - `c_identifier`, `c_index_expr`
  - `c_input`, `c_input_int`, `c_input_float`
  - `c_cast`
- Configura toolbox con categorías: Variables, Control, Funciones, I/O, Operadores, Arrays, Tipos
- Configura minimap, undo/redo
- Inyecta `srcLine` en `block.data` al crear bloques (para debugger)

**Función exportada `getWorkspace() -> Blockly.WorkspaceSvg`**
**Función exportada `getWorkspaceJSON() -> dict`**
**Función exportada `loadWorkspaceJSON(json: dict)`**

#### Done Criteria

- [x] Todos los tipos de bloque del spec §14.2 definidos
- [x] Tipos Blockly correctos: `"Number"`, `"Boolean"`, `"String"` según spec §14.1
- [x] `c_func_call_expr` tiene `output`, `c_func_call_stmt` no
- [x] `setupBlockly` no lanza en DOM
- [x] Checklist universal de pre-commit ✓

---

### T19 · `frontend/features/sync.js`

- [x] T19 completa

**Archivo:** `frontend/features/sync.js`
**Depende de:** T17, T18, T15
**Spec:** §15.1

#### Scope

**Clase `SyncManager`:**

- `constructor(monacoEditor, blocklyWorkspace, apiBase)`
- `_syncIdeToBlocks()` — llama `POST /api/convert` con `direction='c_to_blocks'`, carga resultado en Blockly. Debounce 600ms.
- `_syncBlocksToIde()` — llama `POST /api/convert` con `direction='blocks_to_c'`, actualiza Monaco. Inmediato.
- `_onIdeChange(handler)` — subscribe a cambios en Monaco
- `_onBlocksChange(handler)` — subscribe a cambios en Blockly
- `enableSync()` — activa ambas suscripciones
- `disableSync()` — desactiva (necesario durante sync para evitar loops)
- `_guard: boolean` — previene re-entrancia (sync loop)

**Comportamiento:**

- IDE → Blocks: debounce 600ms, llama `/api/convert c_to_blocks`
- Blocks → IDE: inmediato, llama `/api/convert blocks_to_c`
- Si la conversión falla (errores): no actualizar el lado destino (no perder estado)

#### Done Criteria

- [ ] Debounce IDE→Blocks de 600ms
- [ ] Guard anti-loop funciona: cambio en IDE no dispara sync de Blocks que dispara IDE de vuelta
- [ ] Si API retorna error, lado destino no se modifica
- [ ] Checklist universal de pre-commit ✓

---

### T20 · `frontend/features/ast_viewer.js`

- [x] T20 completa

**Archivo:** `frontend/features/ast_viewer.js`
**Depende de:** T17
**Spec:** §15.3

#### Scope

**Clase `ASTViewer`:**

- `constructor(container: HTMLElement)`
- `render(astData: object)` — renderiza árbol AST usando D3 (layout: árbol vertical)
- `highlight(nodeId: string)` — resalta nodo
- `clear()`
- `_buildD3Tree(astData) -> d3.HierarchyNode`
- `_renderLinks(nodes)`, `_renderNodes(nodes)`
- `_onNodeClick(callback)` — al hacer click en nodo, callback recibe `{line, col}`

**Características requeridas:**

- Nodos con tipo de nodo como label (ej: `BinaryOp`, `IfStmt`)
- Tipo inferido del nodo como sublabel (ej: `int`)
- Click en nodo → resalta línea correspondiente en Monaco
- Zoom y pan con D3

#### Done Criteria

- [ ] D3 árbol renderiza sin error para AST simple
- [ ] Click en nodo dispara callback con `{line, col}`
- [ ] Nodos muestran tipo y tipo inferido
- [ ] Checklist universal de pre-commit ✓

---

### T21 · `frontend/features/asm_panel.js`

- [x] T21 completa

**Archivo:** `frontend/features/asm_panel.js`
**Depende de:** T17
**Spec:** §15.4

#### Scope

**Clase `AsmPanel`:**

- `constructor(container: HTMLElement, monacoEditor)`
- `render(assembly: string, lineMap: object)` — muestra assembly en panel con syntax highlighting básico
- `syncWithEditor(cLine: number)` — dado número de línea C, resalta línea ASM correspondiente usando `lineMap`
- `_buildReverseMap(lineMap) -> object` — `c_line → asm_line`
- `_highlightAsmLine(asmLine: number)`

**Contenido del panel:**

- Assembly mostrado como texto monoespaciado
- Línea activa resaltada con background
- Tooltips en instrucciones ARM64 con descripción en español (tabla del spec §15.4)

#### Done Criteria

- [ ] `render` muestra assembly correctamente
- [ ] `syncWithEditor` resalta línea ASM correspondiente a línea C
- [ ] Tooltips de instrucciones ARM64 presentes
- [ ] Checklist universal de pre-commit ✓

---

### T22 · `frontend/features/debugger.js`

- [x] T22 completa

**Archivo:** `frontend/features/debugger.js`
**Depende de:** T17, T15
**Spec:** §15.2

#### Scope

**Clase `Debugger`:**

- `constructor(monacoEditor, blocklyWorkspace, socketURL)`
- `start(source: string)` — emite `debug:start` vía SocketIO
- `step()` — emite `debug:step`
- `continue(breakpoints: Set<number>)` — emite `debug:continue` con breakpoints
- `stop()` — emite `debug:stop`
- `_onState(state: DebugState)` — actualiza UI: resalta línea en Monaco y en Blockly
- `_updateVariablesPanel(variables: object)` — muestra variables actuales
- `_updateCallStack(callStack: string[])` — muestra call stack
- `_highlightLine(line: number)` — resalta línea en Monaco + bloque en Blockly (usando `srcLine`)

**UI requerida:**

- Panel de variables con nombre, tipo, valor
- Panel de call stack
- Botones: Step, Continue, Stop
- Línea actual resaltada en Monaco (decoration)
- Bloque actual resaltado en Blockly

#### Done Criteria

- [ ] Conexión SocketIO a `/ws/debug` funciona
- [ ] `step()` resalta línea correcta en Monaco y Blockly
- [ ] Panel de variables se actualiza en cada step
- [ ] Checklist universal de pre-commit ✓

---

### T23 · `frontend/features/explainer.js`

- [x] T23 completa

**Archivo:** `frontend/features/explainer.js`
**Depende de:** T17, T15
**Spec:** §15.8

#### Scope

**Clase `ExplainerPanel`:**

- `constructor(container: HTMLElement)`
- `load(source: string)` — llama `POST /api/explain`, muestra resultado
- `render(markdown: string)` — renderiza Markdown en el panel (usar `marked.js` o similar)
- `clear()`

#### Done Criteria

- [ ] `POST /api/explain` llamado con source actual
- [ ] Markdown renderizado (no texto crudo)
- [ ] Panel limpiable
- [ ] Checklist universal de pre-commit ✓

---

### T24 · `frontend/features/gallery.js`

- [x] T24 completa

**Archivo:** `frontend/features/gallery.js`
**Depende de:** T17
**Spec:** §15.6

#### Scope

**8 programas de demo** definidos inline (spec §16):

1. Fibonacci (recursivo)
2. Factorial (recursivo)
3. Bubble sort
4. Collatz conjecture
5. FizzBuzz
6. Suma de array
7. Búsqueda lineal
8. Calculadora (switch emulado con if/else)

**Clase `Gallery`:**

- `constructor(monacoEditor)`
- `getExamples() -> Array<{name: string, source: string}>`
- `load(index: number)` — carga ejemplo en Monaco

#### Done Criteria

- [x] 8 programas de demo incluidos, sintácticamente válidos para el lenguaje
- [x] `load(i)` carga en Monaco sin error
- [x] Checklist universal de pre-commit ✓

---

### T25 · `frontend/features/share.js` + `frontend/features/file_io.js`

- [x] T25 completa

**Archivos:** `frontend/features/share.js`, `frontend/features/file_io.js`
**Depende de:** T17
**Spec:** §15.7, §15.5

#### Scope

**`share.js`** — implementar exactamente la clase `ShareManager` del spec §15.7:

- `_encodeUtf8Base64(str) -> string` — URL-safe base64 (spec §15.7, código exacto)
- `_decodeUtf8Base64(encoded) -> string`
- `encode(state) -> string`
- `decode(encoded) -> object` — lanza si versión incompatible
- `share(state) -> string` — pushState + clipboard
- `loadFromURL() -> object | null`

**`file_io.js`:**

- `saveAsC(source: string)` — descarga archivo `.c`
- `saveAsAsm(assembly: string)` — descarga `.s`
- `saveAsCfproj(state: object)` — descarga `.cfproj` (JSON)
- `saveAsScratch(workspace: object)` — descarga `.scratch` (JSON Blockly)
- `saveAsPng(canvas: HTMLCanvasElement)` — descarga `.png`
- `loadFile(file: File) -> Promise<{type: string, content: any}>` — detecta tipo por extensión, llama `POST /api/validate-file`
- `autoSave(state: object)` — guarda en `localStorage`, mantiene 5 versiones
- `loadAutoSave() -> object | null` — carga versión más reciente

#### Done Criteria

- [ ] `ShareManager` implementado con código exacto del spec §15.7
- [ ] `_encodeUtf8Base64` produce URL-safe base64 (no `+` ni `/`)
- [ ] `loadFromURL()` retorna `null` si no hay parámetro `p`
- [ ] `autoSave` mantiene máximo 5 versiones en localStorage
- [ ] Todos los tipos de descarga generan archivo correcto
- [ ] Checklist universal de pre-commit ✓

---

## ETAPA G — Integración y validación final

---

### T26 · Suite de tests completa

- [x] T26 completa

**Archivos:**

- `tests/conftest.py`
- `tests/unit/` (completar los que falten)
- `tests/integration/test_pipeline.py`
- `tests/robustness/test_bad_inputs.py`
- `tests/roundtrip/test_roundtrip.py`
- `tests/interpreter/test_interpreter.py` (completar)

**Depende de:** T01–T25
**Spec:** §10

#### Scope

**`tests/conftest.py`** — exactamente como spec §10.2:

- `CompileResult` dataclass
- `compile_safe(source, opt_level=0) -> CompileResult`
- `compile_and_run(source, opt_level=1, stdin_data='') -> CompileResult`
- Fixtures: `reporter`, `safe_compile`, `run`

**`tests/robustness/test_bad_inputs.py`** — exactamente como spec §10.3:

- `MALFORMED_INPUTS` (20 strings del spec)
- `EDGE_CASE_INPUTS` (6 strings del spec)
- `BOMB_INPUTS` (6 strings del spec)
- Tests parametrizados: `test_malformed_produces_errors`, `test_edge_cases_no_errors`, `test_bombs_do_not_crash`

**`tests/integration/test_pipeline.py`:**

- Pipeline completo para los 8 programas de demo: compile + run → output correcto
- Fibonacci(10) → `55`
- Factorial(5) → `120`
- etc.

**`tests/unit/test_optimizer.py`** — incluye invariance test (spec §10.4):

- `OPT_INVARIANCE_PROGRAMS` = los 8 programas de demo
- `test_optimization_preserves_semantics`: niveles 0,1,2,3 producen mismo stdout y returncode

**`tests/roundtrip/test_roundtrip.py`:**

- Para cada programa de demo: `parse(ast_to_c(parse(source)))` == `parse(source)`
- Para cada programa de demo: `blocks_to_ast(ast_to_blocks(ast))` produce AST equivalente

**Cobertura mínima:** `pytest --cov=compiler --cov-report=term-missing` debe mostrar ≥ 85% en cada módulo de `compiler/`.

#### Done Criteria

- [x] `conftest.py` implementado con helpers exactos del spec §10.2
- [x] Todos los robustness tests: 20 malformed → errores; 6 edge cases → sin error; 6 bombs → sin crash
- [x] Pipeline integration tests: los 8 programas compilan y producen output correcto
- [x] Optimizer invariance test pasa para todos los niveles 0-3
- [x] Roundtrip test pasa (C→AST→C y Blocks→AST→Blocks)
- [x] Cobertura ≥ 85% en módulos de `compiler/`
- [x] `pytest` al 100% (0 failures, 0 errors)
- [x] Checklist universal de pre-commit ✓

---

## Resumen de dependencias

```
T01 ← (ninguna)
T02 ← T01
T03 ← T01, T02
T04 ← T01, T02, T03
T05 ← T01, T02, T04
T06 ← T01
T07 ← T01, T05
T08 ← T01, T05
T09 ← T08
T10 ← T01, T02
T11 ← T01, T02
T12 ← T01, T11
T13 ← T01
T14 ← T01, T02
T15 ← T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13, T14
T16 ← (ninguna)
T17 ← T16
T18 ← T16
T19 ← T17, T18, T15
T20 ← T17
T21 ← T17
T22 ← T17, T15
T23 ← T17, T15
T24 ← T17
T25 ← T17
T26 ← T01–T25
```

## Paralelización posible

Estas tareas pueden ejecutarse en paralelo (no se bloquean entre sí):

- `T01 + T16` — primer día
- `T06 + T10 + T11 + T13` — después de T01 y T02
- `T07 + T08` — después de T05
- `T09 + T10` — T09 después de T08; T10 después de T01+T02
- `T17 + T18 + T20 + T21 + T24 + T25` — después de T16
- `T22 + T23` — después de T17 + T15
