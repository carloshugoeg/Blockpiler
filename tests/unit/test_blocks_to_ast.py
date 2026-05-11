from compiler.ast_nodes import (
    ArrayDecl,
    BinaryOp,
    Block,
    BoolLiteral,
    BreakStmt,
    CallExpr,
    CastExpr,
    ContinueStmt,
    DoWhileStmt,
    ExprStmt,
    FloatLiteral,
    ForStmt,
    FunctionDecl,
    IfStmt,
    IndexExpr,
    InputExpr,
    IntLiteral,
    PrintStmt,
    Program,
    ReturnStmt,
    StringLiteral,
    UnaryOp,
    VarDecl,
    WhileStmt,
)
from compiler.blocks_to_ast import BlocksToAST, blocks_to_ast
from compiler.error_reporter import ErrorReporter


def _bta(workspace):
    r = ErrorReporter()
    return BlocksToAST(r).convert(workspace), r


def _empty_ws():
    return {'blocks': {'languageVersion': 0, 'blocks': []}}


def _func_ws(func_block):
    return {'blocks': {'languageVersion': 0, 'blocks': [func_block]}}


def _lit_int(val, src_line=0):
    return {'type': 'c_lit_int', 'fields': {'VALUE': val}, 'data': {'srcLine': src_line}}


def _lit_bool(val):
    return {'type': 'c_lit_bool', 'fields': {'VALUE': 'true' if val else 'false'}}


def _identifier(name):
    return {'type': 'c_identifier', 'fields': {'NAME': name}}


# ── Workspace tests ────────────────────────────────────────────────────────────

def test_empty_workspace_returns_empty_program() -> None:
    prog, r = _bta(_empty_ws())
    assert isinstance(prog, Program)
    assert prog.declarations == []
    assert not r.has_errors


def test_none_workspace_no_crash() -> None:
    r = ErrorReporter()
    prog = BlocksToAST(r).convert(None)  # type: ignore[arg-type]
    assert isinstance(prog, Program)
    assert prog.declarations == []


def test_empty_dict_no_crash() -> None:
    prog, _ = _bta({})
    assert isinstance(prog, Program)


# ── Function declaration ───────────────────────────────────────────────────────

def test_function_decl_basic() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'main', 'RETURN_TYPE': 'int'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_return',
                    'inputs': {'VALUE': {'block': _lit_int(0)}},
                }
            }
        },
        'data': {'srcLine': 1},
    }
    prog, r = _bta(_func_ws(func_block))
    assert len(prog.declarations) == 1
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert fn.name == 'main'
    assert fn.return_type == 'int'
    assert not r.has_errors


def test_function_with_params() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'add', 'RETURN_TYPE': 'int'},
        'inputs': {
            'PARAMS': {
                'block': {
                    'type': 'c_param',
                    'fields': {'NAME': 'a', 'TYPE': 'int'},
                    'next': {
                        'block': {'type': 'c_param', 'fields': {'NAME': 'b', 'TYPE': 'int'}}
                    },
                }
            },
            'BODY': {'block': {'type': 'c_return', 'inputs': {'VALUE': {'block': _lit_int(0)}}}},
        },
    }
    prog, r = _bta(_func_ws(func_block))
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert len(fn.params) == 2
    assert fn.params[0].name == 'a'
    assert fn.params[1].name == 'b'


# ── Variable declarations ──────────────────────────────────────────────────────

def test_var_decl_with_init() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'int'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_var_decl',
                    'fields': {'NAME': 'x', 'TYPE': 'int'},
                    'inputs': {'VALUE': {'block': _lit_int(42)}},
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    fn = prog.declarations[0]
    assert isinstance(fn, FunctionDecl)
    stmt = fn.body.stmts[0]
    assert isinstance(stmt, VarDecl)
    assert stmt.name == 'x'
    assert stmt.type == 'int'
    assert isinstance(stmt.init_expr, IntLiteral)
    assert stmt.init_expr.value == 42


def test_var_decl_no_init() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_var_decl',
                    'fields': {'NAME': 'y', 'TYPE': 'float'},
                    'inputs': {},
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmt = prog.declarations[0].body.stmts[0]
    assert isinstance(stmt, VarDecl)
    assert stmt.init_expr is None


# ── Control flow ───────────────────────────────────────────────────────────────

def test_if_without_else() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_if',
                    'inputs': {
                        'COND': {'block': _lit_bool(True)},
                        'THEN': {'block': {'type': 'c_break'}},
                    },
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmt = prog.declarations[0].body.stmts[0]
    assert isinstance(stmt, IfStmt)
    assert stmt.else_body is None
    assert isinstance(stmt.condition, BoolLiteral)
    assert stmt.condition.value is True


def test_if_with_else() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_if',
                    'inputs': {
                        'COND': {'block': _lit_bool(True)},
                        'THEN': {'block': {'type': 'c_break'}},
                        'ELSE': {'block': {'type': 'c_continue'}},
                    },
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmt = prog.declarations[0].body.stmts[0]
    assert isinstance(stmt, IfStmt)
    assert stmt.else_body is not None
    assert isinstance(stmt.else_body.stmts[0], ContinueStmt)


def test_while_stmt() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_while',
                    'inputs': {
                        'COND': {'block': _lit_bool(True)},
                        'BODY': {'block': {'type': 'c_break'}},
                    },
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmt = prog.declarations[0].body.stmts[0]
    assert isinstance(stmt, WhileStmt)


def test_for_stmt() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_for',
                    'inputs': {
                        'INIT': {'block': {'type': 'c_var_decl', 'fields': {'NAME': 'i', 'TYPE': 'int'}, 'inputs': {'VALUE': {'block': _lit_int(0)}}}},
                        'COND': {'block': {'type': 'c_binary_cmp', 'fields': {'OP': '<'}, 'inputs': {'LEFT': {'block': _identifier('i')}, 'RIGHT': {'block': _lit_int(10)}}}},
                        'BODY': {'block': {'type': 'c_break'}},
                    },
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmt = prog.declarations[0].body.stmts[0]
    assert isinstance(stmt, ForStmt)
    assert isinstance(stmt.init, VarDecl)
    assert isinstance(stmt.condition, BinaryOp)
    assert stmt.condition.op == '<'


def test_dowhile_stmt() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_dowhile',
                    'inputs': {
                        'BODY': {'block': {'type': 'c_break'}},
                        'COND': {'block': _lit_bool(False)},
                    },
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmt = prog.declarations[0].body.stmts[0]
    assert isinstance(stmt, DoWhileStmt)


def test_break_continue() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_break',
                    'next': {'block': {'type': 'c_continue'}},
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmts = prog.declarations[0].body.stmts
    assert isinstance(stmts[0], BreakStmt)
    assert isinstance(stmts[1], ContinueStmt)


def test_return_with_value() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'int'},
        'inputs': {
            'BODY': {'block': {'type': 'c_return', 'inputs': {'VALUE': {'block': _lit_int(7)}}}}
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmt = prog.declarations[0].body.stmts[0]
    assert isinstance(stmt, ReturnStmt)
    assert isinstance(stmt.value, IntLiteral)
    assert stmt.value.value == 7


def test_print_and_println() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_print',
                    'inputs': {'VALUE': {'block': _lit_int(1)}},
                    'next': {
                        'block': {
                            'type': 'c_println',
                            'inputs': {'VALUE': {'block': _lit_int(2)}},
                        }
                    },
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmts = prog.declarations[0].body.stmts
    assert isinstance(stmts[0], PrintStmt)
    assert stmts[0].newline is False
    assert isinstance(stmts[1], PrintStmt)
    assert stmts[1].newline is True


# ── Expressions ────────────────────────────────────────────────────────────────

def test_binary_arith() -> None:
    block = {'type': 'c_binary_arith', 'fields': {'OP': '+'}, 'inputs': {
        'LEFT': {'block': _lit_int(3)},
        'RIGHT': {'block': _lit_int(4)},
    }}
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, BinaryOp)
    assert expr.op == '+'
    assert isinstance(expr.left, IntLiteral)
    assert isinstance(expr.right, IntLiteral)


def test_binary_cmp() -> None:
    block = {'type': 'c_binary_cmp', 'fields': {'OP': '=='}, 'inputs': {
        'LEFT': {'block': _lit_int(1)},
        'RIGHT': {'block': _lit_int(1)},
    }}
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, BinaryOp)
    assert expr.op == '=='


def test_binary_logic() -> None:
    block = {'type': 'c_binary_logic', 'fields': {'OP': '&&'}, 'inputs': {
        'LEFT': {'block': _lit_bool(True)},
        'RIGHT': {'block': _lit_bool(False)},
    }}
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, BinaryOp)
    assert expr.op == '&&'


def test_unary_not() -> None:
    block = {'type': 'c_unary_not', 'inputs': {'VALUE': {'block': _lit_bool(True)}}}
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, UnaryOp)
    assert expr.op == '!'
    assert expr.prefix is True


def test_prefix_inc() -> None:
    block = {'type': 'c_prefix_inc', 'inputs': {'VALUE': {'block': _identifier('x')}}}
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, UnaryOp)
    assert expr.op == '++'
    assert expr.prefix is True


def test_postfix_dec() -> None:
    block = {'type': 'c_postfix_dec', 'inputs': {'VALUE': {'block': _identifier('x')}}}
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, UnaryOp)
    assert expr.op == '--'
    assert expr.prefix is False


def test_func_call_expr() -> None:
    block = {
        'type': 'c_func_call_expr',
        'fields': {'NAME': 'foo'},
        'inputs': {'ARGS': {'block': _lit_int(1)}},
    }
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, CallExpr)
    assert expr.name == 'foo'
    assert len(expr.args) == 1


def test_literals() -> None:
    r = ErrorReporter()
    bta = BlocksToAST(r)

    int_expr = bta._convert_expr({'type': 'c_lit_int', 'fields': {'VALUE': 99}})
    assert isinstance(int_expr, IntLiteral)
    assert int_expr.value == 99

    float_expr = bta._convert_expr({'type': 'c_lit_float', 'fields': {'VALUE': 3.14}})
    assert isinstance(float_expr, FloatLiteral)
    assert float_expr.value == 3.14

    bool_expr = bta._convert_expr({'type': 'c_lit_bool', 'fields': {'VALUE': 'true'}})
    assert isinstance(bool_expr, BoolLiteral)
    assert bool_expr.value is True

    str_expr = bta._convert_expr({'type': 'c_lit_string', 'fields': {'VALUE': 'hi'}})
    assert isinstance(str_expr, StringLiteral)
    assert str_expr.value == 'hi'


def test_identifier_and_index() -> None:
    r = ErrorReporter()
    bta = BlocksToAST(r)

    id_expr = bta._convert_expr({'type': 'c_identifier', 'fields': {'NAME': 'abc'}})
    assert isinstance(id_expr, IntLiteral) or hasattr(id_expr, 'name')

    idx_expr = bta._convert_expr({
        'type': 'c_index_expr',
        'fields': {'NAME': 'arr'},
        'inputs': {'INDEX': {'block': _lit_int(0)}},
    })
    assert isinstance(idx_expr, IndexExpr)
    assert idx_expr.name == 'arr'


def test_input_variants() -> None:
    r = ErrorReporter()
    bta = BlocksToAST(r)
    e1 = bta._convert_expr({'type': 'c_input'})
    assert isinstance(e1, InputExpr)
    assert e1.variant == 'string'

    e2 = bta._convert_expr({'type': 'c_input_int'})
    assert isinstance(e2, InputExpr)
    assert e2.variant == 'int'

    e3 = bta._convert_expr({'type': 'c_input_float'})
    assert isinstance(e3, InputExpr)
    assert e3.variant == 'float'


def test_cast_expr() -> None:
    block = {
        'type': 'c_cast',
        'fields': {'TYPE': 'float'},
        'inputs': {'VALUE': {'block': _lit_int(3)}},
    }
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, CastExpr)
    assert expr.target_type == 'float'


# ── Error handling ─────────────────────────────────────────────────────────────

def test_unknown_block_reports_error_no_crash() -> None:
    ws = {'blocks': {'blocks': [{'type': 'c_totally_unknown', 'fields': {}}]}}
    prog, r = _bta(ws)
    assert isinstance(prog, Program)
    assert r.has_errors


def test_none_values_in_inputs_no_crash() -> None:
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'int'},
        'inputs': {'BODY': None},
    }
    prog, _ = _bta(_func_ws(func_block))
    assert isinstance(prog, Program)


def test_srcline_extracted() -> None:
    block = {'type': 'c_lit_int', 'fields': {'VALUE': 5}, 'data': {'srcLine': 7}}
    r = ErrorReporter()
    expr = BlocksToAST(r)._convert_expr(block)
    assert isinstance(expr, IntLiteral)
    assert expr.pos.line == 7


def test_module_level_function() -> None:
    r = ErrorReporter()
    prog = blocks_to_ast(_empty_ws(), r)
    assert isinstance(prog, Program)


def test_array_decl_block() -> None:
    ws = {
        'blocks': {
            'blocks': [{
                'type': 'c_array_decl',
                'fields': {'NAME': 'arr', 'TYPE': 'int', 'SIZE': 5},
                'inputs': {},
            }]
        }
    }
    prog, _ = _bta(ws)
    assert len(prog.declarations) == 1
    assert isinstance(prog.declarations[0], ArrayDecl)
    assert prog.declarations[0].size == 5


def test_chained_statements() -> None:
    """Multiple statements in a function body via next-chaining."""
    func_block = {
        'type': 'c_func_decl',
        'fields': {'NAME': 'f', 'RETURN_TYPE': 'void'},
        'inputs': {
            'BODY': {
                'block': {
                    'type': 'c_break',
                    'next': {'block': {'type': 'c_continue', 'next': {'block': {'type': 'c_break'}}}},
                }
            }
        },
    }
    prog, _ = _bta(_func_ws(func_block))
    stmts = prog.declarations[0].body.stmts
    assert len(stmts) == 3
    assert isinstance(stmts[0], BreakStmt)
    assert isinstance(stmts[1], ContinueStmt)
    assert isinstance(stmts[2], BreakStmt)
