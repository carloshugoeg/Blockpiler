# CompileFlow — Documento de Proyecto Final

> Curso: Compiladores · Proyecto académico  
> Stack: Python 3.11+ · Flask · Google Blockly · Monaco Editor  
> Timeline: 3 semanas  
> Versión: 1.0 (para aprobación)

---

## Tabla de contenidos

1. Visión y alcance
2. Lenguaje soportado
3. Pipeline del compilador
4. Biblioteca de optimizaciones
5. Manejo de excepciones y robustez
6. Suite de tests
7. Frontend — modos y funcionalidades
8. Conversión bidireccional seamless
9. Funcionalidades extra
10. Formatos de archivo — save/load
11. Stack tecnológico
12. Estructura de archivos
13. Timeline de 3 semanas
14. Programas de demostración

---

## 1. Visión y alcance

CompileFlow integra un compilador de un subconjunto de C con dos modos de trabajo sincronizados en tiempo real:

**Modo Bloques:** canvas interactivo estilo Scratch (Google Blockly) donde el usuario construye programas arrastrando bloques con semántica de tipo estricta — un bloque booleano no puede conectarse donde se espera un entero.

**Modo IDE:** editor de texto (Monaco Editor — el engine de VS Code) con syntax highlighting, live error detection con debounce, autocompletado basado en análisis semántico, y hover tooltips con información de la tabla de símbolos en vivo.

Ambos modos comparten el mismo AST como representación intermedia. La conversión entre ellos es bidireccional y ocurre en tiempo real. El programa compila a ARM64 Assembly, ensambla con `as`/`gcc`, y ejecuta el binario nativo. Un intérprete del AST en Python maneja el modo debug paso a paso.

El sistema está diseñado para resistir uso adversarial: entradas malformadas, programas semánticamente inválidos, archivos corruptos, y ataques deliberados de un evaluador que intenta romper el compilador.

---

## 2. Lenguaje soportado

### Gramática (BNF)

```
program         → (declaration | function_decl)*

declaration     → type IDENT ('=' expression)? ';'
                | type IDENT '[' INT_LIT ']' ('=' '{' expr_list '}')? ';'

function_decl   → type IDENT '(' param_list ')' block

param_list      → (type IDENT (',' type IDENT)*)?

block           → '{' statement* '}'

statement       → if_stmt | while_stmt | for_stmt | dowhile_stmt
                | return_stmt | break_stmt | continue_stmt
                | print_stmt | println_stmt | declaration
                | expression ';' | block

if_stmt         → 'if' '(' expression ')' block
                  ('else' 'if' '(' expression ')' block)*
                  ('else' block)?

while_stmt      → 'while' '(' expression ')' block
for_stmt        → 'for' '(' (declaration | expression ';') expression ';' expression ')' block
dowhile_stmt    → 'do' block 'while' '(' expression ')' ';'

expression      → assignment
assignment      → IDENT ('=' | '+=' | '-=' | '*=' | '/=' | '%=') assignment
                | logical_or
logical_or      → logical_and ('||' logical_and)*
logical_and     → equality ('&&' equality)*
equality        → relational (('==' | '!=') relational)*
relational      → additive (('<' | '>' | '<=' | '>=') additive)*
additive        → multiplicative (('+' | '-') multiplicative)*
multiplicative  → unary (('*' | '/' | '%') unary)*
unary           → ('!' | '-' | '++' | '--') unary | postfix
postfix         → primary ('++' | '--')?
primary         → INT_LIT | FLOAT_LIT | STRING_LIT | CHAR_LIT | BOOL_LIT
                | IDENT | IDENT '[' expression ']'
                | IDENT '(' arg_list ')'
                | '(' expression ')' | 'input' '('  ')'

type            → 'int' | 'float' | 'char' | 'bool' | 'void' | 'string'
```

### Tipos y coerciones

| Tipo | Representación | ARM64 |
|---|---|---|
| `int` | entero 64-bit con signo | registros `x`, 8 bytes |
| `float` | IEEE 754 double | registros `d` |
| `char` | entero 8-bit | byte en memoria |
| `bool` | 0 o 1 | byte en memoria |
| `string` | puntero a buffer null-terminated | registro `x` (puntero) |
| `void` | sin valor | N/A |

Coerciones implícitas permitidas: `int→float`, `char→int`, `bool→int`. Con warning: `float→int`, `int→bool`, `int→char`. Son error: cualquier tipo a `string` sin cast, `void` en expresiones, tipos incompatibles en operadores binarios.

### Tabla de símbolos

```python
@dataclass
class Symbol:
    name: str
    type: CType
    kind: Literal['variable', 'parameter', 'function']
    scope_level: int
    line_declared: int
    column_declared: int
    initial_value: Any | None
    use_count: int = 0
    is_initialized: bool = False
    is_mutated: bool = False
```

Stack de diccionarios (uno por scope). Push al entrar a un bloque, pop al salir.

---

## 3. Pipeline del compilador

### Lexer (`lexer.py`)

Produce tokens con tipo, valor, línea y columna. Nunca aborta — emite token `ERROR` y continúa. Tokens reconocidos: keywords, builtins (`print`, `println`, `input`), identificadores, literales de todos los tipos, operadores, delimitadores.

Errores definidos:

- `LEX001` Caracter ilegal
- `LEX002` String literal no cerrado
- `LEX003` Char literal vacío o multi-caracter
- `LEX004` Comentario de bloque no cerrado
- `LEX005` Número mal formado
- `LEX006` Identificador > 255 caracteres
- `LEX007` Secuencia de escape inválida
- `LEX008` String literal > 4096 caracteres
- `LEX009` Input no es texto UTF-8 válido

### Parser (`parser.py`)

Recursive descent (LL(1)). Construye AST con dataclasses tipados, cada nodo con `line` y `col`. Panic mode recovery: al encontrar error, avanza al próximo `;`, `}` o `{` y sigue parseando para reportar múltiples errores.

Nodos del AST:

```
Program, FunctionDecl, VarDecl, ArrayDecl, Parameter
Block, IfStmt, WhileStmt, ForStmt, DoWhileStmt
ReturnStmt, BreakStmt, ContinueStmt, PrintStmt, ExprStmt
BinaryOp, UnaryOp, AssignOp, CallExpr, IndexExpr
Identifier, IntLiteral, FloatLiteral, StringLiteral, CharLiteral, BoolLiteral
InputExpr, CastExpr
```

Errores definidos: PAR001 (token inesperado) hasta PAR010 (demasiados argumentos), incluyendo: llave sin cerrar, `else` suelto, `break`/`continue` fuera de loop, `return` con valor en `void`, función dentro de función, anidamiento > 255 niveles.

### Análisis Semántico (`semantic.py`)

Checks de declaración y scope: SEM001-SEM006 (variable no declarada, doble declaración, uso sin inicializar, declaración sin uso, función no declarada, función doble).

Checks de tipos: SEM010-SEM016 (incompatibilidad en asignación, en operadores, condición no-booleana, división por cero estática, overflow de literal, índice fuera de rango estático, tipo de retorno incorrecto).

Checks de funciones: SEM020-SEM024 (argumentos incorrectos, tipo de argumento, función sin return en todos los paths, código inalcanzable, recursión sin base case).

Checks de arrays: SEM030-SEM035 (acceso en no-array, tamaño 0/negativo/excesivo, lista de init más larga).

### Optimizador (`optimizer.py`)

Ver sección 4 — múltiples passes hasta punto fijo, máximo 20 iteraciones.

### Generador ARM64 (`codegen.py`)

Convención AArch64 ABI completa: argumentos en `x0-x7`/`d0-d7`, retorno en `x0`/`d0`, callee-saved `x19-x28`, frame pointer `x29`, link register `x30`. Stack frames con `stp x29, x30` al inicio y `ldp x29, x30` al final. Labels únicos por función + contador + hash. Emite `; src:LINE:COL` antes de cada grupo para el mapa de sincronización IDE↔ASM. Guards de runtime para división por cero y array out of bounds.

### Ensamblado y ejecución

```
.s → as -o output.o output.s → ld/gcc -o output output.o → ./output
```

Timeout de 10s en ejecución, stdout limitado a 1MB. Stderr del ensamblador se captura y muestra con contexto. QEMU user-mode para emular ARM64 en x86.

---

## 4. Biblioteca de optimizaciones

El optimizador hace múltiples passes sobre el AST hasta punto fijo (máximo 20 passes).

### 4.1 Constant Folding

Evalúa en compilación expresiones con solo literales. Cubre aritmética, comparaciones, lógica, strings. No pliega divisiones donde el divisor podría ser cero, ni operaciones `float` que producirían NaN/Inf, ni expresiones con side effects.

### 4.2 Constant Propagation

Variables declaradas con un literal y nunca mutadas se reemplazan por su valor en todos los usos. Condición: no es parámetro, no es target de ningún `AssignOp` o `++`/`--`.

### 4.3 Dead Code Elimination

Elimina código después de `return`/`break`/`continue`, ramas de `if` con condición constante (true/false), y variables declaradas que nunca se leen.

### 4.4 Algebraic Simplification

```
x + 0 → x       x * 1 → x       x * 0 → 0 (si x es puro)
x - 0 → x       x / 1 → x       x - x → 0 (si x es puro)
x || true → true    x && false → false
x || false → x      x && true → x
!!x → x
```

### 4.5 Strength Reduction

```
x * 2  → x << 1    x / 2  → x >> 1 (int positivos)
x * 4  → x << 2    x / 4  → x >> 2
x * 8  → x << 3    x % 2  → x & 1
x % 4  → x & 3
```

### 4.6 Loop Invariant Code Motion (LICM)

Expresiones sin side effects donde ninguna variable usada se asigna dentro del loop se mueven fuera del cuerpo.

### 4.7 Common Subexpression Elimination (CSE)

Subexpresiones idénticas dentro de un bloque se calculan una vez y se referencian. Genera variables temporales `_cse_N`.

### 4.8 Inlining de funciones pequeñas

Funciones con cuerpo de un solo `return` con expresión y ≤ 5 nodos en el AST se inlinean en el call site.

### 4.9 Tail Call Optimization (TCO)

Llamadas recursivas en tail position se transforman en loops. Solo aplica cuando la llamada recursiva es la última operación sin operaciones pendientes sobre el retorno.

### 4.10 Array Access Optimization

Accesos con índice constante pre-calculan el offset en compilación.

### 4.11 Short-Circuit Evaluation

`&&` y `||` siempre usan short-circuit en el código ARM64 generado.

### 4.12 Peephole Optimization

Sobre el ASM generado: elimina `mov x0, x0`, branches a la siguiente línea, pares `str`/`ldr` redundantes, y fusiona `add` consecutivos con offsets constantes.

---

## 5. Manejo de excepciones y robustez

### Principios generales

**Fail loudly, recover gracefully:** Nunca silenciar un error. Acumular todos los errores de cada etapa antes de reportar. Abortar solo si se superan 50 errores (configurable). Nunca crash silencioso — toda excepción Python no manejada tiene un handler global que retorna JSON de error con mensaje descriptivo.

**Estado inmutable:** Las operaciones destructivas (compilar, convertir) operan sobre copias. Si fallan, el estado del editor queda intacto.

### Casos de error por componente

**Lexer:** input binario, strings gigantes (> 4096), identificadores largos (> 255), comentarios no cerrados, input no-UTF8, input vacío (retorna stream vacío — no es error).

**Parser:** llaves sin cerrar (lista todas al llegar a EOF), `else` suelto, punto y coma faltante (sugiere dónde), función dentro de función, anidamiento > 255 niveles (previene stack overflow), 1000+ argumentos.

**Semántico:** recursión mutua soportada (forward declarations implícitas), recursión sin base case (warning, compila), array tamaño 0/negativo/> 65535, división por cero en runtime (guard en el código generado), index out of bounds en runtime (guard en el código generado).

**Validación de requests del backend:**

```python
class CompileRequest(BaseModel):
    source: str = Field(..., max_length=524288)      # 512KB
    mode: Literal['compile', 'check', 'debug']
    optimization_level: int = Field(default=1, ge=0, le=3)

class BlocksRequest(BaseModel):
    workspace_json: str = Field(..., max_length=2097152)  # 2MB
    direction: Literal['to_c', 'to_blocks']
```

### Casos de "intentional break" anticipados

| Ataque | Respuesta del sistema |
|---|---|
| Comentario `/*` sin cerrar | Error LEX004 con posición exacta |
| String con newline literal | Error LEX002 con posición exacta |
| Recursión infinita | Compila con warning; intérprete detiene en 500 niveles; binario: SIGSEGV capturado |
| `int x = 1/0;` estático | Error SEM013 antes de generar código |
| `arr[-1]` literal | Error SEM015 con el índice y el rango válido |
| `int x = "hello";` | Error SEM010 con tipos esperado y recibido |
| `break` fuera de loop | Error PAR007 |
| `return` sin cubrir todos los paths | Error SEM022 con el path no cubierto |
| Workspace Blockly JSON corrupto | `json.JSONDecodeError` capturado antes del parser de bloques |
| Función con 1000 parámetros | Error PAR010 |
| `int print = 5;` | Error SEM002 — conflicto con builtin |
| `5 = x;` | Error PAR: target de asignación no es lvalue |
| Input de 600KB | Rechazado por validación (máx 512KB) antes de llegar al lexer |
| Archivo binario subido como `.c` | Detectado por magic bytes, rechazado con mensaje claro |

### Robustez del intérprete (modo debug)

- Recursión máxima: 500 niveles → `RuntimeError` con call stack completo
- Iteraciones máximas de loop: 1,000,000 → pausa y pregunta al usuario
- Timeout global: 30 segundos
- Variables no inicializadas: valor centinela `NullValue` → cualquier operación sobre él genera `RuntimeError: variable 'x' usada sin inicializar`

---

## 6. Suite de tests

### Unit tests (`tests/unit/`)

**`test_lexer.py`** (~80 casos): cada tipo de token, combinaciones, strings con escapes, números en todas las bases, todos los errores LEX001-LEX009, input vacío, input de un caracter, solo comentarios.

**`test_parser.py`** (~100 casos): cada statement, precedencia y asociatividad de expresiones, anidamiento, funciones, todos los errores PAR001-PAR010, panic mode recovery.

**`test_semantic.py`** (~120 casos): todos los checks SEM001-SEM035, scoping correcto, cobertura de paths en if-else, recursión, coerciones.

**`test_optimizer.py`** (~80 casos): cada optimización individualmente. Invariante: el programa optimizado produce el mismo output que el original para todos los casos.

**`test_codegen.py`** (~60 casos): instrucciones ARM64 por tipo de nodo, convención de llamada, labels únicos, stack frames.

### Integration tests (`tests/integration/`)

End-to-end: código C → pipeline completo → ejecutar binario → verificar stdout:

```python
def test_fibonacci():
    result = compile_and_run("int fib(int n) { ... } int main() { println(fib(10)); return 0; }")
    assert result.stdout == "55\n"
    assert result.returncode == 0
```

### Robustness tests (`tests/robustness/`)

~30 casos de inputs malformados. Invariante: el compilador nunca hace crash — siempre retorna errores descriptivos:

```python
@pytest.mark.parametrize("bad_input", [
    "",  "\x00\x01", "a"*600000, "/* sin cerrar",
    "{{{{" + "}"*3, "int " + "f("*1000,
    "int 123abc = 5;", "int x = 1/0;",
])
def test_does_not_crash(bad_input):
    result = compile_safe(bad_input)
    assert result.errors is not None and len(result.errors) > 0
    assert result.exception is None
```

### Roundtrip tests (`tests/roundtrip/`)

Verifican que `C → AST → Bloques → AST → C` produce código funcionalmente equivalente (mismo stdout para los 8 programas de la galería).

### API tests (`tests/api/`)

Cada endpoint con input válido (200) e inválido (400), requests de 2MB (413), 10 compilaciones concurrentes.

---

## 7. Frontend — modos y funcionalidades

### Modo Bloques (Google Blockly)

Categorías de bloques: Control (if/else, for, while, do-while, break, continue, return), Variables (declarar, leer, asignar, incr/decr), Operaciones (binario, unario, cast), I/O (print, println, input), Funciones (definir, llamar), Arrays (declarar, leer, escribir), Literales.

Tipado visual: los conectores tienen formas distintas por tipo. Un bloque booleano tiene conector hexagonal; un bloque entero tiene conector redondeado. Tipos incompatibles no conectan — type checking visual.

Características: undo/redo (Ctrl+Z), papelera de reciclaje, minimap, zoom/pan, snap to grid opcional, bloques erróneos marcados con borde rojo, tooltip por bloque con descripción y código C equivalente, exportar como PNG.

### Modo IDE (Monaco Editor)

**Syntax highlighting:** keywords de control (naranja), tipos (azul), builtins (verde), strings (rojo), comentarios (gris), números (cyan).

**Live error detection** (debounce 300ms): errores del lexer/parser como subrayados rojos, warnings semánticos en amarillo, errores de tipo en naranja. Panel "Problemas" con lista navegable.

**Autocompletado:** keywords/tipos con docs inline, variables en scope con tipo y línea, funciones con firma completa, snippets expandibles con Tab (`for`, `if`, `while`, `fn`).

**Signature help:** al abrir paréntesis de una función, muestra firma con tipos y resalta el parámetro actual.

**Hover tooltips:** variable (tipo, scope, línea, use count), función (firma, retorno, call count), operadores y keywords (descripción + ejemplo).

**Comandos:**

- `Ctrl+Enter` — Ejecutar
- `Ctrl+D` — Debug (abrir intérprete)
- `Ctrl+Shift+F` — Formatear código
- `Ctrl+Shift+B` — Sync al canvas de bloques
- `Ctrl+/` — Toggle comentario de línea
- `F2` — Rename symbol (en todos sus usos)

---

## 8. Conversión bidireccional seamless

El AST es la representación intermedia compartida:

```
Bloques Blockly ──blocks_to_ast──► AST ──ast_to_c──► Código C en IDE
Código C en IDE ──lex+parse ──────► AST ──ast_to_blocks──► Bloques Blockly
```

### ast_to_blocks.py

Recorrido post-order del AST. Cada nodo emite un objeto de bloque Blockly con IDs únicos y estructura anidada. Es la dirección más compleja — requiere reconstruir la jerarquía y los tipos de los inputs de Blockly.

### Sincronización en tiempo real

```javascript
class SyncManager {
    onIDEChange(newCode) {
        if (!this.syncEnabled) return;
        clearTimeout(this.pendingSync);
        this.pendingSync = setTimeout(async () => {
            this.syncEnabled = false;
            try {
                const blocks = await api.codeToBlocks(newCode);
                await this.canvas.loadWithTransition(blocks);  // fade 200ms
            } finally { this.syncEnabled = true; }
        }, 600);
    }
    // espejo para onCanvasChange
}
```

El flag `syncEnabled` previene recursión: actualizar el IDE no dispara una actualización del canvas, y viceversa.

---

## 9. Funcionalidades extra

### 9.1 Visualizador del AST interactivo

Panel lateral colapsable con árbol D3.js. Color por tipo: statements (azul), expresiones (verde), declaraciones (morado), literales (gris). Clic en nodo → resalta línea en Monaco y bloque en Blockly. Cursor en Monaco → nodo correspondiente se resalta en el árbol. Botones: expandir todo, colapsar todo, centrar en nodo activo. Hover muestra tipo, línea, columna, tipo inferido.

### 9.2 Vista split C ↔ ASM sincronizada

Divide el panel IDE: C a la izquierda, ARM64 a la derecha. El generador emite `; src:LINE:COL` en el ASM. Al posicionar cursor en una línea de C → instrucciones ASM correspondientes se resaltan en verde. Clic en instrucción ASM → scroll a la línea de C. Botones: copiar ASM, descargar `.s`. Tooltips pedagógicos en cada instrucción (diccionario de ~60 instrucciones ARM64 con explicación en español).

### 9.3 Modo "Explain code"

Botón que recorre el AST semántico y genera una explicación en español por función y por statement. Usa un `CodeExplainer` class que hace pretty-print semántico del árbol. La explicación se muestra en modal y puede exportarse como comentarios dentro del código.

### 9.4 Estimador de complejidad Big-O

Badge en la barra de estado. Analiza anidamiento de loops y patrones de recursión en el AST:

- Sin loops → O(1)
- Un loop → O(n)
- Loops anidados → O(n²), O(n³), etc.
- Recursión doble (fibonacci) → O(2^n)
- Recursión lineal con TCO → O(n)

### 9.5 Compartir por URL

Estado completo serializado en base64 en el query param `?p=`. Incluye: modo activo, código C, workspace de Blockly, tema. Al cargar, se parsea y valida el schema (versión + estructura) antes de restaurar. Errores de decodificación se muestran al usuario sin crashear la app.

### 9.6 Galería de ejemplos precargados

8 programas en archivos `.cfproj` estáticos (JSON). Barra de búsqueda y filtros por concepto. Cada ejemplo carga simultáneamente código C y bloques.

| Programa | Conceptos |
|---|---|
| Fibonacci iterativo | for, variables, aritmética |
| Factorial recursivo | funciones, recursión, if/else |
| Bubble sort | arrays, loops anidados — O(n²) |
| Búsqueda binaria | while, arrays — O(log n) |
| Collatz conjecture | while, divisibilidad |
| Calculadora | if/else if encadenado |
| Contador de vocales | for, char, condiciones |
| Suma acumulativa | for, arrays, acumuladores |

---

## 10. Formatos de archivo — save/load

### Guardar

| Formato | Extensión | Contenido |
|---|---|---|
| Proyecto completo | `.cfproj` | JSON: código C + workspace Blockly + metadatos + settings |
| Código C | `.c` | Solo el código del IDE |
| Assembly ARM64 | `.s` | El ASM generado |
| Workspace Blockly | `.scratch` | JSON del workspace de Blockly |
| Imagen del canvas | `.png` | Captura del workspace |

Formato `.cfproj`:

```json
{
    "version": "1.0",
    "name": "Mi programa",
    "created": "ISO8601",
    "modified": "ISO8601",
    "ide": { "code": "...", "cursorLine": 5, "cursorCol": 10 },
    "blocks": { "workspace": {} },
    "settings": { "theme": "dark", "optimizationLevel": 1 }
}
```

### Cargar — validación por tipo

**`.c`:** Validar UTF-8 → intentar parsear → si hay features no soportadas, listar líneas problemáticas y ofrecer cargar igualmente.

**`.s`/`.asm`:** Validar UTF-8 → mostrar en panel ASM (read-only). No se "descompila" a C — botón compilar deshabilitado con nota explicativa.

**`.scratch` (JSON de Blockly):** Validar JSON → verificar schema de workspace → listar tipos de bloque no reconocidos → si hay bloques desconocidos, preguntar al usuario antes de cargar → `Blockly.serialization.workspaces.load()` → disparar conversión automática a C.

**`.cfproj`:** Validar JSON y versión → carga completa (IDE + canvas + settings) → si versión incompatible, migración best-effort con warning de datos perdidos.

**Rechazos:** archivo binario (detectado por magic bytes), JSON inválido (posición del error), archivo > 512KB, archivo con líneas > 10,000 (warning + truncación visible).

### Autoguardado

Cada 30 segundos y al cerrar la pestaña en `localStorage`. Al reabrir, se ofrece restaurar. Guarda las últimas 5 versiones.

---

## 11. Stack tecnológico

### Backend

| Componente | Tecnología | Justificación |
|---|---|---|
| Lenguaje | Python 3.11+ | Requerido por el curso |
| Lexer/Parser | Implementación manual | Control total, mejor manejo de errores |
| API | Flask 3.x | Ligero, suficiente para el scope |
| WebSocket | flask-socketio 5.x | Debugger en tiempo real |
| Validación | pydantic 2.x | Validación de requests |
| Tests | pytest + pytest-cov | Estándar del ecosistema |
| Ensamblado | `as` + `ld`/`gcc` | ARM64 nativo |
| Emulación | QEMU user-mode | ARM64 en máquinas x86 |

### Frontend

| Componente | Tecnología | Justificación |
|---|---|---|
| Editor de código | Monaco Editor 0.45+ | Engine de VS Code. API de lenguajes completa. |
| Canvas de bloques | Google Blockly 10.x | Motor de Scratch 3.0. Maduro, extensible. |
| Visualizador AST | D3.js 7.x | Estándar para layouts de árbol |
| Framework base | Vanilla JS + CSS | Sin overhead, control total |
| Build | Vite | Bundling moderno de módulos ES |

### Argumentos ante "usaste librerías"

Blockly provee el rendering de bloques. No provee el compilador, el generador ARM64, la conversión bidireccional, ni el debugger. Es análogo a usar `matplotlib` en machine learning. El trabajo intelectual está en lo que se construye encima.

Monaco provee un textarea avanzado. El language server, el autocompletado basado en el AST, los hover tooltips con la tabla de símbolos en vivo, y la sincronización son implementación propia.

---

## 12. Estructura de archivos

```
compileflow/
│
├── compiler/
│   ├── lexer.py
│   ├── parser.py
│   ├── ast_nodes.py
│   ├── semantic.py
│   ├── optimizer.py          # todos los passes
│   ├── codegen.py            # ARM64 con mapa de líneas
│   ├── interpreter.py        # para el debugger
│   ├── error_reporter.py
│   ├── ast_to_blocks.py
│   ├── blocks_to_ast.py
│   ├── ast_to_c.py
│   └── explainer.py
│
├── server/
│   ├── app.py
│   ├── routes/
│   │   ├── compile.py        # POST /api/compile
│   │   ├── check.py          # POST /api/check
│   │   ├── convert.py        # POST /api/convert
│   │   ├── debug.py          # WebSocket /ws/debug
│   │   └── files.py          # POST /api/validate-file
│   ├── executor.py
│   └── validators.py
│
├── frontend/
│   ├── index.html
│   ├── src/
│   │   ├── main.js
│   │   ├── ide/
│   │   │   ├── editor.js
│   │   │   ├── language.js
│   │   │   ├── completions.js
│   │   │   ├── diagnostics.js
│   │   │   └── commands.js
│   │   ├── blocks/
│   │   │   ├── workspace.js
│   │   │   ├── blocks_def.js
│   │   │   ├── toolbox.js
│   │   │   └── theme.js
│   │   └── features/
│   │       ├── sync.js
│   │       ├── debugger.js
│   │       ├── ast_viewer.js
│   │       ├── asm_panel.js
│   │       ├── explainer.js
│   │       ├── gallery.js
│   │       ├── share.js
│   │       └── file_io.js
│   └── public/
│       ├── examples/         # .cfproj estáticos
│       └── arm64_docs.json
│
├── tests/
│   ├── unit/
│   │   ├── test_lexer.py
│   │   ├── test_parser.py
│   │   ├── test_semantic.py
│   │   ├── test_optimizer.py
│   │   └── test_codegen.py
│   ├── integration/
│   │   ├── test_pipeline.py
│   │   └── test_api.py
│   ├── robustness/
│   │   ├── test_bad_inputs.py
│   │   └── test_stress.py
│   ├── roundtrip/
│   │   └── test_roundtrip.py
│   └── interpreter/
│       └── test_interpreter.py
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 13. Timeline de 3 semanas

### Semana 1 — compilador core

| Días | Entregable | Criterio de éxito |
|---|---|---|
| 1-2 | Lexer + error reporter | `test_lexer.py` 100% |
| 3-4 | Parser + todos los nodos AST | `test_parser.py` 100% |
| 5 | Análisis semántico + tabla de símbolos | `test_semantic.py` 100% |
| 6 | `blocks_to_ast.py` + `ast_to_c.py` | Roundtrip básico pasa |
| 7 | Buffer / deuda técnica | — |

### Semana 2 — optimizador, ARM64 y frontend base

| Días | Entregable | Criterio de éxito |
|---|---|---|
| 1 | Optimizer: constant folding/propagation/dead code | test_optimizer.py parcial |
| 2 | Optimizer: LICM, CSE, strength reduction, peephole | test_optimizer.py 100% |
| 3-4 | Generador ARM64 completo | Fibonacci compila y corre |
| 5 | API Flask: todos los endpoints | test_api.py básico |
| 6 | Frontend: Monaco + Blockly en la misma página | Demo manual funciona |
| 7 | Buffer | — |

### Semana 3 — bidireccional, debugger y features

| Días | Entregable | Criterio de éxito |
|---|---|---|
| 1-2 | `ast_to_blocks.py` + sync en tiempo real | test_roundtrip.py completo |
| 3 | Autocompletado + live errors en Monaco | Demo manual |
| 4 | Debugger: intérprete + WebSocket + highlight | test_interpreter.py + demo |
| 5 | AST viewer, split C↔ASM, explain code, Big-O | Demo manual |
| 6 | Save/load, galería, share URL | Demo manual |
| 7 | Polish: temas, test_robustness.py, slides | test_robustness.py 100% |

### Prioridades de corte si el tiempo aprieta

En orden — lo primero se corta primero:

1. `do-while`, `break`/`continue`
2. Estimador de Big-O
3. Modo "Explain code"
4. Debugger visual (dejar el intérprete sin la UI paso a paso)
5. `ast_to_blocks.py` (mantener solo bloques → C)

Lo que **nunca** se corta: pipeline completo, generación ARM64, Monaco con live errors, Blockly funcional, API Flask, save/load de archivos, suite de tests de robustez.

---

## 14. Programas de demostración

### Demo 1 — Fibonacci iterativo

Demuestra `for`, múltiples variables, aritmética, `println`, funciones.  
Secuencia: mostrar en bloques → sync → aparece código C → ejecutar → mostrar ASM con tooltips → badge Big-O: O(n).

### Demo 2 — Factorial recursivo

Demuestra funciones, recursión, `if/else`, `return`.  
Secuencia: escribir en IDE → sync → bloques aparecen → debug paso a paso → el call stack crece y decrece visualmente.

### Demo 3 — Bubble sort

Demuestra arrays, loops anidados, swap.  
Secuencia: cargar desde galería → ejecutar → badge Big-O: O(n²) → vista split C ↔ ASM sincronizada.

### Demo 4 — Demostración de robustez

Input con múltiples errores simultáneos: variable no declarada, división por cero estática, `break` fuera de loop, tipo incompatible en asignación.  
Objetivo: mostrar que el sistema reporta todos los errores simultáneamente con posición exacta y sugerencias, sin crash, sin mensajes genéricos.
