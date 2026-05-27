"""
Page Object Model — Monaco editor interactions.

DOM landmarks (from index.html + main.js):
  #editor-container   — Monaco host div (hidden by default; visible when "Código" tab active)
  #btn-compile        — trigger compile pipeline
  #btn-run            — trigger run/interpret pipeline
  #console-output     — <pre> element with all console text
  #btn-clear-console  — clears the console

Monaco global: the editor instance is accessible via
  window.monaco.editor.getEditors()[0]   — canonical API
  (there is no window.__monacoEditor export; use the monaco namespace)
"""

from __future__ import annotations

from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_code_tab(page: Page) -> None:
    """Switch to the Code (Monaco) tab if not already active."""
    tab = page.locator('[data-target="editor-container"]')
    # Only click if the editor container is hidden (i.e. tab not active)
    editor_container = page.locator('#editor-container')
    if 'hidden' in (editor_container.get_attribute('class') or ''):
        tab.click()
        page.wait_for_selector('#editor-container:not(.hidden)', timeout=5_000)


def _get_monaco_value(page: Page) -> str:
    """Return current Monaco editor value using the monaco namespace."""
    return page.evaluate(
        """
        () => {
            if (window.monaco && window.monaco.editor) {
                const editors = window.monaco.editor.getEditors();
                if (editors && editors.length > 0) return editors[0].getValue();
            }
            return '';
        }
        """
    )


def _set_monaco_value(page: Page, code: str) -> None:
    """
    Set Monaco editor value.

    Primary path: use the Monaco API directly via window.monaco.
    Fallback: focus the editor textarea and use Ctrl+A + type.
    """
    set_ok: bool = page.evaluate(
        """
        (code) => {
            if (window.monaco && window.monaco.editor) {
                const editors = window.monaco.editor.getEditors();
                if (editors && editors.length > 0) {
                    editors[0].setValue(code);
                    return true;
                }
            }
            return false;
        }
        """,
        code,
    )

    if not set_ok:
        # Fallback: keyboard approach — focus the hidden textarea Monaco uses
        textarea = page.locator('#editor-container .monaco-editor textarea').first
        textarea.click()
        page.keyboard.press('Control+A')
        page.keyboard.type(code)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def type_code(page: Page, code: str) -> None:
    """
    Switch to the Code tab, clear Monaco editor, and set *code* as new content.

    Uses the Monaco API when available; falls back to keyboard Ctrl+A + type.
    """
    _ensure_code_tab(page)
    _set_monaco_value(page, code)


def get_code(page: Page) -> str:
    """Return the current content of the Monaco editor."""
    _ensure_code_tab(page)
    return _get_monaco_value(page)


def click_compile(page: Page) -> None:
    """
    Click #btn-compile and wait for the console output to change
    (indicating the compile pipeline has produced a result).
    """
    btn = page.locator('#btn-compile')
    btn.click()
    # Wait up to 30 s for console-output to gain non-empty text
    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=30_000,
    )


def click_run(page: Page) -> None:
    """Click #btn-run (triggers the interpreter pipeline)."""
    page.locator('#btn-run').click()


def get_output(page: Page) -> str:
    """Return the full text content of #console-output."""
    return page.locator('#console-output').text_content() or ''


def clear_output(page: Page) -> None:
    """Click #btn-clear-console to wipe the console output."""
    page.locator('#btn-clear-console').click()


def get_error_messages(page: Page) -> list[str]:
    """
    Return lines from #console-output that look like errors.

    A line is considered an error if:
      - it starts with '[error]'  (case-insensitive), or
      - it starts with '[severity] ... error ...' patterns used by compile(),
      - the #console-output element carries the 'has-errors' CSS class.

    Returns a list of stripped lines (may be empty if no errors).
    """
    raw: str = get_output(page)
    has_errors_class: bool = page.evaluate(
        "document.getElementById('console-output')?.classList.contains('has-errors') ?? false"
    )

    error_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith('[error]') or lower.startswith('[error '):
            error_lines.append(stripped)
        elif has_errors_class and stripped:
            # When the element has the has-errors class, every non-empty line
            # inside is considered error output.
            error_lines.append(stripped)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for ln in error_lines:
        if ln not in seen:
            seen.add(ln)
            unique.append(ln)
    return unique
