from __future__ import annotations

import sys
import pytest

sys.setrecursionlimit(5000)
from compiler.error_reporter import ErrorReporter
from compiler.executor import Executor
from compiler.lexer import Lexer
from compiler.optimizer import Optimizer
from compiler.codegen import CodeGenerator
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer


class CompileResult:
    def __init__(self) -> None:
        self.errors: list = []
        self.warnings: list = []
        self.ast = None
        self.exception: object = None
        self.assembly: str | None = None
        self.stdout: str = ''
        self.returncode: int = 0


def compile_safe(source: str, opt_level: int = 0) -> CompileResult:
    """Run lex+parse+sema without raising. For testing."""
    r = CompileResult()
    try:
        rep = ErrorReporter()
        tokens = Lexer(source, rep).tokenize()
        ast = Parser(tokens, rep).parse()
        SemanticAnalyzer(rep).analyze(ast)
        r.errors = rep.errors
        r.warnings = rep.warnings
        r.ast = ast
    except Exception as e:  # noqa: BLE001
        import traceback
        r.exception = (e, traceback.format_exc())
    return r


def compile_and_run(
    source: str,
    opt_level: int = 1,
    stdin_data: str = '',
) -> CompileResult:
    """Full pipeline: source → execution. Raises if there are compile errors."""
    r = CompileResult()
    rep = ErrorReporter()
    tokens = Lexer(source, rep).tokenize()
    ast = Parser(tokens, rep).parse()
    SemanticAnalyzer(rep).analyze(ast)
    r.errors = rep.errors
    r.warnings = rep.warnings
    if rep.has_errors:
        r.exception = ValueError(f'Errores: {rep.errors}')
        return r
    opt_ast = Optimizer(level=opt_level).optimize(ast)
    asm, _line_map = CodeGenerator().generate(opt_ast)
    r.assembly = asm
    exec_result = Executor().assemble_and_run(asm, 'test', stdin_data)
    r.stdout = exec_result.stdout
    r.returncode = exec_result.returncode
    return r


@pytest.fixture
def reporter() -> ErrorReporter:
    return ErrorReporter()


@pytest.fixture
def safe_compile():  # type: ignore[return]
    return compile_safe


@pytest.fixture
def run():  # type: ignore[return]
    return compile_and_run
