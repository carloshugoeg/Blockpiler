from compiler.error_reporter import ErrorReporter
from compiler.explainer import Explainer, explain
from compiler.lexer import Lexer
from compiler.parser import Parser


def _parse(src: str):
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    return Parser(tokens, r).parse()


def _explain(src: str) -> str:
    return explain(_parse(src))


def test_return_mentions_function_and_retorna() -> None:
    out = _explain('int main() { return 0; }')
    assert 'función' in out or 'Función' in out
    assert 'Retorna' in out or 'retorna' in out


def test_println_mentions_imprime() -> None:
    out = _explain('int main() { println(5); return 0; }')
    assert 'Imprime' in out or 'imprime' in out


def test_if_mentions_si() -> None:
    out = _explain('int main() { int x = 1; if (x > 0) { return 1; } return 0; }')
    assert 'Si' in out


def test_for_loop_mentions_para() -> None:
    out = _explain('int main() { for (int i = 0; i < 3; i++) { println(i); } return 0; }')
    lower = out.lower()
    assert 'para' in lower or 'repite' in lower or 'itera' in lower


def test_while_loop() -> None:
    out = _explain('int main() { int i = 0; while (i < 5) { i++; } return 0; }')
    assert 'Mientras' in out or 'mientras' in out


def test_output_is_markdown_with_headers() -> None:
    out = _explain('int main() { return 0; }')
    assert '#' in out


def test_empty_program_no_crash() -> None:
    from compiler.ast_nodes import Program, SourcePos
    prog = Program(declarations=[], pos=SourcePos(0, 0))
    out = explain(prog)
    assert isinstance(out, str)


def test_var_decl_with_init() -> None:
    out = _explain('int main() { int x = 42; return x; }')
    assert 'x' in out
    assert '42' in out


def test_if_else() -> None:
    out = _explain('int main() { if (1) { println(1); } else { println(2); } return 0; }')
    assert 'Si' in out
    assert 'contrario' in out or 'sino' in out.lower() or 'En caso' in out


def test_function_with_params() -> None:
    src = 'int add(int a, int b) { return a + b; } int main() { return add(1,2); }'
    out = _explain(src)
    assert 'add' in out
    assert 'Parámetros' in out or 'parámetro' in out.lower()


def test_bool_literal() -> None:
    out = _explain('int main() { bool x = true; return 0; }')
    assert 'verdadero' in out or 'booleano' in out


def test_ctype_names() -> None:
    e = Explainer()
    assert e._ctype_name('int') == 'entero'
    assert e._ctype_name('float') == 'decimal'
    assert e._ctype_name('char') == 'carácter'
    assert e._ctype_name('bool') == 'booleano'
    assert e._ctype_name('string') == 'cadena'
    assert e._ctype_name('void') == 'void'


def test_string_concat_expr() -> None:
    out = _explain('int main() { string s = "hello" + " world"; println(s); return 0; }')
    assert 'hello' in out or 'más' in out


def test_do_while() -> None:
    out = _explain('int main() { int i = 0; do { i++; } while (i < 3); return 0; }')
    assert 'Repite' in out or 'repite' in out or 'Hasta' in out


def test_break_and_continue() -> None:
    src = 'int main() { int i=0; while(1){if(i>2){break;}i++;} return 0; }'
    out = _explain(src)
    assert 'break' in out or 'Sale' in out


def test_array_decl() -> None:
    out = _explain('int main() { int a[5]; return 0; }')
    assert 'array' in out.lower() or 'Array' in out


def test_global_var_decl() -> None:
    out = _explain('int g = 10; int main() { return g; }')
    assert 'global' in out.lower() or 'g' in out


def test_global_array_decl() -> None:
    out = _explain('int arr[5]; int main() { return 0; }')
    assert 'global' in out.lower() or 'arr' in out


def test_continue_stmt() -> None:
    src = 'int main() { for (int i=0; i<5; i++) { continue; } return 0; }'
    out = _explain(src)
    assert 'continue' in out or 'Continúa' in out


def test_block_stmt() -> None:
    from compiler.ast_nodes import Block, BreakStmt, SourcePos
    from compiler.explainer import Explainer
    pos = SourcePos(1, 1)
    e = Explainer()
    block_stmt = Block(stmts=[BreakStmt(pos=pos)], pos=pos)
    result = e._explain_stmt(block_stmt, 0)
    assert 'Bloque' in result or 'bloque' in result


def test_var_decl_no_init() -> None:
    out = _explain('int main() { int x; return 0; }')
    assert 'sin inicializar' in out or 'x' in out


def test_array_decl_with_init_list() -> None:
    out = _explain('int main() { int a[3] = {1, 2, 3}; return 0; }')
    assert 'inicializado' in out or '1, 2, 3' in out or 'array' in out.lower()


def test_if_with_elif() -> None:
    src = 'int f(int x) { if (x==1) { return 1; } else if (x==2) { return 2; } return 0; }'
    out = _explain(src)
    assert 'Si no' in out or 'elif' in out.lower() or 'si' in out.lower()


def test_return_no_value() -> None:
    out = _explain('void f() { return; } int main() { f(); return 0; }')
    assert 'sin valor' in out or 'Retorna' in out


def test_assign_op_in_explain() -> None:
    from compiler.ast_nodes import AssignOp, Identifier, IntLiteral
    from compiler.explainer import Explainer
    e = Explainer()
    expr = AssignOp(op='=', target=Identifier('x'), value=IntLiteral(5))
    result = e._explain_expr(expr)
    assert 'asigna' in result or '5' in result


def test_index_expr_in_explain() -> None:
    from compiler.ast_nodes import IndexExpr, IntLiteral
    from compiler.explainer import Explainer
    e = Explainer()
    expr = IndexExpr(name='arr', index=IntLiteral(2))
    result = e._explain_expr(expr)
    assert 'arr' in result and '2' in result


def test_cast_expr_in_explain() -> None:
    from compiler.ast_nodes import CastExpr, Identifier
    from compiler.explainer import Explainer
    e = Explainer()
    expr = CastExpr(target_type='float', expr=Identifier('x'))
    result = e._explain_expr(expr)
    assert 'convierte' in result or 'decimal' in result


def test_input_expr_in_explain() -> None:
    from compiler.ast_nodes import InputExpr
    from compiler.explainer import Explainer
    e = Explainer()
    # int variant
    assert 'entero' in e._explain_expr(InputExpr(variant='int'))
    # float variant
    assert 'decimal' in e._explain_expr(InputExpr(variant='float'))
    # string variant
    assert 'texto' in e._explain_expr(InputExpr(variant='string'))


def test_unary_increment_in_explain() -> None:
    from compiler.ast_nodes import UnaryOp, Identifier
    from compiler.explainer import Explainer
    e = Explainer()
    expr = UnaryOp(op='++', operand=Identifier('i'), prefix=True)
    result = e._explain_expr(expr)
    assert 'incrementa' in result


def test_unary_decrement_postfix_in_explain() -> None:
    from compiler.ast_nodes import UnaryOp, Identifier
    from compiler.explainer import Explainer
    e = Explainer()
    expr = UnaryOp(op='--', operand=Identifier('i'), prefix=False)
    result = e._explain_expr(expr)
    assert 'decrementa' in result and 'después' in result


def test_explain_call_no_args() -> None:
    from compiler.ast_nodes import CallExpr
    from compiler.explainer import Explainer
    e = Explainer()
    expr = CallExpr(name='foo', args=[])
    result = e._explain_expr(expr)
    assert 'foo' in result


def test_explain_call_with_args() -> None:
    from compiler.ast_nodes import CallExpr, IntLiteral
    from compiler.explainer import Explainer
    e = Explainer()
    expr = CallExpr(name='bar', args=[IntLiteral(1), IntLiteral(2)])
    result = e._explain_expr(expr)
    assert 'bar' in result and '1' in result
