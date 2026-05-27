import pytest
import subprocess
import socket
import time
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Generator

PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = Path(__file__).parent / "reports"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_port(port: int, host: str = "127.0.0.1", timeout: int = 60) -> None:
    """Poll host:port until it accepts a connection or timeout seconds elapse."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError(
        f"Service on {host}:{port} did not become ready within {timeout}s"
    )


# ---------------------------------------------------------------------------
# Server fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def flask_server() -> Generator[None, None, None]:
    """Start `python run.py` from the project root; wait for port 5000."""
    env = os.environ.copy()
    env["USE_RELOADER"] = "0"
    proc = subprocess.Popen(
        ["python", "run.py"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        wait_for_port(5000)
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def vite_server() -> Generator[None, None, None]:
    """Start `npm run dev` from the project root; wait for port 5173."""
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        wait_for_port(5173)
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# Browser context override — injects base_url so all pages use Vite's origin
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context_args(
    flask_server: None,
    vite_server: None,
    pytestconfig: Any,
    playwright: Any,
    device: Any,
    base_url: Any,
    _pw_artifacts_folder: Any,
) -> Dict:
    """Override pytest-playwright's browser_context_args to set base_url."""
    context_args: Dict = {}
    if device:
        context_args.update(playwright.devices[device])
    # Always point the browser at the Vite dev server
    context_args["base_url"] = "http://localhost:5173"
    return context_args


# ---------------------------------------------------------------------------
# Marker registration
# ---------------------------------------------------------------------------

def pytest_configure(config: Any) -> None:
    """Register custom severity markers to avoid PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "critical: mark test as critical severity")
    config.addinivalue_line("markers", "ux: mark test as UX severity")
    config.addinivalue_line("markers", "cosmetic: mark test as cosmetic severity")


# ---------------------------------------------------------------------------
# Session-finish report hook
# ---------------------------------------------------------------------------

def _next_qa_id(qa_path: Path) -> int:
    """Return the next available CF-QA-NNN integer by scanning QA_ISSUES.md."""
    if not qa_path.exists():
        return 1
    text = qa_path.read_text(encoding="utf-8")
    numbers = [int(m) for m in re.findall(r"CF-QA-(\d+)", text)]
    return max(numbers, default=0) + 1


def _collect_failures(session: Any) -> list:
    """Return list of (nodeid, longrepr_str) for all failed tests."""
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return []
    failures = []
    for report in reporter.stats.get("failed", []):
        longrepr = str(report.longrepr) if report.longrepr else ""
        failures.append((report.nodeid, longrepr))
    return failures


def _get_marker_severity(session: Any, nodeid: str) -> str:
    """Return 'critical', 'ux', 'cosmetic', or 'unknown' for a test node."""
    for item in session.items:
        if item.nodeid == nodeid:
            for marker in ("critical", "ux", "cosmetic"):
                if item.get_closest_marker(marker) is not None:
                    return marker
    return "unknown"


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Write a failure report and append new issues to QA_ISSUES.md."""
    failures = _collect_failures(session)
    if not failures:
        return

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    report_path = REPORTS_DIR / f"issues_{today}.md"

    # Group failures by severity
    grouped: Dict[str, list] = {"critical": [], "ux": [], "cosmetic": [], "unknown": []}
    for nodeid, longrepr in failures:
        sev = _get_marker_severity(session, nodeid)
        grouped[sev].append((nodeid, longrepr))

    # Write report
    lines = [f"# E2E Failure Report — {today}\n"]
    for sev in ("critical", "ux", "cosmetic", "unknown"):
        items = grouped[sev]
        if not items:
            continue
        lines.append(f"\n## {sev.capitalize()} ({len(items)} failures)\n")
        for nodeid, longrepr in items:
            lines.append(f"### `{nodeid}`\n")
            if longrepr:
                lines.append("```\n")
                lines.append(longrepr[:2000])
                if len(longrepr) > 2000:
                    lines.append("\n... (truncated)")
                lines.append("\n```\n")

    report_path.write_text("".join(lines), encoding="utf-8")

    # Append new issues to QA_ISSUES.md that are not already listed there
    qa_path = PROJECT_ROOT / "QA_ISSUES.md"
    existing_text = qa_path.read_text(encoding="utf-8") if qa_path.exists() else ""
    next_id = _next_qa_id(qa_path)

    new_entries: list = []
    for nodeid, longrepr in failures:
        # Skip if this nodeid is already mentioned in QA_ISSUES.md
        if nodeid in existing_text:
            continue
        sev = _get_marker_severity(session, nodeid)
        entry_id = f"CF-QA-{next_id:03d}"
        next_id += 1
        short_msg = longrepr.strip().splitlines()[0][:200] if longrepr.strip() else "No details"
        entry = (
            f"\n### {entry_id} - E2E failure: `{nodeid}`\n\n"
            f"**Severidad:** {sev.capitalize()}  \n"
            f"**Fecha:** {today}  \n\n"
            f"**Mensaje:**\n\n```\n{short_msg}\n```\n\n---\n"
        )
        new_entries.append(entry)

    if new_entries:
        with open(qa_path, "a", encoding="utf-8") as f:
            for entry in new_entries:
                f.write(entry)
