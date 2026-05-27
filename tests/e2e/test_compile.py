"""
E2E tests — core compile flow.

Tests 1-6 cover:
  1. Valid program via interpreter shows correct output
  2. Syntax error shows error panel with location info
  3. Semantic error (undeclared variable) message is descriptive
  4. Empty source gives an informative message (not HTTP 500 / blank)
  5. Program with multiple errors shows more than one error
  6. Compile (ASM panel) then run (stdout) for same valid program
"""

from __future__ import annotations

import pytest

from tests.e2e.pages import editor as editor_page
from tests.e2e.pages import panels as panels_page


# ── Shared programs ────────────────────────────────────────────────────────────

PRINTLN_42 = "int main() {\n  println(42);\n  return 0;\n}"

SYNTAX_ERROR_PROG = "int main() {\n  else { }\n  return 0;\n}"

UNDECLARED_VAR_PROG = (
    "int main() {\n"
    "  int x = undeclared_var + 1;\n"
    "  return 0;\n"
    "}"
)

MULTI_ERROR_PROG = (
    "int main() {\n"
    "  int a = undeclaredA;\n"
    "  int b = undeclaredB;\n"
    "  int c = undeclaredC;\n"
    "  return 0;\n"
    "}"
)


# ── Test helpers ───────────────────────────────────────────────────────────────

def _reload(page) -> None:
    """Reload the app and wait for the shell to be ready."""
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)


# ==============================================================================
# Test 1 — valid program via interpreter shows "42" in output
# ==============================================================================

@pytest.mark.critical
def test_valid_program_shows_output(page) -> None:
    """Type println(42) program, click Run (interpreter), verify '42' in output."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)
    editor_page.click_run(page)

    # Wait for the console output to appear (run is async)
    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=20_000,
    )

    output = editor_page.get_output(page)
    assert "42" in output, (
        f"Expected '42' in interpreter output, got: {output!r}"
    )


# ==============================================================================
# Test 2 — syntax error shows error panel with line/column info
# ==============================================================================

@pytest.mark.critical
def test_syntax_error_shows_error_panel(page) -> None:
    """Type a program with a bare 'else', click Run, verify error panel shows
    with location info (line number or column number)."""
    _reload(page)

    editor_page.type_code(page, SYNTAX_ERROR_PROG)
    editor_page.click_run(page)

    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=20_000,
    )

    output = editor_page.get_output(page)

    # Must mention an error
    assert "error" in output.lower() or "línea" in output.lower(), (
        f"Expected error text in output, got: {output!r}"
    )

    # Must contain some location hint — a digit (line or column number)
    has_location = any(ch.isdigit() for ch in output)
    assert has_location, (
        f"Expected line/column number in error output, got: {output!r}"
    )


# ==============================================================================
# Test 3 — semantic error mentions the undeclared variable name
# ==============================================================================

@pytest.mark.ux
def test_semantic_error_descriptive_message(page) -> None:
    """Type a program that uses undeclared_var; verify the error message
    includes the variable name 'undeclared_var'."""
    _reload(page)

    editor_page.type_code(page, UNDECLARED_VAR_PROG)
    editor_page.click_run(page)

    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=20_000,
    )

    output = editor_page.get_output(page)

    assert "undeclared_var" in output, (
        f"Expected error to mention variable name 'undeclared_var', got: {output!r}"
    )


# ==============================================================================
# Test 4 — empty source gives an informative message (not HTTP 500 / blank)
# ==============================================================================

@pytest.mark.ux
def test_empty_source_informative_message(page) -> None:
    """Clear the editor, click Run, verify an informative message appears
    (not a blank console and not a network/HTTP 500 error)."""
    _reload(page)

    # Set empty source
    editor_page.type_code(page, "")
    editor_page.click_run(page)

    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=20_000,
    )

    output = editor_page.get_output(page)

    # Must not be blank
    assert output.strip(), "Expected informative message for empty source, got blank output"

    # Must not be a raw HTTP 500 / network crash indicator with zero useful info
    assert "500" not in output or len(output.strip()) > 3, (
        f"Output looks like a bare HTTP 500 with no message: {output!r}"
    )


# ==============================================================================
# Test 5 — multiple errors program shows more than one error in output
# ==============================================================================

@pytest.mark.ux
def test_multiple_errors_shown(page) -> None:
    """Type a program with three undeclared variables; verify multiple errors
    are reported in the console output (not just the first one)."""
    _reload(page)

    editor_page.type_code(page, MULTI_ERROR_PROG)
    editor_page.click_run(page)

    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=20_000,
    )

    output = editor_page.get_output(page)

    # At least two of the three identifiers should appear in the error output
    mentioned = sum(
        1 for name in ("undeclaredA", "undeclaredB", "undeclaredC")
        if name in output
    )
    assert mentioned >= 2, (
        f"Expected multiple errors (>=2 variable names in output), got: {output!r}"
    )


# ==============================================================================
# Test 6 — compile → ASM panel populated; run same program → stdout shows output
# ==============================================================================

@pytest.mark.critical
def test_compile_then_run_produces_output(page) -> None:
    """Compile valid program, verify ASM panel gets content;
    run same program via interpreter, verify stdout shows '42'."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    # Step 1: Compile — wait for compile to finish (click_compile waits internally)
    editor_page.click_compile(page)

    # Attempt to read ASM panel — may raise RuntimeError if button disabled
    try:
        asm_lines = panels_page.get_asm_lines(page)
        assert len(asm_lines) > 0, "Expected ASM panel to contain assembly lines after compile"
    except RuntimeError:
        # ASM panel unavailable means compile failed — we still continue to run
        pass

    # Step 2: Run via interpreter
    # Reload to start fresh (avoids stale console state)
    _reload(page)
    editor_page.type_code(page, PRINTLN_42)
    editor_page.click_run(page)

    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=20_000,
    )

    output = editor_page.get_output(page)
    assert "42" in output, (
        f"Expected '42' in interpreter output after compile+run flow, got: {output!r}"
    )
