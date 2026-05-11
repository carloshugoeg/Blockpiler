from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

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
import threading

from compiler.limits import INT64_MAX, INT64_MIN, INTERP_MAX_DEPTH, INTERP_MAX_ITERS, INTERP_TIMEOUT_SEC


class InterpreterError(Exception):
    pass


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


@dataclass
class DebugState:
    line: int
    col: int
    variables: dict[str, Any]
    call_stack: list[str]
    stdout: str
    finished: bool
    return_code: Optional[int]


class Interpreter:
    def __init__(
        self,
        program: Program,
        input_fn: Optional[Callable[[], str]] = None,
    ) -> None:
        self._program = program
        self._input_fn = input_fn
        self._functions: dict[str, FunctionDecl] = {}
        self._scopes: list[dict[str, Any]] = []
        self._stdout_buf: list[str] = []
        self._call_depth: int = 0
        self._iter_count: int = 0
        self._call_stack: list[str] = []

        # Debug state
        self._debug_stmts: list[Any] = []
        self._debug_pos: int = 0
        self._debug_finished: bool = False
        self._debug_return_code: Optional[int] = None

        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                self._functions[decl.name] = decl

    def run(self) -> tuple[str, int]:
        if 'main' not in self._functions:
            raise InterpreterError("Programa sin función 'main'")
        main_fn = self._functions['main']

        result: list[Any] = [None]
        exc: list[BaseException | None] = [None]

        def _target() -> None:
            try:
                result[0] = self._execute_function(main_fn, [])
            except BaseException as e:  # noqa: BLE001
                exc[0] = e

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=INTERP_TIMEOUT_SEC)

        if thread.is_alive():
            raise InterpreterError(
                f'Timeout: programa excedió el límite de ejecución ({INTERP_TIMEOUT_SEC}s)'
            )
        if exc[0] is not None:
            if isinstance(exc[0], RecursionError):
                raise InterpreterError(
                    f'Profundidad de recursión excede {INTERP_MAX_DEPTH}'
                ) from exc[0]
            raise exc[0]

        rc = int(result[0]) if result[0] is not None else 0
        return ''.join(self._stdout_buf), rc

    def start_debug(self) -> None:
        self._debug_finished = False
        self._debug_return_code = None
        if 'main' not in self._functions:
            raise InterpreterError("Programa sin función 'main'")
        fn = self._functions['main']
        self._debug_stmts = list(fn.body.stmts)
        self._debug_pos = 0
        self._scopes = [{}]
        self._call_stack = ['main']

    def step(self) -> DebugState:
        if self._debug_finished:
            return self.get_state()
        if self._debug_pos >= len(self._debug_stmts):
            self._debug_finished = True
            self._debug_return_code = 0
            return self.get_state()
        stmt = self._debug_stmts[self._debug_pos]
        self._debug_pos += 1
        try:
            self._execute_stmt(stmt)
        except _ReturnSignal as r:
            self._debug_finished = True
            self._debug_return_code = int(r.value) if r.value is not None else 0
        except InterpreterError:
            self._debug_finished = True
        return self.get_state()

    def continue_to_breakpoint(self, breakpoints: set[int]) -> DebugState:
        while not self._debug_finished:
            state = self.step()
            if state.line in breakpoints:
                break
        return self.get_state()

    def get_state(self) -> DebugState:
        stmt = None
        if self._debug_pos < len(self._debug_stmts):
            stmt = self._debug_stmts[self._debug_pos - 1] if self._debug_pos > 0 else None
        line = 0
        col = 0
        if stmt is not None:
            pos = getattr(stmt, 'pos', None)
            if pos is not None:
                line = pos.line
                col = pos.col
        flat_vars: dict[str, Any] = {}
        for scope in self._scopes:
            flat_vars.update(scope)
        return DebugState(
            line=line,
            col=col,
            variables=dict(flat_vars),
            call_stack=list(self._call_stack),
            stdout=''.join(self._stdout_buf),
            finished=self._debug_finished,
            return_code=self._debug_return_code,
        )

    # ── Internal execution ───────────────────────────────────────────────────────

    def _push_scope(self) -> None:
        self._scopes.append({})

    def _pop_scope(self) -> None:
        if len(self._scopes) > 1:
            self._scopes.pop()

    def _set_var(self, name: str, value: Any) -> None:
        # Update in the scope where it was declared first, else current
        for scope in reversed(self._scopes):
            if name in scope:
                scope[name] = value
                return
        self._scopes[-1][name] = value

    def _get_var(self, name: str) -> Any:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise InterpreterError(f"Variable '{name}' no declarada")

    def _execute_function(self, func: FunctionDecl, args: list[Any]) -> Any:
        self._call_depth += 1
        if self._call_depth > INTERP_MAX_DEPTH:
            raise InterpreterError(
                f'Profundidad de recursión excede {INTERP_MAX_DEPTH}'
            )
        self._call_stack.append(func.name)
        self._push_scope()
        for param, val in zip(func.params, args):
            self._scopes[-1][param.name] = val
        result: Any = None
        try:
            result = self._execute_block(func.body)
        except _ReturnSignal as r:
            result = r.value
        finally:
            self._pop_scope()
            self._call_stack.pop()
            self._call_depth -= 1
        return result

    def _execute_block(self, block: Block) -> Any:
        self._push_scope()
        try:
            for stmt in block.stmts:
                self._execute_stmt(stmt)
        finally:
            self._pop_scope()
        return None

    def _execute_stmt(self, stmt: Any) -> None:
        if isinstance(stmt, VarDecl):
            val = self._eval_expr(stmt.init_expr) if stmt.init_expr is not None else None
            self._scopes[-1][stmt.name] = val
        elif isinstance(stmt, ArrayDecl):
            if stmt.init_list:
                arr = [self._eval_expr(e) for e in stmt.init_list]
            else:
                arr = [None] * stmt.size
            self._scopes[-1][stmt.name] = arr
        elif isinstance(stmt, IfStmt):
            cond = bool(self._eval_expr(stmt.condition))
            if cond:
                self._execute_block(stmt.then_body)
            else:
                matched = False
                for ec, eb in stmt.elif_clauses:
                    if bool(self._eval_expr(ec)):
                        self._execute_block(eb)
                        matched = True
                        break
                if not matched and stmt.else_body is not None:
                    self._execute_block(stmt.else_body)
        elif isinstance(stmt, WhileStmt):
            while bool(self._eval_expr(stmt.condition)):
                self._iter_count += 1
                if self._iter_count > INTERP_MAX_ITERS:
                    raise InterpreterError(
                        f'Límite de iteraciones excedido ({INTERP_MAX_ITERS})'
                    )
                try:
                    self._execute_block(stmt.body)
                except _BreakSignal:
                    break
                except _ContinueSignal:
                    continue
        elif isinstance(stmt, ForStmt):
            self._push_scope()
            try:
                if stmt.init is not None:
                    self._execute_stmt(stmt.init)
                while True:
                    if stmt.condition is not None:
                        if not bool(self._eval_expr(stmt.condition)):
                            break
                    self._iter_count += 1
                    if self._iter_count > INTERP_MAX_ITERS:
                        raise InterpreterError(
                            f'Límite de iteraciones excedido ({INTERP_MAX_ITERS})'
                        )
                    try:
                        self._execute_block(stmt.body)
                    except _BreakSignal:
                        break
                    except _ContinueSignal:
                        pass
                    if stmt.update is not None:
                        self._eval_expr(stmt.update)
            finally:
                self._pop_scope()
        elif isinstance(stmt, DoWhileStmt):
            while True:
                self._iter_count += 1
                if self._iter_count > INTERP_MAX_ITERS:
                    raise InterpreterError(
                        f'Límite de iteraciones excedido ({INTERP_MAX_ITERS})'
                    )
                try:
                    self._execute_block(stmt.body)
                except _BreakSignal:
                    break
                except _ContinueSignal:
                    pass
                if not bool(self._eval_expr(stmt.condition)):
                    break
        elif isinstance(stmt, ReturnStmt):
            val = self._eval_expr(stmt.value) if stmt.value is not None else None
            raise _ReturnSignal(val)
        elif isinstance(stmt, BreakStmt):
            raise _BreakSignal()
        elif isinstance(stmt, ContinueStmt):
            raise _ContinueSignal()
        elif isinstance(stmt, PrintStmt):
            val = self._eval_expr(stmt.expr)
            text = str(val) if not isinstance(val, bool) else ('true' if val else 'false')
            self._stdout_buf.append(text + ('\n' if stmt.newline else ''))
        elif isinstance(stmt, ExprStmt):
            self._eval_expr(stmt.expr)
        elif isinstance(stmt, Block):
            self._execute_block(stmt)

    def _eval_expr(self, expr: Any) -> Any:
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, FloatLiteral):
            return expr.value
        if isinstance(expr, StringLiteral):
            return expr.value
        if isinstance(expr, CharLiteral):
            return expr.value
        if isinstance(expr, BoolLiteral):
            return expr.value
        if isinstance(expr, Identifier):
            return self._get_var(expr.name)
        if isinstance(expr, IndexExpr):
            arr = self._get_var(expr.name)
            idx = int(self._eval_expr(expr.index))
            if not isinstance(arr, list):
                raise InterpreterError(f"'{expr.name}' no es un array")
            if idx < 0 or idx >= len(arr):
                raise InterpreterError(
                    f'Índice {idx} fuera de rango para array "{expr.name}"'
                )
            return arr[idx]
        if isinstance(expr, BinaryOp):
            return self._eval_binary(expr)
        if isinstance(expr, UnaryOp):
            return self._eval_unary(expr)
        if isinstance(expr, AssignOp):
            return self._eval_assign(expr)
        if isinstance(expr, CallExpr):
            return self._eval_call(expr)
        if isinstance(expr, CastExpr):
            return self._eval_cast(expr)
        if isinstance(expr, InputExpr):
            return self._eval_input(expr)
        return None

    def _eval_binary(self, expr: BinaryOp) -> Any:
        op = expr.op
        # Short-circuit for logical ops
        if op == '&&':
            left = self._eval_expr(expr.left)
            if not bool(left):
                return False
            return bool(self._eval_expr(expr.right))
        if op == '||':
            left = self._eval_expr(expr.left)
            if bool(left):
                return True
            return bool(self._eval_expr(expr.right))

        left = self._eval_expr(expr.left)
        right = self._eval_expr(expr.right)

        if op == '+':
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            return self._clamp_int(left + right) if isinstance(left, int) and isinstance(right, int) else left + right
        if op == '-':
            return self._clamp_int(left - right) if isinstance(left, int) and isinstance(right, int) else left - right
        if op == '*':
            return self._clamp_int(left * right) if isinstance(left, int) and isinstance(right, int) else left * right
        if op == '/':
            if right == 0:
                raise InterpreterError('División por cero')
            if isinstance(left, int) and isinstance(right, int):
                return int(left / right)
            return left / right
        if op == '%':
            if right == 0:
                raise InterpreterError('División por cero (módulo)')
            return int(left) % int(right)
        if op == '<<':
            return int(left) << int(right)
        if op == '>>':
            return int(left) >> int(right)
        if op == '==':
            return left == right
        if op == '!=':
            return left != right
        if op == '<':
            return left < right
        if op == '>':
            return left > right
        if op == '<=':
            return left <= right
        if op == '>=':
            return left >= right
        return None

    def _clamp_int(self, val: int) -> int:
        if val > INT64_MAX:
            return val & 0xFFFFFFFFFFFFFFFF - (1 << 64)
        if val < INT64_MIN:
            return val
        return val

    def _eval_unary(self, expr: UnaryOp) -> Any:
        op = expr.op
        if op == '++' and expr.prefix:
            val = self._eval_expr(expr.operand) + 1
            self._store(expr.operand, val)
            return val
        if op == '--' and expr.prefix:
            val = self._eval_expr(expr.operand) - 1
            self._store(expr.operand, val)
            return val
        if op == '++':
            old = self._eval_expr(expr.operand)
            self._store(expr.operand, old + 1)
            return old
        if op == '--':
            old = self._eval_expr(expr.operand)
            self._store(expr.operand, old - 1)
            return old
        if op == '-':
            return -self._eval_expr(expr.operand)
        if op == '!':
            return not bool(self._eval_expr(expr.operand))
        return self._eval_expr(expr.operand)

    def _eval_assign(self, expr: AssignOp) -> Any:
        rval = self._eval_expr(expr.value)
        if expr.op == '=':
            self._store(expr.target, rval)
            return rval
        cur = self._eval_expr(expr.target)
        op = expr.op
        if op == '+=':
            new = cur + rval
        elif op == '-=':
            new = cur - rval
        elif op == '*=':
            new = cur * rval
        elif op == '/=':
            if rval == 0:
                raise InterpreterError('División por cero (asignación)')
            new = cur / rval
        elif op == '%=':
            if rval == 0:
                raise InterpreterError('Módulo por cero')
            new = int(cur) % int(rval)
        else:
            new = rval
        self._store(expr.target, new)
        return new

    def _store(self, target: Any, value: Any) -> None:
        if isinstance(target, Identifier):
            self._set_var(target.name, value)
        elif isinstance(target, IndexExpr):
            arr = self._get_var(target.name)
            idx = int(self._eval_expr(target.index))
            if not isinstance(arr, list):
                raise InterpreterError(f"'{target.name}' no es un array")
            if idx < 0 or idx >= len(arr):
                raise InterpreterError(
                    f'Índice {idx} fuera de rango para array "{target.name}"'
                )
            arr[idx] = value

    def _eval_call(self, expr: CallExpr) -> Any:
        if expr.name == 'printf':
            args = [self._eval_expr(a) for a in expr.args]
            self._stdout_buf.append(_format_printf(args))
            return None

        func = self._functions.get(expr.name)
        if func is None:
            raise InterpreterError(f"Función '{expr.name}' no declarada")
        args = [self._eval_expr(a) for a in expr.args]
        return self._execute_function(func, args)

    def _eval_cast(self, expr: CastExpr) -> Any:
        val = self._eval_expr(expr.expr)
        t = expr.target_type
        if t == 'int':
            return int(val)
        if t == 'float':
            return float(val)
        if t == 'bool':
            return bool(val)
        if t == 'char':
            return chr(int(val)) if isinstance(val, int) else str(val)[0]
        if t == 'string':
            return str(val)
        return val

    def _eval_input(self, expr: InputExpr) -> Any:
        if self._input_fn is None:
            raise InterpreterError('input() requiere input_fn configurado')
        raw = self._input_fn()
        if expr.variant == 'int':
            return int(raw.strip())
        if expr.variant == 'float':
            return float(raw.strip())
        return raw


def _format_printf(args: list[Any]) -> str:
    if not args:
        return ''
    fmt = str(args[0])
    values = list(args[1:])
    out: list[str] = []
    i = 0
    arg_i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch != '%' or i + 1 >= len(fmt):
            out.append(ch)
            i += 1
            continue
        if fmt[i + 1] == '%':
            out.append('%')
            i += 2
            continue

        j = i + 1
        while j < len(fmt) and fmt[j] in '0123456789.-+ #lh':
            j += 1
        spec = fmt[j] if j < len(fmt) else ''
        if not spec:
            out.append('%')
            i += 1
            continue

        value = values[arg_i] if arg_i < len(values) else ''
        arg_i += 1
        if spec in 'diu':
            out.append(str(int(value)))
        elif spec in 'fFgGeE':
            out.append(str(float(value)))
        elif spec == 'c':
            out.append(chr(int(value)) if isinstance(value, int) else str(value)[:1])
        else:
            out.append(str(value))
        i = j + 1
    return ''.join(out)
