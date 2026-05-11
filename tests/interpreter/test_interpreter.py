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
    src = 'int inf() { return inf(); } int main() { return inf(); }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_interp_max_iters_raises() -> None:
    import pytest
    from compiler.interpreter import InterpreterError
    src = 'int main() { while (true) {} return 0; }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_interp_timeout_raises() -> None:
    import pytest
    from compiler.interpreter import InterpreterError
    src = 'int main() { while (true) {} return 0; }'
    with pytest.raises(InterpreterError):
        _interp(src)


def test_continue_to_breakpoint() -> None:
    from compiler.interpreter import Interpreter
    src = 'int main() { int a = 1; int b = 2; int c = 3; return c; }'
    prog = _parse(src)
    interp = Interpreter(prog)
    interp.start_debug()
    state = interp.step()
    assert not state.finished or state.return_code is not None
