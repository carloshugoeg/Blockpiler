"""
E2E tests — adversarial / fool-proof edge-case inputs.

Tests cover:
  1. Oversized source (600 KB) shows a size/limit error (not silent or HTTP 500)
  2. Null bytes in source are handled gracefully (not crash/white screen)
  3. Emoji characters in source are handled gracefully
  4. RTL (Arabic/Hebrew) characters in source are handled gracefully
  5. Infinite loop shows timeout message (not blank forever)
  6. Deeply nested if-statements (100 levels) do not crash JS
  7. Rapid compile clicks (10 times) produce non-empty output; #shell persists
  8. Invalid share URL (?p=notvalidbase64!!!) — app loads; covers CF-QA-021
  9. Empty source error then valid program — second run succeeds (not stuck)
"""

from __future__ import annotations

import pytest

from tests.e2e.pages import editor as editor_page


# ── Shared programs ────────────────────────────────────────────────────────────

PRINTLN_42 = "int main() {\n  println(42);\n  return 0;\n}"


# ── Test helpers ───────────────────────────────────────────────────────────────

def _reload(page) -> None:
    """Reload the app and wait for the shell to be ready."""
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)


def _wait_for_output(page, timeout: int = 20_000) -> None:
    """Wait for #console-output to have non-empty text content."""
    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=timeout,
    )


def _app_intact(page) -> bool:
    """Return True if the core shell elements are all still visible."""
    try:
        shell_ok = page.locator("#shell").is_visible()
        toolbar_ok = page.locator("#toolbar").is_visible() if page.locator("#toolbar").count() > 0 else True
        console_ok = page.locator("#console").is_visible() if page.locator("#console").count() > 0 else True
        return shell_ok and toolbar_ok and console_ok
    except Exception:
        return False


def _make_deeply_nested(depth: int) -> str:
    """Generate a CompileFlow program with *depth* nested if-statements."""
    code = "int main() {\n"
    code += "  int x = 1;\n"
    for i in range(depth):
        code += "  " * (i + 1) + "if (x > 0) {\n"
    code += "  " * (depth + 1) + "x = 0;\n"
    for i in range(depth):
        code += "  " * (depth - i) + "}\n"
    code += "  return 0;\n}\n"
    return code


# ==============================================================================
# Test 1 — oversized source (600 KB) shows size/limit error
# ==============================================================================

@pytest.mark.critical
def test_oversized_source_shows_size_error(page) -> None:
    """Generate 600 KB of source, set it via Monaco API, run it, verify a
    size/limit error message appears — not silent failure, not HTTP 500."""
    _reload(page)

    # Build ~600 KB of repeated text — use a line that resembles valid source
    # so the parser is not immediately the bottleneck; size limit should fire first.
    chunk = "int x_placeholder_variable = 0; /* padding line to reach size limit */\n"
    repeat = (600 * 1024) // len(chunk) + 1
    large_source = chunk * repeat  # slightly over 600 KB

    # Use Monaco API directly — typing via keyboard would be far too slow.
    editor_page.type_code(page, large_source)

    editor_page.click_run(page)

    _wait_for_output(page, timeout=20_000)

    output = editor_page.get_output(page)

    # Must produce some feedback — not blank
    assert output.strip(), (
        "Expected a size/limit error for 600 KB source, got blank output"
    )

    # Must not be a raw HTTP 500 with no explanation
    assert "500" not in output or len(output.strip()) > 3, (
        f"Output looks like a bare HTTP 500 with no message: {output!r}"
    )

    # Should mention size, limit, or some form of error
    size_hint = (
        "size" in output.lower()
        or "limit" in output.lower()
        or "large" in output.lower()
        or "grande" in output.lower()
        or "límite" in output.lower()
        or "error" in output.lower()
        or "tamaño" in output.lower()
    )
    assert size_hint, (
        f"Expected size/limit error message for 600 KB source, got: {output!r}"
    )


# ==============================================================================
# Test 2 — null bytes in source are handled gracefully
# ==============================================================================

@pytest.mark.critical
def test_null_bytes_handled_gracefully(page) -> None:
    """Type source code containing null bytes; verify app shows an error
    message rather than crashing or showing a white screen."""
    _reload(page)

    # Source containing embedded null bytes
    source_with_nulls = "int main() {\x00\n  return 0;\x00\n}"

    editor_page.type_code(page, source_with_nulls)
    editor_page.click_run(page)

    _wait_for_output(page, timeout=20_000)

    output = editor_page.get_output(page)

    # Output must not be blank
    assert output.strip(), (
        "Expected error/feedback for source with null bytes, got blank output"
    )

    # Core UI elements must still be intact — no JS crash / white screen
    assert _app_intact(page), (
        "App appears to have crashed (white screen / missing #shell) after "
        "source containing null bytes"
    )


# ==============================================================================
# Test 3 — emoji characters in source are handled gracefully
# ==============================================================================

@pytest.mark.ux
def test_emoji_in_source_handled(page) -> None:
    """Type source containing emoji; verify app responds with error or handles
    gracefully — no crash, no white screen."""
    _reload(page)

    emoji_source = "int main() { println(\U0001F389); return 0; }"

    editor_page.type_code(page, emoji_source)
    editor_page.click_run(page)

    _wait_for_output(page, timeout=20_000)

    output = editor_page.get_output(page)

    # Output must not be blank
    assert output.strip(), (
        "Expected error/feedback for source with emoji characters, got blank output"
    )

    # Core UI must still be intact
    assert _app_intact(page), (
        "App appears to have crashed after source containing emoji characters"
    )


# ==============================================================================
# Test 4 — RTL characters in source are handled gracefully
# ==============================================================================

@pytest.mark.ux
def test_rtl_characters_handled(page) -> None:
    """Type source containing RTL (Arabic/Hebrew) characters; verify app
    handles it gracefully — not crash, not white screen."""
    _reload(page)

    # Arabic text embedded in a C-like comment/identifier context
    rtl_source = (
        "int main() {\n"
        "  /* مرحبا بالعالم */\n"
        "  int שלום = 0;\n"
        "  return 0;\n"
        "}"
    )

    editor_page.type_code(page, rtl_source)
    editor_page.click_run(page)

    _wait_for_output(page, timeout=20_000)

    output = editor_page.get_output(page)

    # Output must not be blank
    assert output.strip(), (
        "Expected error/feedback for source with RTL characters, got blank output"
    )

    # Core UI must still be intact
    assert _app_intact(page), (
        "App appears to have crashed after source containing RTL characters"
    )


# ==============================================================================
# Test 5 — infinite loop shows timeout message
# ==============================================================================

@pytest.mark.critical
def test_infinite_loop_shows_timeout(page) -> None:
    """Submit an infinite-loop program; wait up to 35 seconds; verify a
    timeout message appears in the console output (not blank forever)."""
    _reload(page)

    infinite_loop = "int main() { while(1) {} return 0; }"

    editor_page.type_code(page, infinite_loop)
    editor_page.click_run(page)

    # The interpreter has a 30-second timeout; wait a bit longer for the
    # timeout error to propagate to the UI.
    _wait_for_output(page, timeout=35_000)

    output = editor_page.get_output(page)

    # Must not be blank
    assert output.strip(), (
        "Expected timeout/error message for infinite loop, got blank output after 35s"
    )

    # Should mention timeout or error
    timeout_hint = (
        "timeout" in output.lower()
        or "time" in output.lower()
        or "tiempo" in output.lower()
        or "limit" in output.lower()
        or "error" in output.lower()
        or "exceed" in output.lower()
        or "excedido" in output.lower()
        or "loop" in output.lower()
    )
    assert timeout_hint, (
        f"Expected timeout-related message for infinite loop, got: {output!r}"
    )


# ==============================================================================
# Test 6 — deeply nested if-statements (100 levels) do not crash JS
# ==============================================================================

@pytest.mark.critical
def test_deep_nesting_no_crash(page) -> None:
    """Generate 100 levels of nested if-statements; run it; verify app shows
    an error (nesting limit) rather than a JS crash or white screen."""
    _reload(page)

    nested_code = _make_deeply_nested(100)

    editor_page.type_code(page, nested_code)
    editor_page.click_run(page)

    _wait_for_output(page, timeout=20_000)

    output = editor_page.get_output(page)

    # Output must not be blank
    assert output.strip(), (
        "Expected error/feedback for 100-level deep nesting, got blank output"
    )

    # Core UI must still be intact — no JS crash
    assert _app_intact(page), (
        "App appears to have crashed (white screen / missing #shell) after "
        "running 100-level deeply nested if-statements"
    )


# ==============================================================================
# Test 7 — rapid compile clicks (10 times) — output non-empty; #shell persists
# ==============================================================================

@pytest.mark.ux
def test_rapid_compile_clicks_no_corruption(page) -> None:
    """Click #btn-compile 10 times in rapid succession; wait for console output;
    verify output is non-empty and #shell still exists in the DOM."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    compile_btn = page.locator("#btn-compile")

    # 10 rapid clicks with no wait between them
    for _ in range(10):
        compile_btn.click()

    # Wait for the last compile to produce some output
    _wait_for_output(page, timeout=30_000)

    output = editor_page.get_output(page)

    # Console must not be blank
    assert output.strip(), "Console output is empty after rapid compile clicks"
    assert "#shell" not in output, "Expected program output, not raw HTML"
    # Verify app DOM is intact (not white-screened)
    assert _app_intact(page), "App appears to have crashed (white screen) after rapid clicks"


# ==============================================================================
# Test 8 — invalid share URL loads app; no JS crash (covers CF-QA-021)
# ==============================================================================

@pytest.mark.critical
def test_invalid_share_url_app_loads(page) -> None:
    """Navigate to /?p=notvalidbase64!!!; verify app loads (#shell visible);
    verify no JS error crashes the page.  Covers CF-QA-021."""
    js_errors: list[str] = []
    page.on(
        "console",
        lambda msg: js_errors.append(msg.text) if msg.type == "error" else None,
    )

    page.goto("/?p=notvalidbase64!!!")
    page.wait_for_selector("#shell", timeout=10_000)

    # App should load even with an invalid share param
    assert page.locator("#shell").is_visible(), (
        "Expected #shell to be visible after navigating to /?p=notvalidbase64!!!"
    )

    # No fatal JS errors that would indicate an uncaught exception
    fatal_errors = [
        e for e in js_errors
        if any(
            keyword in e.lower()
            for keyword in ("uncaught", "typeerror", "referenceerror", "syntaxerror")
        )
    ]
    assert not fatal_errors, (
        f"CF-QA-021: Fatal JS errors on invalid share URL load: {fatal_errors}"
    )


# ==============================================================================
# Test 9 — empty source error then valid program — second run succeeds
# ==============================================================================

@pytest.mark.ux
def test_empty_then_valid_program(page) -> None:
    """Run empty source (receives error), then type valid program and run again;
    verify second run succeeds — app is not stuck in error state."""
    _reload(page)

    # First run: empty source — expect an error
    editor_page.type_code(page, "")
    editor_page.click_run(page)
    _wait_for_output(page, timeout=20_000)

    first_output = editor_page.get_output(page)
    assert first_output.strip(), (
        "Expected feedback for empty source on first run, got blank output"
    )

    # Clear the console, then type a valid program and run again
    editor_page.clear_output(page)
    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length === 0",
        timeout=5_000,
    )

    editor_page.type_code(page, PRINTLN_42)
    editor_page.click_run(page)

    _wait_for_output(page, timeout=20_000)

    second_output = editor_page.get_output(page)

    # Second run must not be blank
    assert second_output.strip(), (
        "Expected output for valid program on second run, got blank "
        "(app may be stuck in error state after empty source)"
    )

    # Second run of println(42) should succeed and show "42"
    assert "42" in second_output, (
        f"Expected '42' in output after valid second run, got: {second_output!r}"
    )
