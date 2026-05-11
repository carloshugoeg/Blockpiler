from compiler.ast_nodes import (
    ArrayDecl,
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
    Parameter,
    PrintStmt,
    Program,
    ReturnStmt,
    SourcePos,
    StringLiteral,
    UnaryOp,
    VarDecl,
    WhileStmt,
    get_pos,
    is_expression,
    is_lvalue,
    is_pure_expr,
    node_type_name,
)


# ─── Instantiation tests ───────────────────────────────────────────────────────

def test_source_pos_defaults() -> None:
    p = SourcePos(1, 2)
    assert p.line == 1
    assert p.col == 2
    assert p.length == 1


def test_source_pos_explicit_length() -> None:
    p = SourcePos(3, 4, 5)
    assert p.length == 5


def test_program() -> None:
    pos = SourcePos(1, 1)
    prog = Program(declarations=[], pos=pos)
    assert prog.declarations == []
    assert prog.pos is pos


def test_function_decl() -> None:
    pos = SourcePos(1, 1)
    body = Block(stmts=[], pos=pos)
    fd = FunctionDecl(name='main', return_type='int', params=[], body=body, pos=pos)
    assert fd.name == 'main'
    assert fd.return_type == 'int'


def test_parameter() -> None:
    pos = SourcePos(1, 1)
    p = Parameter(name='x', type='int', pos=pos)
    assert p.name == 'x'


def test_var_decl() -> None:
    pos = SourcePos(1, 1)
    vd = VarDecl(name='x', type='int', init_expr=None, pos=pos)
    assert vd.init_expr is None


def test_array_decl() -> None:
    pos = SourcePos(1, 1)
    ad = ArrayDecl(name='arr', element_type='int', size=10, init_list=[], pos=pos)
    assert ad.size == 10


def test_block() -> None:
    pos = SourcePos(1, 1)
    b = Block(stmts=[], pos=pos)
    assert b.stmts == []


def test_if_stmt() -> None:
    pos = SourcePos(1, 1)
    cond = BoolLiteral(value=True)
    body = Block(stmts=[], pos=pos)
    stmt = IfStmt(condition=cond, then_body=body, elif_clauses=[], else_body=None, pos=pos)
    assert stmt.else_body is None


def test_while_stmt() -> None:
    pos = SourcePos(1, 1)
    cond = BoolLiteral(value=True)
    body = Block(stmts=[], pos=pos)
    w = WhileStmt(condition=cond, body=body, pos=pos)
    assert w.condition is cond


def test_for_stmt() -> None:
    pos = SourcePos(1, 1)
    body = Block(stmts=[], pos=pos)
    f = ForStmt(init=None, condition=None, update=None, body=body, pos=pos)
    assert f.init is None


def test_do_while_stmt() -> None:
    pos = SourcePos(1, 1)
    body = Block(stmts=[], pos=pos)
    cond = BoolLiteral(value=False)
    dw = DoWhileStmt(body=body, condition=cond, pos=pos)
    assert dw.condition is cond


def test_return_stmt() -> None:
    pos = SourcePos(1, 1)
    r = ReturnStmt(value=None, pos=pos)
    assert r.value is None


def test_break_stmt() -> None:
    pos = SourcePos(1, 1)
    b = BreakStmt(pos=pos)
    assert b.pos is pos


def test_continue_stmt() -> None:
    pos = SourcePos(1, 1)
    c = ContinueStmt(pos=pos)
    assert c.pos is pos


def test_print_stmt() -> None:
    pos = SourcePos(1, 1)
    expr = StringLiteral(value='hello')
    ps = PrintStmt(expr=expr, newline=True, pos=pos)
    assert ps.newline is True


def test_expr_stmt() -> None:
    pos = SourcePos(1, 1)
    expr = IntLiteral(value=0)
    es = ExprStmt(expr=expr, pos=pos)
    assert es.expr is expr


def test_binary_op() -> None:
    b = BinaryOp(op='+', left=IntLiteral(1), right=IntLiteral(2))
    assert b.op == '+'
    assert b.inferred_type == 'unknown'


def test_unary_op() -> None:
    u = UnaryOp(op='-', operand=IntLiteral(1), prefix=True)
    assert u.prefix is True
    assert u.inferred_type == 'unknown'


def test_assign_op() -> None:
    a = AssignOp(op='=', target=Identifier('x'), value=IntLiteral(0))
    assert a.op == '='


def test_call_expr_defaults() -> None:
    c = CallExpr(name='foo', args=[])
    assert c.is_tail_call is False
    assert c.inferred_type == 'unknown'


def test_index_expr() -> None:
    ix = IndexExpr(name='arr', index=IntLiteral(0))
    assert ix.inferred_type == 'unknown'


def test_identifier() -> None:
    ident = Identifier(name='x')
    assert ident.inferred_type == 'unknown'


def test_int_literal() -> None:
    n = IntLiteral(value=42)
    assert n.inferred_type == 'int'


def test_float_literal() -> None:
    f = FloatLiteral(value=3.14)
    assert f.inferred_type == 'float'


def test_string_literal() -> None:
    s = StringLiteral(value='hello')
    assert s.inferred_type == 'string'


def test_char_literal() -> None:
    c = CharLiteral(value='a')
    assert c.inferred_type == 'char'


def test_bool_literal() -> None:
    b = BoolLiteral(value=True)
    assert b.inferred_type == 'bool'


def test_input_expr_defaults() -> None:
    ie = InputExpr()
    assert ie.variant == 'string'
    assert ie.inferred_type == 'string'


def test_input_expr_variants() -> None:
    assert InputExpr(variant='int').variant == 'int'
    assert InputExpr(variant='float').variant == 'float'


def test_cast_expr() -> None:
    ce = CastExpr(target_type='float', expr=IntLiteral(1))
    assert ce.inferred_type == 'unknown'


# ─── is_expression ─────────────────────────────────────────────────────────────

def test_is_expression_true_for_all_expr_types() -> None:
    exprs = [
        BinaryOp('+', IntLiteral(1), IntLiteral(2)),
        UnaryOp('-', IntLiteral(1), True),
        AssignOp('=', Identifier('x'), IntLiteral(0)),
        CallExpr('f', []),
        IndexExpr('arr', IntLiteral(0)),
        Identifier('x'),
        IntLiteral(0),
        FloatLiteral(0.0),
        StringLiteral(''),
        CharLiteral('a'),
        BoolLiteral(False),
        InputExpr(),
        CastExpr('int', FloatLiteral(1.0)),
    ]
    for expr in exprs:
        assert is_expression(expr), f"Expected is_expression to be True for {type(expr).__name__}"


def test_is_expression_false_for_statements() -> None:
    pos = SourcePos(1, 1)
    body = Block(stmts=[], pos=pos)
    stmts = [
        Program([], pos),
        FunctionDecl('f', 'void', [], body, pos),
        Parameter('x', 'int', pos),
        VarDecl('x', 'int', None, pos),
        ArrayDecl('a', 'int', 1, [], pos),
        Block([], pos),
        IfStmt(BoolLiteral(True), body, [], None, pos),
        WhileStmt(BoolLiteral(True), body, pos),
        ForStmt(None, None, None, body, pos),
        DoWhileStmt(body, BoolLiteral(False), pos),
        ReturnStmt(None, pos),
        BreakStmt(pos),
        ContinueStmt(pos),
        PrintStmt(StringLiteral(''), False, pos),
        ExprStmt(IntLiteral(0), pos),
    ]
    for stmt in stmts:
        assert not is_expression(stmt), f"Expected is_expression to be False for {type(stmt).__name__}"


# ─── is_lvalue ─────────────────────────────────────────────────────────────────

def test_is_lvalue_true_for_identifier_and_indexexpr() -> None:
    assert is_lvalue(Identifier('x')) is True
    assert is_lvalue(IndexExpr('arr', IntLiteral(0))) is True


def test_is_lvalue_false_for_others() -> None:
    assert is_lvalue(IntLiteral(1)) is False
    assert is_lvalue(CallExpr('f', [])) is False
    assert is_lvalue(BinaryOp('+', IntLiteral(1), IntLiteral(2))) is False
    assert is_lvalue(AssignOp('=', Identifier('x'), IntLiteral(0))) is False


# ─── is_pure_expr ──────────────────────────────────────────────────────────────

def test_is_pure_expr_literals_are_pure() -> None:
    assert is_pure_expr(IntLiteral(1)) is True
    assert is_pure_expr(FloatLiteral(1.0)) is True
    assert is_pure_expr(StringLiteral('hi')) is True
    assert is_pure_expr(CharLiteral('a')) is True
    assert is_pure_expr(BoolLiteral(True)) is True


def test_is_pure_expr_identifier_is_pure() -> None:
    assert is_pure_expr(Identifier('x')) is True


def test_is_pure_expr_call_expr_is_not_pure() -> None:
    assert is_pure_expr(CallExpr('f', [])) is False


def test_is_pure_expr_input_expr_is_not_pure() -> None:
    assert is_pure_expr(InputExpr()) is False


def test_is_pure_expr_assign_op_is_not_pure() -> None:
    assert is_pure_expr(AssignOp('=', Identifier('x'), IntLiteral(0))) is False


def test_is_pure_expr_unary_increment_not_pure() -> None:
    assert is_pure_expr(UnaryOp('++', Identifier('x'), True)) is False
    assert is_pure_expr(UnaryOp('--', Identifier('x'), False)) is False


def test_is_pure_expr_unary_minus_is_pure() -> None:
    assert is_pure_expr(UnaryOp('-', IntLiteral(1), True)) is True


def test_is_pure_expr_unary_not_is_pure() -> None:
    assert is_pure_expr(UnaryOp('!', BoolLiteral(True), True)) is True


def test_is_pure_expr_unary_with_call_not_pure() -> None:
    assert is_pure_expr(UnaryOp('-', CallExpr('f', []), True)) is False


def test_is_pure_expr_binary_with_literals_is_pure() -> None:
    b = BinaryOp('+', IntLiteral(1), IntLiteral(2))
    assert is_pure_expr(b) is True


def test_is_pure_expr_binary_with_call_not_pure() -> None:
    b = BinaryOp('+', CallExpr('f', []), IntLiteral(2))
    assert is_pure_expr(b) is False


def test_is_pure_expr_cast_with_literal_is_pure() -> None:
    assert is_pure_expr(CastExpr('float', IntLiteral(1))) is True


def test_is_pure_expr_cast_with_call_not_pure() -> None:
    assert is_pure_expr(CastExpr('float', CallExpr('f', []))) is False


def test_is_pure_expr_index_with_literal_is_pure() -> None:
    assert is_pure_expr(IndexExpr('arr', IntLiteral(0))) is True


def test_is_pure_expr_index_with_call_not_pure() -> None:
    assert is_pure_expr(IndexExpr('arr', CallExpr('f', []))) is False


# ─── get_pos ───────────────────────────────────────────────────────────────────

def test_get_pos_returns_pos_when_present() -> None:
    pos = SourcePos(5, 10)
    node = IntLiteral(1, pos=pos)
    result = get_pos(node)
    assert result.line == 5
    assert result.col == 10


def test_get_pos_returns_default_when_missing() -> None:
    class NoPos:
        pass
    result = get_pos(NoPos())
    assert result == SourcePos(0, 0)


# ─── node_type_name ────────────────────────────────────────────────────────────

def test_node_type_name() -> None:
    assert node_type_name(IntLiteral(1)) == 'IntLiteral'
    assert node_type_name(BinaryOp('+', IntLiteral(1), IntLiteral(2))) == 'BinaryOp'
    assert node_type_name(SourcePos(1, 1)) == 'SourcePos'
