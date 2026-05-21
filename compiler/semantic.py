from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from compiler.ast_guard import validate_ast_limits
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
    SourcePos,
    StringLiteral,
    CType,
    UnaryOp,
    VarDecl,
    WhileStmt,
)
from compiler.error_reporter import ErrorReporter
from compiler.limits import MAX_ARRAY_SIZE

# ── Coercion tables ─────────────────────────────────────────────────────────────

SAFE_WIDENING: set[tuple[CType, CType]] = {
    ('int',  'float'),
    ('char', 'int'),
    ('bool', 'int'),
}

LOSSY_NARROWING: set[tuple[CType, CType]] = {
    ('float', 'int'),
    ('int',   'bool'),
    ('int',   'char'),
    ('float', 'bool'),
    ('float', 'char'),
}

_BUILTINS = {'print', 'println', 'input', 'input_int', 'input_float', 'true', 'false'}
_LIBC_VARARG_BUILTINS: set[str] = set()


def resolve_binary_type(left: CType, right: CType, op: str) -> tuple[CType, bool]:
    if op in ('==', '!=', '<', '>', '<=', '>='):
        if left == right:
            return ('bool', False)
        if (left, right) in SAFE_WIDENING or (right, left) in SAFE_WIDENING:
            return ('bool', False)
        if left in ('int', 'float', 'char') and right in ('int', 'float', 'char'):
            return ('bool', True)
        return ('unknown', False)

    if op in ('&&', '||'):
        if left == 'bool' and right == 'bool':
            return ('bool', False)
        return ('unknown', False)

    if op in ('+', '-', '*', '/', '%'):
        if op == '+' and left == 'string' and right == 'string':
            return ('string', False)
        if left in ('int', 'float', 'char', 'bool') and right in ('int', 'float', 'char', 'bool'):
            if op == '%' and ('float' in (left, right)):
                return ('unknown', False)
            if 'float' in (left, right):
                return ('float', False)
            return ('int', False)
        return ('unknown', False)

    return ('unknown', False)


def all_paths_return(block: Block) -> bool:
    for stmt in block.stmts:
        if isinstance(stmt, ReturnStmt):
            return True
        if isinstance(stmt, IfStmt) and stmt.else_body is not None:
            branches: list[Block] = [stmt.then_body]
            for _, eb in stmt.elif_clauses:
                branches.append(eb)
            branches.append(stmt.else_body)
            if all(all_paths_return(b) for b in branches):
                return True
        if isinstance(stmt, Block):
            if all_paths_return(stmt):
                return True
    return False


def _collect_calls(node: Any, fn_name: str) -> list[CallExpr]:
    calls: list[CallExpr] = []
    if isinstance(node, CallExpr):
        if node.name == fn_name:
            calls.append(node)
        for arg in node.args:
            calls.extend(_collect_calls(arg, fn_name))
    elif isinstance(node, (BinaryOp,)):
        calls.extend(_collect_calls(node.left, fn_name))
        calls.extend(_collect_calls(node.right, fn_name))
    elif isinstance(node, UnaryOp):
        calls.extend(_collect_calls(node.operand, fn_name))
    elif isinstance(node, AssignOp):
        calls.extend(_collect_calls(node.value, fn_name))
    elif isinstance(node, (IndexExpr, CastExpr)):
        inner = node.index if isinstance(node, IndexExpr) else node.expr
        calls.extend(_collect_calls(inner, fn_name))
    elif isinstance(node, ReturnStmt) and node.value is not None:
        calls.extend(_collect_calls(node.value, fn_name))
    elif isinstance(node, ExprStmt):
        calls.extend(_collect_calls(node.expr, fn_name))
    elif isinstance(node, Block):
        for s in node.stmts:
            calls.extend(_collect_calls(s, fn_name))
    elif isinstance(node, IfStmt):
        calls.extend(_collect_calls(node.condition, fn_name))
        calls.extend(_collect_calls(node.then_body, fn_name))
        for cond, blk in node.elif_clauses:
            calls.extend(_collect_calls(cond, fn_name))
            calls.extend(_collect_calls(blk, fn_name))
        if node.else_body is not None:
            calls.extend(_collect_calls(node.else_body, fn_name))
    elif isinstance(node, (WhileStmt, DoWhileStmt)):
        calls.extend(_collect_calls(node.condition, fn_name))
        calls.extend(_collect_calls(node.body, fn_name))
    elif isinstance(node, ForStmt):
        if node.init is not None:
            calls.extend(_collect_calls(node.init, fn_name))
        if node.condition is not None:
            calls.extend(_collect_calls(node.condition, fn_name))
        if node.update is not None:
            calls.extend(_collect_calls(node.update, fn_name))
        calls.extend(_collect_calls(node.body, fn_name))
    elif isinstance(node, PrintStmt):
        calls.extend(_collect_calls(node.expr, fn_name))
    return calls


def _collect_returns(block: Block) -> list[ReturnStmt]:
    result: list[ReturnStmt] = []
    for stmt in block.stmts:
        if isinstance(stmt, ReturnStmt):
            result.append(stmt)
        elif isinstance(stmt, Block):
            result.extend(_collect_returns(stmt))
        elif isinstance(stmt, IfStmt):
            result.extend(_collect_returns(stmt.then_body))
            for _, b in stmt.elif_clauses:
                result.extend(_collect_returns(b))
            if stmt.else_body is not None:
                result.extend(_collect_returns(stmt.else_body))
        elif isinstance(stmt, (WhileStmt, DoWhileStmt)):
            result.extend(_collect_returns(stmt.body))
        elif isinstance(stmt, ForStmt):
            result.extend(_collect_returns(stmt.body))
    return result


def maybe_infinite_recursion(fn: FunctionDecl) -> bool:
    all_calls = _collect_calls(fn.body, fn.name)
    if not all_calls:
        return False
    returns = _collect_returns(fn.body)
    if not returns:
        return True
    for ret in returns:
        if ret.value is None:
            return False
        if not isinstance(ret.value, CallExpr) or ret.value.name != fn.name:
            return False
    return True


# ── Symbol + SymbolTable ────────────────────────────────────────────────────────

@dataclass
class Symbol:
    name: str
    type: CType
    kind: Literal['variable', 'parameter', 'function', 'array']
    scope_level: int
    line_declared: int
    col_declared: int
    initial_value: Any = None
    use_count: int = 0
    is_initialized: bool = False
    is_mutated: bool = False
    array_size: int = 0
    return_type: CType = 'void'
    param_types: list[CType] = field(default_factory=list)
    call_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'type': self.type,
            'kind': self.kind,
            'scope_level': self.scope_level,
            'line_declared': self.line_declared,
            'col_declared': self.col_declared,
            'use_count': self.use_count,
            'is_initialized': self.is_initialized,
            'is_mutated': self.is_mutated,
            'array_size': self.array_size,
            'return_type': self.return_type,
            'param_types': list(self.param_types),
            'call_count': self.call_count,
        }


@dataclass
class SymbolTable:
    variables: dict[str, Symbol] = field(default_factory=dict)
    functions: dict[str, Symbol] = field(default_factory=dict)

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.variables:
            return self.variables[name]
        if name in self.functions:
            return self.functions[name]
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            'variables': {k: v.to_dict() for k, v in self.variables.items()},
            'functions': {k: v.to_dict() for k, v in self.functions.items()},
        }


# ── SemanticAnalyzer ─────────────────────────────────────────────────────────────

class SemanticAnalyzer:
    def __init__(self, reporter: ErrorReporter) -> None:
        self._reporter = reporter
        self._scopes: list[dict[str, Symbol]] = [{}]
        self._current_func: Optional[FunctionDecl] = None
        self._loop_depth: int = 0
        self._table = SymbolTable()
        self._all_locals: list[Symbol] = []  # all local symbols for unused checks

    def analyze(self, program: Program, mode: str = 'check') -> SymbolTable:
        if not validate_ast_limits(program, self._reporter):
            return self._table
        self._pass1_collect_functions(program)
        self._pass2_globals(program)
        self._pass3_function_bodies(program)
        self._pass4_unused_checks()
        if 'main' not in self._table.functions:
            severity = 'error' if mode == 'compile' else 'warning'
            self._reporter.add(
                'SEM026',
                "Programa sin función 'main' — requerido para ejecutar",
                1, 1,
                severity=severity,
            )
        return self._table

    # ── Pass 1 ──────────────────────────────────────────────────────────────────

    def _pass1_collect_functions(self, program: Program) -> None:
        for decl in program.declarations:
            if not isinstance(decl, FunctionDecl):
                continue
            fn = decl
            if fn.name in self._table.functions:
                prev = self._table.functions[fn.name]
                self._reporter.add(
                    'SEM006',
                    f"Función '{fn.name}' declarada más de una vez",
                    fn.pos.line, fn.pos.col,
                )
                _ = prev
                continue
            if fn.name in _BUILTINS:
                self._reporter.add(
                    'SEM036',
                    f"'{fn.name}' es un identificador reservado (builtin)",
                    fn.pos.line, fn.pos.col,
                )
            sym = Symbol(
                name=fn.name,
                type='void',
                kind='function',
                scope_level=0,
                line_declared=fn.pos.line,
                col_declared=fn.pos.col,
                return_type=fn.return_type,
                param_types=[p.type for p in fn.params],
                is_initialized=True,
            )
            self._table.functions[fn.name] = sym

            # Validate main
            if fn.name == 'main':
                if fn.return_type != 'int' or len(fn.params) != 0:
                    self._reporter.add(
                        'SEM025',
                        "'main' debe tener signatura 'int main()' sin parámetros",
                        fn.pos.line, fn.pos.col,
                    )

    # ── Pass 2 ──────────────────────────────────────────────────────────────────

    def _pass2_globals(self, program: Program) -> None:
        for decl in program.declarations:
            if isinstance(decl, VarDecl):
                self._analyze_var_decl(decl)
            elif isinstance(decl, ArrayDecl):
                self._analyze_array_decl(decl)

    # ── Pass 3 ──────────────────────────────────────────────────────────────────

    def _pass3_function_bodies(self, program: Program) -> None:
        for decl in program.declarations:
            if not isinstance(decl, FunctionDecl):
                continue
            fn = decl
            self._current_func = fn
            self._push_scope()
            for param in fn.params:
                if param.name in _BUILTINS:
                    self._reporter.add(
                        'SEM036',
                        f"'{param.name}' es un identificador reservado (builtin)",
                        param.pos.line, param.pos.col,
                    )
                sym = Symbol(
                    name=param.name,
                    type=param.type,
                    kind='parameter',
                    scope_level=len(self._scopes) - 1,
                    line_declared=param.pos.line,
                    col_declared=param.pos.col,
                    is_initialized=True,
                )
                self._declare(param.name, sym)
            self._analyze_block(fn.body)
            if fn.return_type != 'void' and not all_paths_return(fn.body):
                self._reporter.add(
                    'SEM022',
                    f"Función '{fn.name}' no retorna un valor en todos los caminos",
                    fn.pos.line, fn.pos.col,
                )
            if maybe_infinite_recursion(fn):
                self._reporter.add(
                    'SEM024',
                    f"Función '{fn.name}' parece no tener caso base (heurística)",
                    fn.pos.line, fn.pos.col,
                    severity='warning',
                )
            self._pop_scope()
            self._current_func = None

    # ── Pass 4 ──────────────────────────────────────────────────────────────────

    def _pass4_unused_checks(self) -> None:
        checked: set[int] = set()
        all_syms: list[Symbol] = (
            list(self._table.variables.values()) + self._all_locals
        )
        for sym in all_syms:
            sid = id(sym)
            if sid in checked:
                continue
            checked.add(sid)
            if sym.kind in ('variable', 'parameter', 'array') and sym.use_count == 0:
                self._reporter.add(
                    'SEM004',
                    f"Variable '{sym.name}' declarada pero nunca usada",
                    sym.line_declared, sym.col_declared,
                    severity='warning',
                )

    # ── Scope helpers ────────────────────────────────────────────────────────────

    def _push_scope(self) -> None:
        self._scopes.append({})

    def _pop_scope(self) -> None:
        if len(self._scopes) > 1:
            self._scopes.pop()

    def _declare(self, name: str, sym: Symbol) -> None:
        current = self._scopes[-1]
        if name in current:
            prev = current[name]
            self._reporter.add(
                'SEM002',
                f"'{name}' ya fue declarado en este scope (línea {prev.line_declared})",
                sym.line_declared, sym.col_declared,
            )
            return
        current[name] = sym
        self._all_locals.append(sym)

    def _resolve(self, name: str) -> Optional[Symbol]:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        if name in self._table.variables:
            return self._table.variables[name]
        return None

    # ── Statement analysis ───────────────────────────────────────────────────────

    def _analyze_block(self, block: Block) -> None:
        self._push_scope()
        for i, stmt in enumerate(block.stmts):
            self._analyze_stmt(stmt)
            if isinstance(stmt, (ReturnStmt, BreakStmt, ContinueStmt)):
                remaining = len(block.stmts) - i - 1
                if remaining > 0:
                    next_stmt = block.stmts[i + 1]
                    pos = getattr(next_stmt, 'pos', block.pos)
                    self._reporter.add(
                        'SEM023',
                        f"Código inalcanzable después de '{type(stmt).__name__}' "
                        f"({remaining} sentencia(s) omitida(s))",
                        pos.line, pos.col,
                        severity='warning',
                    )
                break
        self._pop_scope()

    def _analyze_var_decl(self, decl: VarDecl) -> None:
        if decl.name in _BUILTINS:
            self._reporter.add(
                'SEM036',
                f"'{decl.name}' es un identificador reservado (builtin)",
                decl.pos.line, decl.pos.col,
            )
        init_type: Optional[CType] = None
        if decl.init_expr is not None:
            init_type = self._analyze_expr(decl.init_expr)
            self._check_assign_compat(decl.type, init_type, decl.pos)

        is_global = len(self._scopes) == 1
        sym = Symbol(
            name=decl.name,
            type=decl.type,
            kind='variable',
            scope_level=len(self._scopes) - 1,
            line_declared=decl.pos.line,
            col_declared=decl.pos.col,
            is_initialized=decl.init_expr is not None,
        )
        if is_global:
            self._table.variables[decl.name] = sym
        else:
            self._declare(decl.name, sym)

    def _analyze_array_decl(self, decl: ArrayDecl) -> None:
        if decl.name in _BUILTINS:
            self._reporter.add(
                'SEM036',
                f"'{decl.name}' es un identificador reservado (builtin)",
                decl.pos.line, decl.pos.col,
            )
        if decl.size <= 0:
            code = 'SEM034' if decl.size < 0 else 'SEM033'
            msg = ('Tamaño de array no puede ser negativo' if decl.size < 0
                   else 'Tamaño de array debe ser mayor que 0')
            self._reporter.add(code, msg, decl.pos.line, decl.pos.col)
        elif decl.size > MAX_ARRAY_SIZE:
            self._reporter.add(
                'SEM035',
                f'Tamaño de array excede el máximo ({MAX_ARRAY_SIZE})',
                decl.pos.line, decl.pos.col,
            )
        if decl.init_list:
            if len(decl.init_list) != decl.size:
                self._reporter.add(
                    'SEM032',
                    f'Lista de inicialización tiene {len(decl.init_list)} elementos, '
                    f'array tiene tamaño {decl.size}',
                    decl.pos.line, decl.pos.col,
                )
            for elem in decl.init_list:
                self._analyze_expr(elem)

        is_global = len(self._scopes) == 1
        sym = Symbol(
            name=decl.name,
            type=decl.element_type,
            kind='array',
            scope_level=len(self._scopes) - 1,
            line_declared=decl.pos.line,
            col_declared=decl.pos.col,
            array_size=decl.size,
            is_initialized=len(decl.init_list) > 0,
        )
        if is_global:
            self._table.variables[decl.name] = sym
        else:
            self._declare(decl.name, sym)

    def _analyze_stmt(self, stmt: Any) -> None:
        if isinstance(stmt, VarDecl):
            self._analyze_var_decl(stmt)
        elif isinstance(stmt, ArrayDecl):
            self._analyze_array_decl(stmt)
        elif isinstance(stmt, Block):
            self._analyze_block(stmt)
        elif isinstance(stmt, IfStmt):
            self._analyze_if(stmt)
        elif isinstance(stmt, WhileStmt):
            self._analyze_while(stmt)
        elif isinstance(stmt, ForStmt):
            self._analyze_for(stmt)
        elif isinstance(stmt, DoWhileStmt):
            self._analyze_dowhile(stmt)
        elif isinstance(stmt, ReturnStmt):
            self._analyze_return(stmt)
        elif isinstance(stmt, (BreakStmt, ContinueStmt)):
            if self._loop_depth == 0:
                label = 'break' if isinstance(stmt, BreakStmt) else 'continue'
                self._reporter.add(
                    'SEM037',
                    f"'{label}'/'continue' fuera de un loop",
                    stmt.pos.line, stmt.pos.col,
                )
        elif isinstance(stmt, PrintStmt):
            self._analyze_expr(stmt.expr)
        elif isinstance(stmt, ExprStmt):
            self._analyze_expr(stmt.expr)

    def _analyze_if(self, stmt: IfStmt) -> None:
        ctype = self._analyze_expr(stmt.condition)
        if ctype not in ('bool', 'unknown'):
            self._reporter.add(
                'SEM017',
                "Condición de 'if'/'while'/'for'/'do-while' debe ser de tipo 'bool'",
                stmt.pos.line, stmt.pos.col,
            )
        self._analyze_block(stmt.then_body)
        for cond, blk in stmt.elif_clauses:
            ct = self._analyze_expr(cond)
            if ct not in ('bool', 'unknown'):
                self._reporter.add(
                    'SEM017',
                    "Condición de 'if'/'while'/'for'/'do-while' debe ser de tipo 'bool'",
                    stmt.pos.line, stmt.pos.col,
                )
            self._analyze_block(blk)
        if stmt.else_body is not None:
            self._analyze_block(stmt.else_body)

    def _analyze_while(self, stmt: WhileStmt) -> None:
        ctype = self._analyze_expr(stmt.condition)
        if ctype not in ('bool', 'unknown'):
            self._reporter.add(
                'SEM017',
                "Condición de 'if'/'while'/'for'/'do-while' debe ser de tipo 'bool'",
                stmt.pos.line, stmt.pos.col,
            )
        self._loop_depth += 1
        self._analyze_block(stmt.body)
        self._loop_depth -= 1

    def _analyze_for(self, stmt: ForStmt) -> None:
        self._push_scope()
        if stmt.init is not None:
            self._analyze_stmt(stmt.init)
        if stmt.condition is not None:
            ctype = self._analyze_expr(stmt.condition)
            if ctype not in ('bool', 'unknown'):
                self._reporter.add(
                    'SEM017',
                    "Condición de 'if'/'while'/'for'/'do-while' debe ser de tipo 'bool'",
                    stmt.pos.line, stmt.pos.col,
                )
        if stmt.update is not None:
            self._analyze_expr(stmt.update)
        self._loop_depth += 1
        self._analyze_block(stmt.body)
        self._loop_depth -= 1
        self._pop_scope()

    def _analyze_dowhile(self, stmt: DoWhileStmt) -> None:
        self._loop_depth += 1
        self._analyze_block(stmt.body)
        self._loop_depth -= 1
        ctype = self._analyze_expr(stmt.condition)
        if ctype not in ('bool', 'unknown'):
            self._reporter.add(
                'SEM017',
                "Condición de 'if'/'while'/'for'/'do-while' debe ser de tipo 'bool'",
                stmt.pos.line, stmt.pos.col,
            )

    def _analyze_return(self, stmt: ReturnStmt) -> None:
        if self._current_func is None:
            return
        expected = self._current_func.return_type
        if stmt.value is None:
            if expected != 'void':
                self._reporter.add(
                    'SEM016',
                    f"Función '{self._current_func.name}' debe retornar '{expected}', retorna 'void'",
                    stmt.pos.line, stmt.pos.col,
                )
        else:
            found = self._analyze_expr(stmt.value)
            if expected == 'void':
                self._reporter.add(
                    'SEM016',
                    f"Función '{self._current_func.name}' debe retornar 'void', retorna '{found}'",
                    stmt.pos.line, stmt.pos.col,
                )
            elif found != 'unknown':
                self._check_assign_compat(expected, found, stmt.pos)

    # ── Expression analysis ─────────────────────────────────────────────────────

    def _check_assign_compat(self, expected: CType, found: CType, pos: SourcePos) -> None:
        if found == 'unknown' or expected == 'unknown':
            return
        if expected == found:
            return
        if (found, expected) in SAFE_WIDENING:
            return
        if (found, expected) in LOSSY_NARROWING:
            self._reporter.add(
                'SEM012',
                f"Posible pérdida de datos: conversión de '{found}' a '{expected}'",
                pos.line, pos.col,
                severity='warning',
            )
            return
        self._reporter.add(
            'SEM010',
            f"Tipo incompatible en asignación: esperaba '{expected}', encontró '{found}'",
            pos.line, pos.col,
        )

    def _analyze_expr(self, node: Any) -> CType:
        if isinstance(node, IntLiteral):
            node.inferred_type = 'int'
            return 'int'
        if isinstance(node, FloatLiteral):
            node.inferred_type = 'float'
            return 'float'
        if isinstance(node, StringLiteral):
            node.inferred_type = 'string'
            return 'string'
        if isinstance(node, CharLiteral):
            node.inferred_type = 'char'
            return 'char'
        if isinstance(node, BoolLiteral):
            node.inferred_type = 'bool'
            return 'bool'
        if isinstance(node, InputExpr):
            input_type_map: dict[str, CType] = {'string': 'string', 'int': 'int', 'float': 'float'}
            t: CType = input_type_map[node.variant]
            node.inferred_type = t
            return t
        if isinstance(node, Identifier):
            return self._analyze_identifier(node)
        if isinstance(node, IndexExpr):
            return self._analyze_index(node)
        if isinstance(node, CallExpr):
            return self._analyze_call(node)
        if isinstance(node, BinaryOp):
            return self._analyze_binary(node)
        if isinstance(node, UnaryOp):
            return self._analyze_unary(node)
        if isinstance(node, AssignOp):
            return self._analyze_assign(node)
        if isinstance(node, CastExpr):
            self._analyze_expr(node.expr)
            node.inferred_type = node.target_type
            return node.target_type
        return 'unknown'

    def _analyze_identifier(self, node: Identifier) -> CType:
        sym = self._resolve(node.name)
        if sym is None:
            # Check functions table too
            if node.name in self._table.functions:
                sym = self._table.functions[node.name]
            else:
                self._reporter.add(
                    'SEM001',
                    f"Variable '{node.name}' usada antes de ser declarada",
                    node.pos.line, node.pos.col,
                )
                node.inferred_type = 'unknown'
                return 'unknown'
        sym.use_count += 1
        if not sym.is_initialized and sym.kind not in ('function', 'parameter'):
            self._reporter.add(
                'SEM003',
                f"Variable '{node.name}' usada sin haber sido inicializada",
                node.pos.line, node.pos.col,
                severity='warning',
            )
        node.inferred_type = sym.type
        return sym.type

    def _analyze_index(self, node: IndexExpr) -> CType:
        sym = self._resolve(node.name)
        if sym is None and node.name in self._table.variables:
            sym = self._table.variables[node.name]
        if sym is None:
            self._reporter.add(
                'SEM001',
                f"Variable '{node.name}' usada antes de ser declarada",
                node.pos.line, node.pos.col,
            )
            return 'unknown'
        if sym.kind != 'array':
            self._reporter.add(
                'SEM030',
                f"'{node.name}' no es un array",
                node.pos.line, node.pos.col,
            )
        sym.use_count += 1
        self._analyze_expr(node.index)
        # Static index check
        if isinstance(node.index, IntLiteral) and sym.kind == 'array':
            idx_val = node.index.value
            if idx_val < 0 or idx_val >= sym.array_size:
                self._reporter.add(
                    'SEM015',
                    f'Índice {idx_val} fuera del rango válido '
                    f'[0, {sym.array_size - 1}] para el array \'{node.name}\'',
                    node.pos.line, node.pos.col,
                )
        node.inferred_type = sym.type
        return sym.type

    def _analyze_call(self, node: CallExpr) -> CType:
        if node.name in _LIBC_VARARG_BUILTINS:
            for arg in node.args:
                self._analyze_expr(arg)
            node.inferred_type = 'void'
            return 'void'

        sym = self._table.functions.get(node.name)
        if sym is None:
            var_sym = self._resolve(node.name)
            if var_sym is not None and var_sym.kind in ('variable', 'parameter', 'array'):
                self._reporter.add(
                    'SEM031',
                    f"'{node.name}' no es una función",
                    node.pos.line, node.pos.col,
                )
            else:
                self._reporter.add(
                    'SEM005',
                    f"Función '{node.name}' llamada pero no declarada",
                    node.pos.line, node.pos.col,
                )
            for arg in node.args:
                self._analyze_expr(arg)
            node.inferred_type = 'unknown'
            return 'unknown'

        sym.use_count += 1
        sym.call_count += 1

        if len(node.args) != len(sym.param_types):
            self._reporter.add(
                'SEM020',
                f"Función '{node.name}' espera {len(sym.param_types)} argumentos, "
                f'se encontraron {len(node.args)}',
                node.pos.line, node.pos.col,
            )
        for i, arg in enumerate(node.args):
            atype = self._analyze_expr(arg)
            if i < len(sym.param_types):
                expected_t = sym.param_types[i]
                if atype != 'unknown' and expected_t != 'unknown' and atype != expected_t:
                    if (atype, expected_t) not in SAFE_WIDENING:
                        self._reporter.add(
                            'SEM021',
                            f"Argumento {i + 1} de '{node.name}': tipo '{atype}', "
                            f"se esperaba '{expected_t}'",
                            node.pos.line, node.pos.col,
                        )

        node.inferred_type = sym.return_type
        return sym.return_type

    def _analyze_binary(self, node: BinaryOp) -> CType:
        left = self._analyze_expr(node.left)
        right = self._analyze_expr(node.right)

        # Division by zero check
        if node.op in ('/', '%') and isinstance(node.right, IntLiteral) and node.right.value == 0:
            self._reporter.add('SEM013', 'División por cero en tiempo de compilación',
                               node.pos.line, node.pos.col)

        result, lossy = resolve_binary_type(left, right, node.op)
        if result == 'unknown' and left != 'unknown' and right != 'unknown':
            self._reporter.add(
                'SEM011',
                f"Operador '{node.op}' no puede aplicarse a tipos '{left}' y '{right}'",
                node.pos.line, node.pos.col,
            )
        if lossy:
            self._reporter.add(
                'SEM012',
                f"Posible pérdida de datos: conversión de '{left}' a '{right}'",
                node.pos.line, node.pos.col,
                severity='warning',
            )
        node.inferred_type = result
        return result

    def _analyze_unary(self, node: UnaryOp) -> CType:
        t = self._analyze_expr(node.operand)
        if node.op == '!':
            if t not in ('bool', 'unknown'):
                self._reporter.add(
                    'SEM011',
                    f"Operador '!' no puede aplicarse a tipo '{t}'",
                    node.pos.line, node.pos.col,
                )
            node.inferred_type = 'bool'
            return 'bool'
        if node.op == '-':
            if t not in ('int', 'float', 'char', 'unknown'):
                self._reporter.add(
                    'SEM011',
                    f"Operador '-' no puede aplicarse a tipo '{t}'",
                    node.pos.line, node.pos.col,
                )
            node.inferred_type = t if t != 'unknown' else 'int'
            return node.inferred_type
        if node.op in ('++', '--'):
            if t not in ('int', 'float', 'char', 'unknown'):
                self._reporter.add(
                    'SEM011',
                    f"Operador '{node.op}' no puede aplicarse a tipo '{t}'",
                    node.pos.line, node.pos.col,
                )
            if isinstance(node.operand, Identifier):
                sym = self._resolve(node.operand.name)
                if sym:
                    sym.is_mutated = True
                    sym.is_initialized = True
            node.inferred_type = t if t != 'unknown' else 'int'
            return node.inferred_type
        node.inferred_type = t
        return t

    def _analyze_assign(self, node: AssignOp) -> CType:
        target_type = self._analyze_expr(node.target)
        val_type = self._analyze_expr(node.value)

        # Mark target as initialized
        if isinstance(node.target, Identifier):
            sym = self._resolve(node.target.name)
            if sym:
                sym.is_initialized = True
                sym.is_mutated = True

        if target_type != 'unknown' and val_type != 'unknown':
            self._check_assign_compat(target_type, val_type, node.pos)

        return target_type
