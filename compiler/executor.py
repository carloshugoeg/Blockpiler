from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

from compiler.limits import EXEC_TIMEOUT_SEC, MAX_OUTPUT_SIZE


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    assembly_path: str
    binary_path: Optional[str]
    error: Optional[str]


class Executor:
    def __init__(self, work_dir: str = '/tmp/compileflow') -> None:
        self._work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    def assemble_and_run(
        self,
        assembly: str,
        session_id: str,
        stdin_data: str = '',
    ) -> ExecutionResult:
        asm_path = f'{self._work_dir}/{session_id}.s'
        bin_path = f'{self._work_dir}/{session_id}'

        with open(asm_path, 'w', encoding='utf-8') as f:
            f.write(assembly)

        cmd = self._gcc_cmd(asm_path, bin_path)
        try:
            as_proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
        except FileNotFoundError as exc:
            return ExecutionResult(
                stdout='', stderr=str(exc), returncode=-1,
                timed_out=False, assembly_path=asm_path, binary_path=None,
                error=f'Compilador no encontrado: {exc}',
            )

        if as_proc.returncode != 0:
            return ExecutionResult(
                stdout='', stderr=as_proc.stderr, returncode=-1,
                timed_out=False, assembly_path=asm_path, binary_path=None,
                error=f'Error al ensamblar:\n{as_proc.stderr}',
            )

        run_cmd = self._run_cmd(bin_path)
        try:
            proc = subprocess.run(
                run_cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT_SEC,
            )
            stdout = proc.stdout[:MAX_OUTPUT_SIZE]
            if len(proc.stdout) > MAX_OUTPUT_SIZE:
                stdout += '\n[Output truncado — máximo 1MB]'
            return ExecutionResult(
                stdout=stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                timed_out=False,
                assembly_path=asm_path,
                binary_path=bin_path,
                error=None,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                stdout='', stderr='', returncode=-1, timed_out=True,
                assembly_path=asm_path, binary_path=bin_path,
                error=f'Tiempo de ejecución excedido ({EXEC_TIMEOUT_SEC}s)',
            )
        finally:
            if os.path.exists(bin_path):
                os.remove(bin_path)

    def _is_native_arm64(self) -> bool:
        return platform.machine().lower() in ('arm64', 'aarch64')

    def _gcc_cmd(self, asm: str, out: str) -> list[str]:
        if self._is_native_arm64():
            return ['gcc', '-o', out, asm]
        return ['aarch64-linux-gnu-gcc', '-static', '-o', out, asm]

    def _run_cmd(self, bin_path: str) -> list[str]:
        if self._is_native_arm64():
            return [bin_path]
        return ['qemu-aarch64', bin_path]
