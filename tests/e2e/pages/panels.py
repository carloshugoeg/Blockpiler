"""
Page Object Model — Right-side panels (AST, ASM, Debug, Explain).

DOM landmarks (from index.html + main.js):
  #btn-asm          — toolbar button; clicking it calls activateRightPanel('asm-container')
  #btn-ast          — toolbar button; clicking it calls activateRightPanel('ast-container')
  #btn-debug        — toolbar button; opens debug panel
  #ast-container    — right panel content div (visible by default after compile)
  #asm-container    — right panel content div (hidden by default)
  #debug-container  — right panel content div (hidden by default); populated by Debugger.mountUI
  #console-output   — <pre> in the console footer

  Debug variable rows:
    .dbg-variables     — container div
      .dbg-var-row     — one row per variable
        .dbg-var-name  — variable name span
        .dbg-var-value — variable value span
"""

from __future__ import annotations

from playwright.sync_api import Page

# Re-use editor.get_output to avoid duplication
from tests.e2e.pages.editor import get_output


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_asm_lines(page: Page) -> list[str]:
    """
    Click #btn-asm (which makes #asm-container visible) and return the
    assembly lines displayed in that panel.

    The AsmPanel renders assembly as text inside #asm-container.  We
    return each non-empty line as a string.

    Raises RuntimeError if the ASM button is disabled (requires compilation first).
    """
    btn_asm = page.locator('#btn-asm')
    if not btn_asm.is_enabled():
        raise RuntimeError("ASM button is disabled; compile first")
    btn_asm.click()
    # Wait for asm-container to become visible
    page.wait_for_selector('#asm-container:not(.hidden)', timeout=5_000)

    raw: str = page.locator('#asm-container').inner_text()
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    return lines


def get_ast_visible(page: Page) -> bool:
    """
    Return True if #ast-container is currently visible (i.e. does NOT have
    the 'hidden' CSS class).
    """
    css_classes: str = page.locator('#ast-container').get_attribute('class') or ''
    return 'hidden' not in css_classes


def get_debug_vars(page: Page) -> dict[str, str]:
    """
    Return a dict of variable name → value strings from the debug panel.

    The Debugger.mountUI() renders each variable as a .dbg-var-row inside
    .dbg-variables, with .dbg-var-name and .dbg-var-value spans.

    If the debug panel has no variable rows yet, an empty dict is returned.
    """
    rows = page.locator('#debug-container .dbg-var-row')
    count = rows.count()
    result: dict[str, str] = {}
    for i in range(count):
        row = rows.nth(i)
        name = (row.locator('.dbg-var-name').text_content() or '').strip()
        value = (row.locator('.dbg-var-value').text_content() or '').strip()
        if name:
            result[name] = value
    return result


def get_console_text(page: Page) -> str:
    """
    Alias for editor.get_output — returns the full text of #console-output.
    """
    return get_output(page)
