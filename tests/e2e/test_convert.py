"""
E2E tests — C ↔ Blocks conversion.

Tests cover:
  1. Type simple C code, switch to Blockly tab, verify block count > 0
  2. Switch to Blockly then back to Code, verify editor has non-empty code
  3. Type CompileFlow code, roundtrip through Blockly, verify no #include/printf
     (covers CF-QA-004)
  4. Roundtrip simple program and verify the result is runnable (no HTTP 500)
  5. Direct API: POST c_to_blocks, verify ok:true and workspace field
  6. Direct API: POST blocks_to_c with minimal workspace, verify ok:true and
     source field
"""

from __future__ import annotations

import pytest
import requests

from tests.e2e.pages import editor as editor_page
from tests.e2e.pages import blocks as blocks_page

# ── Base URLs ──────────────────────────────────────────────────────────────────
FLASK = "http://localhost:5000"

# ── Shared test programs ───────────────────────────────────────────────────────
PRINTLN_42 = "int main() {\n  println(42);\n  return 0;\n}"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _reload(page) -> None:
    """Navigate to the app root and wait for #shell to be ready."""
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)


# ==============================================================================
# Test 1 — typing C code and switching to Blockly renders blocks
# ==============================================================================

@pytest.mark.critical
def test_c_to_blocks_renders_blocks(page) -> None:
    """Type a simple println program, switch to the Blockly tab, verify that
    at least one top-level block is present in the workspace."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    blocks_page.switch_to_blocks(page)
    # Give the IDE→Blocks sync a moment to complete
    page.wait_for_timeout(1_000)

    count = blocks_page.get_block_count(page)
    assert count > 0, (
        f"Expected at least one block in Blockly workspace after C→Blocks "
        f"conversion, but got {count}"
    )


# ==============================================================================
# Test 2 — switching to Blockly then back to Code preserves non-empty code
# ==============================================================================

@pytest.mark.critical
def test_blocks_to_c_produces_valid_code(page) -> None:
    """Switch to the Blockly tab first, then switch back to the Code tab.
    Verify the Monaco editor contains non-empty code (not just whitespace)."""
    _reload(page)

    # Start on the Blockly tab (it is the default, but be explicit)
    blocks_page.switch_to_blocks(page)
    page.wait_for_timeout(500)

    # Switch back to Code — this triggers the Blocks→IDE sync
    code = blocks_page.convert_to_code(page)

    # The editor must have some content (even an empty workspace may produce
    # a skeleton; we accept any non-whitespace-only string)
    assert code.strip(), (
        "Expected Monaco editor to contain non-empty code after switching "
        f"Blockly→Code, but got: {code!r}"
    )


# ==============================================================================
# Test 3 — roundtrip does not inject #include / printf (CF-QA-004)
# ==============================================================================

@pytest.mark.critical
def test_c_to_blocks_no_printf_injection(page) -> None:
    """Type CompileFlow source, switch to Blockly (IDE→Blocks), switch back
    to Code (Blocks→IDE).  The resulting source must NOT contain '#include'
    or 'printf' — those are C artefacts, not CompileFlow syntax."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    # IDE → Blocks
    blocks_page.switch_to_blocks(page)
    page.wait_for_timeout(1_000)

    # Blocks → IDE
    code_after = blocks_page.convert_to_code(page)

    assert "#include" not in code_after, (
        "Blockly→IDE sync corrupted the source by adding '#include <stdio.h>'"
    )
    assert "printf" not in code_after, (
        "Blockly→IDE sync corrupted the source by replacing 'println' with 'printf'"
    )


# ==============================================================================
# Test 4 — roundtrip simple program compiles without HTTP 500
# ==============================================================================

@pytest.mark.ux
def test_roundtrip_simple_program(page) -> None:
    """Type a simple program, go to Blockly, return to Code, then run the
    resulting code via /api/run.  The endpoint must NOT return HTTP 500 or
    crash — the roundtripped program must still be interpretable."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    # IDE → Blocks → IDE roundtrip
    blocks_page.switch_to_blocks(page)
    page.wait_for_timeout(1_000)
    code_after = blocks_page.convert_to_code(page)

    # POST the roundtripped code to /api/run and check for no HTTP 500
    resp = requests.post(
        f"{FLASK}/api/run",
        json={"source": code_after},
        timeout=20,
    )
    assert resp.status_code != 500, (
        f"Roundtripped program caused HTTP 500 on /api/run. "
        f"Source after roundtrip: {code_after!r}"
    )
    # The response must be valid JSON — no crash
    data = resp.json()
    assert isinstance(data, dict), (
        f"Expected JSON dict from /api/run, got: {data!r}"
    )


# ==============================================================================
# Test 5 — direct API: POST c_to_blocks returns ok:true and workspace field
# ==============================================================================

@pytest.mark.critical
def test_convert_api_c_to_blocks(page) -> None:  # noqa: ARG001
    """Direct API test (page fixture ensures servers are running).

    POST /api/convert with direction='c_to_blocks' and a simple program;
    verify the response has ok=True and a 'workspace' field in the data."""
    resp = requests.post(
        f"{FLASK}/api/convert",
        json={
            "direction": "c_to_blocks",
            "source": PRINTLN_42,
        },
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"Expected HTTP 200 from /api/convert c_to_blocks, got {resp.status_code}"
    )
    data = resp.json()
    assert data.get("ok") is True, (
        f"Expected ok=True from /api/convert c_to_blocks, got: {data!r}"
    )
    # workspace may be nested inside 'data' key or at the top level
    workspace = data.get("data", {}).get("workspace") or data.get("workspace")
    assert workspace is not None, (
        f"Expected 'workspace' field in /api/convert c_to_blocks response, "
        f"got: {data!r}"
    )


# ==============================================================================
# Test 6 — direct API: POST blocks_to_c returns ok:true and source field
# ==============================================================================

@pytest.mark.critical
def test_convert_api_blocks_to_c(page) -> None:  # noqa: ARG001
    """Direct API test (page fixture ensures servers are running).

    POST /api/convert with direction='blocks_to_c' and a minimal valid
    workspace JSON; verify the response has ok=True and a 'source' field."""
    workspace = {
        "blocks": {
            "languageVersion": 0,
            "blocks": [],
        }
    }
    resp = requests.post(
        f"{FLASK}/api/convert",
        json={
            "direction": "blocks_to_c",
            "workspace": workspace,
        },
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"Expected HTTP 200 from /api/convert blocks_to_c, got {resp.status_code}"
    )
    data = resp.json()
    assert data.get("ok") is True, (
        f"Expected ok=True from /api/convert blocks_to_c, got: {data!r}"
    )
    # source may be nested inside 'data' key or at the top level
    source = data.get("data", {}).get("source") if "data" in data else data.get("source")
    assert source is not None, (
        f"Expected 'source' field in /api/convert blocks_to_c response, "
        f"got: {data!r}"
    )
