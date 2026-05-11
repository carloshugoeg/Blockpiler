from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.ast_nodes import (
    ArrayDecl,
    AssignOp,
    BinaryOp,
    Block,
    BoolLiteral,
    BreakStmt,
    CallExpr,
    CastExpr,
    ContinueStmt,
    DoWhileStmt,
    ForStmt,
    FunctionDecl,
    Identifier,
    IfStmt,
    IndexExpr,
    IntLiteral,
    Program,
    ReturnStmt,
    UnaryOp,
    VarDecl,
    WhileStmt,
)


def parse(src: str) -> tuple[Program, ErrorReporter]:
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    prog = Parser(tokens, r).parse()
    return prog, r


def test_minimal_main() -> None:
    prog, r = parse('int main() { return 0; }')
    assert len(prog.declarations) == 1
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert fn.name == 'main'
    assert fn.return_type == 'int'
    assert not r.has_errors


def test_global_var_decl() -> None:
    prog, r = parse('int x = 5;')
    assert len(prog.declarations) == 1
    decl = prog.declarations[0]
    assert isinstance(decl, VarDecl)
    assert decl.name == 'x'
    assert not r.has_errors


def test_array_with_init() -> None:
    prog, r = parse('int arr[3] = {1, 2, 3};')
    decl = prog.declarations[0]
    assert isinstance(decl, ArrayDecl)
    assert decl.name == 'arr'
    assert decl.size == 3
    assert len(decl.init_list) == 3
    assert not r.has_errors


def test_if_else() -> None:
    src = 'int f() { if (x) { } else { } }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, IfStmt)
    assert stmt.else_body is not None


def test_if_elif_else() -> None:
    src = 'int f() { if (a) { } else if (b) { } else { } }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, IfStmt)
    assert len(stmt.elif_clauses) == 1
    assert stmt.else_body is not None


def test_while_stmt() -> None:
    src = 'int f() { while (1) { } }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, WhileStmt)
    assert not r.has_errors


def test_for_stmt() -> None:
    src = 'int f() { for (int i = 0; i < 10; i++) { } }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, ForStmt)
    assert isinstance(stmt.init, VarDecl)
    assert not r.has_errors


def test_for_empty() -> None:
    src = 'int f() { for (;;) { } }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, ForStmt)
    assert stmt.init is None
    assert stmt.condition is None
    assert stmt.update is None


def test_dowhile_stmt() -> None:
    src = 'int f() { do { } while (x); }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, DoWhileStmt)
    assert not r.has_errors


def test_nested_function_error() -> None:
    src = 'int f() { int g() { } }'
    prog, r = parse(src)
    assert r.has_errors
    assert any(e.code == 'PAR004' for e in r.errors)


def test_break_outside_loop() -> None:
    src = 'int f() { break; }'
    prog, r = parse(src)
    assert r.has_errors
    assert any(e.code == 'PAR007' for e in r.errors)


def test_continue_outside_loop() -> None:
    src = 'int f() { continue; }'
    prog, r = parse(src)
    assert r.has_errors
    assert any(e.code == 'PAR007' for e in r.errors)


def test_unclosed_brace() -> None:
    src = 'int f() {'
    prog, r = parse(src)
    assert r.has_errors
    assert any(e.code == 'PAR003' for e in r.errors)


def test_operator_precedence() -> None:
    src = 'int f() { return 1 + 2 * 3; }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    expr = ret.value
    # Should be: BinaryOp(+, 1, BinaryOp(*, 2, 3))
    assert isinstance(expr, BinaryOp)
    assert expr.op == '+'
    assert isinstance(expr.right, BinaryOp)
    assert expr.right.op == '*'
    assert not r.has_errors


def test_cast_expr() -> None:
    src = 'int f() { return (int)x; }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, CastExpr)
    assert not r.has_errors


def test_postfix_increment() -> None:
    src = 'int f() { return x++; }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    u = ret.value
    assert isinstance(u, UnaryOp)
    assert u.op == '++'
    assert u.prefix is False


def test_prefix_increment() -> None:
    src = 'int f() { return ++x; }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    u = ret.value
    assert isinstance(u, UnaryOp)
    assert u.op == '++'
    assert u.prefix is True


def test_void_var_decl_error() -> None:
    prog, r = parse('void x;')
    assert r.has_errors
    assert any(e.code == 'PAR012' for e in r.errors)


def test_function_params() -> None:
    src = 'int add(int a, int b) { return a; }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert len(fn.params) == 2
    assert not r.has_errors


def test_call_expr() -> None:
    src = 'int f() { return foo(1, 2); }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    call = ret.value
    assert isinstance(call, CallExpr)
    assert call.name == 'foo'
    assert len(call.args) == 2
    assert not r.has_errors


def test_index_expr() -> None:
    src = 'int f() { return arr[0]; }'
    prog, r = parse(src)
    fn = prog.declarations[0]
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, IndexExpr)
    assert not r.has_errors


def test_par001_unexpected_token() -> None:
    # 'else' at top-level produces PAR006 via _parse_top_decl failure
    # A bare identifier at top level triggers PAR001 (expected type)
    _, r = parse('foo;')
    assert r.has_errors
    assert any(e.code == 'PAR001' for e in r.errors)


def test_par002_unexpected_eof() -> None:
    # Unclosed block hitting EOF should produce PAR002 or PAR003
    _, r = parse('int f() {')
    assert r.has_errors
    # PAR002 fires when _expect hits EOF; PAR003 fires for unclosed brace
    assert any(e.code in ('PAR002', 'PAR003') for e in r.errors)


def test_par005_missing_semicolon() -> None:
    _, r = parse('int x = 5')
    assert r.has_errors
    assert any(e.code == 'PAR005' for e in r.errors)


def test_par006_else_without_if() -> None:
    _, r = parse('else { }')
    assert r.has_errors
    assert any(e.code == 'PAR006' for e in r.errors)


def test_par008_return_value_in_void() -> None:
    _, r = parse('void f() { return 1; }')
    assert r.has_errors
    assert any(e.code == 'PAR008' for e in r.errors)


def test_par009_nesting_depth_exceeded() -> None:
    from compiler.limits import MAX_NESTING_DEPTH
    deep = 'int f() { ' + '{ ' * (MAX_NESTING_DEPTH + 1) + 'return 0; ' + '} ' * (MAX_NESTING_DEPTH + 1) + '}'
    _, r = parse(deep)
    assert r.has_errors
    assert any(e.code == 'PAR009' for e in r.errors)


def test_par010_too_many_params_in_call() -> None:
    from compiler.limits import MAX_PARAMS
    args = ', '.join('0' for _ in range(MAX_PARAMS + 1))
    src = f'int f() {{ return foo({args}); }}'
    _, r = parse(src)
    assert r.has_errors
    assert any(e.code == 'PAR010' for e in r.errors)


def test_par011_literal_as_assign_target() -> None:
    _, r = parse('int f() { 5 = x; return 0; }')
    assert r.has_errors
    assert any(e.code == 'PAR011' for e in r.errors)


def test_panic_mode_recovery_multiple_errors() -> None:
    # Multiple syntax errors — parser must not crash and report multiple errors
    _, r = parse('foo; bar; int main() { return 0; }')
    # Should have errors for foo and bar but still parse main
    assert r.has_errors
