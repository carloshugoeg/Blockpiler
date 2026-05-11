from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer, TokenType
from compiler.limits import INT64_MAX, INT64_MIN, MAX_IDENTIFIER_LEN, MAX_SOURCE_SIZE, MAX_STRING_LEN


def lex(src: str) -> tuple[list, ErrorReporter]:
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    return tokens, r


def test_empty_input() -> None:
    tokens, r = lex('')
    assert len(tokens) == 1
    assert tokens[0].type == TokenType.EOF
    assert not r.has_errors


def test_whitespace_only() -> None:
    tokens, r = lex('   \t\n  ')
    assert len(tokens) == 1
    assert tokens[0].type == TokenType.EOF
    assert not r.has_errors


def test_keywords() -> None:
    src = 'if else for while do return break continue'
    tokens, r = lex(src)
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [
        TokenType.IF, TokenType.ELSE, TokenType.FOR, TokenType.WHILE,
        TokenType.DO, TokenType.RETURN, TokenType.BREAK, TokenType.CONTINUE,
    ]
    assert not r.has_errors


def test_type_keywords() -> None:
    src = 'int float char bool void string'
    tokens, r = lex(src)
    for t in tokens[:-1]:
        assert t.type == TokenType.TYPE_KW
    assert not r.has_errors


def test_builtins() -> None:
    src = 'print println input input_int input_float true false'
    tokens, r = lex(src)
    for t in tokens[:-1]:
        assert t.type == TokenType.BUILTIN
    assert not r.has_errors


def test_integer_zero() -> None:
    tokens, r = lex('0')
    assert tokens[0].type == TokenType.INT_LIT
    assert tokens[0].value == '0'
    assert not r.has_errors


def test_integer_max() -> None:
    tokens, r = lex(str(INT64_MAX))
    assert tokens[0].type == TokenType.INT_LIT
    assert not r.has_errors


def test_integer_overflow() -> None:
    tokens, r = lex(str(INT64_MAX + 1))
    assert tokens[0].type == TokenType.INT_LIT
    assert r.has_errors
    assert r.errors[0].code == 'LEX011'


def test_float_basic() -> None:
    tokens, r = lex('1.0')
    assert tokens[0].type == TokenType.FLOAT_LIT
    assert not r.has_errors


def test_float_exponent() -> None:
    tokens, r = lex('1e3')
    assert tokens[0].type == TokenType.FLOAT_LIT
    assert not r.has_errors


def test_float_leading_dot() -> None:
    tokens, r = lex('.5')
    assert tokens[0].type == TokenType.FLOAT_LIT
    assert not r.has_errors


def test_float_infinity() -> None:
    tokens, r = lex('1e999')
    assert tokens[0].type == TokenType.FLOAT_LIT
    assert r.has_errors
    assert r.errors[0].code == 'LEX012'


def test_string_valid_escapes() -> None:
    tokens, r = lex(r'"hello\nworld"')
    assert tokens[0].type == TokenType.STRING_LIT
    assert '\n' in tokens[0].value
    assert not r.has_errors


def test_string_invalid_escape() -> None:
    tokens, r = lex(r'"bad\q"')
    assert tokens[0].type == TokenType.STRING_LIT
    assert r.has_errors
    assert r.errors[0].code == 'LEX007'


def test_string_unclosed() -> None:
    tokens, r = lex('"unclosed')
    assert r.has_errors
    assert r.errors[0].code == 'LEX002'


def test_char_valid() -> None:
    tokens, r = lex("'a'")
    assert tokens[0].type == TokenType.CHAR_LIT
    assert tokens[0].value == 'a'
    assert not r.has_errors


def test_char_empty() -> None:
    tokens, r = lex("''")
    assert tokens[0].type == TokenType.CHAR_LIT
    assert r.has_errors
    assert r.errors[0].code == 'LEX003'


def test_char_multiple() -> None:
    tokens, r = lex("'ab'")
    assert tokens[0].type == TokenType.CHAR_LIT
    assert r.has_errors
    assert r.errors[0].code == 'LEX003'


def test_block_comment_unclosed() -> None:
    tokens, r = lex('/* unclosed')
    assert r.has_errors
    assert r.errors[0].code == 'LEX004'


def test_illegal_char() -> None:
    tokens, r = lex('@')
    assert tokens[0].type == TokenType.ERROR
    assert r.has_errors
    assert r.errors[0].code == 'LEX001'


def test_sequence_int_x_assign() -> None:
    tokens, r = lex('int x = 5;')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [
        TokenType.TYPE_KW,
        TokenType.IDENT,
        TokenType.ASSIGN,
        TokenType.INT_LIT,
        TokenType.SEMICOLON,
    ]
    assert not r.has_errors


def test_line_comment_ignored() -> None:
    tokens, r = lex('// comment\nint')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.TYPE_KW]
    assert not r.has_errors


def test_two_char_operators() -> None:
    src = '== != <= >= && || ++ -- += -= *= /= %='
    tokens, r = lex(src)
    expected = [
        TokenType.EQ, TokenType.NEQ, TokenType.LE, TokenType.GE,
        TokenType.AND, TokenType.OR, TokenType.INC, TokenType.DEC,
        TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN, TokenType.STAR_ASSIGN,
        TokenType.SLASH_ASSIGN, TokenType.PERCENT_ASSIGN,
    ]
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == expected
    assert not r.has_errors


def test_illegal_char_advances_one() -> None:
    tokens, r = lex('@x')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types[0] == TokenType.ERROR
    assert types[1] == TokenType.IDENT
    assert len(r.errors) == 1


def test_lex005_malformed_number() -> None:
    _, r = lex('1.2.3')
    assert r.has_errors
    assert any(e.code == 'LEX005' for e in r.errors)


def test_lex006_identifier_too_long() -> None:
    long_id = 'a' * (MAX_IDENTIFIER_LEN + 1)
    _, r = lex(long_id)
    assert r.has_errors
    assert any(e.code == 'LEX006' for e in r.errors)


def test_lex008_string_too_long() -> None:
    long_str = '"' + 'x' * (MAX_STRING_LEN + 1) + '"'
    _, r = lex(long_str)
    assert r.has_errors
    assert any(e.code == 'LEX008' for e in r.errors)


def test_lex009_utf8_validation() -> None:
    # Lone surrogate is valid as a Python str but not encodable to UTF-8
    src = '\ud800'
    _, r = lex(src)
    assert r.has_errors
    assert any(e.code == 'LEX009' for e in r.errors)


def test_lex010_source_too_large() -> None:
    huge_src = 'x' * (MAX_SOURCE_SIZE + 1)
    _, r = lex(huge_src)
    assert r.has_errors
    assert any(e.code == 'LEX010' for e in r.errors)
