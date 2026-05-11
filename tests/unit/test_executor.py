"""
Tests for executor.py — these are structural tests that don't require
an actual ARM64 toolchain to be installed. They test the executor's
logic (error handling, timeout, truncation) using mocks.
"""
import os
import subprocess
from unittest.mock import MagicMock, patch

from compiler.executor import ExecutionResult, Executor
from compiler.limits import EXEC_TIMEOUT_SEC, MAX_OUTPUT_SIZE


def _make_executor(tmp_path: str) -> Executor:
    return Executor(work_dir=tmp_path)


def test_executor_creates_work_dir(tmp_path: object) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        new_dir = os.path.join(d, 'new_subdir')
        ex = Executor(work_dir=new_dir)
        assert os.path.isdir(new_dir)


def test_assemble_failure_returns_error(tmp_path: object) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ex = Executor(work_dir=d)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = 'Error: bad asm'
        with patch('subprocess.run', return_value=mock_result):
            result = ex.assemble_and_run('bad asm', 'test_session')
        assert result.returncode == -1
        assert result.error is not None
        assert 'Error al ensamblar' in result.error
        assert result.binary_path is None


def test_assemble_success_run_success(tmp_path: object) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ex = Executor(work_dir=d)

        def fake_run(cmd: list, **kwargs: object) -> MagicMock:
            r = MagicMock()
            if cmd[0] in ('gcc', 'aarch64-linux-gnu-gcc'):
                r.returncode = 0
                r.stderr = ''
            else:
                r.returncode = 0
                r.stdout = 'hello\n'
                r.stderr = ''
            return r

        with patch('subprocess.run', side_effect=fake_run):
            result = ex.assemble_and_run('valid asm', 'sess1')
        assert result.returncode == 0
        assert result.stdout == 'hello\n'
        assert result.timed_out is False


def test_timeout_returns_timed_out(tmp_path: object) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ex = Executor(work_dir=d)

        call_count = 0

        def fake_run(cmd: list, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                r = MagicMock()
                r.returncode = 0
                r.stderr = ''
                return r
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=EXEC_TIMEOUT_SEC)

        with patch('subprocess.run', side_effect=fake_run):
            result = ex.assemble_and_run('asm', 'sess2')
        assert result.timed_out is True
        assert result.returncode == -1


def test_output_truncated(tmp_path: object) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ex = Executor(work_dir=d)
        large_output = 'x' * (MAX_OUTPUT_SIZE + 100)

        def fake_run(cmd: list, **kwargs: object) -> MagicMock:
            r = MagicMock()
            r.returncode = 0
            r.stdout = large_output
            r.stderr = ''
            return r

        with patch('subprocess.run', side_effect=fake_run):
            result = ex.assemble_and_run('asm', 'sess3')
        assert '[Output truncado' in result.stdout


def test_gcc_not_found_returns_error(tmp_path: object) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ex = Executor(work_dir=d)
        with patch('subprocess.run', side_effect=FileNotFoundError('gcc not found')):
            result = ex.assemble_and_run('asm', 'sess4')
        assert result.returncode == -1
        assert result.error is not None


def test_is_native_arm64() -> None:
    import tempfile
    import platform
    with tempfile.TemporaryDirectory() as d:
        ex = Executor(work_dir=d)
        machine = platform.machine().lower()
        expected = machine in ('arm64', 'aarch64')
        assert ex._is_native_arm64() == expected


def test_execution_result_fields() -> None:
    r = ExecutionResult(
        stdout='out', stderr='err', returncode=0, timed_out=False,
        assembly_path='/tmp/t.s', binary_path=None, error=None
    )
    assert r.stdout == 'out'
    assert r.timed_out is False
    assert r.error is None
