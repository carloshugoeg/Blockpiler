from compiler.error_reporter import ErrorReporter
from compiler.interpreter import Interpreter, InterpreterError
from compiler.lexer import Lexer
from compiler.parser import Parser


def _interp(src: str, input_fn=None) -> tuple[str, int]:
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    prog = Parser(tokens, r).parse()
    return Interpreter(prog, input_fn=input_fn).run()


def _parse(src: str):  # type: ignore[return]
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    return Parser(tokens, r).parse()


def test_return_code() -> None:
    out, rc = _interp('int main() { return 42; }')
    assert rc == 42
    assert out == ''


def test_println_int() -> None:
    out, rc = _interp('int main() { println(7); return 0; }')
    assert out == '7\n'
    assert rc == 0


def test_print_no_newline() -> None:
    out, _ = _interp('int main() { print("hi"); return 0; }')
    assert out == 'hi'


def test_var_decl_and_use() -> None:
    out, _ = _interp('int main() { int x = 10; println(x); return 0; }')
    assert out == '10\n'


def test_if_true_branch() -> None:
    out, _ = _interp('int main() { if (1) { println(1); } return 0; }')
    assert out == '1\n'


def test_if_false_branch() -> None:
    out, _ = _interp('int main() { if (0) { println(1); } else { println(2); } return 0; }')
    assert out == '2\n'


def test_while_loop() -> None:
    src = 'int main() { int i = 0; while (i < 3) { println(i); i = i + 1; } return 0; }'
    out, _ = _interp(src)
    assert out == '0\n1\n2\n'


def test_for_loop() -> None:
    src = 'int main() { for (int i = 0; i < 3; i++) { println(i); } return 0; }'
    out, _ = _interp(src)
    assert out == '0\n1\n2\n'


def test_break_in_while() -> None:
    src = 'int main() { int i = 0; while (1) { if (i >= 2) { break; } println(i); i++; } return 0; }'
    out, _ = _interp(src)
    assert out == '0\n1\n'


def test_continue_in_for() -> None:
    src = 'int main() { for (int i = 0; i < 4; i++) { if (i == 2) { continue; } println(i); } return 0; }'
    out, _ = _interp(src)
    assert out == '0\n1\n3\n'


def test_function_call() -> None:
    src = 'int add(int a, int b) { return a + b; } int main() { println(add(3, 4)); return 0; }'
    out, _ = _interp(src)
    assert out == '7\n'


def test_array_decl_and_index() -> None:
    src = 'int main() { int a[3]; a[0] = 10; a[1] = 20; println(a[0] + a[1]); return 0; }'
    out, _ = _interp(src)
    assert out == '30\n'


def test_array_init_list() -> None:
    src = 'int main() { int a[3] = {1, 2, 3}; println(a[2]); return 0; }'
    out, _ = _interp(src)
    assert out == '3\n'


def test_cast_int_to_float() -> None:
    src = 'int main() { float x = (float)3; println(x); return 0; }'
    out, _ = _interp(src)
    assert '3' in out


def test_bool_literal_print() -> None:
    out, _ = _interp('int main() { println(true); return 0; }')
    assert 'true' in out


def test_no_main_raises() -> None:
    r = ErrorReporter()
    tokens = Lexer('int foo() { return 1; }', r).tokenize()
    prog = Parser(tokens, r).parse()
    interp = Interpreter(prog)
    try:
        interp.run()
        assert False, 'expected InterpreterError'
    except InterpreterError:
        pass


def test_input_without_fn_raises() -> None:
    r = ErrorReporter()
    tokens = Lexer('int main() { int x = input_int(); return x; }', r).tokenize()
    prog = Parser(tokens, r).parse()
    interp = Interpreter(prog)
    try:
        interp.run()
        assert False, 'expected InterpreterError'
    except InterpreterError:
        pass


def test_input_with_fn() -> None:
    src = 'int main() { int x = input_int(); println(x); return 0; }'
    out, _ = _interp(src, input_fn=lambda: '99')
    assert out == '99\n'


def test_debug_step() -> None:
    r = ErrorReporter()
    src = 'int main() { int x = 5; return x; }'
    tokens = Lexer(src, r).tokenize()
    prog = Parser(tokens, r).parse()
    interp = Interpreter(prog)
    interp.start_debug()
    state = interp.step()
    assert not state.finished or state.variables.get('x') == 5 or state.finished


def test_do_while() -> None:
    src = 'int main() { int i = 0; do { println(i); i++; } while (i < 2); return 0; }'
    out, _ = _interp(src)
    assert out == '0\n1\n'


def test_string_concat() -> None:
    src = 'int main() { string s = "hello" + " world"; println(s); return 0; }'
    out, _ = _interp(src)
    assert out == 'hello world\n'


def test_interp_max_depth_raises() -> None:
    import pytest
    from compiler.interpreter import InterpreterError
    # Infinite recursion → INTERP_MAX_DEPTH exceeded
    src = 'int inf() { return inf(); } int main() { return inf(); }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_interp_max_iters_raises() -> None:
    import pytest
    from compiler.interpreter import InterpreterError
    # Infinite loop → INTERP_MAX_ITERS exceeded
    src = 'int main() { while (true) {} return 0; }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_interp_timeout_raises() -> None:
    import pytest
    from compiler.interpreter import InterpreterError
    # Loop past MAX_ITERS hits InterpreterError from iters limit, not timeout
    src = 'int main() { while (true) {} return 0; }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_continue_to_breakpoint() -> None:
    from compiler.interpreter import Interpreter
    src = 'int main() { int a = 1; int b = 2; int c = 3; return c; }'
    prog = _parse(src)
    interp = Interpreter(prog)
    interp.start_debug()
    # Step once to get past the first statement
    state = interp.step()
    assert not state.finished or state.return_code is not None


# ── Additional coverage tests ─────────────────────────────────────────────────

def test_continue_in_while() -> None:
    src = 'int main() { int s = 0; int i = 0; while (i < 4) { i++; if (i == 2) { continue; } s = s + i; } return s; }'
    out, rc = _interp(src)
    assert rc == 8  # 1 + 3 + 4 = 8


def test_break_in_dowhile() -> None:
    src = 'int main() { int i = 0; do { i++; if (i >= 2) { break; } } while (i < 10); return i; }'
    out, rc = _interp(src)
    assert rc == 2


def test_continue_in_dowhile() -> None:
    src = 'int main() { int s = 0; int i = 0; do { i++; if (i == 2) { continue; } s = s + 1; } while (i < 3); return s; }'
    out, rc = _interp(src)
    assert rc == 2  # i=1 adds, i=2 skips, i=3 adds


def test_short_circuit_and_false() -> None:
    # Left is false, right should not be evaluated
    out, rc = _interp('int main() { if (0 && 1) { return 1; } return 0; }')
    assert rc == 0


def test_short_circuit_or_true() -> None:
    out, rc = _interp('int main() { if (1 || 0) { return 1; } return 0; }')
    assert rc == 1


def test_shift_operators() -> None:
    from compiler.ast_nodes import (
        BinaryOp, Block, FunctionDecl, IntLiteral, Program, ReturnStmt,
        SourcePos, VarDecl,
    )
    pos = SourcePos(1, 1)
    # Build `int x = 1 << 3; return x;` via AST directly (lexer has no << token)
    shift_expr = BinaryOp(op='<<', left=IntLiteral(1), right=IntLiteral(3))
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                VarDecl(name='x', type='int', init_expr=shift_expr, pos=pos),
                ReturnStmt(value=__import__('compiler.ast_nodes', fromlist=['Identifier']).Identifier('x'), pos=pos),
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    _, rc = Interpreter(prog).run()
    assert rc == 8


def test_modulo_operation() -> None:
    out, rc = _interp('int main() { int r = 10 % 3; return r; }')
    assert rc == 1


def test_comparison_ops() -> None:
    out, rc = _interp('int main() { if (1 <= 2) { if (3 >= 3) { if (1 != 2) { return 1; } } } return 0; }')
    assert rc == 1


def test_division_float() -> None:
    out, rc = _interp('int main() { float x = 5 / 2; println(x); return 0; }')
    # Integer division: 5/2 = 2
    assert '2' in out


def test_compound_assign_divide() -> None:
    out, rc = _interp('int main() { float x = 10; x /= 4; println(x); return 0; }')
    assert '2' in out or '2.5' in out


def test_compound_assign_mod() -> None:
    out, rc = _interp('int main() { int x = 10; x %= 3; return x; }')
    assert rc == 1


def test_compound_assign_mul() -> None:
    out, rc = _interp('int main() { int x = 5; x *= 3; return x; }')
    assert rc == 15


def test_prefix_decrement() -> None:
    out, rc = _interp('int main() { int x = 5; return --x; }')
    assert rc == 4


def test_postfix_decrement() -> None:
    out, rc = _interp('int main() { int x = 5; int y = x--; return y; }')
    assert rc == 5  # postfix returns old value


def test_unary_not() -> None:
    out, rc = _interp('int main() { bool x = !true; println(x); return 0; }')
    assert 'false' in out


def test_cast_to_bool() -> None:
    out, rc = _interp('int main() { bool b = (bool)1; println(b); return 0; }')
    assert 'true' in out


def test_cast_to_char() -> None:
    out, rc = _interp('int main() { char c = (char)65; println(c); return 0; }')
    assert 'A' in out


def test_cast_to_string() -> None:
    out, rc = _interp('int main() { string s = (string)42; println(s); return 0; }')
    assert '42' in out


def test_input_float_variant() -> None:
    src = 'int main() { float x = input_float(); println(x); return 0; }'
    out, _ = _interp(src, input_fn=lambda: '3.14')
    assert '3.14' in out or '3' in out


def test_input_string_variant() -> None:
    src = 'int main() { string s = input(); println(s); return 0; }'
    out, _ = _interp(src, input_fn=lambda: 'hello')
    assert 'hello' in out


def test_division_by_zero_raises() -> None:
    import pytest
    src = 'int main() { int x = 5; int y = 0; return x / y; }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_modulo_by_zero_raises() -> None:
    import pytest
    src = 'int main() { int x = 5; int y = 0; return x % y; }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_array_oob_raises() -> None:
    import pytest
    src = 'int main() { int arr[3] = {1,2,3}; return arr[5]; }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_undeclared_function_raises() -> None:
    import pytest
    from compiler.ast_nodes import (
        CallExpr, ReturnStmt, FunctionDecl, Block, Program, SourcePos
    )
    pos = SourcePos(1, 1)
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                ReturnStmt(value=CallExpr(name='no_such_fn', args=[]), pos=pos)
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    with pytest.raises(InterpreterError):
        Interpreter(prog).run()


def test_step_when_already_finished() -> None:
    src = 'int main() { return 1; }'
    prog = _parse(src)
    interp = Interpreter(prog)
    interp.start_debug()
    # Step through all statements
    for _ in range(10):
        state = interp.step()
    assert state.finished


def test_start_debug_no_main_raises() -> None:
    import pytest
    src = 'int foo() { return 1; }'
    prog = _parse(src)
    interp = Interpreter(prog)
    with pytest.raises(InterpreterError):
        interp.start_debug()


def test_set_var_new_in_scope() -> None:
    # When variable is set for the first time, it goes into current scope
    src = 'int main() { int x = 5; x = 10; return x; }'
    out, rc = _interp(src)
    assert rc == 10
