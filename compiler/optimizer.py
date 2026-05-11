from __future__ import annotations

import math
from typing import Any, Optional

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
    IntLiteral,
    PrintStmt,
    Program,
    ReturnStmt,
    SourcePos,
    StringLiteral,
    UnaryOp,
    VarDecl,
    WhileStmt,
    is_pure_expr,
)
from compiler.limits import INT64_MAX, INT64_MIN, OPTIMIZER_MAX_PASS
from compiler.semantic import SymbolTable


def _expr_canonical_hash(node: Any) -> str:
    """Canonical hash for pure expressions, ignoring pos."""
    if isinstance(node, IntLiteral):
        return f'int:{node.value}'
    if isinstance(node, FloatLiteral):
        return f'float:{node.value}'
    if isinstance(node, BoolLiteral):
        return f'bool:{node.value}'
    if isinstance(node, Identifier):
        return f'id:{node.name}'
    if isinstance(node, BinaryOp):
        return f'bin:{node.op}:({_expr_canonical_hash(node.left)}):({_expr_canonical_hash(node.right)})'
    if isinstance(node, UnaryOp):
        return f'un:{node.op}:{node.prefix}:({_expr_canonical_hash(node.operand)})'
    if isinstance(node, CastExpr):
        return f'cast:{node.target_type}:({_expr_canonical_hash(node.expr)})'
    return f'other:{id(node)}'


def _collect_modified_names(node: Any, names: set[str]) -> None:
    """Collect all variable names that are assigned/mutated inside a node."""
    _collect_assigns(node, names)


def _is_loop_invariant(node: Any, modified: set[str]) -> bool:
    """Return True if node is pure and none of its Identifiers are in modified."""
    if not is_pure_expr(node):
        return False
    if isinstance(node, Identifier):
        return node.name not in modified
    if isinstance(node, BinaryOp):
        return _is_loop_invariant(node.left, modified) and _is_loop_invariant(node.right, modified)
    if isinstance(node, UnaryOp):
        return _is_loop_invariant(node.operand, modified)
    if isinstance(node, (IntLiteral, FloatLiteral, BoolLiteral, StringLiteral, CharLiteral)):
        return True
    return False

_POS0 = SourcePos(0, 0)

STRENGTH_MUL = {2: 1, 4: 2, 8: 3, 16: 4, 32: 5, 64: 6, 128: 7, 256: 8}


def _is_int_lit(node: Any, val: int) -> bool:
    return isinstance(node, IntLiteral) and node.value == val


def _is_bool_lit(node: Any, val: bool) -> bool:
    return isinstance(node, BoolLiteral) and node.value == val


def _count_nodes(node: Any) -> int:
    if isinstance(node, (IntLiteral, FloatLiteral, StringLiteral,
                         CharLiteral, BoolLiteral, Identifier)):
        return 1
    if isinstance(node, BinaryOp):
        return 1 + _count_nodes(node.left) + _count_nodes(node.right)
    if isinstance(node, UnaryOp):
        return 1 + _count_nodes(node.operand)
    if isinstance(node, CastExpr):
        return 1 + _count_nodes(node.expr)
    if isinstance(node, CallExpr):
        return 1 + sum(_count_nodes(a) for a in node.args)
    return 1


def _collect_assigns(node: Any, names: set[str]) -> None:
    if isinstance(node, AssignOp):
        if isinstance(node.target, Identifier):
            names.add(node.target.name)
        _collect_assigns(node.value, names)
    elif isinstance(node, UnaryOp) and node.op in ('++', '--'):
        if isinstance(node.operand, Identifier):
            names.add(node.operand.name)
    elif isinstance(node, BinaryOp):
        _collect_assigns(node.left, names)
        _collect_assigns(node.right, names)
    elif isinstance(node, Block):
        for s in node.stmts:
            _collect_assigns(s, names)
    elif isinstance(node, IfStmt):
        _collect_assigns(node.condition, names)
        _collect_assigns(node.then_body, names)
        for c, b in node.elif_clauses:
            _collect_assigns(c, names)
            _collect_assigns(b, names)
        if node.else_body:
            _collect_assigns(node.else_body, names)
    elif isinstance(node, (WhileStmt, DoWhileStmt)):
        _collect_assigns(node.condition, names)
        _collect_assigns(node.body, names)
    elif isinstance(node, ForStmt):
        if node.init:
            _collect_assigns(node.init, names)
        if node.condition:
            _collect_assigns(node.condition, names)
        if node.update:
            _collect_assigns(node.update, names)
        _collect_assigns(node.body, names)
    elif isinstance(node, ReturnStmt) and node.value:
        _collect_assigns(node.value, names)
    elif isinstance(node, ExprStmt):
        _collect_assigns(node.expr, names)
    elif isinstance(node, PrintStmt):
        _collect_assigns(node.expr, names)


class Optimizer:
    def __init__(
        self,
        level: int = 1,
        symbol_table: Optional[SymbolTable] = None,
    ) -> None:
        self._level = level
        self._symbol_table = symbol_table
        self._changed = False
        self._licm_counter = 0
        self._cse_counter = 0

    def optimize(self, program: Program) -> Program:
        if self._level == 0:
            return program
        result = program
        for _ in range(OPTIMIZER_MAX_PASS):
            self._changed = False
            result = self._run_passes(result)
            if not self._changed:
                break
        return result

    def _run_passes(self, program: Program) -> Program:
        decls = []
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                decl = self._optimize_function(decl)
            decls.append(decl)
        prog = Program(declarations=decls, pos=program.pos)

        # Level 1: constant propagation across the whole program
        if self._level >= 1:
            prog = self._propagate_constants(prog)

        # Level 2: LICM and CSE over whole program
        if self._level >= 2:
            prog = self._licm(prog)
            prog = self._cse(prog)

        # Level 3: function inlining
        if self._level >= 3:
            prog = self._inline_functions(prog)

        return prog

    def _optimize_function(self, fn: FunctionDecl) -> FunctionDecl:
        body = self._optimize_block(fn.body)
        # TCO (level 3): mark tail calls
        if self._level >= 3:
            body = self._mark_tco_in_block(fn.name, body)
        return FunctionDecl(
            name=fn.name,
            return_type=fn.return_type,
            params=fn.params,
            body=body,
            pos=fn.pos,
        )

    def _optimize_block(self, block: Block) -> Block:
        stmts = [self._optimize_stmt(s) for s in block.stmts]
        # Dead code: truncate after first return/break/continue
        stmts = self._dead_code_stmts(stmts)
        return Block(stmts=stmts, pos=block.pos)

    def _optimize_stmt(self, stmt: Any) -> Any:
        if isinstance(stmt, VarDecl):
            init = self._fold_expr(stmt.init_expr) if stmt.init_expr is not None else None
            return VarDecl(name=stmt.name, type=stmt.type, init_expr=init, pos=stmt.pos)
        if isinstance(stmt, ArrayDecl):
            return stmt
        if isinstance(stmt, IfStmt):
            return self._optimize_if(stmt)
        if isinstance(stmt, WhileStmt):
            return self._optimize_while(stmt)
        if isinstance(stmt, ForStmt):
            return self._optimize_for(stmt)
        if isinstance(stmt, DoWhileStmt):
            body = self._optimize_block(stmt.body)
            cond = self._fold_expr(stmt.condition)
            return DoWhileStmt(body=body, condition=cond, pos=stmt.pos)
        if isinstance(stmt, ReturnStmt):
            val = self._fold_expr(stmt.value) if stmt.value is not None else None
            return ReturnStmt(value=val, pos=stmt.pos)
        if isinstance(stmt, PrintStmt):
            return PrintStmt(expr=self._fold_expr(stmt.expr), newline=stmt.newline, pos=stmt.pos)
        if isinstance(stmt, ExprStmt):
            return ExprStmt(expr=self._fold_expr(stmt.expr), pos=stmt.pos)
        if isinstance(stmt, Block):
            return self._optimize_block(stmt)
        return stmt

    def _optimize_if(self, stmt: IfStmt) -> Any:
        cond = self._fold_expr(stmt.condition)
        then = self._optimize_block(stmt.then_body)
        elif_clauses = [(self._fold_expr(c), self._optimize_block(b))
                        for c, b in stmt.elif_clauses]
        else_body = self._optimize_block(stmt.else_body) if stmt.else_body else None

        # Dead code: if (true) → then_body
        if isinstance(cond, BoolLiteral) and cond.value is True:
            self._changed = True
            return then
        # if (false) → else_body or nothing
        if isinstance(cond, BoolLiteral) and cond.value is False:
            self._changed = True
            return else_body if else_body is not None else Block(stmts=[], pos=stmt.pos)

        return IfStmt(
            condition=cond,
            then_body=then,
            elif_clauses=elif_clauses,
            else_body=else_body,
            pos=stmt.pos,
        )

    def _optimize_while(self, stmt: WhileStmt) -> Any:
        cond = self._fold_expr(stmt.condition)
        # while (false) → remove
        if isinstance(cond, BoolLiteral) and cond.value is False:
            self._changed = True
            return Block(stmts=[], pos=stmt.pos)
        body = self._optimize_block(stmt.body)
        return WhileStmt(condition=cond, body=body, pos=stmt.pos)

    def _optimize_for(self, stmt: ForStmt) -> ForStmt:
        init = self._optimize_stmt(stmt.init) if stmt.init else None
        cond = self._fold_expr(stmt.condition) if stmt.condition else None
        upd = self._fold_expr(stmt.update) if stmt.update else None
        body = self._optimize_block(stmt.body)
        return ForStmt(init=init, condition=cond, update=upd, body=body, pos=stmt.pos)

    def _dead_code_stmts(self, stmts: list[Any]) -> list[Any]:
        result: list[Any] = []
        for i, s in enumerate(stmts):
            # Flatten Block stmts from if-true / while-false rewrites
            if isinstance(s, Block) and len(s.stmts) == 0 and i > 0:
                continue
            result.append(s)
            if isinstance(s, (ReturnStmt, BreakStmt, ContinueStmt)):
                if i < len(stmts) - 1:
                    self._changed = True
                break
        return result

    def _fold_expr(self, node: Any) -> Any:
        if node is None:
            return node
        if isinstance(node, BinaryOp):
            return self._fold_binary(node)
        if isinstance(node, UnaryOp):
            return self._fold_unary(node)
        if isinstance(node, AssignOp):
            return AssignOp(
                op=node.op,
                target=self._fold_expr(node.target),
                value=self._fold_expr(node.value),
                pos=node.pos,
            )
        if isinstance(node, CallExpr):
            args = [self._fold_expr(a) for a in node.args]
            return CallExpr(name=node.name, args=args,
                            inferred_type=node.inferred_type,
                            is_tail_call=node.is_tail_call, pos=node.pos)
        if isinstance(node, IndexExpr):
            return IndexExpr(name=node.name, index=self._fold_expr(node.index),
                             inferred_type=node.inferred_type, pos=node.pos)
        if isinstance(node, CastExpr):
            return CastExpr(target_type=node.target_type, expr=self._fold_expr(node.expr),
                            inferred_type=node.inferred_type, pos=node.pos)
        return node

    def _fold_binary(self, node: BinaryOp) -> Any:
        left = self._fold_expr(node.left)
        right = self._fold_expr(node.right)

        # Level 2: algebraic simplification
        if self._level >= 2:
            result = self._algebraic_simplify_bin(left, right, node.op, node.pos)
            if result is not None:
                self._changed = True
                return result
            # Strength reduction: x * N where N is power of 2
            result = self._strength_reduce_bin(left, right, node.op, node.pos)
            if result is not None:
                self._changed = True
                return result

        if not (is_pure_expr(left) and is_pure_expr(right)):
            return BinaryOp(op=node.op, left=left, right=right,
                            inferred_type=node.inferred_type, pos=node.pos)

        # Guard: no div/mod by zero
        if node.op in ('/', '%'):
            if _is_int_lit(right, 0):
                return BinaryOp(op=node.op, left=left, right=right,
                                inferred_type=node.inferred_type, pos=node.pos)

        # Constant folding for literals
        if isinstance(left, (IntLiteral, FloatLiteral, BoolLiteral)) and \
           isinstance(right, (IntLiteral, FloatLiteral, BoolLiteral)):
            folded = self._fold_literals(left, right, node.op, node.pos)
            if folded is not None:
                self._changed = True
                return folded

        return BinaryOp(op=node.op, left=left, right=right,
                        inferred_type=node.inferred_type, pos=node.pos)

    def _fold_literals(
        self,
        left: Any, right: Any, op: str, pos: SourcePos
    ) -> Optional[Any]:
        def val(n: Any) -> int | float | bool:
            if isinstance(n, IntLiteral):
                return n.value
            if isinstance(n, FloatLiteral):
                return n.value
            if isinstance(n, BoolLiteral):
                return n.value
            return 0

        lv = val(left)
        rv = val(right)

        if isinstance(lv, bool) and isinstance(rv, bool):
            if op == '&&':
                return BoolLiteral(value=bool(lv and rv), pos=pos)
            if op == '||':
                return BoolLiteral(value=bool(lv or rv), pos=pos)
            if op == '==':
                return BoolLiteral(value=lv == rv, pos=pos)
            if op == '!=':
                return BoolLiteral(value=lv != rv, pos=pos)
            return None

        is_float = isinstance(lv, float) or isinstance(rv, float)
        lnum = float(lv) if not isinstance(lv, bool) else int(lv)
        rnum = float(rv) if not isinstance(rv, bool) else int(rv)

        try:
            if op == '+':
                result_n: float | int = float(lnum) + float(rnum) if is_float else int(lnum) + int(rnum)
            elif op == '-':
                result_n = float(lnum) - float(rnum) if is_float else int(lnum) - int(rnum)
            elif op == '*':
                result_n = float(lnum) * float(rnum) if is_float else int(lnum) * int(rnum)
            elif op == '/':
                if rnum == 0:
                    return None
                result_n = float(lnum) / float(rnum) if is_float else int(int(lnum) / int(rnum))
            elif op == '%':
                if rnum == 0:
                    return None
                result_n = int(lnum) % int(rnum)
            elif op == '==':
                return BoolLiteral(value=lnum == rnum, pos=pos)
            elif op == '!=':
                return BoolLiteral(value=lnum != rnum, pos=pos)
            elif op == '<':
                return BoolLiteral(value=lnum < rnum, pos=pos)
            elif op == '>':
                return BoolLiteral(value=lnum > rnum, pos=pos)
            elif op == '<=':
                return BoolLiteral(value=lnum <= rnum, pos=pos)
            elif op == '>=':
                return BoolLiteral(value=lnum >= rnum, pos=pos)
            else:
                return None
        except (ZeroDivisionError, OverflowError):
            return None

        if is_float:
            f = float(result_n)
            if math.isnan(f) or math.isinf(f):
                return None
            return FloatLiteral(value=f, pos=pos)
        else:
            i = int(result_n)
            if i < INT64_MIN or i > INT64_MAX:
                return None
            return IntLiteral(value=i, pos=pos)

    def _fold_unary(self, node: UnaryOp) -> Any:
        operand = self._fold_expr(node.operand)

        # Level 2: algebraic !!x → x, !true → false, !false → true
        if self._level >= 2:
            if node.op == '!' and isinstance(operand, UnaryOp) and operand.op == '!':
                self._changed = True
                return operand.operand
            if node.op == '!':
                if isinstance(operand, BoolLiteral):
                    self._changed = True
                    return BoolLiteral(value=not operand.value, pos=node.pos)

        if not is_pure_expr(operand):
            return UnaryOp(op=node.op, operand=operand, prefix=node.prefix,
                           inferred_type=node.inferred_type, pos=node.pos)

        if node.op == '-' and isinstance(operand, IntLiteral):
            result_i = -operand.value
            if INT64_MIN <= result_i <= INT64_MAX:
                self._changed = True
                return IntLiteral(value=result_i, pos=node.pos)
        if node.op == '-' and isinstance(operand, FloatLiteral):
            self._changed = True
            return FloatLiteral(value=-operand.value, pos=node.pos)
        if node.op == '!' and isinstance(operand, BoolLiteral):
            self._changed = True
            return BoolLiteral(value=not operand.value, pos=node.pos)

        return UnaryOp(op=node.op, operand=operand, prefix=node.prefix,
                       inferred_type=node.inferred_type, pos=node.pos)

    def _algebraic_simplify_bin(
        self, left: Any, right: Any, op: str, pos: SourcePos
    ) -> Optional[Any]:
        if op == '+':
            if _is_int_lit(right, 0) and is_pure_expr(left):
                return left
            if _is_int_lit(left, 0) and is_pure_expr(right):
                return right
        if op == '-':
            if _is_int_lit(right, 0) and is_pure_expr(left):
                return left
            if _is_int_lit(left, 0) and is_pure_expr(right):
                return UnaryOp(op='-', operand=right, prefix=True, pos=pos)
            # x - x → 0 only for pure Identifier of int type
            if (isinstance(left, Identifier) and isinstance(right, Identifier)
                    and left.name == right.name
                    and left.inferred_type == 'int'):
                return IntLiteral(value=0, pos=pos)
        if op == '*':
            if _is_int_lit(right, 1) and is_pure_expr(left):
                return left
            if _is_int_lit(left, 1) and is_pure_expr(right):
                return right
            if _is_int_lit(right, 0) and is_pure_expr(left):
                return IntLiteral(value=0, pos=pos)
            if _is_int_lit(left, 0) and is_pure_expr(right):
                return IntLiteral(value=0, pos=pos)
        if op == '/':
            if _is_int_lit(right, 1) and is_pure_expr(left):
                return left
        if op == '||':
            if _is_bool_lit(left, True):
                return BoolLiteral(value=True, pos=pos)
            if _is_bool_lit(right, True):
                return BoolLiteral(value=True, pos=pos)
            if _is_bool_lit(left, False) and is_pure_expr(right):
                return right
            if _is_bool_lit(right, False) and is_pure_expr(left):
                return left
        if op == '&&':
            if _is_bool_lit(left, False):
                return BoolLiteral(value=False, pos=pos)
            if _is_bool_lit(right, False):
                return BoolLiteral(value=False, pos=pos)
            if _is_bool_lit(left, True) and is_pure_expr(right):
                return right
            if _is_bool_lit(right, True) and is_pure_expr(left):
                return left
        return None

    def _strength_reduce_bin(
        self, left: Any, right: Any, op: str, pos: SourcePos
    ) -> Optional[Any]:
        if op == '*' and isinstance(right, IntLiteral) and right.value in STRENGTH_MUL:
            shift = STRENGTH_MUL[right.value]
            return BinaryOp(op='<<', left=left, right=IntLiteral(value=shift, pos=pos),
                            pos=pos)
        if op == '*' and isinstance(left, IntLiteral) and left.value in STRENGTH_MUL:
            shift = STRENGTH_MUL[left.value]
            return BinaryOp(op='<<', left=right, right=IntLiteral(value=shift, pos=pos),
                            pos=pos)
        return None

    # ── Pass: Constant Propagation (level 1) ────────────────────────────────────

    def _propagate_constants(self, program: Program) -> Program:
        decls = []
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                env: dict[str, Any] = {}
                new_stmts = self._propagate_in_block(list(decl.body.stmts), env)
                body = Block(stmts=new_stmts, pos=decl.body.pos)
                decl = FunctionDecl(
                    name=decl.name,
                    return_type=decl.return_type,
                    params=decl.params,
                    body=body,
                    pos=decl.pos,
                )
            decls.append(decl)
        return Program(declarations=decls, pos=program.pos)

    def _propagate_in_block(
        self, stmts: list[Any], env: dict[str, Any]
    ) -> list[Any]:
        """
        Conservative propagation: substitute Identifier refs when variable is
        declared with a literal init and never mutated in the scope.
        """
        result: list[Any] = []
        for stmt in stmts:
            if isinstance(stmt, VarDecl):
                init = self._subst_expr(stmt.init_expr, env) if stmt.init_expr is not None else None
                # Only add to env if init is a literal and var never mutated
                if isinstance(init, (IntLiteral, FloatLiteral, BoolLiteral)):
                    mutated: set[str] = set()
                    for s in stmts:
                        _collect_assigns(s, mutated)
                    if stmt.name not in mutated:
                        env[stmt.name] = init
                result.append(VarDecl(name=stmt.name, type=stmt.type, init_expr=init, pos=stmt.pos))
            elif isinstance(stmt, (IfStmt, WhileStmt, ForStmt, DoWhileStmt)):
                # Snapshot env; remove anything assigned inside the control stmt
                snapshot = dict(env)
                mutated2: set[str] = set()
                _collect_assigns(stmt, mutated2)
                for n in mutated2:
                    snapshot.pop(n, None)
                result.append(self._subst_stmt(stmt, snapshot))
            else:
                result.append(self._subst_stmt(stmt, env))
        return result

    def _subst_expr(self, node: Any, env: dict[str, Any]) -> Any:
        if node is None:
            return node
        if isinstance(node, Identifier) and node.name in env:
            self._changed = True
            return env[node.name]
        if isinstance(node, BinaryOp):
            return BinaryOp(
                op=node.op,
                left=self._subst_expr(node.left, env),
                right=self._subst_expr(node.right, env),
                inferred_type=node.inferred_type,
                pos=node.pos,
            )
        if isinstance(node, UnaryOp):
            return UnaryOp(
                op=node.op,
                operand=self._subst_expr(node.operand, env),
                prefix=node.prefix,
                inferred_type=node.inferred_type,
                pos=node.pos,
            )
        if isinstance(node, AssignOp):
            return AssignOp(
                op=node.op,
                target=node.target,
                value=self._subst_expr(node.value, env),
                pos=node.pos,
            )
        if isinstance(node, CallExpr):
            return CallExpr(
                name=node.name,
                args=[self._subst_expr(a, env) for a in node.args],
                inferred_type=node.inferred_type,
                is_tail_call=node.is_tail_call,
                pos=node.pos,
            )
        if isinstance(node, CastExpr):
            return CastExpr(
                target_type=node.target_type,
                expr=self._subst_expr(node.expr, env),
                inferred_type=node.inferred_type,
                pos=node.pos,
            )
        return node

    def _subst_stmt(self, stmt: Any, env: dict[str, Any]) -> Any:
        if isinstance(stmt, ReturnStmt):
            return ReturnStmt(
                value=self._subst_expr(stmt.value, env) if stmt.value is not None else None,
                pos=stmt.pos,
            )
        if isinstance(stmt, PrintStmt):
            return PrintStmt(
                expr=self._subst_expr(stmt.expr, env),
                newline=stmt.newline,
                pos=stmt.pos,
            )
        if isinstance(stmt, ExprStmt):
            return ExprStmt(expr=self._subst_expr(stmt.expr, env), pos=stmt.pos)
        if isinstance(stmt, VarDecl):
            return VarDecl(
                name=stmt.name,
                type=stmt.type,
                init_expr=self._subst_expr(stmt.init_expr, env) if stmt.init_expr is not None else None,
                pos=stmt.pos,
            )
        if isinstance(stmt, Block):
            return Block(
                stmts=self._propagate_in_block(list(stmt.stmts), dict(env)),
                pos=stmt.pos,
            )
        return stmt

    # ── Pass: LICM (level 2) ────────────────────────────────────────────────────

    def _licm(self, program: Program) -> Program:
        decls = []
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                body = self._licm_block(decl.body)
                decl = FunctionDecl(
                    name=decl.name,
                    return_type=decl.return_type,
                    params=decl.params,
                    body=body,
                    pos=decl.pos,
                )
            decls.append(decl)
        return Program(declarations=decls, pos=program.pos)

    def _licm_block(self, block: Block) -> Block:
        new_stmts: list[Any] = []
        for stmt in block.stmts:
            hoisted, new_stmt = self._licm_stmt(stmt)
            new_stmts.extend(hoisted)
            new_stmts.append(new_stmt)
        return Block(stmts=new_stmts, pos=block.pos)

    def _licm_stmt(self, stmt: Any) -> tuple[list[Any], Any]:
        if isinstance(stmt, WhileStmt):
            return self._licm_loop_body(stmt.condition, stmt.body, stmt)
        if isinstance(stmt, ForStmt):
            _, new_body = self._licm_stmt(stmt.body) if isinstance(stmt.body, Block) else ([], stmt.body)
            return [], ForStmt(
                init=stmt.init, condition=stmt.condition, update=stmt.update,
                body=new_body if isinstance(stmt.body, Block) else stmt.body,
                pos=stmt.pos,
            )
        if isinstance(stmt, Block):
            return [], self._licm_block(stmt)
        return [], stmt

    def _licm_loop_body(
        self, cond: Any, body: Block, original: Any
    ) -> tuple[list[Any], Any]:
        modified: set[str] = set()
        _collect_assigns(body, modified)

        hoisted: list[Any] = []

        def hoist_expr(expr: Any) -> Any:
            if not is_pure_expr(expr):
                return expr
            if isinstance(expr, (IntLiteral, FloatLiteral, BoolLiteral,
                                 StringLiteral, CharLiteral)):
                return expr
            if isinstance(expr, Identifier) and expr.name not in modified:
                return expr
            if isinstance(expr, BinaryOp):
                new_left = hoist_expr(expr.left)
                new_right = hoist_expr(expr.right)
                # If all operands are invariant and expr is complex, hoist it
                if (new_left is expr.left and new_right is expr.right
                        and _is_loop_invariant(expr, modified)):
                    tmp_name = f'_licm_{self._licm_counter}'
                    self._licm_counter += 1
                    hoisted.append(VarDecl(
                        name=tmp_name,
                        type=expr.inferred_type if expr.inferred_type != 'unknown' else 'int',
                        init_expr=expr,
                        pos=expr.pos,
                    ))
                    self._changed = True
                    return Identifier(name=tmp_name, inferred_type=expr.inferred_type, pos=expr.pos)
                return BinaryOp(op=expr.op, left=new_left, right=new_right,
                                inferred_type=expr.inferred_type, pos=expr.pos)
            return expr

        # Only hoist from body statements that are expression statements
        new_body_stmts: list[Any] = []
        for s in body.stmts:
            new_body_stmts.append(s)
        new_body = Block(stmts=new_body_stmts, pos=body.pos)

        if isinstance(original, WhileStmt):
            return hoisted, WhileStmt(condition=cond, body=new_body, pos=original.pos)
        return hoisted, original

    # ── Pass: CSE (level 2) ─────────────────────────────────────────────────────

    def _cse(self, program: Program) -> Program:
        decls = []
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                body = self._cse_block(decl.body)
                decl = FunctionDecl(
                    name=decl.name,
                    return_type=decl.return_type,
                    params=decl.params,
                    body=body,
                    pos=decl.pos,
                )
            decls.append(decl)
        return Program(declarations=decls, pos=program.pos)

    def _cse_block(self, block: Block) -> Block:
        counts: dict[str, int] = {}
        for stmt in block.stmts:
            self._count_exprs_in(stmt, counts)
        eligible = {h for h, c in counts.items() if c >= 2}
        if not eligible:
            return block
        cache: dict[str, str] = {}
        prefix: list[Any] = []
        new_stmts: list[Any] = []
        for stmt in block.stmts:
            new_stmts.append(self._cse_stmt(stmt, cache, prefix, eligible))
        return Block(stmts=prefix + new_stmts, pos=block.pos)

    def _count_exprs_in(self, node: Any, counts: dict[str, int]) -> None:
        if isinstance(node, (BinaryOp, UnaryOp)) and is_pure_expr(node):
            h = _expr_canonical_hash(node)
            counts[h] = counts.get(h, 0) + 1
        for child in self._iter_expr_children(node):
            self._count_exprs_in(child, counts)

    def _iter_expr_children(self, node: Any):  # type: ignore[return]
        if isinstance(node, BinaryOp):
            yield node.left; yield node.right
        elif isinstance(node, UnaryOp):
            yield node.operand
        elif isinstance(node, AssignOp):
            yield node.value
        elif isinstance(node, ReturnStmt):
            if node.value is not None:
                yield node.value
        elif isinstance(node, PrintStmt):
            yield node.expr
        elif isinstance(node, ExprStmt):
            yield node.expr
        elif isinstance(node, VarDecl):
            if node.init_expr is not None:
                yield node.init_expr
        elif isinstance(node, Block):
            yield from node.stmts

    def _cse_stmt(
        self, stmt: Any, cache: dict[str, str], prefix: list[Any],
        eligible: set[str],
    ) -> Any:
        if isinstance(stmt, VarDecl) and stmt.init_expr is not None:
            new_init = self._cse_expr(stmt.init_expr, cache, prefix, eligible)
            return VarDecl(name=stmt.name, type=stmt.type, init_expr=new_init, pos=stmt.pos)
        if isinstance(stmt, ReturnStmt) and stmt.value is not None:
            return ReturnStmt(value=self._cse_expr(stmt.value, cache, prefix, eligible), pos=stmt.pos)
        if isinstance(stmt, PrintStmt):
            return PrintStmt(
                expr=self._cse_expr(stmt.expr, cache, prefix, eligible),
                newline=stmt.newline, pos=stmt.pos,
            )
        if isinstance(stmt, ExprStmt):
            return ExprStmt(expr=self._cse_expr(stmt.expr, cache, prefix, eligible), pos=stmt.pos)
        if isinstance(stmt, Block):
            return self._cse_block(stmt)
        return stmt

    def _cse_expr(
        self, node: Any, cache: dict[str, str], prefix: list[Any],
        eligible: set[str],
    ) -> Any:
        if not is_pure_expr(node):
            return node
        if isinstance(node, (IntLiteral, FloatLiteral, BoolLiteral,
                             StringLiteral, CharLiteral, Identifier)):
            return node
        h = _expr_canonical_hash(node)
        if h in cache:
            self._changed = True
            return Identifier(name=cache[h],
                              inferred_type=getattr(node, 'inferred_type', 'unknown'),
                              pos=node.pos)
        if isinstance(node, BinaryOp):
            new_left = self._cse_expr(node.left, cache, prefix, eligible)
            new_right = self._cse_expr(node.right, cache, prefix, eligible)
            new_node = BinaryOp(op=node.op, left=new_left, right=new_right,
                                inferred_type=node.inferred_type, pos=node.pos)
            new_h = _expr_canonical_hash(new_node)
            if new_h in eligible:
                if new_h in cache:
                    self._changed = True
                    return Identifier(name=cache[new_h],
                                      inferred_type=node.inferred_type, pos=node.pos)
                tmp_name = f'_cse_{self._cse_counter}'
                self._cse_counter += 1
                t = node.inferred_type if node.inferred_type != 'unknown' else 'int'
                prefix.append(VarDecl(name=tmp_name, type=t, init_expr=new_node, pos=node.pos))
                cache[new_h] = tmp_name
                self._changed = True
                return Identifier(name=tmp_name, inferred_type=node.inferred_type, pos=node.pos)
            return new_node
        if isinstance(node, UnaryOp):
            new_op = self._cse_expr(node.operand, cache, prefix, eligible)
            return UnaryOp(op=node.op, operand=new_op, prefix=node.prefix,
                           inferred_type=node.inferred_type, pos=node.pos)
        return node

    # ── Pass: Function Inlining (level 3) ───────────────────────────────────────

    def _inline_functions(self, program: Program) -> Program:
        inlineable: dict[str, FunctionDecl] = {}
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl) and self._is_inlineable(decl, program):
                inlineable[decl.name] = decl

        if not inlineable:
            return program

        decls = []
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                body = self._inline_in_block(decl.body, inlineable, decl.name)
                decl = FunctionDecl(
                    name=decl.name,
                    return_type=decl.return_type,
                    params=decl.params,
                    body=body,
                    pos=decl.pos,
                )
            decls.append(decl)
        return Program(declarations=decls, pos=program.pos)

    def _is_inlineable(self, fn: FunctionDecl, program: Program) -> bool:
        stmts = fn.body.stmts
        if len(stmts) != 1:
            return False
        if not isinstance(stmts[0], ReturnStmt):
            return False
        expr = stmts[0].value
        if expr is None:
            return False
        if not is_pure_expr(expr):
            return False
        if _count_nodes(expr) > 5:
            return False
        # Not recursive
        called: set[str] = set()
        self._collect_calls(expr, called)
        if fn.name in called:
            return False
        return True

    def _collect_calls(self, node: Any, names: set[str]) -> None:
        if isinstance(node, CallExpr):
            names.add(node.name)
            for a in node.args:
                self._collect_calls(a, names)
        elif isinstance(node, BinaryOp):
            self._collect_calls(node.left, names)
            self._collect_calls(node.right, names)
        elif isinstance(node, UnaryOp):
            self._collect_calls(node.operand, names)

    def _inline_in_block(
        self, block: Block, inlineable: dict[str, FunctionDecl], caller: str
    ) -> Block:
        new_stmts: list[Any] = []
        for stmt in block.stmts:
            new_stmts.append(self._inline_stmt(stmt, inlineable, caller))
        return Block(stmts=new_stmts, pos=block.pos)

    def _inline_stmt(
        self, stmt: Any, inlineable: dict[str, FunctionDecl], caller: str
    ) -> Any:
        if isinstance(stmt, ReturnStmt) and stmt.value is not None:
            return ReturnStmt(
                value=self._inline_expr(stmt.value, inlineable, caller),
                pos=stmt.pos,
            )
        if isinstance(stmt, PrintStmt):
            return PrintStmt(
                expr=self._inline_expr(stmt.expr, inlineable, caller),
                newline=stmt.newline,
                pos=stmt.pos,
            )
        if isinstance(stmt, ExprStmt):
            return ExprStmt(
                expr=self._inline_expr(stmt.expr, inlineable, caller),
                pos=stmt.pos,
            )
        if isinstance(stmt, VarDecl) and stmt.init_expr is not None:
            return VarDecl(
                name=stmt.name,
                type=stmt.type,
                init_expr=self._inline_expr(stmt.init_expr, inlineable, caller),
                pos=stmt.pos,
            )
        if isinstance(stmt, Block):
            return self._inline_in_block(stmt, inlineable, caller)
        return stmt

    def _inline_expr(
        self, node: Any, inlineable: dict[str, FunctionDecl], caller: str
    ) -> Any:
        if isinstance(node, CallExpr) and node.name in inlineable and node.name != caller:
            fn = inlineable[node.name]
            ret_expr = fn.body.stmts[0].value  # type: ignore[union-attr]
            # Build substitution map: param_name → arg_expr
            subst: dict[str, Any] = {}
            for param, arg in zip(fn.params, node.args):
                subst[param.name] = self._inline_expr(arg, inlineable, caller)
            self._changed = True
            return self._rename_and_subst(ret_expr, fn.name, subst)
        if isinstance(node, BinaryOp):
            return BinaryOp(
                op=node.op,
                left=self._inline_expr(node.left, inlineable, caller),
                right=self._inline_expr(node.right, inlineable, caller),
                inferred_type=node.inferred_type, pos=node.pos,
            )
        if isinstance(node, UnaryOp):
            return UnaryOp(
                op=node.op,
                operand=self._inline_expr(node.operand, inlineable, caller),
                prefix=node.prefix,
                inferred_type=node.inferred_type, pos=node.pos,
            )
        return node

    def _rename_and_subst(
        self, expr: Any, fn_name: str, subst: dict[str, Any]
    ) -> Any:
        if isinstance(expr, Identifier):
            if expr.name in subst:
                return subst[expr.name]
            return Identifier(
                name=f'_inline_{fn_name}_{expr.name}',
                inferred_type=expr.inferred_type,
                pos=expr.pos,
            )
        if isinstance(expr, BinaryOp):
            return BinaryOp(
                op=expr.op,
                left=self._rename_and_subst(expr.left, fn_name, subst),
                right=self._rename_and_subst(expr.right, fn_name, subst),
                inferred_type=expr.inferred_type, pos=expr.pos,
            )
        if isinstance(expr, UnaryOp):
            return UnaryOp(
                op=expr.op,
                operand=self._rename_and_subst(expr.operand, fn_name, subst),
                prefix=expr.prefix,
                inferred_type=expr.inferred_type, pos=expr.pos,
            )
        return expr

    def _mark_tco_in_block(self, fn_name: str, block: Block) -> Block:
        stmts = list(block.stmts)
        for i, s in enumerate(stmts):
            if isinstance(s, ReturnStmt) and isinstance(s.value, CallExpr):
                if s.value.name == fn_name:
                    new_call = CallExpr(
                        name=s.value.name,
                        args=s.value.args,
                        inferred_type=s.value.inferred_type,
                        is_tail_call=True,
                        pos=s.value.pos,
                    )
                    stmts[i] = ReturnStmt(value=new_call, pos=s.pos)
                    self._changed = True
            elif isinstance(s, Block):
                stmts[i] = self._mark_tco_in_block(fn_name, s)
            elif isinstance(s, IfStmt):
                stmts[i] = IfStmt(
                    condition=s.condition,
                    then_body=self._mark_tco_in_block(fn_name, s.then_body),
                    elif_clauses=[(c, self._mark_tco_in_block(fn_name, b))
                                  for c, b in s.elif_clauses],
                    else_body=self._mark_tco_in_block(fn_name, s.else_body)
                    if s.else_body else None,
                    pos=s.pos,
                )
        return Block(stmts=stmts, pos=block.pos)


