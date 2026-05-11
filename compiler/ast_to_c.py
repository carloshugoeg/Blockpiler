from __future__ import annotations

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
    PrintStmt,
    Program,
    ReturnStmt,
    StringLiteral,
    UnaryOp,
    VarDecl,
    WhileStmt,
)

_CTYPE_MAP = {
    'int': 'int',
    'float': 'double',
    'char': 'char',
    'bool': 'int',
    'string': 'char*',
    'void': 'void',
    'unknown': 'void',
}


class ASTtoC:
    def __init__(self) -> None:
        pass

    def generate(self, program: Program) -> str:
        return self._visit_program(program)

    def _visit(self, node: Any, indent: int = 0) -> str:
        if isinstance(node, Program):
            return self._visit_program(node)
        if isinstance(node, FunctionDecl):
            return self._visit_function_decl(node)
        if isinstance(node, VarDecl):
            return self._visit_var_decl(node, indent)
        if isinstance(node, ArrayDecl):
            return self._visit_array_decl(node, indent)
        if isinstance(node, Block):
            return self._visit_block(node, indent)
        if isinstance(node, IfStmt):
            return self._visit_if_stmt(node, indent)
        if isinstance(node, WhileStmt):
            return self._visit_while_stmt(node, indent)
        if isinstance(node, ForStmt):
            return self._visit_for_stmt(node, indent)
        if isinstance(node, DoWhileStmt):
            return self._visit_dowhile_stmt(node, indent)
        if isinstance(node, ReturnStmt):
            return self._visit_return_stmt(node, indent)
        if isinstance(node, BreakStmt):
            return self._visit_break_stmt(indent)
        if isinstance(node, ContinueStmt):
            return self._visit_continue_stmt(indent)
        if isinstance(node, PrintStmt):
            return self._visit_print_stmt(node, indent)
        if isinstance(node, ExprStmt):
            return self._visit_expr_stmt(node, indent)
        if isinstance(node, BinaryOp):
            return self._visit_binary_op(node)
        if isinstance(node, UnaryOp):
            return self._visit_unary_op(node)
        if isinstance(node, AssignOp):
            return self._visit_assign_op(node)
        if isinstance(node, CallExpr):
            return self._visit_call_expr(node)
        if isinstance(node, IndexExpr):
            return self._visit_index_expr(node)
        if isinstance(node, Identifier):
            return self._visit_identifier(node)
        if isinstance(node, IntLiteral):
            return self._visit_int_literal(node)
        if isinstance(node, FloatLiteral):
            return self._visit_float_literal(node)
        if isinstance(node, StringLiteral):
            return self._visit_string_literal(node)
        if isinstance(node, CharLiteral):
            return self._visit_char_literal(node)
        if isinstance(node, BoolLiteral):
            return self._visit_bool_literal(node)
        if isinstance(node, InputExpr):
            return self._visit_input_expr(node)
        if isinstance(node, CastExpr):
            return self._visit_cast_expr(node)
        return ''

    def _ind(self, level: int) -> str:
        return '    ' * level

    def _visit_program(self, node: Program) -> str:
        parts = ['#include <stdio.h>', '#include <string.h>', '']
        for decl in node.declarations:
            parts.append(self._visit(decl))
        return '\n'.join(parts)

    def _visit_function_decl(self, node: FunctionDecl) -> str:
        ctype = _CTYPE_MAP.get(node.return_type, 'void')
        params = ', '.join(
            f'{_CTYPE_MAP.get(p.type, "void")} {p.name}' for p in node.params
        )
        body = self._visit_block(node.body, 0)
        return f'{ctype} {node.name}({params}) {body}\n'

    def _visit_var_decl(self, node: VarDecl, indent: int = 0) -> str:
        ctype = _CTYPE_MAP.get(node.type, 'void')
        pad = self._ind(indent)
        if node.init_expr is not None:
            init = self._visit(node.init_expr)
            return f'{pad}{ctype} {node.name} = {init};'
        return f'{pad}{ctype} {node.name};'

    def _visit_array_decl(self, node: ArrayDecl, indent: int = 0) -> str:
        ctype = _CTYPE_MAP.get(node.element_type, 'void')
        pad = self._ind(indent)
        if node.init_list:
            elems = ', '.join(self._visit(e) for e in node.init_list)
            return f'{pad}{ctype} {node.name}[{node.size}] = {{{elems}}};'
        return f'{pad}{ctype} {node.name}[{node.size}];'

    def _visit_block(self, node: Block, indent: int = 0) -> str:
        pad = self._ind(indent)
        lines = [f'{pad}{{']
        for stmt in node.stmts:
            line = self._visit(stmt, indent + 1)
            lines.append(line)
        lines.append(f'{pad}}}')
        return '\n'.join(lines)

    def _visit_if_stmt(self, node: IfStmt, indent: int = 0) -> str:
        pad = self._ind(indent)
        cond = self._visit(node.condition)
        then = self._visit_block(node.then_body, indent)
        result = f'{pad}if ({cond}) {then[len(pad):]}'
        for elif_cond, elif_body in node.elif_clauses:
            ec = self._visit(elif_cond)
            eb = self._visit_block(elif_body, indent)
            result += f'\n{pad}else if ({ec}) {eb[len(pad):]}'
        if node.else_body is not None:
            eb2 = self._visit_block(node.else_body, indent)
            result += f'\n{pad}else {eb2[len(pad):]}'
        return result

    def _visit_while_stmt(self, node: WhileStmt, indent: int = 0) -> str:
        pad = self._ind(indent)
        cond = self._visit(node.condition)
        body = self._visit_block(node.body, indent)
        return f'{pad}while ({cond}) {body[len(pad):]}'

    def _visit_for_stmt(self, node: ForStmt, indent: int = 0) -> str:
        pad = self._ind(indent)
        init_str = ''
        if node.init is not None:
            raw = self._visit(node.init, 0)
            init_str = raw.strip().rstrip(';')
        cond_str = self._visit(node.condition) if node.condition is not None else ''
        upd_str = self._visit(node.update) if node.update is not None else ''
        body = self._visit_block(node.body, indent)
        return f'{pad}for ({init_str}; {cond_str}; {upd_str}) {body[len(pad):]}'

    def _visit_dowhile_stmt(self, node: DoWhileStmt, indent: int = 0) -> str:
        pad = self._ind(indent)
        body = self._visit_block(node.body, indent)
        cond = self._visit(node.condition)
        return f'{pad}do {body[len(pad):]} while ({cond});'

    def _visit_return_stmt(self, node: ReturnStmt, indent: int = 0) -> str:
        pad = self._ind(indent)
        if node.value is None:
            return f'{pad}return;'
        val = self._visit(node.value)
        return f'{pad}return {val};'

    def _visit_break_stmt(self, indent: int = 0) -> str:
        return f'{self._ind(indent)}break;'

    def _visit_continue_stmt(self, indent: int = 0) -> str:
        return f'{self._ind(indent)}continue;'

    def _visit_print_stmt(self, node: PrintStmt, indent: int = 0) -> str:
        pad = self._ind(indent)
        val = self._visit(node.expr)
        newline = r'\n' if node.newline else ''
        # Use %s for strings, %g for floats, %d for int/bool/char
        fmt = '%s'  # default
        return f'{pad}printf("{fmt}{newline}", {val});'

    def _visit_expr_stmt(self, node: ExprStmt, indent: int = 0) -> str:
        pad = self._ind(indent)
        return f'{pad}{self._visit(node.expr)};'

    def _visit_binary_op(self, node: BinaryOp) -> str:
        left = self._visit(node.left)
        right = self._visit(node.right)
        return f'({left} {node.op} {right})'

    def _visit_unary_op(self, node: UnaryOp) -> str:
        operand = self._visit(node.operand)
        if node.prefix:
            return f'({node.op}{operand})'
        return f'({operand}{node.op})'

    def _visit_assign_op(self, node: AssignOp) -> str:
        target = self._visit(node.target)
        value = self._visit(node.value)
        return f'{target} {node.op} {value}'

    def _visit_call_expr(self, node: CallExpr) -> str:
        args = ', '.join(self._visit(a) for a in node.args)
        return f'{node.name}({args})'

    def _visit_index_expr(self, node: IndexExpr) -> str:
        idx = self._visit(node.index)
        return f'{node.name}[{idx}]'

    def _visit_identifier(self, node: Identifier) -> str:
        return node.name

    def _visit_int_literal(self, node: IntLiteral) -> str:
        return str(node.value)

    def _visit_float_literal(self, node: FloatLiteral) -> str:
        return repr(node.value)

    def _visit_string_literal(self, node: StringLiteral) -> str:
        escaped = node.value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return f'"{escaped}"'

    def _visit_char_literal(self, node: CharLiteral) -> str:
        escaped = node.value.replace('\\', '\\\\').replace("'", "\\'")
        return f"'{escaped}'"

    def _visit_bool_literal(self, node: BoolLiteral) -> str:
        return '1' if node.value else '0'

    def _visit_input_expr(self, node: InputExpr) -> str:
        # Return a scanf-like placeholder
        if node.variant == 'int':
            return 'getchar_int()'
        if node.variant == 'float':
            return 'getchar_float()'
        return 'getchar_str()'

    def _visit_cast_expr(self, node: CastExpr) -> str:
        ctype = _CTYPE_MAP.get(node.target_type, 'void')
        expr = self._visit(node.expr)
        return f'({ctype}){expr}'


def ast_to_c(program: Program) -> str:
    return ASTtoC().generate(program)
