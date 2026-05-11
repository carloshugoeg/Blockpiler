from compiler.ast_nodes import (
    AssignOp,
    BinaryOp,
    Block,
    BoolLiteral,
    BreakStmt,
    CallExpr,
    CastExpr,
    CharLiteral,
    ContinueStmt,
    DoWhileStmt,
    ExprStmt,
    FloatLiteral,
    ForStmt,
    FunctionDecl,
    Identifier,
    IfStmt,
    IndexExpr,
    InputExpr,
    IntLiteral,
    PrintStmt,
    Program,
    ReturnStmt,
    SourcePos,
    StringLiteral,
    UnaryOp,
    VarDecl,
    WhileStmt,
)
from compiler.ast_to_blocks import ASTtoBlocks, ast_to_blocks
from compiler.blocks_to_ast import blocks_to_ast
from compiler.error_reporter import ErrorReporter

_POS = SourcePos(1, 1)


def _prog(*decls):
    return Program(declarations=list(decls), pos=_POS)


def _func(name='main', rtype='int', params=None, stmts=None):
    return FunctionDecl(
        name=name,
        return_type=rtype,
        params=params or [],
        body=Block(stmts=stmts or [], pos=_POS),
        pos=_POS,
    )


def _block(stmts):
    return Block(stmts=stmts, pos=_POS)


# ── Workspace structure ────────────────────────────────────────────────────────

def test_empty_program() -> None:
    prog = _prog()
    ws = ast_to_blocks(prog)
    assert 'blocks' in ws
    assert ws['blocks']['blocks'] == []


def test_function_decl_structure() -> None:
    prog = _prog(_func('main', 'int', stmts=[ReturnStmt(value=IntLiteral(0), pos=_POS)]))
    ws = ast_to_blocks(prog)
    top = ws['blocks']['blocks']
    assert len(top) == 1
    assert top[0]['type'] == 'c_func_decl'
    assert top[0]['fields']['NAME'] == 'main'
    assert top[0]['fields']['RETURN_TYPE'] == 'int'


def test_srcline_injected() -> None:
    pos = SourcePos(line=5, col=1)
    lit = IntLiteral(value=42, pos=pos)
    prog = _prog(_func(stmts=[ReturnStmt(value=lit, pos=pos)]))
    ws = ast_to_blocks(prog)
    ret_block = ws['blocks']['blocks'][0]['inputs']['BODY']['block']
    assert ret_block['type'] == 'c_return'
    val_block = ret_block['inputs']['VALUE']['block']
    assert val_block['data']['srcLine'] == 5


# ── BinaryOp type selection ────────────────────────────────────────────────────

def test_binary_arith_ops() -> None:
    atb = ASTtoBlocks()
    for op in ('+', '-', '*', '/', '%'):
        b = atb._visit_expr(BinaryOp(op=op, left=IntLiteral(1), right=IntLiteral(2)))
        assert b['type'] == 'c_binary_arith'
        assert b['fields']['OP'] == op


def test_binary_cmp_ops() -> None:
    atb = ASTtoBlocks()
    for op in ('==', '!=', '<', '>', '<=', '>='):
        b = atb._visit_expr(BinaryOp(op=op, left=IntLiteral(1), right=IntLiteral(2)))
        assert b['type'] == 'c_binary_cmp'


def test_binary_logic_ops() -> None:
    atb = ASTtoBlocks()
    for op in ('&&', '||'):
        b = atb._visit_expr(BinaryOp(op=op, left=BoolLiteral(True), right=BoolLiteral(False)))
        assert b['type'] == 'c_binary_logic'


# ── CallExpr in expression vs statement position ──────────────────────────────

def test_call_expr_in_expression_position() -> None:
    atb = ASTtoBlocks()
    call = CallExpr(name='foo', args=[IntLiteral(1)])
    b = atb._visit_expr(call)
    assert b['type'] == 'c_func_call_expr'


def test_call_expr_in_stmt_position() -> None:
    atb = ASTtoBlocks()
    call = CallExpr(name='bar', args=[])
    stmt = ExprStmt(expr=call, pos=_POS)
    b = atb._visit_stmt(stmt)
    assert b is not None
    assert b['type'] == 'c_func_call_stmt'


# ── Literals ──────────────────────────────────────────────────────────────────

def test_int_literal() -> None:
    b = ASTtoBlocks()._visit_expr(IntLiteral(99))
    assert b['type'] == 'c_lit_int'
    assert b['fields']['VALUE'] == 99


def test_float_literal() -> None:
    b = ASTtoBlocks()._visit_expr(FloatLiteral(3.14))
    assert b['type'] == 'c_lit_float'
    assert b['fields']['VALUE'] == 3.14


def test_bool_literal_true() -> None:
    b = ASTtoBlocks()._visit_expr(BoolLiteral(True))
    assert b['type'] == 'c_lit_bool'
    assert b['fields']['VALUE'] == 'true'


def test_bool_literal_false() -> None:
    b = ASTtoBlocks()._visit_expr(BoolLiteral(False))
    assert b['fields']['VALUE'] == 'false'


def test_string_literal() -> None:
    b = ASTtoBlocks()._visit_expr(StringLiteral('hello'))
    assert b['type'] == 'c_lit_string'
    assert b['fields']['VALUE'] == 'hello'


def test_char_literal() -> None:
    b = ASTtoBlocks()._visit_expr(CharLiteral('a'))
    assert b['type'] == 'c_lit_char'


def test_identifier() -> None:
    b = ASTtoBlocks()._visit_expr(Identifier('x'))
    assert b['type'] == 'c_identifier'
    assert b['fields']['NAME'] == 'x'


def test_index_expr() -> None:
    b = ASTtoBlocks()._visit_expr(IndexExpr('arr', IntLiteral(0)))
    assert b['type'] == 'c_index_expr'
    assert b['fields']['NAME'] == 'arr'


# ── Control flow ───────────────────────────────────────────────────────────────

def test_if_without_else() -> None:
    stmt = IfStmt(
        condition=BoolLiteral(True),
        then_body=_block([BreakStmt(pos=_POS)]),
        elif_clauses=[],
        else_body=None,
        pos=_POS,
    )
    b = ASTtoBlocks()._visit_stmt(stmt)
    assert b is not None
    assert b['type'] == 'c_if'
    assert 'ELSE' not in b['inputs']


def test_if_with_else() -> None:
    stmt = IfStmt(
        condition=BoolLiteral(True),
        then_body=_block([BreakStmt(pos=_POS)]),
        elif_clauses=[],
        else_body=_block([ContinueStmt(pos=_POS)]),
        pos=_POS,
    )
    b = ASTtoBlocks()._visit_stmt(stmt)
    assert b is not None
    assert 'ELSE' in b['inputs']


def test_while_stmt() -> None:
    stmt = WhileStmt(condition=BoolLiteral(True), body=_block([BreakStmt(pos=_POS)]), pos=_POS)
    b = ASTtoBlocks()._visit_stmt(stmt)
    assert b is not None
    assert b['type'] == 'c_while'


def test_for_stmt() -> None:
    stmt = ForStmt(
        init=VarDecl('i', 'int', IntLiteral(0), _POS),
        condition=BinaryOp('<', Identifier('i'), IntLiteral(10)),
        update=UnaryOp('++', Identifier('i'), prefix=False),
        body=_block([BreakStmt(pos=_POS)]),
        pos=_POS,
    )
    b = ASTtoBlocks()._visit_stmt(stmt)
    assert b is not None
    assert b['type'] == 'c_for'
    assert 'INIT' in b['inputs']
    assert 'COND' in b['inputs']
    assert 'UPDATE' in b['inputs']


def test_dowhile_stmt() -> None:
    stmt = DoWhileStmt(
        body=_block([BreakStmt(pos=_POS)]),
        condition=BoolLiteral(False),
        pos=_POS,
    )
    b = ASTtoBlocks()._visit_stmt(stmt)
    assert b is not None
    assert b['type'] == 'c_dowhile'


def test_return_stmt() -> None:
    b = ASTtoBlocks()._visit_stmt(ReturnStmt(value=IntLiteral(0), pos=_POS))
    assert b is not None
    assert b['type'] == 'c_return'
    assert 'VALUE' in b['inputs']


def test_break_stmt() -> None:
    b = ASTtoBlocks()._visit_stmt(BreakStmt(pos=_POS))
    assert b is not None
    assert b['type'] == 'c_break'


def test_continue_stmt() -> None:
    b = ASTtoBlocks()._visit_stmt(ContinueStmt(pos=_POS))
    assert b is not None
    assert b['type'] == 'c_continue'


def test_print_stmt() -> None:
    b = ASTtoBlocks()._visit_stmt(PrintStmt(expr=IntLiteral(1), newline=False, pos=_POS))
    assert b is not None
    assert b['type'] == 'c_print'


def test_println_stmt() -> None:
    b = ASTtoBlocks()._visit_stmt(PrintStmt(expr=IntLiteral(1), newline=True, pos=_POS))
    assert b is not None
    assert b['type'] == 'c_println'


# ── Expressions ────────────────────────────────────────────────────────────────

def test_unary_not() -> None:
    b = ASTtoBlocks()._visit_expr(UnaryOp('!', BoolLiteral(True), prefix=True))
    assert b['type'] == 'c_unary_not'


def test_unary_neg() -> None:
    b = ASTtoBlocks()._visit_expr(UnaryOp('-', IntLiteral(1), prefix=True))
    assert b['type'] == 'c_unary_neg'


def test_prefix_inc() -> None:
    b = ASTtoBlocks()._visit_expr(UnaryOp('++', Identifier('x'), prefix=True))
    assert b['type'] == 'c_prefix_inc'


def test_postfix_dec() -> None:
    b = ASTtoBlocks()._visit_expr(UnaryOp('--', Identifier('x'), prefix=False))
    assert b['type'] == 'c_postfix_dec'


def test_assign_op() -> None:
    b = ASTtoBlocks()._visit_expr(AssignOp('=', Identifier('x'), IntLiteral(5)))
    assert b['type'] == 'c_assign'


def test_compound_assign_op() -> None:
    b = ASTtoBlocks()._visit_expr(AssignOp('+=', Identifier('x'), IntLiteral(1)))
    assert b['type'] == 'c_compound_assign'


def test_cast_expr() -> None:
    b = ASTtoBlocks()._visit_expr(CastExpr('float', IntLiteral(3)))
    assert b['type'] == 'c_cast'
    assert b['fields']['TYPE'] == 'float'


def test_input_variants() -> None:
    atb = ASTtoBlocks()
    assert atb._visit_expr(InputExpr('string'))['type'] == 'c_input'
    assert atb._visit_expr(InputExpr('int'))['type'] == 'c_input_int'
    assert atb._visit_expr(InputExpr('float'))['type'] == 'c_input_float'


# ── Module-level function ──────────────────────────────────────────────────────

def test_module_level_function() -> None:
    prog = _prog()
    ws = ast_to_blocks(prog)
    assert isinstance(ws, dict)


# ── Roundtrip AST → Blocks → AST ──────────────────────────────────────────────

def _roundtrip(prog: Program) -> Program:
    ws = ast_to_blocks(prog)
    r = ErrorReporter()
    return blocks_to_ast(ws, r)


def test_roundtrip_empty_program() -> None:
    prog = _prog()
    rt = _roundtrip(prog)
    assert isinstance(rt, Program)
    assert rt.declarations == []


def test_roundtrip_function_with_return() -> None:
    orig = _prog(_func('main', 'int', stmts=[ReturnStmt(value=IntLiteral(42), pos=_POS)]))
    rt = _roundtrip(orig)
    assert len(rt.declarations) == 1
    fn = rt.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert fn.name == 'main'
    assert fn.return_type == 'int'
    assert len(fn.body.stmts) == 1
    assert isinstance(fn.body.stmts[0], ReturnStmt)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 42


def test_roundtrip_binary_op() -> None:
    expr = BinaryOp('+', IntLiteral(1), IntLiteral(2))
    stmt = ReturnStmt(value=expr, pos=_POS)
    orig = _prog(_func(stmts=[stmt]))
    rt = _roundtrip(orig)
    fn = rt.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, BinaryOp)
    assert ret.value.op == '+'


def test_roundtrip_var_decl() -> None:
    decl = VarDecl('x', 'int', IntLiteral(10), _POS)
    orig = _prog(_func(stmts=[decl]))
    rt = _roundtrip(orig)
    fn = rt.declarations[0]
    assert isinstance(fn, FunctionDecl)
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, VarDecl)
    assert stmt.name == 'x'
    assert isinstance(stmt.init_expr, IntLiteral)
    assert stmt.init_expr.value == 10


def test_roundtrip_if_else() -> None:
    if_stmt = IfStmt(
        condition=BoolLiteral(True),
        then_body=_block([BreakStmt(pos=_POS)]),
        elif_clauses=[],
        else_body=_block([ContinueStmt(pos=_POS)]),
        pos=_POS,
    )
    orig = _prog(_func(stmts=[if_stmt]))
    rt = _roundtrip(orig)
    fn = rt.declarations[0]
    assert isinstance(fn, FunctionDecl)
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, IfStmt)
    assert stmt.else_body is not None


def test_roundtrip_while() -> None:
    while_stmt = WhileStmt(
        condition=BoolLiteral(True),
        body=_block([BreakStmt(pos=_POS)]),
        pos=_POS,
    )
    orig = _prog(_func(stmts=[while_stmt]))
    rt = _roundtrip(orig)
    fn = rt.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert isinstance(fn.body.stmts[0], WhileStmt)


def test_roundtrip_print() -> None:
    print_stmt = PrintStmt(expr=IntLiteral(5), newline=True, pos=_POS)
    orig = _prog(_func(stmts=[print_stmt]))
    rt = _roundtrip(orig)
    fn = rt.declarations[0]
    assert isinstance(fn, FunctionDecl)
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, PrintStmt)
    assert stmt.newline is True
