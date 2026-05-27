"""
Page Object Model — Blockly workspace interactions.

DOM landmarks (from index.html + main.js):
  #left-tabs                      — container for tab buttons
  [data-target="editor-container"] — tab button for Monaco ("Código")
  [data-target="blocks-container"] — tab button for Blockly ("Blockly")
  #blocks-container               — Blockly host div (active by default)
  #editor-container               — Monaco host div (hidden by default)

Blockly global: the workspace instance is the return value of
  Blockly.inject(...)  stored in the module-level `workspace` variable
  inside blockly_setup.js and exposed as getWorkspace().
  The Playwright-visible API is window.Blockly and the workspace can be
  retrieved via Blockly.common.getMainWorkspace() or the getEditors
  pattern below.
"""

from __future__ import annotations

from playwright.sync_api import Page


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_workspace_js(page: Page) -> str:
    """Return a JS expression that resolves to the main Blockly workspace."""
    # Blockly exposes the main workspace through getMainWorkspace() in recent
    # versions.  Fall back to common.getMainWorkspace if needed.
    return "(window.Blockly?.common?.getMainWorkspace?.() ?? window.Blockly?.getMainWorkspace?.())"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def switch_to_blocks(page: Page) -> None:
    """
    Click the Blockly tab button (text "Blockly", data-target="blocks-container")
    and wait for the blocks container to become visible.
    """
    tab = page.locator('[data-target="blocks-container"]')
    tab.click()
    page.wait_for_selector('#blocks-container:not(.hidden)', timeout=5_000)


def switch_to_code(page: Page) -> None:
    """
    Click the Code tab button (data-target="editor-container") and wait for
    the Monaco container to become visible.
    """
    tab = page.locator('[data-target="editor-container"]')
    tab.click()
    page.wait_for_selector('#editor-container:not(.hidden)', timeout=5_000)


def get_block_count(page: Page) -> int:
    """
    Count the number of top-level blocks in the Blockly workspace.

    Uses page.evaluate() to access the Blockly workspace and count
    top-level blocks (getTopBlocks).  Returns 0 if the workspace is not
    yet initialised.
    """
    ws_expr = _get_workspace_js(page)
    count: int = page.evaluate(
        f"""
        () => {{
            const ws = {ws_expr};
            if (!ws || typeof ws.getTopBlocks !== 'function') return 0;
            return ws.getTopBlocks(false).length;
        }}
        """
    )
    return int(count)


def convert_to_code(page: Page) -> str:
    """
    Switch to the Code tab (which triggers the Blocks→IDE sync) and
    return the resulting Monaco editor value.

    The sync is performed by the SyncManager listening on tab-click events
    in main.js (flushBlocksToIde).  We wait for the editor container to
    become visible before reading the value.
    """
    switch_to_code(page)
    # Give the async sync event a moment to fire and complete
    page.wait_for_timeout(300)
    # Now wait for Monaco editor to be available
    page.wait_for_function(
        """
        () => {
            if (window.monaco && window.monaco.editor) {
                const editors = window.monaco.editor.getEditors();
                return editors && editors.length > 0;
            }
            return false;
        }
        """,
        timeout=10_000,
    )
    value: str = page.evaluate(
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
    return value
