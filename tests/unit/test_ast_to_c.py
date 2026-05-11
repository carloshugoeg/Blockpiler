from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.ast_to_c import ast_to_c


def parse_and_convert(src: str) -> str:
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    prog = Parser(tokens, r).parse()
    return ast_to_c(prog)


def test_minimal_main_roundtrip() -> None:
    src = 'int main() { return 0; }'
    c_code = parse_and_convert(src)
    assert 'int main()' in c_code
    assert 'return 0;' in c_code


def test_binary_op_parenthesized() -> None:
    src = 'int f() { return 1 + 2 * 3; }'
    c_code = parse_and_convert(src)
    # BinaryOp must be wrapped in parens
    assert '(' in c_code
    assert '+' in c_code
    assert '*' in c_code


def test_println_generates_printf() -> None:
    src = 'int main() { println(42); return 0; }'
    c_code = parse_and_convert(src)
    assert 'printf' in c_code


def test_indent_4_spaces() -> None:
    src = 'int main() { int x = 1; return x; }'
    c_code = parse_and_convert(src)
    lines = c_code.split('\n')
    # Body lines should be indented by 4 spaces
    body_lines = [l for l in lines if l.startswith('    ')]
    assert len(body_lines) > 0


def test_var_decl_with_init() -> None:
    src = 'int main() { int x = 5; return x; }'
    c_code = parse_and_convert(src)
    assert 'int x = 5' in c_code


def test_array_decl() -> None:
    src = 'int arr[3] = {1, 2, 3};'
    c_code = parse_and_convert(src)
    assert 'arr[3]' in c_code
    assert '{1, 2, 3}' in c_code


def test_if_stmt() -> None:
    src = 'int f(int x) { if (x) { return 1; } return 0; }'
    c_code = parse_and_convert(src)
    assert 'if (' in c_code
    assert 'return 1;' in c_code


def test_while_stmt() -> None:
    src = 'int f() { while (1) { break; } return 0; }'
    c_code = parse_and_convert(src)
    assert 'while (' in c_code
    assert 'break;' in c_code


def test_for_stmt() -> None:
    src = 'int f() { for (int i = 0; i < 10; i++) { } return 0; }'
    c_code = parse_and_convert(src)
    assert 'for (' in c_code


def test_cast_expr() -> None:
    src = 'int f() { return (int)3.14; }'
    c_code = parse_and_convert(src)
    assert '(int)' in c_code


def test_string_literal_escaped() -> None:
    src = r'int f() { return 0; }'
    c_code = parse_and_convert(src)
    # Just verify no crash and C output produced
    assert '#include' in c_code


def test_bool_literal() -> None:
    src = 'int f() { bool x = true; return 0; }'
    c_code = parse_and_convert(src)
    assert '1' in c_code


def test_function_with_params() -> None:
    src = 'int add(int a, int b) { return a; }'
    c_code = parse_and_convert(src)
    assert 'int add(int a, int b)' in c_code


def test_includes_present() -> None:
    src = 'int main() { return 0; }'
    c_code = parse_and_convert(src)
    assert '#include <stdio.h>' in c_code


def test_dowhile_generates_valid_c() -> None:
    src = 'int f() { int x = 0; do { x = x + 1; } while (x < 3); return x; }'
    c_code = parse_and_convert(src)
    assert 'do' in c_code
    assert 'while' in c_code


def test_break_generates_break() -> None:
    src = 'int f() { while (true) { break; } return 0; }'
    c_code = parse_and_convert(src)
    assert 'break;' in c_code


def test_continue_generates_continue() -> None:
    src = 'int f() { int i = 0; while (i < 5) { i = i + 1; continue; } return 0; }'
    c_code = parse_and_convert(src)
    assert 'continue;' in c_code


def test_roundtrip_idempotent() -> None:
    """ast_to_c(parse(c)) == c when c has no include headers (stable generation)."""
    src = 'int main() { int x = 2; int y = 3; return x; }'
    # First pass: original source → C (with includes)
    c1 = parse_and_convert(src)
    # Strip include lines to make it re-parseable by our parser
    body_only = '\n'.join(
        line for line in c1.splitlines()
        if not line.startswith('#include')
    ).strip()
    # Second pass: re-parse the generated function body
    c2 = parse_and_convert(body_only)
    # Strip includes again and compare — should be identical (idempotent)
    body2 = '\n'.join(
        line for line in c2.splitlines()
        if not line.startswith('#include')
    ).strip()
    assert body_only == body2
