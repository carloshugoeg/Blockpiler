# CompileFlow QA Issues

Fecha de revision: 2026-05-14  
Alcance: pruebas manuales reales en la app local (`Flask` + `Vite`), mas una segunda pasada estatica/API sobre rutas, sincronizacion, imports/exports, debugger, share y paneles.

No se reparo nada durante esta revision.

## Resumen Ejecutivo

La app tiene varios problemas criticos en la integracion frontend-backend:

- El boton **Compilar** puede decir "Compilacion exitosa" aunque el ensamblado/linking falle.
- La sincronizacion Blockly <-> IDE puede transformar el lenguaje CompileFlow en C con `#include`/`printf`, corrompiendo el source del usuario.
- Blockly no carga correctamente programas comunes con variables o parametros.
- Import/export esta incompleto para `.s`, Blockly/Scratch, Mermaid y PNG.
- El debugger funciona parcialmente, pero oculta errores y no muestra stdout.
- Algunos endpoints devuelven errores con formatos inconsistentes o incluso HTTP 500 en entradas de usuario razonables.

## Issues

### CF-QA-001 - Compilar reporta exito aunque el ensamblado falla

**Severidad:** Critica  
**Area:** API compile, UI compile, codegen/executor

**Reproduccion:**

1. Abrir la app.
2. Ir a **Codigo**.
3. Escribir:

```c
int main() {
  println(42);
  return 0;
}
```

4. Presionar **Compilar**.

**Resultado actual:**

La consola de la UI muestra:

```text
Compilacion exitosa. Paneles AST, Ensamblador y Explicacion actualizados.
```

Pero la API trae `returncode: -1` y `stderr` con error de linker:

```text
Undefined symbols for architecture arm64:
  ".Lfmt_int_nl"
```

**Resultado esperado:**

Si el assembler/linker falla, la compilacion no debe reportarse como exitosa. Debe mostrarse el error de ensamblado/linking.

**Root cause probable:**

- `server/routes/compile.py` devuelve `ok: true` aunque `Executor().assemble_and_run(...)` falle.
- `frontend/main.js` solo revisa `data.ok`, no `data.data.returncode`, `stderr`, `timed_out` ni `error`.

**Referencias:**

- `server/routes/compile.py`
- `frontend/main.js`
- `compiler/executor.py`

**Posible solucion:**

Si `ExecutionResult.error` existe, `returncode == -1` o `timed_out == true`, responder `ok: false` o incluir un estado explicito que la UI trate como fallo.

---

### CF-QA-002 - Codegen no emite labels estandar de formato (`.Lfmt_*`)

**Severidad:** Critica  
**Area:** ARM64 codegen

**Reproduccion:**

Compilar cualquier programa que use `print`, `println`, `input_int` o `input_float`.

```c
int main() {
  println(1);
  return 0;
}
```

**Resultado actual:**

El assembly referencia `.Lfmt_int_nl`, `.Lfmt_str_nl`, `.Lfmt_float`, etc., pero esos labels no aparecen en `.rodata`; el linker falla.

**Resultado esperado:**

El assembly debe incluir todos los format strings requeridos por `printf`/`scanf`.

**Root cause probable:**

`compiler/codegen.py` define `_add_standard_rodata(gen)`, pero no se llama desde `CodeGenerator.generate()` ni desde `_build_output()`. Ademas `_emit_rodata_section()` esta vacio.

**Referencias:**

- `compiler/codegen.py`

**Posible solucion:**

Llamar `_add_standard_rodata(self)` antes de `_build_output()`, o integrar esos labels al inicializar `_rodata`.

---

### CF-QA-003 - `Ejecutar` y `Compilar` no prueban lo mismo

**Severidad:** Alta  
**Area:** UX, runtime

**Reproduccion:**

1. Escribir:

```c
int main() {
  println(42);
  return 0;
}
```

2. Presionar **Ejecutar**.
3. Presionar **Compilar**.

**Resultado actual:**

- **Ejecutar** imprime `42`.
- **Compilar** puede fallar en ARM64/linking, pero aun asi reportar exito por CF-QA-001.

**Resultado esperado:**

La UI debe dejar claro si esta interpretando o compilando/ejecutando assembly real. Si se llama "Ejecutar", un usuario esperaria que use el mismo pipeline del compilador o que diga "Interpretar".

**Root cause probable:**

`frontend/main.js` usa `/api/run` para **Ejecutar**, que ejecuta el `Interpreter`, mientras **Compilar** usa `/api/compile`, que genera ARM64 y usa `Executor`.

**Referencias:**

- `frontend/main.js`
- `server/routes/run.py`
- `server/routes/compile.py`

**Posible solucion:**

Renombrar el boton a **Interpretar**, o agregar dos acciones separadas: "Interpretar" y "Compilar + ejecutar binario".

---

### CF-QA-004 - Sync Blockly -> IDE corrompe source CompileFlow a C

**Severidad:** Critica  
**Area:** Sync, conversiones, IDE

**Reproduccion:**

1. Escribir:

```c
int main() {
  println(7);
  return 0;
}
```

2. Cambiar a Blockly, cargar desde Galeria o usar Compartir.

**Resultado actual:**

El editor cambia a C generado:

```c
#include <stdio.h>
#include <string.h>

int main() {
    printf("%s\n", 7);
    return 0;
}
```

**Resultado esperado:**

El IDE debe conservar lenguaje CompileFlow, no C con includes/libc.

**Root cause probable:**

`/api/convert` con `direction="blocks_to_c"` usa `ASTtoC().generate(program)`. Ese generador produce C real, no source CompileFlow.

**Referencias:**

- `server/routes/convert.py`
- `compiler/ast_to_c.py`
- `frontend/features/sync.js`

**Posible solucion:**

Crear un pretty-printer CompileFlow separado para Blockly -> IDE, o cambiar `ASTtoC` para no usarse en sincronizacion interactiva.

---

### CF-QA-005 - `ASTtoC` genera `printf("%s", int)` para cualquier tipo

**Severidad:** Alta  
**Area:** AST to C, sync

**Reproduccion:**

Roundtrip de:

```c
int main() {
  println(42);
  return 0;
}
```

**Resultado actual:**

Genera:

```c
printf("%s\n", 42);
```

**Resultado esperado:**

Para int deberia ser `%d`/`%ld`, para float `%g`/`%f`, para string `%s`, etc.

**Root cause probable:**

En `_visit_print_stmt`, `fmt = '%s'` esta hardcodeado.

**Referencias:**

- `compiler/ast_to_c.py`

**Posible solucion:**

Usar `node.expr.inferred_type`, o hacer un generador de CompileFlow para la UI y dejar `ASTtoC` como generador C correcto.

---

### CF-QA-006 - Blockly falla cargando programas con variables locales

**Severidad:** Alta  
**Area:** Blockly serialization, AST to blocks

**Reproduccion:**

1. Escribir:

```c
int main() {
  int i = 1;
  while (i <= 3) {
    println(i);
    i = i + 1;
  }
  return 0;
}
```

2. Cambiar a Blockly o abrir Flowchart mientras sync esta activo.

**Resultado actual:**

Consola del browser:

```text
MissingConnection: The block "c_var_decl" block (...) is missing a(n) output connection
```

**Resultado esperado:**

Blockly debe cargar los bloques sin excepciones.

**Root cause probable:**

La estructura serializada por `ASTtoBlocks` conecta un bloque statement (`c_var_decl`) en una posicion que Blockly interpreta como `input_value`, o hay mismatch entre `input_statement`/`input_value` en bloques anidados.

**Referencias:**

- `compiler/ast_to_blocks.py`
- `frontend/blocks/blockly_setup.js`
- `frontend/features/sync.js`

**Posible solucion:**

Validar el JSON de `ASTtoBlocks` contra las conexiones declaradas en `blockly_setup.js`. Asegurar que statements se conecten solo por `next` o `input_statement`.

---

### CF-QA-007 - Blockly falla cargando funciones con parametros

**Severidad:** Alta  
**Area:** Blockly function blocks

**Reproduccion:**

1. Abrir **Galeria**.
2. Cargar **Fibonacci (recursivo)**.

**Resultado actual:**

Consola del browser:

```text
MissingConnection: The block "c_param" block (...) is missing a(n) output connection
```

**Resultado esperado:**

Los parametros deben aparecer correctamente en el bloque de funcion.

**Root cause probable:**

`c_func_decl` define `PARAMS` como `input_value`, pero `c_param` esta definido como statement con `previousStatement`/`nextStatement`, no como bloque con `output`.

**Referencias:**

- `frontend/blocks/blockly_setup.js`
- `compiler/ast_to_blocks.py`

**Posible solucion:**

Hacer `c_param` un bloque con `output` compatible con `PARAMS`, o cambiar `PARAMS` a `input_statement`/modelo de lista.

---

### CF-QA-008 - Galeria puede dejar el editor vacio o convertido a C

**Severidad:** Alta  
**Area:** Gallery, sync

**Reproduccion:**

1. Abrir app.
2. Abrir **Galeria**.
3. Cargar **FizzBuzz** o **Fibonacci**.

**Resultado actual:**

El editor puede quedar solo con:

```c
#include <stdio.h>
#include <string.h>
```

o con C generado corrupto.

**Resultado esperado:**

El ejemplo debe cargarse completo en CompileFlow y, si Blockly falla, no debe pisar el editor.

**Root cause probable:**

`loadSourceAfterClean()` deshabilita sync solo mientras limpia y setea el source, pero luego re-habilita sync antes de `await syncMan._syncIdeToBlocks()`. Los eventos de Blockly pueden disparar `_syncBlocksToIde()` y pisar el source.

**Referencias:**

- `frontend/main.js`
- `frontend/features/sync.js`

**Posible solucion:**

Mantener `_guard`/sync deshabilitado durante toda la operacion async de carga y manejar excepciones de Blockly sin actualizar IDE.

---

### CF-QA-009 - `printf` se acepta como funcion del lenguaje aunque no esta en spec

**Severidad:** Media  
**Area:** Semantica

**Reproduccion:**

Enviar a `/api/check`:

```c
int main() {
  printf("%s", 7);
  return 0;
}
```

**Resultado actual:**

`ok: true`.

**Resultado esperado:**

El lenguaje soportado solo incluye `print`, `println`, `input`, `input_int`, `input_float`; `printf` deberia ser error, salvo que se documente como extension.

**Root cause probable:**

`_LIBC_VARARG_BUILTINS = {'printf'}` en semantic.

**Referencias:**

- `compiler/semantic.py`

**Posible solucion:**

Eliminar `printf` del subset o documentar oficialmente la extension y agregar validacion de formato/tipos.

---

### CF-QA-010 - `input_int()` sin stdin causa HTTP 500

**Severidad:** Alta  
**Area:** Runtime, API run

**Reproduccion:**

Ejecutar:

```c
int main() {
  int x = input_int();
  println(x);
  return 0;
}
```

sin enviar stdin.

**Resultado actual:**

`/api/run` responde HTTP 500.

**Resultado esperado:**

Debe devolver JSON controlado con `ok:false`, error de runtime y mensaje claro.

**Root cause probable:**

`server/routes/run.py` crea `input_fn` que retorna `''` si no hay mas lineas. Luego `Interpreter._eval_input()` hace `int(raw.strip())`, lanzando `ValueError`, pero la ruta solo captura `InterpreterError`.

**Referencias:**

- `server/routes/run.py`
- `compiler/interpreter.py`

**Posible solucion:**

Convertir errores de parseo de input a `InterpreterError`, y capturar tambien excepciones esperadas en `/api/run`.

---

### CF-QA-011 - La UI no permite ingresar stdin

**Severidad:** Alta  
**Area:** UX runtime

**Reproduccion:**

Crear programa con `input()`, `input_int()` o `input_float()` y presionar **Ejecutar**.

**Resultado actual:**

No hay textarea/campo para stdin. El frontend envia solo `{ source }`.

**Resultado esperado:**

Debe existir un panel/campo de entrada, o la UI debe bloquear/explicar que programas con input no pueden ejecutarse.

**Root cause probable:**

`run()` en `frontend/main.js` no incluye `stdin`.

**Referencias:**

- `frontend/main.js`
- `server/routes/run.py`

**Posible solucion:**

Agregar campo de stdin en consola y enviarlo a `/api/run` y/o `/api/compile`.

---

### CF-QA-012 - Importar `.s` esta permitido pero no hace nada

**Severidad:** Media  
**Area:** File IO

**Reproduccion:**

1. Click en **Abrir**.
2. Seleccionar archivo `.s`.

**Resultado actual:**

`loadFile()` retorna tipo `asm`, pero el handler no tiene rama para `asm`; no se muestra nada.

**Resultado esperado:**

O se carga el assembly en el panel Ensamblador, o `.s` no debe aparecer como tipo aceptado.

**Root cause probable:**

`file-input` acepta `.s`, `loadFile()` reconoce `asm`, pero `fileInput.onchange` solo maneja `c`, `scratch`, `cfproj`.

**Referencias:**

- `frontend/main.js`
- `frontend/features/file_io.js`

**Posible solucion:**

Agregar manejo de `asm` o quitar `.s` del `accept`.

---

### CF-QA-013 - `/api/validate-file` no valida el contenido

**Severidad:** Media  
**Area:** API files

**Reproduccion:**

Enviar cualquier contenido con `file_type: "c"` o `file_type: "cfproj"`.

**Resultado actual:**

El endpoint responde `ok:true` y devuelve el contenido sin parsear/validar.

**Resultado esperado:**

Debe validar al menos JSON para `.scratch`/`.cfproj`, source para `.c`, y assembly si se acepta `.s`.

**Root cause probable:**

`server/routes/files.py` solo aplica Pydantic y retorna `req.content`.

**Referencias:**

- `server/routes/files.py`

**Posible solucion:**

Implementar validadores por tipo.

---

### CF-QA-014 - Export faltante: Scratch/Blockly, Mermaid y PNG

**Severidad:** Media  
**Area:** File IO, Flowchart

**Reproduccion:**

Abrir menu **Guardar**.

**Resultado actual:**

Solo aparecen:

- Guardar como `.c`
- Guardar como `.s`
- Guardar proyecto

**Resultado esperado:**

Segun lo probado/esperado para la app, deberia poder exportar Blockly/Scratch, Mermaid y posiblemente PNG del diagrama.

**Root cause probable:**

`saveAsScratch()` y `saveAsPng()` existen, pero no estan conectadas al menu. No hay opcion para Mermaid text.

**Referencias:**

- `frontend/features/file_io.js`
- `frontend/main.js`

**Posible solucion:**

Agregar opciones de menu y handlers para `.scratch`, `.mmd`/`.mermaid` y PNG del flowchart.

---

### CF-QA-015 - No existe import Mermaid

**Severidad:** Media  
**Area:** File IO, Flowchart

**Reproduccion:**

Intentar abrir un archivo `.mmd` o `.mermaid`.

**Resultado actual:**

El input no acepta esos tipos, y el validator tampoco.

**Resultado esperado:**

Si la app promete importar Mermaid, debe aceptar y renderizar Mermaid. Si no, debe quedar fuera de alcance explicitamente.

**Root cause probable:**

`file-input` solo acepta `.c,.s,.cfproj,.scratch`; `ValidateFileRequest.file_type` no incluye Mermaid.

**Referencias:**

- `frontend/main.js`
- `server/validators.py`

**Posible solucion:**

Agregar `mermaid`/`mmd` como tipo soportado o quitarlo del alcance/documentacion.

---

### CF-QA-016 - Errores Pydantic exponen payload gigante

**Severidad:** Media  
**Area:** API validation

**Reproduccion:**

Enviar a `/api/check` un `source` de mas de 512 KB.

**Resultado actual:**

El JSON 422 incluye el campo `input` con el payload completo.

**Resultado esperado:**

El error debe ser compacto y seguir el formato CompileFlow (`code`, `message`, `line`, `column`, etc.) sin repetir el input.

**Root cause probable:**

Las rutas devuelven `e.errors()` crudo de Pydantic.

**Referencias:**

- `server/routes/check.py`
- `server/routes/compile.py`
- `server/routes/convert.py`
- `server/routes/explain.py`
- `server/routes/files.py`

**Posible solucion:**

Crear helper para normalizar `ValidationError` a formato de error del spec y omitir `input`.

---

### CF-QA-017 - Paneles muestran estado viejo despues de errores

**Severidad:** Media  
**Area:** UI state

**Reproduccion:**

1. Compilar programa valido.
2. Cambiar source a:

```c
int main() {
  else { }
  return 0;
}
```

3. Presionar **Compilar**.

**Resultado actual:**

La consola muestra el error, pero paneles como ASM/AST pueden seguir mostrando la compilacion anterior.

**Resultado esperado:**

Al fallar, los paneles derivados deben limpiarse o marcarse como obsoletos.

**Root cause probable:**

La rama de error en `compile()` solo imprime errores; no limpia `lastAssembly`, `asmPanel`, `astViewer`, flowchart ni explanation.

**Referencias:**

- `frontend/main.js`

**Posible solucion:**

Limpiar paneles derivados antes de compilar o al recibir `ok:false`.

---

### CF-QA-018 - Consola conserva errores viejos en Flowchart/Explain/Debug

**Severidad:** Baja/Media  
**Area:** UI state

**Reproduccion:**

1. Provocar un error de compilacion.
2. Luego generar Flowchart valido o usar Explicar/Depurar.

**Resultado actual:**

La consola sigue mostrando errores anteriores, aunque la accion nueva haya funcionado.

**Resultado esperado:**

Cada accion debe limpiar o segmentar su salida.

**Root cause probable:**

Handlers de Flowchart, Explain y Debug no limpian la consola global.

**Referencias:**

- `frontend/main.js`

**Posible solucion:**

Llamar `clearConsole()` al iniciar acciones principales, o separar outputs por panel.

---

### CF-QA-019 - Debugger no muestra stdout

**Severidad:** Media  
**Area:** Debugger frontend

**Reproduccion:**

1. Depurar:

```c
int main() {
  int x = 1;
  x = x + 2;
  println(x);
  return 0;
}
```

2. Presionar **Step** / **Continue**.

**Resultado actual:**

Las variables se actualizan, pero no aparece stdout acumulado.

**Resultado esperado:**

El panel debugger debe mostrar `state.stdout`.

**Root cause probable:**

`Debugger._onState()` ignora `state.stdout`.

**Referencias:**

- `frontend/features/debugger.js`
- `server/routes/debug.py`

**Posible solucion:**

Agregar panel stdout y actualizarlo en cada `debug:state`.

---

### CF-QA-020 - Errores del debugger se tragan silenciosamente

**Severidad:** Media  
**Area:** Debugger frontend

**Reproduccion:**

1. Depurar un source invalido.
2. Observar UI.

**Resultado actual:**

El servidor emite `debug:error`, pero la UI no muestra nada util.

**Resultado esperado:**

El panel debe mostrar el error de parser/semantica/runtime.

**Root cause probable:**

`Debugger._onError()` esta vacio.

**Referencias:**

- `frontend/features/debugger.js`

**Posible solucion:**

Renderizar errores en el panel debugger o consola.

---

### CF-QA-021 - Share con parametro invalido puede romper el arranque de la app

**Severidad:** Alta  
**Area:** Share, boot

**Reproduccion:**

Abrir una URL como:

```text
http://127.0.0.1:5173/?p=no-es-base64-json
```

**Resultado actual esperado por codigo:**

`ShareManager.loadFromURL()` lanza, y `frontend/main.js` lo llama sin `try/catch` durante el arranque.

**Resultado esperado:**

La app debe cargar normalmente y mostrar un mensaje de "estado compartido invalido".

**Root cause probable:**

`loadFromURL()` re-lanza errores, pero `main.js` no los captura.

**Referencias:**

- `frontend/features/share.js`
- `frontend/main.js`

**Posible solucion:**

Envolver `shareMan.loadFromURL()` en `try/catch`, limpiar query param invalido y reportar error no fatal.

---

### CF-QA-022 - `blocks_to_c` acepta `workspace.blocks = null` como exito

**Severidad:** Media  
**Area:** Convert API, robustness

**Reproduccion:**

Enviar a `/api/convert`:

```json
{
  "direction": "blocks_to_c",
  "workspace": { "blocks": null }
}
```

**Resultado actual:**

Devuelve `ok:true` con:

```c
#include <stdio.h>
#include <string.h>
```

**Resultado esperado:**

Debe devolver error de workspace invalido o, como minimo, programa vacio CompileFlow sin C includes si se decide aceptar workspace vacio.

**Root cause probable:**

`BlocksToAST` trata estructuras incompletas como programa vacio, y `ASTtoC` genera includes.

**Referencias:**

- `server/routes/convert.py`
- `compiler/blocks_to_ast.py`
- `compiler/ast_to_c.py`

**Posible solucion:**

Validar schema minimo de workspace antes de convertir.

---

### CF-QA-023 - ASTViewer tiene click callback pero no esta conectado

**Severidad:** Baja/Media  
**Area:** AST panel

**Reproduccion:**

1. Compilar programa valido.
2. Click en nodos del AST.

**Resultado actual esperado por codigo:**

El viewer tiene `_onNodeClick(callback)`, pero `main.js` nunca lo llama. Por lo tanto el click no puede resaltar linea en Monaco.

**Resultado esperado:**

Click en nodo AST debe llevar/resaltar la linea de source correspondiente.

**Root cause probable:**

Falta wiring entre `ASTViewer._onNodeClick(...)` y editor Monaco.

**Referencias:**

- `frontend/features/ast_viewer.js`
- `frontend/main.js`

**Posible solucion:**

Registrar callback despues de crear `astViewer`, usando `editor.revealLineInCenter()` y decorations.

---

### CF-QA-024 - Formato de errores 422 no coincide con formato CompileFlow y rompe mensajes de UI

**Severidad:** Media  
**Area:** API validation, UI errors

**Reproduccion:**

Enviar `optimization_level: 99` a `/api/compile`, o `file_type: "mermaid"` a `/api/validate-file`.

**Resultado actual:**

La respuesta tiene errores Pydantic (`loc`, `msg`, `type`, `ctx`) en vez de `severity`, `line`, `column`, `message`. La UI que hace `.map(e => [${e.severity}] linea ${e.line}: ${e.message})` puede mostrar `undefined`.

**Resultado esperado:**

Todos los errores publicos deben usar el formato del spec.

**Root cause probable:**

Las rutas retornan `e.errors()` directamente.

**Referencias:**

- `server/routes/*.py`
- `frontend/main.js`

**Posible solucion:**

Normalizar errores de validacion a `VAL001` o similar con el schema CompileFlow.

---

### CF-QA-025 - Monaco worker fallback y errores de consola al cargar

**Severidad:** Baja/Media  
**Area:** Frontend build/dev ergonomics

**Reproduccion:**

Abrir la app local.

**Resultado actual:**

Consola:

```text
Could not create web worker(s). Falling back to loading web worker code in main thread
[Unhandled error] Event
ResizeObserver loop completed with undelivered notifications
```

**Resultado esperado:**

La app debe arrancar limpia, sin errores no manejados.

**Root cause probable:**

Configuracion incompleta de Monaco workers en Vite y errores de layout/ResizeObserver sin manejo.

**Referencias:**

- `frontend/ide/monaco_setup.js`
- `vite.config.js`

**Posible solucion:**

Configurar workers de Monaco para Vite y revisar lifecycle/layout de los paneles.

---

### CF-QA-026 - `saveAsAsm` permite guardar assembly viejo o vacio

**Severidad:** Baja/Media  
**Area:** Export

**Reproduccion:**

1. Abrir app.
2. Sin compilar, abrir **Guardar** -> **Guardar como .s**.
3. O compilar una vez, cambiar el source a algo invalido y guardar `.s`.

**Resultado actual esperado por codigo:**

Se descarga `program.s` con `lastAssembly`, que puede estar vacio u obsoleto.

**Resultado esperado:**

La UI debe deshabilitar export de ASM si no hay compilacion valida reciente, o marcarlo como obsoleto.

**Root cause probable:**

`lastAssembly` no se limpia en errores ni se valida antes de `saveAsAsm(lastAssembly)`.

**Referencias:**

- `frontend/main.js`
- `frontend/features/file_io.js`

**Posible solucion:**

Resetear `lastAssembly` al cambiar source o al fallar compile; deshabilitar opcion `.s` sin assembly valido.

---

### CF-QA-027 - `compile` ejecuta el binario como efecto secundario

**Severidad:** Media  
**Area:** API design, UX

**Reproduccion:**

Llamar `/api/compile` con un programa que lee input, imprime mucho, tarda, o tiene comportamiento runtime.

**Resultado actual:**

`/api/compile` genera assembly y tambien llama `Executor().assemble_and_run(...)`.

**Resultado esperado:**

El endpoint llamado "compile" deberia compilar; ejecutar deberia ser accion separada, especialmente porque puede leer stdin, tener timeout o efectos de runtime.

**Root cause probable:**

La ruta `compile_source()` mezcla compile + execute.

**Referencias:**

- `server/routes/compile.py`

**Posible solucion:**

Separar `/api/compile` y `/api/execute-assembly` o renombrar comportamiento a `compile_and_run`.

## Casos Probados

- Escritura real en Monaco con teclado.
- Botones: Compilar, Ejecutar, AST, Flowchart, Ensamblador, Depurar, Explicar, Galeria, Compartir, Abrir, Guardar.
- Programas simples con `println`, loops, variables, strings, floats, input.
- Errores sintacticos como `else` sin `if`.
- Conversion C -> Blockly -> C via UI/API.
- Flowchart/Mermaid con codigo valido e invalido.
- Debugger con Step/Continue.
- Share URL generado.
- API directa para `/api/check`, `/api/compile`, `/api/run`, `/api/convert`, `/api/flowchart`, `/api/validate-file`.
- Entradas grandes o invalidas para validadores.

## Notas para el Agente que Repare

Prioridad sugerida:

1. Arreglar reporting de `/api/compile` y rodata de codegen (`CF-QA-001`, `CF-QA-002`).
2. Cortar la corrupcion de source por sync (`CF-QA-004`, `CF-QA-006`, `CF-QA-007`, `CF-QA-008`).
3. Normalizar errores y evitar 500 (`CF-QA-010`, `CF-QA-016`, `CF-QA-024`).
4. Completar imports/exports y stdin (`CF-QA-011` a `CF-QA-015`, `CF-QA-026`).
5. Mejorar paneles/debugger/AST UX (`CF-QA-017` a `CF-QA-023`, `CF-QA-025`).

