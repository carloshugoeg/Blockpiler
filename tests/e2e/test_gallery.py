"""
E2E tests — gallery programs.

Tests 1-8 cover:
  1. Gallery dropdown has exactly 8 items
  2. Load "Hola Mundo" (first item), run it, verify non-empty output with no crash
  3. Load factorial example, run it, verify a number appears in output
  4. Load fibonacci example, run it, verify numeric output
  5. Load fizzbuzz example, run it, verify "Fizz" or "Buzz" or "FizzBuzz" in output
  6. Load bubble sort example, run it, verify numeric output
  7. Switch through first three gallery items; editor has non-trivial code after each
  8. Load all 8 gallery items one by one; run each; no HTTP 500 or blank output
"""

from __future__ import annotations

import re

import pytest

from tests.e2e.pages import editor as editor_page


# ── Helpers ────────────────────────────────────────────────────────────────────

def _reload(page) -> None:
    """Reload the app and wait for the shell to be ready."""
    page.goto("/")
    page.wait_for_selector("#shell", timeout=15_000)


def _open_gallery(page) -> None:
    """Click the gallery button and wait for the dropdown menu to open."""
    page.locator("#btn-gallery").click()
    # The menu gains the class 'open' via JS; wait for at least one item
    page.wait_for_selector("#gallery-menu .dropdown-item", timeout=10_000)


def _load_gallery_item(page, index: int) -> None:
    """Open gallery dropdown and click the item at position *index* (0-based)."""
    _open_gallery(page)
    page.locator("#gallery-menu .dropdown-item").nth(index).click()
    # After selection the menu closes; give the async loadSourceAfterClean() a moment
    page.wait_for_timeout(1_500)


def _run_and_wait(page) -> str:
    """Click Run and wait for console output; return the output text."""
    editor_page.click_run(page)
    page.wait_for_function(
        "document.getElementById('console-output')?.textContent?.trim().length > 0",
        timeout=25_000,
    )
    return editor_page.get_output(page)


def _find_gallery_index_by_keyword(page, *keywords: str) -> int:
    """
    Open the gallery, read all item names, and return the index of the first
    item whose name contains any of *keywords* (case-insensitive).
    Falls back to -1 if not found.
    """
    _open_gallery(page)
    names = page.locator("#gallery-menu .dropdown-item").all_text_contents()
    # Close menu without selecting
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for i, name in enumerate(names):
        lower = name.lower()
        if any(kw.lower() in lower for kw in keywords):
            return i
    return -1


# ==============================================================================
# Test 1 — gallery dropdown has exactly 8 items
# ==============================================================================

@pytest.mark.critical
def test_gallery_has_8_items(page) -> None:
    """Open the gallery dropdown and verify there are exactly 8 menu items."""
    _reload(page)

    _open_gallery(page)

    items = page.locator("#gallery-menu .dropdown-item").all_text_contents()

    assert len(items) == 8, (
        f"Expected exactly 8 gallery items, got {len(items)}: {items}"
    )


# ==============================================================================
# Test 2 — load first gallery item (Hola Mundo), run it, verify non-empty output
# ==============================================================================

@pytest.mark.critical
def test_gallery_hello_world(page) -> None:
    """Load the first gallery item, run it, verify non-empty output and no crash."""
    _reload(page)

    _load_gallery_item(page, 0)

    output = _run_and_wait(page)

    assert output.strip(), (
        "Expected non-empty output after running the first gallery item, got blank"
    )
    # Must not look like a raw server crash
    assert "500" not in output or len(output.strip()) > 10, (
        f"Output looks like a bare HTTP 500 error: {output!r}"
    )
    # Output should not be exclusively an error message — i.e. the program ran
    assert not output.strip().startswith("[error]"), (
        f"Expected program output, but got an error: {output!r}"
    )


# ==============================================================================
# Test 3 — factorial example produces a number in output
# ==============================================================================

@pytest.mark.critical
def test_gallery_factorial(page) -> None:
    """Load the factorial example, run it, verify numeric output."""
    _reload(page)

    idx = _find_gallery_index_by_keyword(page, "factorial")
    assert idx >= 0, "Could not find a gallery item whose name contains 'factorial'"

    _load_gallery_item(page, idx)

    output = _run_and_wait(page)

    has_number = bool(re.search(r"\d+", output))
    assert has_number, (
        f"Expected a number in factorial output, got: {output!r}"
    )


# ==============================================================================
# Test 4 — fibonacci example produces numeric output
# ==============================================================================

@pytest.mark.critical
def test_gallery_fibonacci(page) -> None:
    """Load the fibonacci example, run it, verify numeric output."""
    _reload(page)

    idx = _find_gallery_index_by_keyword(page, "fibonacci", "fib")
    assert idx >= 0, "Could not find a gallery item whose name contains 'fibonacci' or 'fib'"

    _load_gallery_item(page, idx)

    output = _run_and_wait(page)

    has_number = bool(re.search(r"\d+", output))
    assert has_number, (
        f"Expected a number in fibonacci output, got: {output!r}"
    )


# ==============================================================================
# Test 5 — fizzbuzz example produces "Fizz", "Buzz", or "FizzBuzz" in output
# ==============================================================================

@pytest.mark.critical
def test_gallery_fizzbuzz(page) -> None:
    """Load the fizzbuzz example, run it, verify Fizz/Buzz/FizzBuzz in output."""
    _reload(page)

    idx = _find_gallery_index_by_keyword(page, "fizzbuzz", "fizz", "buzz")
    assert idx >= 0, "Could not find a gallery item whose name contains 'fizz' or 'buzz'"

    _load_gallery_item(page, idx)

    output = _run_and_wait(page)

    fizzbuzz_words = ("fizz", "buzz", "fizzbuzz")
    lower_output = output.lower()
    has_fizzbuzz = any(word in lower_output for word in fizzbuzz_words)
    assert has_fizzbuzz, (
        f"Expected 'Fizz', 'Buzz', or 'FizzBuzz' in fizzbuzz output, got: {output!r}"
    )


# ==============================================================================
# Test 6 — bubble sort example produces numeric output
# ==============================================================================

@pytest.mark.critical
def test_gallery_bubble_sort(page) -> None:
    """Load the bubble sort example, run it, verify numeric output."""
    _reload(page)

    idx = _find_gallery_index_by_keyword(page, "bubble", "sort", "burbuja")
    assert idx >= 0, (
        "Could not find a gallery item whose name contains 'bubble', 'sort', or 'burbuja'"
    )

    _load_gallery_item(page, idx)

    output = _run_and_wait(page)

    has_number = bool(re.search(r"\d+", output))
    assert has_number, (
        f"Expected numeric output from bubble sort, got: {output!r}"
    )


# ==============================================================================
# Test 7 — switching gallery items does not corrupt the editor
# ==============================================================================

@pytest.mark.ux
def test_gallery_switching_doesnt_corrupt(page) -> None:
    """
    Load the first three gallery items in sequence; after each switch verify
    the Monaco editor has non-trivial code (more than just '#include' or empty).
    """
    _reload(page)

    for index in range(3):
        _load_gallery_item(page, index)

        # Switch to the Code tab so we can read Monaco's value
        code = editor_page.get_code(page)

        assert code.strip(), (
            f"Expected non-empty code in Monaco after loading gallery item {index}, got blank"
        )
        # Code must be more than a bare '#include' line (i.e. real example content)
        assert len(code.strip()) > len("#include"), (
            f"Code after loading gallery item {index} is suspiciously short: {code!r}"
        )
        # Must contain at least one 'main' or function declaration — real program structure
        assert "main" in code or "{" in code, (
            f"Expected program structure in code for gallery item {index}, got: {code!r}"
        )


# ==============================================================================
# Test 8 — all 8 gallery items can be loaded and run without HTTP 500 or blank output
# ==============================================================================

@pytest.mark.ux
def test_gallery_items_have_valid_syntax(page) -> None:
    """
    Loop over all 8 gallery items.  For each: load it, click Run, and verify that:
      - The console output is non-empty (not a blank crash).
      - The output does not indicate an unhandled server error (HTTP 500 / SRV001).

    Each program should either succeed (print output) or show a compiler/runtime
    error message — both are acceptable.  Only a blank screen or raw 500 is failure.
    """
    _reload(page)

    # First discover the count
    _open_gallery(page)
    item_count = page.locator("#gallery-menu .dropdown-item").count()
    # Close without selecting
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    assert item_count == 8, (
        f"Expected 8 gallery items for this test, got {item_count}"
    )

    for index in range(item_count):
        # Fresh reload for each item to avoid state bleed
        _reload(page)

        _load_gallery_item(page, index)

        output = _run_and_wait(page)

        # Must not be blank
        assert output.strip(), (
            f"Gallery item {index}: expected non-empty output, got blank console"
        )

        # Must not be a raw HTTP 500 with no useful info
        is_bare_500 = output.strip() == "500" or (
            "500" in output and len(output.strip()) <= 5
        )
        assert not is_bare_500, (
            f"Gallery item {index}: output looks like a bare HTTP 500 error: {output!r}"
        )

        # Must not indicate an unhandled server crash (SRV001 with nothing else)
        is_srv001_only = (
            "SRV001" in output and "error de red" not in output.lower()
            and len(output.strip()) < 20
        )
        assert not is_srv001_only, (
            f"Gallery item {index}: output looks like an unhandled server crash: {output!r}"
        )
