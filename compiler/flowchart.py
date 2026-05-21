from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class _LoopTargets:
    continue_target: str
    break_target: str


class FlowchartGenerator:
    """Generate a Mermaid flowchart from the validated CompileFlow AST."""

    def __init__(self) -> None:
        self._nodes: list[str] = []
        self._edges: list[str] = []
        self._next_id = 0
        self._function_end = ''
        self._loop_stack: list[_LoopTargets] = []

    def generate(self, program: Program) -> str:
        self._nodes = []
        self._edges = []
        self._next_id = 0
        self._function_end = ''
        self._loop_stack = []

        lines = ['flowchart TD']
        global_decls = [
            decl for decl in program.declarations
            if isinstance(decl, (VarDecl, ArrayDecl))
        ]
        functions = [
            decl for decl in program.declarations
            if isinstance(decl, FunctionDecl)
        ]

        if global_decls:
            lines.append('    subgraph globals["Globales"]')
            entry = self._node('Inicio global', 'stadium')
            tails = [entry]
            tails = self._build_block(Block(global_decls, program.pos), tails)
            end = self._node('Fin global', 'stadium')
            self._connect_many(tails, end)
            lines.extend(self._indented_graph())
            lines.append('    end')
            self._clear_graph()

        if not functions:
            lines.append('    empty(["Programa vacio"])')
            return '\n'.join(lines)

        for function in functions:
            safe_name = self._safe_subgraph_id(function.name)
            title = self._label(f'Funcion {function.name}')
            lines.append(f'    subgraph {safe_name}["{title}"]')
            start = self._node(f'Inicio {function.name}', 'stadium')
            self._function_end = self._node(f'Fin {function.name}', 'stadium')
            tails = self._build_block(function.body, [start])
            self._connect_many(tails, self._function_end)
            lines.extend(self._indented_graph())
            lines.append('    end')
            self._clear_graph()

        return '\n'.join(lines)

    def _clear_graph(self) -> None:
        self._nodes = []
        self._edges = []

    def _indented_graph(self) -> list[str]:
        return [f'        {line}' for line in [*self._nodes, *self._edges]]

    def _node(self, label: str, shape: str = 'process') -> str:
        node_id = f'n{self._next_id}'
        self._next_id += 1
        text = self._label(label)
        if shape == 'decision':
            self._nodes.append(f'{node_id}{{"{text}"}}')
        elif shape == 'stadium':
            self._nodes.append(f'{node_id}(["{text}"])')
        else:
            self._nodes.append(f'{node_id}["{text}"]')
        return node_id

    def _connect(self, source: str, target: str, label: str | None = None) -> None:
        if label:
            self._edges.append(f'{source} -- "{self._label(label)}" --> {target}')
        else:
            self._edges.append(f'{source} --> {target}')

    def _connect_many(
        self,
        sources: list[str],
        target: str,
        label: str | None = None,
    ) -> None:
        for source in sources:
            self._connect(source, target, label)

    def _build_block(self, block: Block, tails: list[str]) -> list[str]:
        current = tails
        for stmt in block.stmts:
            if not current:
                self._build_unreachable(stmt)
                continue
            current = self._build_stmt(stmt, current)
        return current

    def _build_stmt(self, stmt: Any, tails: list[str]) -> list[str]:
        if isinstance(stmt, IfStmt):
            return self._build_if(stmt, tails)
        if isinstance(stmt, WhileStmt):
            return self._build_while(stmt, tails)
        if isinstance(stmt, ForStmt):
            return self._build_for(stmt, tails)
        if isinstance(stmt, DoWhileStmt):
            return self._build_dowhile(stmt, tails)
        if isinstance(stmt, Block):
            return self._build_block(stmt, tails)
        if isinstance(stmt, ReturnStmt):
            node = self._node(self._stmt_label(stmt))
            self._connect_many(tails, node)
            self._connect(node, self._function_end)
            return []
        if isinstance(stmt, BreakStmt):
            node = self._node('break')
            self._connect_many(tails, node)
            if self._loop_stack:
                self._connect(node, self._loop_stack[-1].break_target)
            return []
        if isinstance(stmt, ContinueStmt):
            node = self._node('continue')
            self._connect_many(tails, node)
            if self._loop_stack:
                self._connect(node, self._loop_stack[-1].continue_target)
            return []

        node = self._node(self._stmt_label(stmt))
        self._connect_many(tails, node)
        return [node]

    def _build_unreachable(self, stmt: Any) -> None:
        if isinstance(stmt, (IfStmt, WhileStmt, ForStmt, DoWhileStmt, Block)):
            self._build_stmt(stmt, [])

    def _build_if(self, stmt: IfStmt, tails: list[str]) -> list[str]:
        join = self._node('Fin if')
        condition = self._node(self._condition_label('if', stmt.condition), 'decision')
        self._connect_many(tails, condition)

        then_tails = self._build_branch(stmt.then_body, condition, 'Si')
        self._connect_many(then_tails, join)

        false_entry = condition
        for elif_condition, elif_body in stmt.elif_clauses:
            elif_node = self._node(
                self._condition_label('else if', elif_condition),
                'decision',
            )
            self._connect(false_entry, elif_node, 'No')
            elif_tails = self._build_branch(elif_body, elif_node, 'Si')
            self._connect_many(elif_tails, join)
            false_entry = elif_node

        if stmt.else_body is not None:
            else_tails = self._build_branch(stmt.else_body, false_entry, 'No')
            self._connect_many(else_tails, join)
        else:
            self._connect(false_entry, join, 'No')

        return [join]

    def _build_branch(self, block: Block, entry: str, label: str) -> list[str]:
        if not block.stmts:
            passthrough = self._node('Bloque vacio')
            self._connect(entry, passthrough, label)
            return [passthrough]

        marker = self._node('Bloque')
        self._connect(entry, marker, label)
        return self._build_block(block, [marker])

    def _build_while(self, stmt: WhileStmt, tails: list[str]) -> list[str]:
        join = self._node('Fin while')
        condition = self._node(self._condition_label('while', stmt.condition), 'decision')
        self._connect_many(tails, condition)
        self._connect(condition, join, 'No')

        body_entry = self._node('Cuerpo while')
        self._connect(condition, body_entry, 'Si')
        self._loop_stack.append(_LoopTargets(condition, join))
        body_tails = self._build_block(stmt.body, [body_entry])
        self._loop_stack.pop()
        self._connect_many(body_tails, condition)
        return [join]

    def _build_for(self, stmt: ForStmt, tails: list[str]) -> list[str]:
        current = tails
        if stmt.init is not None:
            init = self._node(f'for init: {self._inline_stmt(stmt.init)}')
            self._connect_many(current, init)
            current = [init]

        join = self._node('Fin for')
        cond_text = self._expr(stmt.condition) if stmt.condition is not None else 'true'
        condition = self._node(f'for: {cond_text}', 'decision')
        self._connect_many(current, condition)
        if stmt.condition is not None:
            self._connect(condition, join, 'No')

        update_target = condition
        if stmt.update is not None:
            update_target = self._node(f'for update: {self._expr(stmt.update)}')
            self._connect(update_target, condition)

        body_entry = self._node('Cuerpo for')
        self._connect(condition, body_entry, 'Si')
        self._loop_stack.append(_LoopTargets(update_target, join))
        body_tails = self._build_block(stmt.body, [body_entry])
        self._loop_stack.pop()
        self._connect_many(body_tails, update_target)
        return [join]

    def _build_dowhile(self, stmt: DoWhileStmt, tails: list[str]) -> list[str]:
        join = self._node('Fin do while')
        body_entry = self._node('Cuerpo do while')
        self._connect_many(tails, body_entry)
        condition = self._node(
            self._condition_label('do while', stmt.condition),
            'decision',
        )
        self._loop_stack.append(_LoopTargets(condition, join))
        body_tails = self._build_block(stmt.body, [body_entry])
        self._loop_stack.pop()
        self._connect_many(body_tails, condition)
        self._connect(condition, body_entry, 'Si')
        self._connect(condition, join, 'No')
        return [join]

    def _stmt_label(self, stmt: Any) -> str:
        if isinstance(stmt, VarDecl):
            if stmt.init_expr is None:
                return f'{stmt.type} {stmt.name}'
            return f'{stmt.type} {stmt.name} = {self._expr(stmt.init_expr)}'
        if isinstance(stmt, ArrayDecl):
            if stmt.init_list:
                values = ', '.join(self._expr(value) for value in stmt.init_list)
                return f'{stmt.element_type} {stmt.name}[{stmt.size}] = {{{values}}}'
            return f'{stmt.element_type} {stmt.name}[{stmt.size}]'
        if isinstance(stmt, PrintStmt):
            name = 'println' if stmt.newline else 'print'
            return f'{name}({self._expr(stmt.expr)})'
        if isinstance(stmt, ExprStmt):
            return self._expr(stmt.expr)
        if isinstance(stmt, ReturnStmt):
            if stmt.value is None:
                return 'return'
            return f'return {self._expr(stmt.value)}'
        return type(stmt).__name__

    def _inline_stmt(self, stmt: Any) -> str:
        if isinstance(stmt, VarDecl):
            return self._stmt_label(stmt)
        if isinstance(stmt, ExprStmt):
            return self._expr(stmt.expr)
        return self._expr(stmt)

    def _condition_label(self, keyword: str, expr: Any) -> str:
        return f'{keyword}: {self._expr(expr)}'

    def _expr(self, expr: Any) -> str:
        if expr is None:
            return ''
        if isinstance(expr, BinaryOp):
            return f'({self._expr(expr.left)} {expr.op} {self._expr(expr.right)})'
        if isinstance(expr, UnaryOp):
            operand = self._expr(expr.operand)
            if expr.prefix:
                return f'({expr.op}{operand})'
            return f'({operand}{expr.op})'
        if isinstance(expr, AssignOp):
            return f'{self._expr(expr.target)} {expr.op} {self._expr(expr.value)}'
        if isinstance(expr, CallExpr):
            args = ', '.join(self._expr(arg) for arg in expr.args)
            return f'{expr.name}({args})'
        if isinstance(expr, IndexExpr):
            return f'{expr.name}[{self._expr(expr.index)}]'
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, IntLiteral):
            return str(expr.value)
        if isinstance(expr, FloatLiteral):
            return repr(expr.value)
        if isinstance(expr, StringLiteral):
            return repr(expr.value)
        if isinstance(expr, CharLiteral):
            return repr(expr.value)
        if isinstance(expr, BoolLiteral):
            return 'true' if expr.value else 'false'
        if isinstance(expr, InputExpr):
            if expr.variant == 'int':
                return 'input_int()'
            if expr.variant == 'float':
                return 'input_float()'
            return 'input()'
        if isinstance(expr, CastExpr):
            return f'(({expr.target_type}) {self._expr(expr.expr)})'
        return type(expr).__name__

    def _label(self, label: str) -> str:
        return (
            label.replace('&', '&amp;')
            .replace('\\', '&#92;')
            .replace('"', '&quot;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('\n', '<br/>')
        )

    def _safe_subgraph_id(self, name: str) -> str:
        safe = ''.join(ch if ch.isalnum() else '_' for ch in name)
        return f'cluster_{safe}_{self._next_id}'


def ast_to_flowchart(program: Program) -> str:
    return FlowchartGenerator().generate(program)
