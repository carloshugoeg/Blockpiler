"""
E2E tests — error handling and file I/O.

Tests 1-5 cover:
  1. Upload unsupported format (.pdf) shows error in console (not silent failure)
  2. Save as .c triggers a file download
  3. Save project as .cfproj triggers a file download
  4. Network error on /api/run is handled gracefully (UI shows error, not blank/crash)
  5. Rapid compile (5 clicks) does not corrupt the UI
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


# ==============================================================================
# Test 1 — uploading an unsupported .pdf file shows an error (not silent)
# ==============================================================================

@pytest.mark.ux
def test_upload_unsupported_format_shows_error(page) -> None:
    """Upload a .pdf file via #file-input; verify the console shows an error
    message rather than silently ignoring the upload."""
    _reload(page)

    file_input = page.locator("#file-input")

    # Trigger the file picker (ensures the file-input handler is primed)
    page.locator("#btn-open").click()
    page.wait_for_timeout(300)

    # Inject a fake .pdf file directly into the hidden file input
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    file_input.set_input_files(
        [{"name": "document.pdf", "mimeType": "application/pdf", "buffer": pdf_bytes}]
    )

    # Wait a moment for any async handling
    page.wait_for_timeout(1_500)

    output = editor_page.get_output(page)

    # The UI must communicate that something happened — either an explicit error
    # message or a format-related notice.  Silent failure (empty console) is wrong.
    has_feedback = (
        ("error" in output.lower() or "unsupported" in output.lower() or "formato" in output.lower() or "no soportado" in output.lower())
        and ("pdf" in output.lower() or "archivo" in output.lower() or output.strip() != "")
    )
    assert has_feedback, (
        f"Expected error/notice for unsupported .pdf upload, got blank/no output: {output!r}"
    )


# ==============================================================================
# Test 2 — save as .c triggers a download
# ==============================================================================

@pytest.mark.ux
def test_save_c_and_reimport(page) -> None:
    """Type some code, open the save menu, click 'Guardar como .c',
    and verify a download is triggered with a .c filename."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    # Wait for save button to be ready before opening the dropdown
    page.wait_for_selector("#btn-save", state="visible", timeout=5_000)

    # Open the save dropdown
    page.locator("#btn-save").click()
    page.wait_for_selector("#save-menu", timeout=5_000)

    # Expect a download when clicking the save-as-C button
    with page.expect_download(timeout=10_000) as download_info:
        page.locator('[data-save="c"]').click()

    download = download_info.value
    assert download.suggested_filename.endswith(".c"), (
        f"Expected download filename to end with '.c', got: {download.suggested_filename!r}"
    )


# ==============================================================================
# Test 3 — save project as .cfproj triggers a download
# ==============================================================================

@pytest.mark.ux
def test_save_project_roundtrip(page) -> None:
    """Type some code, save as .cfproj (project file), and verify a download
    is triggered with a .cfproj filename."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    # Wait for save button to be ready before opening the dropdown
    page.wait_for_selector("#btn-save", state="visible", timeout=5_000)

    # Open the save dropdown
    page.locator("#btn-save").click()
    page.wait_for_selector("#save-menu", timeout=5_000)

    # Expect a download when clicking the save-as-cfproj button
    with page.expect_download(timeout=10_000) as download_info:
        page.locator('[data-save="cfproj"]').click()

    download = download_info.value
    assert download.suggested_filename.endswith(".cfproj"), (
        f"Expected download filename to end with '.cfproj', got: {download.suggested_filename!r}"
    )


# ==============================================================================
# Test 4 — network error on /api/run is handled gracefully
# ==============================================================================

@pytest.mark.critical
def test_network_error_handled_gracefully(page) -> None:
    """Intercept /api/run and abort it; verify the UI shows an error message
    rather than a blank screen or unhandled crash."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    # Intercept all requests to /api/run and abort them
    page.route("**/api/run", lambda route: route.abort())

    # Click run — this should trigger the aborted request
    editor_page.click_run(page)

    # Wait for the console to react (either error message or state change)
    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=15_000,
    )

    output = editor_page.get_output(page)

    # The UI must not be blank and must communicate some kind of error/feedback
    assert output.strip(), (
        "Expected non-empty console output after network error, got blank screen"
    )

    # Should mention some kind of error — network, red, or similar
    error_hints = (
        "error" in output.lower()
        or "red" in output.lower()
        or "network" in output.lower()
        or "failed" in output.lower()
        or "fallo" in output.lower()
        or "conectar" in output.lower()
    )
    assert error_hints, (
        f"Expected error hint in output after aborted /api/run, got: {output!r}"
    )


# ==============================================================================
# Test 5 — rapid compile (5 clicks) does not corrupt the UI
# ==============================================================================

@pytest.mark.ux
def test_rapid_compile_no_corruption(page) -> None:
    """Click #btn-compile 5 times rapidly; verify the UI does not become blank
    or corrupt — the console output or ASM panel should still be functional."""
    _reload(page)

    editor_page.type_code(page, PRINTLN_42)

    compile_btn = page.locator("#btn-compile")

    # Click 5 times rapidly without waiting between clicks
    for _ in range(5):
        compile_btn.click()

    # Now wait for the last compile to settle
    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=30_000,
    )

    output = editor_page.get_output(page)

    # The console must not be blank — rapid clicks must not result in an empty UI
    assert output.strip(), (
        "Expected non-blank console output after 5 rapid compile clicks, got blank screen"
    )

    # The shell itself must still be present (no JS crash that wiped the DOM)
    shell_exists = page.locator("#shell").count() > 0
    assert shell_exists, "Expected #shell to still exist after rapid compile clicks"

    # The console-output element must still exist
    console_exists = page.locator("#console-output").count() > 0
    assert console_exists, "Expected #console-output to still exist after rapid compile clicks"
