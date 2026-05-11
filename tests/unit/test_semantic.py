from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer, all_paths_return, maybe_infinite_recursion
from compiler.ast_nodes import (
    Block, BoolLiteral, CallExpr, FunctionDecl, IfStmt, IntLiteral, Program,
    ReturnStmt, SourcePos, UnaryOp, VarDecl,
)


def analyze(src: str) -> tuple[object, ErrorReporter]:
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    prog = Parser(tokens, r).parse()
    r2 = ErrorReporter()
    table = SemanticAnalyzer(r2).analyze(prog)
    return table, r2


def test_undeclared_variable() -> None:
    _, r = analyze('int f() { return x; }')
    assert any(e.code == 'SEM001' for e in r.errors)


def test_duplicate_variable() -> None:
    _, r = analyze('int f() { int x = 1; int x = 2; return x; }')
    assert any(e.code == 'SEM002' for e in r.errors)


def test_uninitialized_variable_warning() -> None:
    _, r = analyze('int f() { int x; return x; }')
    assert any(e.code == 'SEM003' for e in r.warnings)


def test_unused_variable_warning() -> None:
    _, r = analyze('int f() { int x = 1; return 0; }')
    assert any(e.code == 'SEM004' for e in r.warnings)


def test_undeclared_function() -> None:
    _, r = analyze('int f() { return foo(); }')
    assert any(e.code == 'SEM005' for e in r.errors)


def test_duplicate_function() -> None:
    _, r = analyze('int f() { return 1; } int f() { return 2; }')
    assert any(e.code == 'SEM006' for e in r.errors)


def test_incompatible_assign_types() -> None:
    _, r = analyze('int f() { int x = "hello"; return x; }')
    assert any(e.code == 'SEM010' for e in r.errors)


def test_invalid_binary_int_string() -> None:
    _, r = analyze('int f() { int x = 1; int y = x + "hi"; return y; }')
    assert any(e.code == 'SEM011' for e in r.errors)


def test_lossy_narrowing_warning() -> None:
    _, r = analyze('int f() { int x = 1; float y = 1.5; int z = y; return z; }')
    # float → int is lossy narrowing → SEM012 warning
    assert any(e.code == 'SEM012' for e in r.warnings)


def test_division_by_zero() -> None:
    _, r = analyze('int f() { int x = 5 / 0; return x; }')
    assert any(e.code == 'SEM013' for e in r.errors)


def test_array_size_zero() -> None:
    _, r = analyze('int arr[0];')
    assert any(e.code == 'SEM033' for e in r.errors)


def test_array_size_too_large() -> None:
    from compiler.limits import MAX_ARRAY_SIZE
    _, r = analyze(f'int arr[{MAX_ARRAY_SIZE + 1}];')
    assert any(e.code == 'SEM035' for e in r.errors)


def test_main_with_params_error() -> None:
    _, r = analyze('int main(int x) { return 0; }')
    assert any(e.code == 'SEM025' for e in r.errors)


def test_builtin_name_as_variable() -> None:
    _, r = analyze('int print = 5;')
    assert any(e.code == 'SEM036' for e in r.errors)


def test_mutual_recursion_no_error() -> None:
    # Both functions declared at top level — pass 1 collects both before bodies are analyzed
    src = ('int f(int x) { return g(x); } '
           'int g(int x) { return f(x); }')
    _, r = analyze(src)
    assert not any(e.code == 'SEM005' for e in r.errors)


def test_valid_program_no_errors() -> None:
    src = 'int main() { int x = 5; return x; }'
    _, r = analyze(src)
    assert not r.has_errors


# ── all_paths_return ─────────────────────────────────────────────────────────────

def _make_pos() -> SourcePos:
    return SourcePos(1, 1)


def _return_block() -> Block:
    return Block(stmts=[ReturnStmt(value=IntLiteral(1), pos=_make_pos())], pos=_make_pos())


def _empty_block() -> Block:
    return Block(stmts=[], pos=_make_pos())


def test_all_paths_return_simple_return() -> None:
    b = _return_block()
    assert all_paths_return(b) is True


def test_all_paths_return_empty_block() -> None:
    assert all_paths_return(_empty_block()) is False


def test_all_paths_return_if_with_else() -> None:
    cond = BoolLiteral(True)
    stmt = IfStmt(
        condition=cond,
        then_body=_return_block(),
        elif_clauses=[],
        else_body=_return_block(),
        pos=_make_pos(),
    )
    b = Block(stmts=[stmt], pos=_make_pos())
    assert all_paths_return(b) is True


def test_all_paths_return_if_without_else() -> None:
    cond = BoolLiteral(True)
    stmt = IfStmt(
        condition=cond,
        then_body=_return_block(),
        elif_clauses=[],
        else_body=None,
        pos=_make_pos(),
    )
    b = Block(stmts=[stmt], pos=_make_pos())
    assert all_paths_return(b) is False


def test_sem022_function_missing_return() -> None:
    _, r = analyze('int f() { int x = 1; }')
    assert any(e.code == 'SEM022' for e in r.errors)


# ── maybe_infinite_recursion ────────────────────────────────────────────────────

def test_maybe_infinite_recursion_direct() -> None:
    r = ErrorReporter()
    tokens = Lexer('int f(int x) { return f(x); }', r).tokenize()
    prog = Parser(tokens, r).parse()
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert maybe_infinite_recursion(fn) is True


def test_maybe_infinite_recursion_with_base() -> None:
    src = 'int f(int x) { if (x == 0) { return 1; } return f(x); }'
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    prog = Parser(tokens, r).parse()
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert maybe_infinite_recursion(fn) is False


# ── Previously-untested implemented codes ───────────────────────────────────────

def test_sem015_static_array_oob() -> None:
    _, r = analyze('int main() { int a[3]; return a[5]; }')
    assert any(e.code == 'SEM015' for e in r.errors)


def test_sem016_return_type_mismatch() -> None:
    _, r = analyze('int f() { return; }')
    assert any(e.code == 'SEM016' for e in r.errors)


def test_sem016_void_returns_value() -> None:
    _, r = analyze('void f() { return 1; }')
    assert any(e.code == 'SEM016' for e in r.errors)


def test_sem017_non_bool_condition() -> None:
    _, r = analyze('int f() { int x = 1; if (x + 1) { return 1; } return 0; }')
    assert any(e.code == 'SEM017' for e in r.errors)


def test_sem020_wrong_arg_count() -> None:
    _, r = analyze('int add(int a, int b) { return a + b; } int f() { return add(1); }')
    assert any(e.code == 'SEM020' for e in r.errors)


def test_sem021_wrong_arg_type() -> None:
    _, r = analyze('int add(int a, int b) { return a + b; } int f() { return add(1, "x"); }')
    assert any(e.code == 'SEM021' for e in r.errors)


def test_sem030_index_non_array() -> None:
    _, r = analyze('int f() { int x = 5; return x[0]; }')
    assert any(e.code == 'SEM030' for e in r.errors)


def test_sem032_init_list_size_mismatch() -> None:
    _, r = analyze('int f() { int a[3] = {1, 2}; return a[0]; }')
    assert any(e.code == 'SEM032' for e in r.errors)


# ── New SEM codes ────────────────────────────────────────────────────────────────

def test_sem023_unreachable_code_after_return() -> None:
    _, r = analyze('int f() { return 1; int x = 2; }')
    assert any(e.code == 'SEM023' for e in r.warnings)


def test_sem026_no_main_function_warning() -> None:
    r = ErrorReporter()
    from compiler.lexer import Lexer
    from compiler.parser import Parser
    from compiler.semantic import SemanticAnalyzer
    tokens = Lexer('int f() { return 1; }', r).tokenize()
    prog = Parser(tokens, r).parse()
    r2 = ErrorReporter()
    SemanticAnalyzer(r2).analyze(prog, mode='check')
    assert any(e.code == 'SEM026' for e in r2.warnings)


def test_sem026_no_main_function_error_in_compile_mode() -> None:
    r = ErrorReporter()
    from compiler.lexer import Lexer
    from compiler.parser import Parser
    from compiler.semantic import SemanticAnalyzer
    tokens = Lexer('int f() { return 1; }', r).tokenize()
    prog = Parser(tokens, r).parse()
    r2 = ErrorReporter()
    SemanticAnalyzer(r2).analyze(prog, mode='compile')
    assert any(e.code == 'SEM026' for e in r2.errors)


def test_sem031_call_non_function() -> None:
    _, r = analyze('int f() { int x = 5; return x(); }')
    assert any(e.code == 'SEM031' for e in r.errors)


def test_sem037_break_outside_loop() -> None:
    _, r = analyze('int f() { break; return 0; }')
    assert any(e.code == 'SEM037' for e in r.errors)


def test_sem037_continue_outside_loop() -> None:
    _, r = analyze('int f() { continue; return 0; }')
    assert any(e.code == 'SEM037' for e in r.errors)
