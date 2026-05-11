from __future__ import annotations

import pytest

MALFORMED_INPUTS = [
    "\x00\x01\x02\x03",
    "/* comentario sin cerrar",
    '"string sin cerrar',
    "'",
    "'ab'",
    "{{{{{{" + "}" * 3,
    "if if if if if",
    "int x = 1/0;",
    "else { }",
    "int outer(){ int inner(){return 1;} return 0;}",
    "int arr[-1];",
    "int arr[0];",
    "int arr[999999999];",
    "true = 5;",
    "5 = x;",
    "int print = 5;",
    "return; break; continue;",
    "int main() { break; return 0; }",
    "int f(){} int f(){}",
    'int x = "hello";',
]

EDGE_CASE_INPUTS = [
    "",
    "   ",
    "\n" * 100,
    "// solo un comentario",
    "/* comentario\nmultilinea */",
    "int x;",
]

BOMB_INPUTS = [
    pytest.param("a" * 600_000, id="bomb_600k_a"),
    pytest.param("a" * 500, id="bomb_500_a"),
    pytest.param("int x = " + "1 + " * 200 + "1;", id="bomb_deep_expr"),
    pytest.param("int " + "f(" * 300 + ")" * 300 + ";", id="bomb_balanced_parens"),
    pytest.param("#@$%", id="bomb_illegal_chars"),
    pytest.param('{"blocks":null}', id="bomb_json_like"),
]


@pytest.mark.parametrize("src", MALFORMED_INPUTS)
def test_malformed_produces_errors(src: str, safe_compile) -> None:
    r = safe_compile(src)
    assert r.exception is None, (
        f"Compiler crashed on:\n{src!r}\n{r.exception}"
    )
    assert len(r.errors) > 0, f"Esperaba errores para: {src!r}"
    for err in r.errors:
        assert isinstance(err.code, str) and err.code
        assert isinstance(err.message, str) and err.message
        assert err.line >= 0 and err.column >= 0


@pytest.mark.parametrize("src", EDGE_CASE_INPUTS)
def test_edge_cases_no_errors(src: str, safe_compile) -> None:
    r = safe_compile(src)
    assert r.exception is None
    assert len(r.errors) == 0, f"Error inesperado en: {src!r}: {r.errors}"


@pytest.mark.parametrize("src", BOMB_INPUTS)
def test_bombs_do_not_crash(src: str, safe_compile) -> None:
    r = safe_compile(src)
    assert r.exception is None, (
        f"Compiler crashed on bomb input:\n{src[:80]!r}\n{r.exception}"
    )
