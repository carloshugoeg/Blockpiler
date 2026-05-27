"""
E2E tests — step-through debugger.

Tests 1-5 cover:
  1. Click #btn-debug makes #debug-container visible
  2. Debug panel shows Step/Continue/Stop controls after opening
  3. Stepping through a program with variables shows a variable in the inspector
  4. Invalid program shows an error in the debug panel or console (CF-QA-020)
  5. Stopping the debugger returns controls to their initial state

Note: The debugger relies on WebSocket (/ws/debug via Socket.IO) for real-time
state updates.  CF-QA-019 and CF-QA-020 document known bugs; these tests are
written to document *expected* behaviour even when the debugger has active bugs.
"""

from __future__ import annotations

import pytest

from tests.e2e.pages import editor as editor_page
from tests.e2e.pages import panels as panels_page


# ── Shared programs ────────────────────────────────────────────────────────────

DEBUG_SIMPLE = (
    "int main() {\n"
    "  int x = 5;\n"
    "  x = x + 3;\n"
    "  println(x);\n"
    "  return 0;\n"
    "}"
)

INVALID_PROG = "int main() { else { } return 0; }"


# ── Test helpers ───────────────────────────────────────────────────────────────

def _reload(page) -> None:
    """Navigate to the app root and wait for the shell to be ready."""
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)


def _open_debug_panel(page) -> None:
    """Click #btn-debug and wait for #debug-container to become visible."""
    page.locator("#btn-debug").click()
    page.wait_for_selector("#debug-container:not(.hidden)", timeout=5_000)


# ==============================================================================
# Test 1 — clicking #btn-debug makes #debug-container visible
# ==============================================================================

@pytest.mark.critical
def test_debug_panel_opens(page) -> None:
    """Click #btn-debug; verify #debug-container loses the 'hidden' class."""
    _reload(page)

    # Before clicking, the debug-container should be hidden
    debug_container = page.locator("#debug-container")
    initial_classes = debug_container.get_attribute("class") or ""
    assert "hidden" in initial_classes, (
        f"Expected #debug-container to be hidden before opening; classes: {initial_classes!r}"
    )

    # Click the debug button
    page.locator("#btn-debug").click()

    # The container must become visible (i.e. lose the 'hidden' class)
    page.wait_for_selector("#debug-container:not(.hidden)", timeout=5_000)

    final_classes = debug_container.get_attribute("class") or ""
    assert "hidden" not in final_classes, (
        f"Expected #debug-container to be visible after #btn-debug click; classes: {final_classes!r}"
    )


# ==============================================================================
# Test 2 — debug panel shows Step/Continue/Stop controls
# ==============================================================================

@pytest.mark.critical
def test_debug_start_shows_controls(page) -> None:
    """Type a simple program, open the debug panel, verify Step/Continue/Stop
    buttons are present inside #debug-container."""
    _reload(page)

    editor_page.type_code(page, DEBUG_SIMPLE)
    _open_debug_panel(page)

    # The Debugger.mountUI() creates three buttons: Step, Continue, Stop
    # inside a .dbg-controls div inside #debug-container.
    controls = page.locator("#debug-container button")

    # Wait for at least one button to appear
    page.wait_for_selector("#debug-container button", timeout=5_000)

    button_count = controls.count()
    assert button_count >= 3, (
        f"Expected at least 3 control buttons (Step/Continue/Stop) in debug panel, "
        f"got {button_count}"
    )

    # Collect button labels for a more specific check
    labels = [
        (controls.nth(i).text_content() or "").strip()
        for i in range(button_count)
    ]
    label_text = " ".join(labels).lower()

    assert "step" in label_text, (
        f"Expected a 'Step' button in debug controls; found labels: {labels!r}"
    )
    assert "stop" in label_text or "continue" in label_text, (
        f"Expected 'Stop' or 'Continue' button in debug controls; found labels: {labels!r}"
    )


# ==============================================================================
# Test 3 — stepping updates the variable inspector
# ==============================================================================

@pytest.mark.ux
def test_debug_step_updates_variables(page) -> None:
    """Type a program that declares int x, start the debugger, click Step,
    and verify that the variable inspector panel shows at least one variable."""
    _reload(page)

    editor_page.type_code(page, DEBUG_SIMPLE)
    _open_debug_panel(page)

    # Wait for the debug UI to be mounted (buttons present)
    page.wait_for_selector("#debug-container button", timeout=5_000)

    # Click the first button (Step) to advance one statement
    step_btn = page.locator("#debug-container button").first
    step_btn.click()

    # Give the WebSocket a moment to respond with a debug:state event
    page.wait_for_timeout(2_000)

    # Check for variable rows rendered by _updateVariablesPanel
    # The Debugger renders .dbg-var-row elements inside .dbg-variables
    vars_dict = panels_page.get_debug_vars(page)

    # The test documents *expected* behaviour: at least one variable should be
    # visible after stepping.  If the debugger is not yet functional (CF-QA-019),
    # this test will fail and a QA issue will be recorded.
    assert len(vars_dict) >= 1, (
        f"Expected at least one variable in the debug inspector after Step, "
        f"got: {vars_dict!r}. "
        f"(This may be CF-QA-019 — WebSocket debug state not received.)"
    )


# ==============================================================================
# Test 4 — invalid program shows error, not silent failure (CF-QA-020)
# ==============================================================================

@pytest.mark.ux
def test_debug_error_shown_not_swallowed(page) -> None:
    """Type an invalid program (bare 'else'), click #btn-debug, and verify that
    an error appears either in the debug container or in the console output.

    This covers CF-QA-020: debug errors must be surfaced, not silently dropped."""
    _reload(page)

    editor_page.type_code(page, INVALID_PROG)

    page.locator("#btn-debug").click()
    # Allow a brief moment for async error delivery
    page.wait_for_timeout(3_000)

    debug_text = (page.locator("#debug-container").inner_text() or "").lower()
    console_text = (editor_page.get_output(page) or "").lower()

    has_error_in_debug = any(
        kw in debug_text
        for kw in ("error", "err", "syntax", "else", "par", "sem", "lex", "invalid")
    )
    has_error_in_console = any(
        kw in console_text
        for kw in ("error", "err", "syntax", "else", "par", "sem", "lex", "invalid")
    )

    assert has_error_in_debug or has_error_in_console, (
        "Expected an error to be surfaced in the debug panel or console for an invalid program. "
        f"Debug panel text: {debug_text!r}. Console text: {console_text!r}. "
        "(This may indicate CF-QA-020 — debug errors are silently swallowed.)"
    )


# ==============================================================================
# Test 5 — stopping the debugger returns controls to initial (non-active) state
# ==============================================================================

@pytest.mark.ux
def test_debug_stop_clears_state(page) -> None:
    """Start the debugger, then click Stop; verify that the variable panel is
    empty (or the debug state is cleared) and the layout is in a stable state."""
    _reload(page)

    editor_page.type_code(page, DEBUG_SIMPLE)
    _open_debug_panel(page)

    # Wait for control buttons to appear
    page.wait_for_selector("#debug-container button", timeout=5_000)

    # Find and click the Stop button (last of the three controls created by mountUI)
    buttons = page.locator("#debug-container button")
    stop_btn = None
    for i in range(buttons.count()):
        label = (buttons.nth(i).text_content() or "").strip().lower()
        if label == "stop":
            stop_btn = buttons.nth(i)
            break

    if stop_btn is None:
        # Fallback: use the last button in the control group
        stop_btn = buttons.last

    stop_btn.click()

    # Allow a short moment for cleanup to propagate
    page.wait_for_timeout(1_000)

    # After Stop: the variable panel should be empty (no .dbg-var-row elements)
    # because _clearHighlight() and socket disconnect are called.
    vars_after_stop = panels_page.get_debug_vars(page)

    # The variable panel should be cleared.  If it is not empty the debugger
    # did not clean up, which is a UX bug.
    assert len(vars_after_stop) == 0, (
        f"Expected variable inspector to be empty after Stop; "
        f"found variables: {vars_after_stop!r}"
    )

    # The shell and debug container must still exist (no DOM crash)
    assert page.locator("#shell").count() > 0, (
        "Expected #shell to still exist after debug Stop"
    )
    assert page.locator("#debug-container").count() > 0, (
        "Expected #debug-container to still exist after debug Stop"
    )
