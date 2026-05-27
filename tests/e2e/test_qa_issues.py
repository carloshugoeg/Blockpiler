"""
Regression tests for CF-QA-001 through CF-QA-027.

Each test documents a known bug from QA_ISSUES.md.  Every test is written to
FAIL against the current (buggy) implementation — passing means the bug was
fixed.

Severity markers:
  @pytest.mark.critical  — data-loss or silent wrong-result bugs
  @pytest.mark.ux        — user-visible broken flows
  @pytest.mark.cosmetic  — low-impact visual/console issues
"""

from __future__ import annotations

import pytest
import requests

from tests.e2e.pages import editor as editor_page
from tests.e2e.pages import blocks as blocks_page
from tests.e2e.pages import panels as panels_page

# ── Base URLs ──────────────────────────────────────────────────────────────────
FLASK_BASE = "http://localhost:5000"
VITE_BASE = "http://localhost:5173"

# ── Shared test programs ───────────────────────────────────────────────────────
PRINTLN_INT_PROG = "int main() {\n  println(42);\n  return 0;\n}"
PRINTLN_LOOP_PROG = (
    "int main() {\n"
    "  int i = 1;\n"
    "  while (i <= 3) {\n"
    "    println(i);\n"
    "    i = i + 1;\n"
    "  }\n"
    "  return 0;\n"
    "}"
)
INPUT_INT_PROG = (
    "int main() {\n"
    "  int x = input_int();\n"
    "  println(x);\n"
    "  return 0;\n"
    "}"
)
DEBUG_PROG = (
    "int main() {\n"
    "  int x = 1;\n"
    "  x = x + 2;\n"
    "  println(x);\n"
    "  return 0;\n"
    "}"
)


# ==============================================================================
# CF-QA-001
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_001_compile_reports_success_when_assembler_fails(page):
    """CF-QA-001: Compile button shows success even when assembler/linker fails.

    Steps: Type println(42) program, click Compile.
    Expected: Error shown if assembler fails (returncode=-1 / linker error).
    Bug: Shows 'Compilación exitosa' even when returncode=-1.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    editor_page.type_code(page, PRINTLN_INT_PROG)
    editor_page.click_compile(page)
    output = editor_page.get_output(page)

    # The correct behaviour: if the assembler/linker fails the UI must NOT show
    # a success message without also surfacing the error.
    # Should fail: success message present, no error message
    assert not ('compilación exitosa' in output.lower() and 'error' not in output.lower()), \
        "CF-QA-001: Shows 'compilación exitosa' even when linker fails"


# ==============================================================================
# CF-QA-002
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_002_codegen_missing_format_string_labels(page):
    """CF-QA-002: Generated assembly is missing .Lfmt_* labels causing linker failure.

    Steps: Compile any program using println.
    Expected: Assembly includes .Lfmt_int_nl and all format-string labels.
    Bug: Labels missing; linker reports 'Undefined symbols'.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    editor_page.type_code(page, PRINTLN_INT_PROG)
    editor_page.click_compile(page)

    try:
        asm_lines = panels_page.get_asm_lines(page)
    except RuntimeError:
        # ASM panel disabled — compile itself failed; that's also a symptom.
        asm_lines = []

    asm_text = "\n".join(asm_lines)
    assert ".Lfmt_int_nl" in asm_text, (
        "CF-QA-002: codegen does not emit .Lfmt_int_nl label in .rodata section"
    )


# ==============================================================================
# CF-QA-003
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_003_ejecutar_and_compilar_test_different_things(page):
    """CF-QA-003: Ejecutar (interpreter) and Compilar (native ARM64) use different
    pipelines but the UI gives no indication of the distinction.

    Steps: Run then Compile the same program.
    Expected: UI labels clarify 'Interpretar' vs 'Compilar + ejecutar binario'.
    Bug: Both buttons say they ran successfully with no visible distinction.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    editor_page.type_code(page, PRINTLN_INT_PROG)

    # Run (interpreter)
    editor_page.click_run(page)
    page.wait_for_timeout(2_000)
    run_output = editor_page.get_output(page)

    editor_page.clear_output(page)

    # Compile (native)
    editor_page.click_compile(page)
    compile_output = editor_page.get_output(page)

    # Expected: the UI distinguishes the two modes, e.g. via different labels
    # or preamble text.  Currently both produce identical-looking output.
    run_has_mode_label = (
        "interpret" in run_output.lower()
        or "intérprete" in run_output.lower()
        or "ejecutar" in run_output.lower()
    )
    compile_has_mode_label = (
        "compil" in compile_output.lower()
        or "binario" in compile_output.lower()
        or "arm64" in compile_output.lower()
    )
    assert run_has_mode_label and compile_has_mode_label, (
        "CF-QA-003: UI does not distinguish interpreter (Ejecutar) from native "
        "compiler (Compilar) in console output"
    )


# ==============================================================================
# CF-QA-004
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_004_blockly_sync_corrupts_compileflow_source(page):
    """CF-QA-004: Switching Code→Blockly→Code converts CompileFlow source to C
    with #include <stdio.h> and printf, corrupting the user's file.

    Steps: Type CompileFlow source, switch to Blockly, switch back to Code.
    Expected: Source preserved in CompileFlow syntax (no #include).
    Bug: Gets converted to C with #include <stdio.h>.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    editor_page.type_code(page, PRINTLN_INT_PROG)

    # Switch to Blockly (triggers IDE→Blocks sync)
    blocks_page.switch_to_blocks(page)
    page.wait_for_timeout(1_000)

    # Switch back to Code (triggers Blocks→IDE sync)
    code_after = blocks_page.convert_to_code(page)

    assert "#include" not in code_after, (
        "CF-QA-004: Blockly→IDE sync corrupted source — added #include <stdio.h>"
    )
    assert "printf" not in code_after, (
        "CF-QA-004: Blockly→IDE sync corrupted source — replaced println with printf"
    )


# ==============================================================================
# CF-QA-005
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_005_ast_to_c_generates_wrong_format_spec_for_int(page):
    """CF-QA-005: ASTtoC always generates printf("%s", val) regardless of type.

    Steps: POST a roundtrip via /api/convert for a program with println(42).
    Expected: printf uses %d (or %ld) for int arguments.
    Bug: Always uses %s.
    """
    payload = {
        "direction": "c_to_blocks",
        "source": PRINTLN_INT_PROG,
    }
    resp = requests.post(f"{FLASK_BASE}/api/convert", json=payload, timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    if not data.get("ok"):
        pytest.skip("c_to_blocks conversion failed — cannot test roundtrip")

    workspace = data.get("data", {}).get("workspace") or data.get("workspace")

    payload2 = {
        "direction": "blocks_to_c",
        "workspace": workspace,
    }
    resp2 = requests.post(f"{FLASK_BASE}/api/convert", json=payload2, timeout=10)
    assert resp2.status_code == 200
    data2 = resp2.json()
    c_source = data2.get("data", {}).get("source") or data2.get("source", "")

    assert '%s' not in c_source or '%d' in c_source or '%ld' in c_source, (
        "CF-QA-005: ASTtoC uses %s for int argument; expected %d or %ld"
    )


# ==============================================================================
# CF-QA-006
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_006_blockly_fails_loading_local_variables(page):
    """CF-QA-006: Blockly throws MissingConnection when loading a program with
    local variable declarations.

    Steps: Type while-loop with int i = 1; switch to Blockly tab.
    Expected: Blocks render without errors.
    Bug: MissingConnection error for c_var_decl block.
    """
    errors: list[str] = []

    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    page.on(
        "console",
        lambda msg: errors.append(msg.text) if msg.type == "error" else None,
    )

    editor_page.type_code(page, PRINTLN_LOOP_PROG)
    blocks_page.switch_to_blocks(page)
    page.wait_for_timeout(2_000)

    missing_conn_errors = [e for e in errors if "MissingConnection" in e]
    assert not missing_conn_errors, (
        f"CF-QA-006: Blockly MissingConnection errors on local-var program: "
        f"{missing_conn_errors}"
    )


# ==============================================================================
# CF-QA-007
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_007_blockly_fails_loading_functions_with_params(page):
    """CF-QA-007: Blockly throws MissingConnection when loading a function with
    parameters (e.g. Fibonacci from Gallery).

    Steps: Open Gallery → Fibonacci (recursivo), switch to Blockly.
    Expected: Param blocks render correctly.
    Bug: MissingConnection error for c_param block.
    """
    errors: list[str] = []

    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)
    page.wait_for_timeout(1_000)

    page.on(
        "console",
        lambda msg: errors.append(msg.text) if msg.type == "error" else None,
    )

    # Open gallery menu
    page.locator("#btn-gallery").click()
    page.wait_for_selector("#gallery-menu", timeout=5_000)

    # Click a gallery item that contains a function with parameters
    gallery_items = page.locator("#gallery-menu .dropdown-item")
    count = gallery_items.count()
    if count == 0:
        pytest.skip("Gallery menu has no items — cannot test CF-QA-007")

    # Try to find Fibonacci or any item with "recursivo" / "fibonacci"
    target = None
    for i in range(count):
        text = (gallery_items.nth(i).text_content() or "").lower()
        if "fibonacci" in text or "recursivo" in text:
            target = gallery_items.nth(i)
            break
    if target is None:
        target = gallery_items.first

    target.click()
    page.wait_for_timeout(2_000)

    blocks_page.switch_to_blocks(page)
    page.wait_for_timeout(2_000)

    missing_conn_errors = [e for e in errors if "MissingConnection" in e]
    assert not missing_conn_errors, (
        f"CF-QA-007: Blockly MissingConnection errors on parameterised function: "
        f"{missing_conn_errors}"
    )


# ==============================================================================
# CF-QA-008
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_008_gallery_leaves_editor_empty_or_converted_to_c(page):
    """CF-QA-008: Loading a Gallery example can leave the editor empty or with
    only '#include <stdio.h>' (converted to C).

    Steps: Open Gallery → load FizzBuzz or Fibonacci.
    Expected: Editor shows full CompileFlow source.
    Bug: Editor may only contain #include <stdio.h> or be empty.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)
    page.wait_for_timeout(1_000)

    page.locator("#btn-gallery").click()
    page.wait_for_selector("#gallery-menu", timeout=5_000)

    gallery_items = page.locator("#gallery-menu .dropdown-item")
    count = gallery_items.count()
    if count == 0:
        pytest.skip("Gallery menu has no items — cannot test CF-QA-008")

    # Pick FizzBuzz or Fibonacci, or fall back to first item
    target = None
    for i in range(count):
        text = (gallery_items.nth(i).text_content() or "").lower()
        if "fizz" in text or "fibonacci" in text:
            target = gallery_items.nth(i)
            break
    if target is None:
        target = gallery_items.first

    target.click()
    page.wait_for_timeout(2_000)

    # Switch to Code tab
    editor_page.type_code(page, "")  # ensures Code tab is active
    source_after = editor_page.get_code(page)

    assert source_after.strip() != "", (
        "CF-QA-008: Gallery load left editor empty"
    )
    # A properly loaded CompileFlow example must not be reduced to only C headers
    meaningful = source_after.replace("#include <stdio.h>", "").replace(
        "#include <string.h>", ""
    ).strip()
    assert meaningful, (
        "CF-QA-008: Gallery load left editor with only #include headers (C corruption)"
    )


# ==============================================================================
# CF-QA-009
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_009_printf_accepted_as_language_function():
    """CF-QA-009: /api/check accepts printf as a valid language function even
    though it is not part of the CompileFlow spec.

    Expected: ok=False (printf is not in the language).
    Bug: Returns ok=True.
    """
    source = 'int main() {\n  printf("%s", 7);\n  return 0;\n}'
    resp = requests.post(
        f"{FLASK_BASE}/api/check",
        json={"source": source},
        timeout=10,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is False, (
        "CF-QA-009: /api/check accepts printf as valid; it should be rejected"
    )


# ==============================================================================
# CF-QA-010
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_010_input_int_without_stdin_causes_http_500():
    """CF-QA-010: /api/run returns HTTP 500 when input_int() is called without
    providing stdin.

    Expected: JSON response with ok=False and a clear error message.
    Bug: Returns HTTP 500.
    """
    resp = requests.post(
        f"{FLASK_BASE}/api/run",
        json={"source": INPUT_INT_PROG},  # no stdin field
        timeout=10,
    )
    assert resp.status_code != 500, (
        f"CF-QA-010: /api/run returned HTTP {resp.status_code} (500) for "
        "input_int() without stdin"
    )
    data = resp.json()
    assert data.get("ok") is False, (
        "CF-QA-010: /api/run should return ok=False for missing stdin"
    )


# ==============================================================================
# CF-QA-011
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_011_ui_has_no_stdin_input_field(page):
    """CF-QA-011: The UI has no visible stdin input field for programs that use
    input() / input_int() / input_float().

    Expected: An input/textarea is visible (or revealed) when the program uses
    input functions so the user can provide stdin.
    Bug: No field shown; frontend sends only {source} without stdin.

    Note: index.html actually includes #stdin-input hidden behind a toggle;
    this test verifies the toggle works and the field becomes visible/functional.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    # The stdin panel is hidden by default — the toggle button must exist
    toggle = page.locator("#btn-toggle-stdin")
    assert toggle.count() > 0, (
        "CF-QA-011: #btn-toggle-stdin button not found — no stdin toggle in UI"
    )

    # Clicking the toggle should reveal #stdin-input
    # First confirm the panel starts hidden
    stdin_panel = page.locator("#stdin-panel")
    initial_hidden = "hidden" in (stdin_panel.get_attribute("class") or "")

    toggle.click()
    page.wait_for_timeout(300)

    after_class = stdin_panel.get_attribute("class") or ""
    now_hidden = "hidden" in after_class

    if initial_hidden:
        # After click it should no longer be hidden
        assert not now_hidden, (
            "CF-QA-011: Clicking stdin toggle did not reveal #stdin-panel"
        )
    # If it wasn't hidden initially, that's fine — stdin is already visible

    stdin_input = page.locator("#stdin-input")
    assert stdin_input.count() > 0, (
        "CF-QA-011: #stdin-input textarea not found in DOM"
    )

    # The real bug: frontend run() does not include the stdin value in the
    # POST body.  Verify by injecting a value and checking run payload.
    stdin_input.fill("99\n")

    # Intercept the /api/run request to verify stdin is included
    request_body: dict = {}

    def capture_request(req):
        if "/api/run" in req.url:
            try:
                request_body.update(req.post_data_json() or {})
            except Exception:
                pass

    page.on("request", capture_request)

    editor_page.type_code(page, INPUT_INT_PROG)
    editor_page.click_run(page)
    page.wait_for_timeout(3_000)

    assert "stdin" in request_body and request_body["stdin"], (
        "CF-QA-011: /api/run POST body does not include stdin value from textarea"
    )


# ==============================================================================
# CF-QA-012
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_012_importing_asm_file_does_nothing(page):
    """CF-QA-012: Clicking Abrir and selecting a .s file has no visible effect —
    the asm type is recognised by loadFile() but not handled.

    Expected: Assembly loaded into ASM panel, or a clear error message shown,
    or .s removed from the accepted file types.
    Bug: Nothing happens.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    file_input = page.locator("#file-input")

    # Check that the file input accepts .s files
    accept_attr = file_input.get_attribute("accept") or ""
    # The bug: .s is accepted but not handled.  The correct fix is either to
    # handle it or to remove it.  We assert that .s is NOT in accept (fix) or
    # that a handler is wired up.

    # For the regression test, we set a .s buffer and verify the UI reacts.
    page.locator("#btn-open").click()
    page.wait_for_timeout(300)

    asm_content = b".text\n.globl _main\n_main:\n  ret\n"
    file_input.set_input_files(
        [{"name": "test.s", "mimeType": "text/plain", "buffer": asm_content}]
    )
    page.wait_for_timeout(1_000)

    output = editor_page.get_output(page)
    asm_panel_text = ""
    try:
        asm_lines = panels_page.get_asm_lines(page)
        asm_panel_text = "\n".join(asm_lines)
    except RuntimeError:
        pass

    # Either the console shows an error/message or the ASM panel shows content
    has_feedback = (
        ".text" in asm_panel_text
        or "asm" in output.lower()
        or "ensamblador" in output.lower()
        or "error" in output.lower()
        or ".s" in output.lower()
    )
    assert has_feedback, (
        "CF-QA-012: Opening a .s file produced no visible feedback in UI "
        "(no console message, no ASM panel update)"
    )


# ==============================================================================
# CF-QA-013
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_013_validate_file_does_not_validate_content():
    """CF-QA-013: /api/validate-file returns ok=True for any content without
    actually parsing or validating it.

    Expected: Validation of content based on file_type.
    Bug: Always returns ok=True without checking the content.
    """
    # Send garbage content as a 'c' file
    resp = requests.post(
        f"{FLASK_BASE}/api/validate-file",
        json={"content": "THIS IS NOT VALID C CODE @@@###", "file_type": "c"},
        timeout=10,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is False, (
        "CF-QA-013: /api/validate-file returns ok=True for invalid C content "
        "without performing actual validation"
    )


# ==============================================================================
# CF-QA-014
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_014_missing_exports_scratch_mermaid_png(page):
    """CF-QA-014: The Guardar menu only shows .c, .s, proyecto — missing
    Scratch/Blockly, Mermaid and PNG export options.

    Expected: Export options for Scratch/Blockly, Mermaid (.mmd), and PNG.
    Bug: Only three options present.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    # Open the save dropdown
    page.locator("#btn-save").click()
    page.wait_for_selector("#save-menu", timeout=5_000)

    save_menu_text = (page.locator("#save-menu").text_content() or "").lower()

    has_scratch = "scratch" in save_menu_text or "blockly" in save_menu_text
    has_mermaid = "mermaid" in save_menu_text or ".mmd" in save_menu_text
    has_png = "png" in save_menu_text

    assert has_scratch and has_mermaid and has_png, (
        f"CF-QA-014: Guardar menu missing export options. "
        f"scratch={has_scratch}, mermaid={has_mermaid}, png={has_png}. "
        f"Menu text: '{save_menu_text}'"
    )


# ==============================================================================
# CF-QA-015
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_015_no_mermaid_import(page):
    """CF-QA-015: The app does not accept .mmd / .mermaid files for import.

    Expected: Either import is supported (with rendering) or clearly out-of-scope.
    Bug: file-input accept attribute does not include .mmd; no mermaid import handler.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    file_input = page.locator("#file-input")
    accept_attr = file_input.get_attribute("accept") or ""

    # The test asserts that .mmd IS accepted (the correct/fixed behaviour).
    # Currently it is not, so this test will FAIL.
    assert ".mmd" in accept_attr or "mermaid" in accept_attr, (
        f"CF-QA-015: file-input does not accept .mmd files. accept='{accept_attr}'"
    )


# ==============================================================================
# CF-QA-016
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_016_pydantic_errors_expose_giant_payload():
    """CF-QA-016: A 422 Pydantic validation error for /api/check echoes the full
    input payload in the response body.

    Expected: Compact error without re-embedding the input.
    Bug: 422 JSON includes 'input' field with the full payload.
    """
    big_source = "x" * (512 * 1024 + 1)  # > 512 KB
    resp = requests.post(
        f"{FLASK_BASE}/api/check",
        json={"source": big_source},
        timeout=30,
    )
    # Could be 200 (if size check happens inside) or 422
    response_text = resp.text

    # The bug: the response echoes back the giant source in an 'input' field.
    # A proper fix strips 'input' from Pydantic error details.
    assert '"input"' not in response_text or len(response_text) < 1024, (
        "CF-QA-016: Pydantic validation error echoes the full oversized input "
        f"in response (response size={len(response_text)} bytes)"
    )


# ==============================================================================
# CF-QA-017
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_017_panels_show_stale_state_after_errors(page):
    """CF-QA-017: After a successful compile followed by a failing compile, the
    AST/ASM panels continue to show the previous (stale) compilation's data.

    Steps: Compile valid program, then compile syntactically invalid program.
    Expected: Panels cleared or marked stale on error.
    Bug: Old compile panels still shown after error.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    # 1. Compile a valid program
    editor_page.type_code(page, PRINTLN_INT_PROG)
    editor_page.click_compile(page)
    page.wait_for_timeout(2_000)

    # Check AST was populated
    ast_visible_after_valid = panels_page.get_ast_visible(page)

    # 2. Now compile something invalid
    editor_page.clear_output(page)
    editor_page.type_code(page, "int main() {\n  else { }\n  return 0;\n}")
    editor_page.click_compile(page)
    page.wait_for_timeout(2_000)

    output_after_error = editor_page.get_output(page)
    ast_visible_after_error = panels_page.get_ast_visible(page)

    # If the first compile populated the AST and the second compile errors out,
    # the AST panel should be cleared or marked stale — not remain visible.
    # (The correct behaviour is to hide/clear it on error.)
    assert ast_visible_after_valid, "Precondition failed: valid compile did not populate AST panel"
    assert "error" in output_after_error.lower(), "Precondition failed: error compile did not show error"
    assert not ast_visible_after_error, "CF-QA-017: AST panel still shows after error compile"


# ==============================================================================
# CF-QA-018
# ==============================================================================

@pytest.mark.cosmetic
def test_cf_qa_018_console_retains_old_errors_in_flowchart(page):
    """CF-QA-018: After a compile error, triggering Flowchart does not clear
    old error messages from the console.

    Steps: Cause compile error, then successfully generate Flowchart.
    Expected: Console cleared for new action output.
    Bug: Old errors still visible alongside flowchart output.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    # 1. Cause a compile error
    editor_page.type_code(page, "int main() {\n  else { }\n  return 0;\n}")
    editor_page.click_compile(page)
    page.wait_for_timeout(2_000)
    output_with_error = editor_page.get_output(page)
    assert "error" in output_with_error.lower(), "Precondition: need compile error"

    # 2. Load a valid program and generate Flowchart
    editor_page.type_code(page, PRINTLN_INT_PROG)
    page.locator("#btn-flowchart").click()
    page.wait_for_timeout(5_000)

    output_after_flowchart = editor_page.get_output(page)

    # The console should NOT still contain the previous error.
    # After a new action, old errors must be cleared — not silently mixed in.
    assert "error" not in output_after_flowchart.lower(), (
        "CF-QA-018: Old error messages still visible in console after "
        "generating a successful Flowchart"
    )


# ==============================================================================
# CF-QA-019
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_019_debugger_does_not_show_stdout(page):
    """CF-QA-019: The Debugger panel does not display stdout from println calls
    as the user steps through a program.

    Steps: Debug program with println, press Step.
    Expected: stdout visible in debug panel.
    Bug: stdout not shown; Debugger._onState() ignores state.stdout.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    editor_page.type_code(page, DEBUG_PROG)

    # Open debug panel
    page.locator("#btn-debug").click()
    page.wait_for_selector("#debug-container:not(.hidden)", timeout=5_000)

    # Start debugging — look for a Start/Step button inside debug-container
    debug_container = page.locator("#debug-container")
    start_btn = debug_container.locator("button").filter(
        has_text="Iniciar"
    ).first
    if not start_btn.count():
        start_btn = debug_container.locator("button").first

    if start_btn.count():
        start_btn.click()
        page.wait_for_timeout(2_000)

        step_btn = debug_container.locator("button").filter(has_text="Step").first
        if not step_btn.count():
            step_btn = debug_container.locator("button").filter(
                has_text="Paso"
            ).first
        if step_btn.count():
            step_btn.click()
            page.wait_for_timeout(1_000)
            step_btn.click()
            page.wait_for_timeout(1_000)
            step_btn.click()
            page.wait_for_timeout(1_000)

    debug_text = (debug_container.text_content() or "").lower()
    # After executing println(3), stdout "3" should appear in the panel
    assert "3" in debug_text or "stdout" in debug_text, (
        "CF-QA-019: Debugger panel does not show stdout output after stepping "
        "through a println statement"
    )


# ==============================================================================
# CF-QA-020
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_020_debugger_errors_swallowed_silently(page):
    """CF-QA-020: Debugging invalid source emits 'debug:error' on the server
    but the frontend Debugger._onError() is empty so nothing is shown.

    Steps: Start debugger with invalid source.
    Expected: Error message visible in debug panel or console.
    Bug: Nothing shown.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    invalid_source = "int main() {\n  else { }\n  return 0;\n}"
    editor_page.type_code(page, invalid_source)

    page.locator("#btn-debug").click()
    page.wait_for_selector("#debug-container:not(.hidden)", timeout=5_000)

    debug_container = page.locator("#debug-container")
    start_btn = debug_container.locator("button").filter(
        has_text="Iniciar"
    ).first
    if not start_btn.count():
        start_btn = debug_container.locator("button").first

    if start_btn.count():
        start_btn.click()
        page.wait_for_timeout(3_000)

    debug_text = (debug_container.text_content() or "").lower()
    console_text = editor_page.get_output(page).lower()

    has_error_visible = (
        "error" in debug_text
        or "error" in console_text
        or "inválido" in debug_text
        or "syntax" in debug_text
    )
    assert has_error_visible, (
        "CF-QA-020: Debugger silently swallowed parse/semantic error for "
        "invalid source — no error message shown in debug panel or console"
    )


# ==============================================================================
# CF-QA-021
# ==============================================================================

@pytest.mark.critical
def test_cf_qa_021_share_invalid_url_param_breaks_app_startup(page):
    """CF-QA-021: Navigating to /?p=<invalid-base64> can throw an uncaught
    exception in ShareManager.loadFromURL() causing the app to fail to load.

    Steps: Navigate to /?p=not-base64-json-garbage-input.
    Expected: App loads normally, error message shown for invalid share param.
    Bug: App may throw/break on startup.
    """
    page.goto("/?p=not-base64-json-garbage-input")

    try:
        page.wait_for_selector("#shell", timeout=10_000)
        app_loaded = True
    except Exception:
        app_loaded = False

    assert app_loaded, (
        "CF-QA-021: App failed to load when URL param ?p= contains invalid "
        "base64/JSON — ShareManager.loadFromURL() threw uncaught exception"
    )


# ==============================================================================
# CF-QA-022
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_022_blocks_to_c_accepts_null_blocks_as_success():
    """CF-QA-022: /api/convert with direction=blocks_to_c and workspace.blocks=null
    returns ok=True with C include headers instead of an error.

    Expected: Error response for invalid/null workspace.
    Bug: Returns ok=True with '#include <stdio.h>' output.
    """
    payload = {
        "direction": "blocks_to_c",
        "workspace": {"blocks": None},
    }
    resp = requests.post(
        f"{FLASK_BASE}/api/convert",
        json=payload,
        timeout=10,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data.get("ok") is False, (
        "CF-QA-022: /api/convert accepts workspace.blocks=null as success; "
        "expected ok=False for null/empty workspace"
    )


# ==============================================================================
# CF-QA-023
# ==============================================================================

@pytest.mark.cosmetic
def test_cf_qa_023_ast_click_callback_not_wired_up(page):
    """CF-QA-023: Clicking an AST node in the ASTViewer does nothing because
    ASTViewer._onNodeClick() is never registered in main.js.

    Steps: Compile valid program, click an AST node.
    Expected: Corresponding source line highlighted in Monaco editor.
    Bug: Nothing happens on click.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    editor_page.type_code(page, PRINTLN_INT_PROG)
    editor_page.click_compile(page)
    page.wait_for_timeout(2_000)

    # Make sure AST panel is visible
    page.locator("#btn-ast").click()
    page.wait_for_selector("#ast-container:not(.hidden)", timeout=5_000)

    ast_container = page.locator("#ast-container")
    # Find any clickable node in the AST tree
    node = ast_container.locator("[data-line], .ast-node, .node").first
    if node.count() == 0:
        # Try any element that might represent a tree node
        node = ast_container.locator("text, tspan, circle, rect").first

    if node.count() == 0:
        pytest.skip("No AST nodes found to click — cannot test CF-QA-023")

    # Track Monaco decorations before and after click
    decorations_before = page.evaluate(
        """
        () => {
            if (window.monaco && window.monaco.editor) {
                const eds = window.monaco.editor.getEditors();
                if (eds && eds.length > 0) {
                    return eds[0].getModel()?.getAllDecorations()?.length ?? 0;
                }
            }
            return -1;
        }
        """
    )

    node.click()
    page.wait_for_timeout(500)

    decorations_after = page.evaluate(
        """
        () => {
            if (window.monaco && window.monaco.editor) {
                const eds = window.monaco.editor.getEditors();
                if (eds && eds.length > 0) {
                    return eds[0].getModel()?.getAllDecorations()?.length ?? 0;
                }
            }
            return -1;
        }
        """
    )

    assert decorations_after > decorations_before, (
        "CF-QA-023: Clicking AST node did not add any Monaco decorations — "
        "_onNodeClick callback is not wired up"
    )


# ==============================================================================
# CF-QA-024
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_024_422_error_format_does_not_match_compileflow_format():
    """CF-QA-024: Pydantic 422 validation errors use Pydantic's format (loc, msg,
    type, ctx) instead of the CompileFlow format (severity, line, column, message).

    Steps: Send optimization_level=99 to /api/compile.
    Expected: Errors with CompileFlow fields.
    Bug: Raw Pydantic error format returned.
    """
    payload = {
        "source": "int main() { return 0; }",
        "optimization_level": 99,
    }
    resp = requests.post(
        f"{FLASK_BASE}/api/compile",
        json=payload,
        timeout=15,
    )
    # Pydantic validation error yields 422
    if resp.status_code not in (200, 422):
        pytest.skip(f"Unexpected status {resp.status_code}")

    data = resp.json()
    errors = data.get("errors", [])
    if not errors:
        pytest.skip("No errors returned — optimization_level=99 may be valid")

    # Each error should have CompileFlow fields
    for err in errors:
        assert "severity" in err, (
            f"CF-QA-024: Error object missing 'severity' field. Got: {err}"
        )
        assert "message" in err, (
            f"CF-QA-024: Error object missing 'message' field. Got: {err}"
        )
        assert "line" in err, (
            f"CF-QA-024: Error object missing 'line' field. Got: {err}"
        )
        # Pydantic-style fields must NOT be present
        assert "loc" not in err, (
            f"CF-QA-024: Raw Pydantic 'loc' field exposed in error: {err}"
        )
        assert "type" not in err or err.get("type") in (None,), (
            f"CF-QA-024: Raw Pydantic 'type' field exposed in error: {err}"
        )


# ==============================================================================
# CF-QA-025
# ==============================================================================

@pytest.mark.cosmetic
def test_cf_qa_025_monaco_worker_console_errors_on_load(page):
    """CF-QA-025: Opening the app produces console errors about Monaco worker
    fallback and ResizeObserver.

    Steps: Open app, check browser console for errors.
    Expected: No unhandled errors on load.
    Bug: Worker fallback message and ResizeObserver errors appear.
    """
    errors: list[str] = []
    page.on(
        "console",
        lambda msg: errors.append(msg.text) if msg.type == "error" else None,
    )

    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)
    page.wait_for_timeout(3_000)  # Let Monaco fully initialise

    worker_errors = [
        e for e in errors
        if "worker" in e.lower()
        or "fallback" in e.lower()
        or "ResizeObserver" in e
        or "Unhandled" in e
    ]
    assert not worker_errors, (
        f"CF-QA-025: Console errors on app load: {worker_errors}"
    )


# ==============================================================================
# CF-QA-026
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_026_save_as_asm_exports_stale_or_empty_assembly(page):
    """CF-QA-026: Clicking Guardar → Guardar como .s without compiling first
    (or after compiling then editing) downloads an empty or stale file.

    Expected: Export disabled/greyed-out when no valid recent compilation exists.
    Bug: Empty or old assembly downloaded.
    """
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)

    # Do NOT compile — open save menu directly
    page.locator("#btn-save").click()
    page.wait_for_selector("#save-menu", timeout=5_000)

    asm_save_btn = page.locator('[data-save="asm"]')

    # The fix would make the button disabled when no assembly is available
    is_disabled = asm_save_btn.get_attribute("disabled") is not None
    aria_disabled = asm_save_btn.get_attribute("aria-disabled") == "true"

    assert is_disabled or aria_disabled, (
        "CF-QA-026: 'Guardar como .s' button is enabled even without a valid "
        "recent compilation — saving would download empty or stale assembly"
    )


# ==============================================================================
# CF-QA-027
# ==============================================================================

@pytest.mark.ux
def test_cf_qa_027_compile_executes_binary_as_side_effect():
    """CF-QA-027: /api/compile not only compiles but also executes the binary,
    making compile a side-effectful operation with runtime behavior.

    Steps: POST to /api/compile and inspect response for execution results.
    Expected: compile endpoint only compiles; execution is a separate step.
    Bug: /api/compile calls Executor().assemble_and_run() and returns stdout/stderr.
    """
    payload = {"source": PRINTLN_INT_PROG}
    resp = requests.post(
        f"{FLASK_BASE}/api/compile",
        json=payload,
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()

    compile_data = data.get("data", {})

    # A pure compile endpoint should NOT include execution outputs
    has_execution_output = (
        "stdout" in compile_data
        or "returncode" in compile_data
        or "timed_out" in compile_data
    )

    assert not has_execution_output, (
        "CF-QA-027: /api/compile response includes execution fields (stdout, "
        "returncode, timed_out) — compile is executing the binary as a side effect"
    )
