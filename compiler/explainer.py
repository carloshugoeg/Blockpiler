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
    CType,
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

_ARITH_OPS: dict[str, str] = {
    '+': 'más', '-': 'menos', '*': 'por', '/': 'dividido entre', '%': 'módulo',
    '<<': 'desplazado izquierda', '>>': 'desplazado derecha', '&': 'AND bit a bit',
}
_CMP_OPS: dict[str, str] = {
    '==': 'igual a', '!=': 'distinto de', '<': 'menor que',
    '>': 'mayor que', '<=': 'menor o igual que', '>=': 'mayor o igual que',
}
_LOGIC_OPS: dict[str, str] = {'&&': 'y', '||': 'o'}


class Explainer:
    def __init__(self) -> None:
        self._counter: int = 0

    def explain(self, program: Program) -> str:
        return self._explain_program(program)

    def _explain_program(self, program: Program) -> str:
        lines: list[str] = ['## Programa CompileFlow', '']
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                lines.append(self._explain_function(decl))
                lines.append('')
            elif isinstance(decl, VarDecl):
                lines.append(f'**Variable global:** {self._explain_var_decl(decl, 0)}')
                lines.append('')
            elif isinstance(decl, ArrayDecl):
                lines.append(
                    f'**Array global:** `{decl.name}` de tipo '
                    f'{self._ctype_name(decl.element_type)}, tamaño {decl.size}'
                )
                lines.append('')
        return '\n'.join(lines).rstrip() + '\n'

    def _explain_function(self, func: FunctionDecl) -> str:
        ret = self._ctype_name(func.return_type)
        params = ', '.join(
            f'`{p.name}` ({self._ctype_name(p.type)})' for p in func.params
        )
        header = f'### Función `{func.name}` (retorna {ret})'
        if params:
            header += f'\n**Parámetros:** {params}'
        body_lines = self._explain_block_numbered(func.body, indent=0)
        return header + '\n' + body_lines

    def _explain_block_numbered(self, block: Block, indent: int) -> str:
        prefix = '   ' * indent
        lines: list[str] = []
        for i, stmt in enumerate(block.stmts, 1):
            explained = self._explain_stmt(stmt, indent)
            lines.append(f'{prefix}{i}. {explained}')
        return '\n'.join(lines) if lines else f'{prefix}_(bloque vacío)_'

    def _explain_block_bullets(self, block: Block, indent: int) -> str:
        prefix = '   ' * indent
        lines: list[str] = []
        for stmt in block.stmts:
            explained = self._explain_stmt(stmt, indent)
            lines.append(f'{prefix}- {explained}')
        return '\n'.join(lines) if lines else f'{prefix}- _(vacío)_'

    def _explain_stmt(self, stmt: Any, indent: int) -> str:
        if isinstance(stmt, VarDecl):
            return self._explain_var_decl(stmt, indent)
        if isinstance(stmt, ArrayDecl):
            return self._explain_array_decl(stmt)
        if isinstance(stmt, IfStmt):
            return self._explain_if(stmt, indent)
        if isinstance(stmt, WhileStmt):
            return self._explain_while(stmt, indent)
        if isinstance(stmt, ForStmt):
            return self._explain_for(stmt, indent)
        if isinstance(stmt, DoWhileStmt):
            return self._explain_dowhile(stmt, indent)
        if isinstance(stmt, ReturnStmt):
            return self._explain_return(stmt)
        if isinstance(stmt, BreakStmt):
            return 'Sale del bucle (`break`)'
        if isinstance(stmt, ContinueStmt):
            return 'Continúa a la siguiente iteración (`continue`)'
        if isinstance(stmt, PrintStmt):
            suffix = 'con salto de línea' if stmt.newline else 'sin salto de línea'
            return f'Imprime {self._explain_expr(stmt.expr)} {suffix}'
        if isinstance(stmt, ExprStmt):
            return f'Evalúa: {self._explain_expr(stmt.expr)}'
        if isinstance(stmt, Block):
            inner = self._explain_block_bullets(stmt, indent + 1)
            return f'Bloque:\n{inner}'
        return f'_(instrucción desconocida: {type(stmt).__name__})_'

    def _explain_var_decl(self, decl: VarDecl, indent: int) -> str:  # noqa: ARG002
        tipo = self._ctype_name(decl.type)
        if decl.init_expr is not None:
            return (
                f'Declara variable {tipo} `{decl.name}` '
                f'con valor inicial **{self._explain_expr(decl.init_expr)}**'
            )
        return f'Declara variable {tipo} `{decl.name}` (sin inicializar)'

    def _explain_array_decl(self, decl: ArrayDecl) -> str:
        tipo = self._ctype_name(decl.element_type)
        base = f'Declara array `{decl.name}` de {decl.size} elementos {tipo}'
        if decl.init_list:
            vals = ', '.join(self._explain_expr(e) for e in decl.init_list)
            return f'{base}, inicializado con [{vals}]'
        return base

    def _explain_if(self, stmt: IfStmt, indent: int) -> str:
        cond = self._explain_expr(stmt.condition)
        then_txt = self._explain_block_bullets(stmt.then_body, indent + 1)
        result = f'Si {cond}:\n{then_txt}'
        for elif_cond, elif_body in stmt.elif_clauses:
            ec = self._explain_expr(elif_cond)
            eb = self._explain_block_bullets(elif_body, indent + 1)
            result += f'\nSi no, si {ec}:\n{eb}'
        if stmt.else_body is not None:
            eb2 = self._explain_block_bullets(stmt.else_body, indent + 1)
            result += f'\nEn caso contrario:\n{eb2}'
        return result

    def _explain_while(self, stmt: WhileStmt, indent: int) -> str:
        cond = self._explain_expr(stmt.condition)
        body = self._explain_block_bullets(stmt.body, indent + 1)
        return f'Mientras {cond}:\n{body}'

    def _explain_for(self, stmt: ForStmt, indent: int) -> str:
        parts: list[str] = []
        if stmt.init is not None:
            parts.append(f'inicio: {self._explain_stmt(stmt.init, indent)}')
        if stmt.condition is not None:
            parts.append(f'mientras {self._explain_expr(stmt.condition)}')
        if stmt.update is not None:
            parts.append(f'actualiza: {self._explain_expr(stmt.update)}')
        header = 'Para (' + '; '.join(parts) + ')'
        body = self._explain_block_bullets(stmt.body, indent + 1)
        return f'{header}:\n{body}'

    def _explain_dowhile(self, stmt: DoWhileStmt, indent: int) -> str:
        body = self._explain_block_bullets(stmt.body, indent + 1)
        cond = self._explain_expr(stmt.condition)
        return f'Repite:\n{body}\nHasta que {cond} sea falso'

    def _explain_return(self, stmt: ReturnStmt) -> str:
        if stmt.value is None:
            return 'Retorna (sin valor)'
        return f'Retorna **{self._explain_expr(stmt.value)}**'

    def _explain_expr(self, expr: Any) -> str:
        if isinstance(expr, IntLiteral):
            return str(expr.value)
        if isinstance(expr, FloatLiteral):
            return str(expr.value)
        if isinstance(expr, StringLiteral):
            return f'`"{expr.value}"`'
        if isinstance(expr, CharLiteral):
            return f"`'{expr.value}'`"
        if isinstance(expr, BoolLiteral):
            return 'verdadero' if expr.value else 'falso'
        if isinstance(expr, Identifier):
            return f'`{expr.name}`'
        if isinstance(expr, BinaryOp):
            return self._explain_binary(expr)
        if isinstance(expr, UnaryOp):
            return self._explain_unary(expr)
        if isinstance(expr, AssignOp):
            return (
                f'asigna {self._explain_expr(expr.value)} a '
                f'{self._explain_expr(expr.target)}'
            )
        if isinstance(expr, CallExpr):
            return self._explain_call(expr)
        if isinstance(expr, IndexExpr):
            return f'`{expr.name}[{self._explain_expr(expr.index)}]`'
        if isinstance(expr, CastExpr):
            return (
                f'convierte {self._explain_expr(expr.expr)} '
                f'a {self._ctype_name(expr.target_type)}'
            )
        if isinstance(expr, InputExpr):
            if expr.variant == 'int':
                return 'lee un entero de la entrada'
            if expr.variant == 'float':
                return 'lee un decimal de la entrada'
            return 'lee texto de la entrada'
        return f'_(expr desconocida: {type(expr).__name__})_'

    def _explain_binary(self, expr: BinaryOp) -> str:
        left = self._explain_expr(expr.left)
        right = self._explain_expr(expr.right)
        op = expr.op
        if op in _ARITH_OPS:
            return f'{left} {_ARITH_OPS[op]} {right}'
        if op in _CMP_OPS:
            return f'{left} {_CMP_OPS[op]} {right}'
        if op in _LOGIC_OPS:
            return f'{left} {_LOGIC_OPS[op]} {right}'
        return f'{left} {op} {right}'

    def _explain_unary(self, expr: UnaryOp) -> str:
        operand = self._explain_expr(expr.operand)
        op = expr.op
        if op == '!':
            return f'negación de {operand}'
        if op == '-':
            return f'negativo de {operand}'
        if op == '++':
            return f'incrementa {operand}' + (' (antes)' if expr.prefix else ' (después)')
        if op == '--':
            return f'decrementa {operand}' + (' (antes)' if expr.prefix else ' (después)')
        return f'{op}{operand}'

    def _explain_call(self, expr: CallExpr) -> str:
        if not expr.args:
            return f'llama a `{expr.name}()`'
        args = ', '.join(self._explain_expr(a) for a in expr.args)
        return f'llama a `{expr.name}({args})`'

    def _ctype_name(self, ctype: CType) -> str:
        mapping: dict[str, str] = {
            'int': 'entero',
            'float': 'decimal',
            'char': 'carácter',
            'bool': 'booleano',
            'string': 'cadena',
            'void': 'void',
            'unknown': 'desconocido',
        }
        return mapping.get(ctype, ctype)


def explain(program: Program) -> str:
    return Explainer().explain(program)
