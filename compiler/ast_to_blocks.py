from __future__ import annotations

import uuid
from typing import Any

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
)

_ARITH_OPS = {'+', '-', '*', '/', '%'}
_CMP_OPS = {'==', '!=', '<', '>', '<=', '>='}
_LOGIC_OPS = {'&&', '||'}


class ASTtoBlocks:
    def __init__(self) -> None:
        pass

    def convert(self, program: Program) -> dict[str, Any]:
        return self._visit_program(program)

    # ── Top-level ──────────────────────────────────────────────────────────────

    def _visit_program(self, program: Program) -> dict[str, Any]:
        top_blocks: list[dict[str, Any]] = []
        for i, decl in enumerate(program.declarations):
            if isinstance(decl, FunctionDecl):
                block = self._visit_function_decl(decl)
            elif isinstance(decl, VarDecl):
                block = self._visit_var_decl(decl)
            elif isinstance(decl, ArrayDecl):
                block = self._visit_array_decl(decl)
            else:
                continue
            block['x'] = 20
            block['y'] = 20 + i * 300
            top_blocks.append(block)
        return {'blocks': {'languageVersion': 0, 'blocks': top_blocks}}

    def _visit_function_decl(self, func: FunctionDecl) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_func_decl',
            'id': self._uid(),
            'fields': {
                'NAME': func.name,
                'TYPE': func.return_type,
                'RETURN_TYPE': func.return_type,
            },
            'inputs': {},
        }
        self._inject_src_line(block, func.pos)
        if func.params:
            block['inputs']['PARAMS'] = self._chain_params(func.params)
        body_stmts = self._visit_block(func.body)
        if body_stmts:
            block['inputs']['BODY'] = {'block': self._chain_stmts(body_stmts)}
        return block

    def _chain_params(self, params: list[Parameter]) -> dict[str, Any]:
        root: dict[str, Any] | None = None
        current: dict[str, Any] | None = None
        for p in params:
            pb: dict[str, Any] = {
                'type': 'c_param',
                'id': self._uid(),
                'fields': {'NAME': p.name, 'TYPE': p.type},
            }
            self._inject_src_line(pb, p.pos)
            if root is None:
                root = pb
                current = pb
            else:
                assert current is not None
                current['next'] = {'block': pb}
                current = pb
        return {'block': root}

    def _visit_var_decl(self, decl: VarDecl) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_var_decl',
            'id': self._uid(),
            'fields': {'NAME': decl.name, 'TYPE': decl.type},
            'inputs': {},
        }
        self._inject_src_line(block, decl.pos)
        if decl.init_expr is not None:
            block['inputs']['VALUE'] = {'block': self._visit_expr(decl.init_expr)}
        return block

    def _visit_array_decl(self, decl: ArrayDecl) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_array_decl',
            'id': self._uid(),
            'fields': {'NAME': decl.name, 'TYPE': decl.element_type, 'SIZE': decl.size},
            'inputs': {
                'SIZE': {'block': {
                    'type': 'c_lit_int', 'id': self._uid(),
                    'fields': {'VALUE': decl.size}, 'data': {'srcLine': 0},
                }},
            },
        }
        self._inject_src_line(block, decl.pos)
        if decl.init_list:
            block['inputs']['INIT'] = {'block': self._chain_exprs(decl.init_list)}
        return block

    # ── Statements ─────────────────────────────────────────────────────────────

    def _visit_block(self, block: Block) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for stmt in block.stmts:
            b = self._visit_stmt(stmt)
            if b is not None:
                result.append(b)
        return result

    def _visit_stmt(self, stmt: Any) -> dict[str, Any] | None:
        if isinstance(stmt, VarDecl):
            return self._visit_var_decl(stmt)
        if isinstance(stmt, ArrayDecl):
            return self._visit_array_decl(stmt)
        if isinstance(stmt, IfStmt):
            return self._visit_if_stmt(stmt)
        if isinstance(stmt, WhileStmt):
            return self._visit_while_stmt(stmt)
        if isinstance(stmt, ForStmt):
            return self._visit_for_stmt(stmt)
        if isinstance(stmt, DoWhileStmt):
            return self._visit_dowhile_stmt(stmt)
        if isinstance(stmt, ReturnStmt):
            return self._visit_return_stmt(stmt)
        if isinstance(stmt, BreakStmt):
            return self._visit_break_stmt(stmt)
        if isinstance(stmt, ContinueStmt):
            return self._visit_continue_stmt(stmt)
        if isinstance(stmt, PrintStmt):
            return self._visit_print_stmt(stmt)
        if isinstance(stmt, ExprStmt):
            return self._visit_expr_stmt(stmt)
        if isinstance(stmt, Block):
            stmts = self._visit_block(stmt)
            if stmts:
                return self._chain_stmts(stmts)
        return None

    def _visit_if_stmt(self, stmt: IfStmt) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_if',
            'id': self._uid(),
            'inputs': {
                'COND': {'block': self._visit_expr(stmt.condition)},
                'THEN': self._block_input(stmt.then_body),
            },
        }
        self._inject_src_line(block, stmt.pos)
        if stmt.elif_clauses:
            block['extraState'] = {'elseIfCount': len(stmt.elif_clauses)}
        for n, (ec, eb) in enumerate(stmt.elif_clauses):
            block['inputs'][f'ELIF_COND{n}'] = {'block': self._visit_expr(ec)}
            block['inputs'][f'ELIF{n}'] = self._block_input(eb)
        if stmt.else_body is not None:
            block['inputs']['ELSE'] = self._block_input(stmt.else_body)
        return block

    def _visit_while_stmt(self, stmt: WhileStmt) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_while',
            'id': self._uid(),
            'inputs': {
                'COND': {'block': self._visit_expr(stmt.condition)},
                'BODY': self._block_input(stmt.body),
            },
        }
        self._inject_src_line(block, stmt.pos)
        return block

    def _visit_for_stmt(self, stmt: ForStmt) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_for',
            'id': self._uid(),
            'inputs': {},
        }
        self._inject_src_line(block, stmt.pos)
        if stmt.init is not None:
            init_b = self._visit_stmt(stmt.init)
            if init_b is not None:
                block['inputs']['INIT'] = {'block': init_b}
        if stmt.condition is not None:
            block['inputs']['COND'] = {'block': self._visit_expr(stmt.condition)}
        if stmt.update is not None:
            block['inputs']['UPDATE'] = {'block': self._visit_expr(stmt.update)}
        block['inputs']['BODY'] = self._block_input(stmt.body)
        return block

    def _visit_dowhile_stmt(self, stmt: DoWhileStmt) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_dowhile',
            'id': self._uid(),
            'inputs': {
                'BODY': self._block_input(stmt.body),
                'COND': {'block': self._visit_expr(stmt.condition)},
            },
        }
        self._inject_src_line(block, stmt.pos)
        return block

    def _visit_return_stmt(self, stmt: ReturnStmt) -> dict[str, Any]:
        block: dict[str, Any] = {'type': 'c_return', 'id': self._uid(), 'inputs': {}}
        self._inject_src_line(block, stmt.pos)
        if stmt.value is not None:
            block['inputs']['VALUE'] = {'block': self._visit_expr(stmt.value)}
        return block

    def _visit_break_stmt(self, stmt: BreakStmt) -> dict[str, Any]:
        block: dict[str, Any] = {'type': 'c_break', 'id': self._uid()}
        self._inject_src_line(block, stmt.pos)
        return block

    def _visit_continue_stmt(self, stmt: ContinueStmt) -> dict[str, Any]:
        block: dict[str, Any] = {'type': 'c_continue', 'id': self._uid()}
        self._inject_src_line(block, stmt.pos)
        return block

    def _visit_print_stmt(self, stmt: PrintStmt) -> dict[str, Any]:
        btype = 'c_println' if stmt.newline else 'c_print'
        block: dict[str, Any] = {
            'type': btype,
            'id': self._uid(),
            'inputs': {'VALUE': {'block': self._visit_expr(stmt.expr)}},
        }
        self._inject_src_line(block, stmt.pos)
        return block

    def _visit_expr_stmt(self, stmt: ExprStmt) -> dict[str, Any]:
        if isinstance(stmt.expr, CallExpr):
            return self._visit_call_stmt(stmt.expr, stmt.pos)
        if isinstance(stmt.expr, AssignOp):
            return self._visit_assign_stmt(stmt.expr, stmt.pos)
        if isinstance(stmt.expr, UnaryOp) and stmt.expr.op in ('++', '--'):
            b = self._visit_expr(stmt.expr)
            self._inject_src_line(b, stmt.pos)
            return b
        expr_b = self._visit_expr(stmt.expr)
        self._inject_src_line(expr_b, stmt.pos)
        return expr_b

    def _visit_call_stmt(self, call: CallExpr, pos: SourcePos) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_func_call_stmt',
            'id': self._uid(),
            'fields': {'NAME': call.name},
            'inputs': {},
        }
        self._inject_src_line(block, pos)
        if call.args:
            block['inputs']['ARGS'] = {'block': self._chain_exprs(call.args)}
        return block

    def _visit_assign_stmt(self, assign: AssignOp, pos: SourcePos) -> dict[str, Any]:
        if isinstance(assign.target, IndexExpr):
            block: dict[str, Any] = {
                'type': 'c_array_assign',
                'id': self._uid(),
                'fields': {'NAME': assign.target.name},
                'inputs': {
                    'INDEX': {'block': self._visit_expr(assign.target.index)},
                    'VALUE': {'block': self._visit_expr(assign.value)},
                },
            }
            self._inject_src_line(block, pos)
            return block

        btype = 'c_compound_assign' if assign.op != '=' else 'c_assign'
        target_name = assign.target.name if isinstance(assign.target, Identifier) else ''
        fields: dict[str, Any] = {'NAME': target_name}
        if assign.op != '=':
            fields['OP'] = assign.op
        block: dict[str, Any] = {
            'type': btype,
            'id': self._uid(),
            'fields': fields,
            'inputs': {'VALUE': {'block': self._visit_expr(assign.value)}},
        }
        self._inject_src_line(block, pos)
        return block

    # ── Expressions ────────────────────────────────────────────────────────────

    def _visit_expr(self, expr: Any) -> dict[str, Any]:
        if isinstance(expr, IntLiteral):
            return self._visit_int_literal(expr)
        if isinstance(expr, FloatLiteral):
            return self._visit_float_literal(expr)
        if isinstance(expr, BoolLiteral):
            return self._visit_bool_literal(expr)
        if isinstance(expr, StringLiteral):
            return self._visit_string_literal(expr)
        if isinstance(expr, CharLiteral):
            return self._visit_char_literal(expr)
        if isinstance(expr, Identifier):
            return self._visit_identifier(expr)
        if isinstance(expr, IndexExpr):
            return self._visit_index_expr(expr)
        if isinstance(expr, BinaryOp):
            return self._visit_binary_op(expr)
        if isinstance(expr, UnaryOp):
            return self._visit_unary_op(expr)
        if isinstance(expr, AssignOp):
            return self._visit_assign_op(expr)
        if isinstance(expr, CallExpr):
            return self._visit_call_expr(expr)
        if isinstance(expr, CastExpr):
            return self._visit_cast_expr(expr)
        if isinstance(expr, InputExpr):
            return self._visit_input_expr(expr)
        block: dict[str, Any] = {
            'type': 'c_lit_int', 'id': self._uid(), 'fields': {'VALUE': 0},
        }
        self._inject_src_line(block, SourcePos(0, 0))
        return block

    def _visit_int_literal(self, expr: IntLiteral) -> dict[str, Any]:
        block = {'type': 'c_lit_int', 'id': self._uid(), 'fields': {'VALUE': expr.value}}
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_float_literal(self, expr: FloatLiteral) -> dict[str, Any]:
        block = {'type': 'c_lit_float', 'id': self._uid(), 'fields': {'VALUE': expr.value}}
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_bool_literal(self, expr: BoolLiteral) -> dict[str, Any]:
        block = {
            'type': 'c_lit_bool',
            'id': self._uid(),
            'fields': {'VALUE': 'true' if expr.value else 'false'},
        }
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_string_literal(self, expr: StringLiteral) -> dict[str, Any]:
        block = {'type': 'c_lit_string', 'id': self._uid(), 'fields': {'VALUE': expr.value}}
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_char_literal(self, expr: CharLiteral) -> dict[str, Any]:
        block = {'type': 'c_lit_char', 'id': self._uid(), 'fields': {'VALUE': expr.value}}
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_identifier(self, expr: Identifier) -> dict[str, Any]:
        block = {'type': 'c_identifier', 'id': self._uid(), 'fields': {'NAME': expr.name}}
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_index_expr(self, expr: IndexExpr) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_index_expr',
            'id': self._uid(),
            'fields': {'NAME': expr.name},
            'inputs': {'INDEX': {'block': self._visit_expr(expr.index)}},
        }
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_binary_op(self, expr: BinaryOp) -> dict[str, Any]:
        op = expr.op
        if op in _ARITH_OPS:
            btype = 'c_binary_arith'
        elif op in _CMP_OPS:
            btype = 'c_binary_cmp'
        elif op in _LOGIC_OPS:
            btype = 'c_binary_logic'
        else:
            btype = 'c_binary_arith'
        block: dict[str, Any] = {
            'type': btype,
            'id': self._uid(),
            'fields': {'OP': op},
            'inputs': {
                'LEFT': {'block': self._visit_expr(expr.left)},
                'RIGHT': {'block': self._visit_expr(expr.right)},
            },
        }
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_unary_op(self, expr: UnaryOp) -> dict[str, Any]:
        op = expr.op
        if op == '!':
            btype = 'c_unary_not'
        elif op == '-':
            btype = 'c_unary_neg'
        elif op == '++':
            btype = 'c_prefix_inc' if expr.prefix else 'c_postfix_inc'
        elif op == '--':
            btype = 'c_prefix_dec' if expr.prefix else 'c_postfix_dec'
        else:
            btype = 'c_unary_neg'
        if op in ('!', '-'):
            block: dict[str, Any] = {
                'type': btype,
                'id': self._uid(),
                'inputs': {'OPERAND': {'block': self._visit_expr(expr.operand)}},
            }
        else:
            operand_name = expr.operand.name if isinstance(expr.operand, Identifier) else ''
            block = {
                'type': btype,
                'id': self._uid(),
                'fields': {'NAME': operand_name},
            }
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_assign_op(self, expr: AssignOp) -> dict[str, Any]:
        if isinstance(expr.target, IndexExpr):
            block: dict[str, Any] = {
                'type': 'c_array_assign',
                'id': self._uid(),
                'fields': {'NAME': expr.target.name},
                'inputs': {
                    'INDEX': {'block': self._visit_expr(expr.target.index)},
                    'VALUE': {'block': self._visit_expr(expr.value)},
                },
            }
            self._inject_src_line(block, expr.pos)
            return block

        btype = 'c_compound_assign' if expr.op != '=' else 'c_assign'
        target_name = expr.target.name if isinstance(expr.target, Identifier) else ''
        fields: dict[str, Any] = {'NAME': target_name}
        if expr.op != '=':
            fields['OP'] = expr.op
        block: dict[str, Any] = {
            'type': btype,
            'id': self._uid(),
            'fields': fields,
            'inputs': {'VALUE': {'block': self._visit_expr(expr.value)}},
        }
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_call_expr(self, expr: CallExpr) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_func_call_expr',
            'id': self._uid(),
            'fields': {'NAME': expr.name},
            'inputs': {},
        }
        self._inject_src_line(block, expr.pos)
        if expr.args:
            block['inputs']['ARGS'] = {'block': self._chain_exprs(expr.args)}
        return block

    def _visit_cast_expr(self, expr: CastExpr) -> dict[str, Any]:
        block: dict[str, Any] = {
            'type': 'c_cast',
            'id': self._uid(),
            'fields': {'TYPE': expr.target_type},
            'inputs': {'VALUE': {'block': self._visit_expr(expr.expr)}},
        }
        self._inject_src_line(block, expr.pos)
        return block

    def _visit_input_expr(self, expr: InputExpr) -> dict[str, Any]:
        btype_map = {'string': 'c_input', 'int': 'c_input_int', 'float': 'c_input_float'}
        btype = btype_map.get(expr.variant, 'c_input')
        block: dict[str, Any] = {'type': btype, 'id': self._uid()}
        self._inject_src_line(block, expr.pos)
        return block

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _block_input(self, block: Block) -> dict[str, Any]:
        stmts = self._visit_block(block)
        if stmts:
            return {'block': self._chain_stmts(stmts)}
        return {'block': None}

    def _chain_stmts(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        """Link a list of statement blocks via 'next'."""
        if not blocks:
            return {}
        root = blocks[0]
        current = root
        for b in blocks[1:]:
            current['next'] = {'block': b}
            current = b
        return root

    def _chain_exprs(self, exprs: list[Any]) -> dict[str, Any]:
        """Link expression blocks via 'next' (for arg lists)."""
        blocks = [self._visit_expr(e) for e in exprs]
        return self._chain_stmts(blocks)

    def _inject_src_line(self, block: dict[str, Any], pos: SourcePos) -> dict[str, Any]:
        block['data'] = {'srcLine': pos.line}
        return block

    def _uid(self) -> str:
        return str(uuid.uuid4())[:8]


def ast_to_blocks(program: Program) -> dict[str, Any]:
    return ASTtoBlocks().convert(program)
