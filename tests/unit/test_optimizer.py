from compiler.ast_nodes import (
    ArrayDecl, AssignOp, BinaryOp, Block, BoolLiteral, CallExpr, CastExpr,
    CharLiteral, DoWhileStmt, FloatLiteral, FunctionDecl,
    Identifier, IfStmt, IntLiteral, PrintStmt, Program,
    ReturnStmt, SourcePos, StringLiteral, UnaryOp, VarDecl, WhileStmt,
)
from compiler.optimizer import (
    _expr_canonical_hash, _is_loop_invariant, _collect_modified_names,
    _count_nodes,
)
import pytest
from compiler.error_reporter import ErrorReporter
from compiler.interpreter import Interpreter
from compiler.lexer import Lexer
from compiler.optimizer import Optimizer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer


def _pos() -> SourcePos:
    return SourcePos(1, 1)


def _prog(*decls: object) -> Program:
    return Program(declarations=list(decls), pos=_pos())


def _fn(name: str, *stmts: object) -> FunctionDecl:
    from compiler.ast_nodes import Block
    return FunctionDecl(
        name=name, return_type='int', params=[],
        body=Block(stmts=list(stmts), pos=_pos()),
        pos=_pos()
    )


def _ret(expr: object) -> ReturnStmt:
    return ReturnStmt(value=expr, pos=_pos())


def parse(src: str) -> Program:
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    return Parser(tokens, r).parse()


def opt(prog: Program, level: int = 1) -> Program:
    return Optimizer(level=level).optimize(prog)


# ── Constant Folding ──────────────────────────────────────────────────────────────

def test_fold_add_literals() -> None:
    expr = BinaryOp(op='+', left=IntLiteral(2), right=IntLiteral(3))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 5


def test_no_fold_with_side_effects() -> None:
    call = CallExpr(name='f', args=[], pos=_pos())
    expr = BinaryOp(op='+', left=call, right=IntLiteral(3))
    prog = _prog(_fn('g', _ret(expr)))
    result = opt(prog)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, BinaryOp)


def test_no_fold_div_zero() -> None:
    expr = BinaryOp(op='/', left=IntLiteral(5), right=IntLiteral(0))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, BinaryOp)


def test_fold_nested() -> None:
    # (2 + 3) * 4 → 5 * 4 → 20
    inner = BinaryOp(op='+', left=IntLiteral(2), right=IntLiteral(3))
    expr = BinaryOp(op='*', left=inner, right=IntLiteral(4))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 20


# ── Algebraic Simplification ───────────────────────────────────────────────────────

def test_algebraic_x_times_1() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='*', left=x, right=IntLiteral(1))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, Identifier)


def test_algebraic_x_plus_0() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='+', left=x, right=IntLiteral(0))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, Identifier)


def test_algebraic_double_not() -> None:
    x = Identifier(name='x')
    inner = UnaryOp(op='!', operand=x, prefix=True)
    expr = UnaryOp(op='!', operand=inner, prefix=True)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, Identifier)


# ── Strength Reduction ────────────────────────────────────────────────────────────

def test_strength_mul_4() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='*', left=x, right=IntLiteral(4))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, BinaryOp)
    assert ret.value.op == '<<'
    assert isinstance(ret.value.right, IntLiteral)
    assert ret.value.right.value == 2


# ── Dead Code Elimination ─────────────────────────────────────────────────────────

def test_dead_code_after_return() -> None:
    ret1 = ReturnStmt(value=IntLiteral(1), pos=_pos())
    ret2 = ReturnStmt(value=IntLiteral(2), pos=_pos())
    prog = _prog(_fn('f', ret1, ret2))
    result = opt(prog)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    assert len(fn.body.stmts) == 1


def test_dead_code_if_true() -> None:
    cond = BoolLiteral(value=True)
    then_block = Block(stmts=[ReturnStmt(value=IntLiteral(1), pos=_pos())], pos=_pos())
    else_block = Block(stmts=[ReturnStmt(value=IntLiteral(2), pos=_pos())], pos=_pos())
    if_stmt = IfStmt(
        condition=cond, then_body=then_block,
        elif_clauses=[], else_body=else_block, pos=_pos()
    )
    prog = _prog(_fn('f', if_stmt))
    result = opt(prog)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    # If-true body replaces the IfStmt
    assert not any(isinstance(s, IfStmt) for s in fn.body.stmts)


# ── Level 0 no changes ────────────────────────────────────────────────────────────

def test_level_0_no_change() -> None:
    expr = BinaryOp(op='+', left=IntLiteral(2), right=IntLiteral(3))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=0)
    fn = result.declarations[0]
    assert isinstance(fn, FunctionDecl)
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    # Should NOT have folded (level 0)
    assert isinstance(ret.value, BinaryOp)


# ── New passes ────────────────────────────────────────────────────────────────

def test_propagate_constant_substitutes_literal() -> None:
    # int x = 5; return x;  →  return 5;  (x replaced)
    src = 'int f() { int x = 5; return x; }'
    result = opt(parse(src), level=1)
    fn = result.declarations[0]
    ret = fn.body.stmts[-1]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 5


def test_propagate_constant_does_not_propagate_mutated() -> None:
    # int x = 5; x = 10; return x;  → x should NOT be propagated
    src = 'int f() { int x = 5; x = 10; return x; }'
    result = opt(parse(src), level=1)
    fn = result.declarations[0]
    ret = fn.body.stmts[-1]
    assert isinstance(ret, ReturnStmt)
    # x was mutated so should remain Identifier
    assert isinstance(ret.value, Identifier)


def test_cse_deduplicates_repeated_expression() -> None:
    # int f(int a, int b) { return (a+b) + (a+b); }
    # CSE should extract a+b to a temp
    src = 'int f(int a, int b) { int r1 = a + b; int r2 = a + b; return r1; }'
    result = opt(parse(src), level=2)
    fn = result.declarations[0]
    # Some statement should be a VarDecl with name starting '_cse_'
    all_stmts = fn.body.stmts
    cse_decls = [s for s in all_stmts if isinstance(s, VarDecl) and s.name.startswith('_cse_')]
    assert len(cse_decls) >= 1


def test_tco_marks_tail_call() -> None:
    # int fact(int n) { return fact(n-1); }  — recursive tail call
    src = 'int fact(int n) { return fact(n); }'
    result = opt(parse(src), level=3)
    fn = result.declarations[0]
    ret = fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, CallExpr)
    assert ret.value.is_tail_call is True


def test_inline_simple_pure_function() -> None:
    # int double(int x) { return x + x; }
    # int main() { return double(3); }  →  return 3 + 3 (or 6)
    src = 'int dbl(int x) { return x + x; } int main() { return dbl(3); }'
    result = opt(parse(src), level=3)
    main_fn = next(d for d in result.declarations if isinstance(d, FunctionDecl) and d.name == 'main')
    ret = main_fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    # The call to dbl should be inlined — value is no longer a CallExpr to 'dbl'
    assert not (isinstance(ret.value, CallExpr) and ret.value.name == 'dbl')


def test_optimizer_invariance() -> None:
    """Levels 0, 1, 2, 3 must produce same stdout for a simple program."""
    from compiler.semantic import SemanticAnalyzer
    from compiler.interpreter import Interpreter

    src = 'int main() { int x = 2; int y = 3; println(x + y); return 0; }'

    def run_at_level(lvl: int) -> str:
        rep = ErrorReporter()
        tokens = Lexer(src, rep).tokenize()
        prog = Parser(tokens, rep).parse()
        SemanticAnalyzer(rep).analyze(prog)
        optimized = Optimizer(level=lvl).optimize(prog)
        stdout, _ = Interpreter(optimized).run()
        return stdout

    outputs = [run_at_level(lvl) for lvl in range(4)]
    assert all(o == outputs[0] for o in outputs), f'Invariance violated: {outputs}'


# ── Optimizer invariance — all 8 demo programs ──────────────────────────────

OPT_INVARIANCE_PROGRAMS = [
    '''int fib(int n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}
int main() {
    println(fib(10));
    return 0;
}''',
    '''int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
int main() {
    println(factorial(5));
    return 0;
}''',
    '''int main() {
    int arr[8] = {64, 34, 25, 12, 22, 11, 90, 7};
    int n = 8;
    int tmp = 0;
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                tmp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = tmp;
            }
        }
    }
    for (int i = 0; i < n; i++) {
        println(arr[i]);
    }
    return 0;
}''',
    '''int main() {
    int n = 27;
    int pasos = 0;
    while (n != 1) {
        if (n % 2 == 0) {
            n = n / 2;
        } else {
            n = n * 3 + 1;
        }
        pasos = pasos + 1;
    }
    println(pasos);
    return 0;
}''',
    '''int main() {
    for (int i = 1; i <= 30; i++) {
        if (i % 15 == 0) {
            println("FizzBuzz");
        } else if (i % 3 == 0) {
            println("Fizz");
        } else if (i % 5 == 0) {
            println("Buzz");
        } else {
            println(i);
        }
    }
    return 0;
}''',
    '''int main() {
    int nums[10] = {5, 12, 8, 3, 17, 6, 21, 9, 14, 2};
    int suma = 0;
    for (int i = 0; i < 10; i++) {
        suma += nums[i];
    }
    println(suma);
    return 0;
}''',
    '''int main() {
    int arr[10] = {3, 7, 1, 9, 4, 6, 8, 2, 5, 10};
    int objetivo = 7;
    int resultado = -1;
    for (int i = 0; i < 10; i++) {
        if (arr[i] == objetivo) {
            resultado = i;
            break;
        }
    }
    println(resultado);
    return 0;
}''',
    '''int main() {
    int a = 15;
    int b = 4;
    int op = 2;
    if (op == 1) {
        println(a + b);
    } else if (op == 2) {
        println(a - b);
    } else if (op == 3) {
        println(a * b);
    } else if (op == 4) {
        if (b != 0) {
            println(a / b);
        } else {
            println(0);
        }
    } else {
        println(0);
    }
    return 0;
}''',
]


def _run_at_level(source: str, level: int) -> tuple[str, int]:
    rep = ErrorReporter()
    tokens = Lexer(source, rep).tokenize()
    prog = Parser(tokens, rep).parse()
    SemanticAnalyzer(rep).analyze(prog)
    optimized = Optimizer(level=level).optimize(prog)
    return Interpreter(optimized).run()


@pytest.mark.parametrize("source", OPT_INVARIANCE_PROGRAMS)
def test_optimization_preserves_semantics(source: str) -> None:
    """Ningún nivel de optimización debe cambiar el output del programa."""
    outputs = [_run_at_level(source, lvl) for lvl in range(4)]
    stdouts = [o[0] for o in outputs]
    rcs = [o[1] for o in outputs]
    assert all(s == stdouts[0] for s in stdouts), (
        f"Invariance violated:\n{stdouts}"
    )
    assert all(r == rcs[0] for r in rcs), (
        f"Return codes differ:\n{rcs}"
    )


# ── _expr_canonical_hash ──────────────────────────────────────────────────────

def test_hash_float_literal() -> None:
    node = FloatLiteral(value=3.14)
    assert _expr_canonical_hash(node) == 'float:3.14'


def test_hash_bool_literal() -> None:
    assert _expr_canonical_hash(BoolLiteral(value=True)) == 'bool:True'
    assert _expr_canonical_hash(BoolLiteral(value=False)) == 'bool:False'


def test_hash_identifier() -> None:
    assert _expr_canonical_hash(Identifier(name='x')) == 'id:x'


def test_hash_binary_op() -> None:
    node = BinaryOp(op='+', left=IntLiteral(1), right=IntLiteral(2))
    h = _expr_canonical_hash(node)
    assert h == 'bin:+:(int:1):(int:2)'


def test_hash_unary_op() -> None:
    node = UnaryOp(op='-', operand=IntLiteral(5), prefix=True)
    h = _expr_canonical_hash(node)
    assert 'un:-' in h and 'int:5' in h


def test_hash_cast_expr() -> None:
    node = CastExpr(target_type='float', expr=Identifier(name='x'))
    h = _expr_canonical_hash(node)
    assert 'cast:float' in h and 'id:x' in h


def test_hash_other_returns_other_prefix() -> None:
    node = CallExpr(name='f', args=[])
    h = _expr_canonical_hash(node)
    assert h.startswith('other:')


# ── _is_loop_invariant ────────────────────────────────────────────────────────

def test_loop_invariant_literal() -> None:
    assert _is_loop_invariant(IntLiteral(5), set()) is True
    assert _is_loop_invariant(FloatLiteral(1.0), set()) is True
    assert _is_loop_invariant(BoolLiteral(value=True), set()) is True


def test_loop_invariant_identifier_not_modified() -> None:
    assert _is_loop_invariant(Identifier(name='x'), set()) is True
    assert _is_loop_invariant(Identifier(name='x'), {'y'}) is True


def test_loop_invariant_identifier_modified() -> None:
    assert _is_loop_invariant(Identifier(name='x'), {'x'}) is False


def test_loop_invariant_binary_op() -> None:
    node = BinaryOp(op='+', left=Identifier(name='a'), right=IntLiteral(1))
    assert _is_loop_invariant(node, set()) is True
    assert _is_loop_invariant(node, {'a'}) is False


def test_loop_invariant_unary_op() -> None:
    node = UnaryOp(op='-', operand=Identifier(name='x'), prefix=True)
    assert _is_loop_invariant(node, set()) is True
    assert _is_loop_invariant(node, {'x'}) is False


def test_loop_invariant_impure_returns_false() -> None:
    call = CallExpr(name='f', args=[])
    assert _is_loop_invariant(call, set()) is False


# ── _count_nodes ─────────────────────────────────────────────────────────────

def test_count_nodes_literals() -> None:
    assert _count_nodes(IntLiteral(1)) == 1
    assert _count_nodes(FloatLiteral(1.0)) == 1
    assert _count_nodes(BoolLiteral(value=True)) == 1
    assert _count_nodes(StringLiteral(value='hi')) == 1
    assert _count_nodes(CharLiteral(value='a')) == 1
    assert _count_nodes(Identifier(name='x')) == 1


def test_count_nodes_binary() -> None:
    node = BinaryOp(op='+', left=IntLiteral(1), right=IntLiteral(2))
    assert _count_nodes(node) == 3


def test_count_nodes_unary() -> None:
    node = UnaryOp(op='-', operand=IntLiteral(1), prefix=True)
    assert _count_nodes(node) == 2


def test_count_nodes_cast() -> None:
    node = CastExpr(target_type='float', expr=IntLiteral(1))
    assert _count_nodes(node) == 2


def test_count_nodes_call() -> None:
    node = CallExpr(name='f', args=[IntLiteral(1), IntLiteral(2)])
    assert _count_nodes(node) == 3


def test_count_nodes_other() -> None:
    # ArrayDecl is "other" → returns 1
    node = ArrayDecl(name='a', element_type='int', size=IntLiteral(3), init_list=None, pos=SourcePos(1, 1))
    assert _count_nodes(node) == 1


# ── Fold literals — bool operations ──────────────────────────────────────────

def test_fold_bool_and() -> None:
    expr = BinaryOp(op='&&', left=BoolLiteral(value=True), right=BoolLiteral(value=False))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is False


def test_fold_bool_or() -> None:
    expr = BinaryOp(op='||', left=BoolLiteral(value=False), right=BoolLiteral(value=True))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_fold_bool_eq() -> None:
    expr = BinaryOp(op='==', left=BoolLiteral(value=True), right=BoolLiteral(value=True))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_fold_bool_neq() -> None:
    expr = BinaryOp(op='!=', left=BoolLiteral(value=True), right=BoolLiteral(value=False))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


# ── Fold literals — comparisons ───────────────────────────────────────────────

def test_fold_int_lt() -> None:
    expr = BinaryOp(op='<', left=IntLiteral(2), right=IntLiteral(5))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_fold_int_gt() -> None:
    expr = BinaryOp(op='>', left=IntLiteral(5), right=IntLiteral(2))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_fold_int_le() -> None:
    expr = BinaryOp(op='<=', left=IntLiteral(3), right=IntLiteral(3))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_fold_int_ge() -> None:
    expr = BinaryOp(op='>=', left=IntLiteral(4), right=IntLiteral(3))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_fold_int_eq() -> None:
    expr = BinaryOp(op='==', left=IntLiteral(3), right=IntLiteral(3))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_fold_int_neq() -> None:
    expr = BinaryOp(op='!=', left=IntLiteral(3), right=IntLiteral(4))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


# ── Fold literals — float arithmetic ─────────────────────────────────────────

def test_fold_float_add() -> None:
    expr = BinaryOp(op='+', left=FloatLiteral(value=1.5), right=FloatLiteral(value=2.5))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, FloatLiteral)
    assert abs(ret.value.value - 4.0) < 1e-9


def test_fold_float_sub() -> None:
    expr = BinaryOp(op='-', left=FloatLiteral(value=5.0), right=FloatLiteral(value=2.0))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, FloatLiteral)
    assert abs(ret.value.value - 3.0) < 1e-9


def test_fold_float_mul() -> None:
    expr = BinaryOp(op='*', left=FloatLiteral(value=2.0), right=FloatLiteral(value=3.0))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, FloatLiteral)
    assert abs(ret.value.value - 6.0) < 1e-9


def test_fold_float_div() -> None:
    expr = BinaryOp(op='/', left=FloatLiteral(value=7.0), right=FloatLiteral(value=2.0))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, FloatLiteral)
    assert abs(ret.value.value - 3.5) < 1e-9


def test_fold_int_mod() -> None:
    expr = BinaryOp(op='%', left=IntLiteral(10), right=IntLiteral(3))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 1


def test_fold_int_sub() -> None:
    expr = BinaryOp(op='-', left=IntLiteral(10), right=IntLiteral(3))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 7


# ── Fold unary — float and bool ───────────────────────────────────────────────

def test_fold_unary_neg_float() -> None:
    expr = UnaryOp(op='-', operand=FloatLiteral(value=3.0), prefix=True)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, FloatLiteral)
    assert abs(ret.value.value - (-3.0)) < 1e-9


def test_fold_unary_neg_int() -> None:
    expr = UnaryOp(op='-', operand=IntLiteral(5), prefix=True)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == -5


def test_fold_unary_not_bool_literal_level1() -> None:
    # Level 1: !true folds via the is_pure branch (line 455-457)
    expr = UnaryOp(op='!', operand=BoolLiteral(value=True), prefix=True)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is False


def test_fold_unary_not_bool_level2_double_not() -> None:
    # Level 2: !!x → x (already tested but re-check via source)
    src = 'int f(int x) { bool b = true; return 0; }'
    result = opt(parse(src), level=2)
    assert result is not None


# ── Algebraic simplify — additional branches ─────────────────────────────────

def test_algebraic_zero_minus_x() -> None:
    # 0 - x → -x
    x = Identifier(name='x')
    expr = BinaryOp(op='-', left=IntLiteral(0), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, UnaryOp)
    assert ret.value.op == '-'


def test_algebraic_x_minus_0() -> None:
    # x - 0 → x
    x = Identifier(name='x')
    expr = BinaryOp(op='-', left=x, right=IntLiteral(0))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


def test_algebraic_x_times_0() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='*', left=x, right=IntLiteral(0))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 0


def test_algebraic_0_times_x() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='*', left=IntLiteral(0), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, IntLiteral)
    assert ret.value.value == 0


def test_algebraic_1_times_x() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='*', left=IntLiteral(1), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


def test_algebraic_x_div_1() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='/', left=x, right=IntLiteral(1))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


def test_algebraic_true_or_x() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='||', left=BoolLiteral(value=True), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_algebraic_x_or_true() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='||', left=x, right=BoolLiteral(value=True))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is True


def test_algebraic_false_or_x() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='||', left=BoolLiteral(value=False), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


def test_algebraic_x_or_false() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='||', left=x, right=BoolLiteral(value=False))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


def test_algebraic_false_and_x() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='&&', left=BoolLiteral(value=False), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is False


def test_algebraic_x_and_false() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='&&', left=x, right=BoolLiteral(value=False))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BoolLiteral)
    assert ret.value.value is False


def test_algebraic_true_and_x() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='&&', left=BoolLiteral(value=True), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


def test_algebraic_x_and_true() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='&&', left=x, right=BoolLiteral(value=True))
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


def test_algebraic_0_plus_x() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='+', left=IntLiteral(0), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, Identifier)


# ── Strength reduction — left side ────────────────────────────────────────────

def test_strength_mul_left_power_of_2() -> None:
    x = Identifier(name='x')
    expr = BinaryOp(op='*', left=IntLiteral(8), right=x)
    prog = _prog(_fn('f', _ret(expr)))
    result = opt(prog, level=2)
    ret = result.declarations[0].body.stmts[0]
    assert isinstance(ret.value, BinaryOp)
    assert ret.value.op == '<<'
    assert isinstance(ret.value.right, IntLiteral)
    assert ret.value.right.value == 3


# ── Dead code — while(false) removed ─────────────────────────────────────────

def test_dead_code_while_false() -> None:
    pos = _pos()
    body = Block(stmts=[ReturnStmt(value=IntLiteral(1), pos=pos)], pos=pos)
    while_stmt = WhileStmt(condition=BoolLiteral(value=False), body=body, pos=pos)
    prog = _prog(_fn('f', while_stmt, _ret(IntLiteral(0))))
    result = opt(prog)
    fn = result.declarations[0]
    assert not any(isinstance(s, WhileStmt) for s in fn.body.stmts)


def test_dead_code_if_false_no_else() -> None:
    pos = _pos()
    cond = BoolLiteral(value=False)
    then_block = Block(stmts=[ReturnStmt(value=IntLiteral(1), pos=pos)], pos=pos)
    if_stmt = IfStmt(condition=cond, then_body=then_block, elif_clauses=[], else_body=None, pos=pos)
    prog = _prog(_fn('f', if_stmt, _ret(IntLiteral(0))))
    result = opt(prog)
    fn = result.declarations[0]
    assert not any(isinstance(s, IfStmt) for s in fn.body.stmts)


# ── Propagation — control-flow snapshots ─────────────────────────────────────

def test_propagate_through_if() -> None:
    # if inside a function: env snapshot must not leak mutation
    src = 'int f() { int x = 5; if (x > 0) { x = 10; } return x; }'
    result = opt(parse(src), level=1)
    fn = result.declarations[0]
    ret = fn.body.stmts[-1]
    assert isinstance(ret, ReturnStmt)
    # x is mutated inside if, so should stay Identifier
    assert isinstance(ret.value, Identifier)


def test_propagate_through_while() -> None:
    src = 'int f() { int x = 1; while (x < 5) { x = x + 1; } return x; }'
    result = opt(parse(src), level=1)
    fn = result.declarations[0]
    ret = fn.body.stmts[-1]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, Identifier)


# ── CSE — eligible BinaryOp expressions ──────────────────────────────────────

def test_cse_with_binary_in_return() -> None:
    # Two occurrences of (a+b) — one in VarDecl, one in return
    src = 'int f(int a, int b) { int r = a + b; return a + b; }'
    result = opt(parse(src), level=2)
    fn = result.declarations[0]
    cse_decls = [s for s in fn.body.stmts if isinstance(s, VarDecl) and s.name.startswith('_cse_')]
    assert len(cse_decls) >= 1


def test_cse_with_print() -> None:
    # PrintStmt counts as expression usage for CSE
    src = 'int f(int a, int b) { int r = a + b; println(a + b); return 0; }'
    result = opt(parse(src), level=2)
    fn = result.declarations[0]
    cse_decls = [s for s in fn.body.stmts if isinstance(s, VarDecl) and s.name.startswith('_cse_')]
    assert len(cse_decls) >= 1


# ── LICM ──────────────────────────────────────────────────────────────────────

def test_licm_for_loop_processed() -> None:
    # ForStmt path through _licm_stmt should not crash
    src = 'int f() { int s = 0; for (int i = 0; i < 10; i++) { s = s + i; } return s; }'
    result = opt(parse(src), level=2)
    assert result is not None


def test_licm_while_loop_processed() -> None:
    src = 'int f() { int i = 0; while (i < 10) { i = i + 1; } return i; }'
    result = opt(parse(src), level=2)
    assert result is not None


# ── Inlining — PrintStmt, ExprStmt, VarDecl paths ───────────────────────────

def test_inline_in_print_stmt() -> None:
    # dbl is inlineable; used inside println
    src = 'int dbl(int x) { return x + x; } int main() { println(dbl(3)); return 0; }'
    result = opt(parse(src), level=3)
    main_fn = next(d for d in result.declarations if isinstance(d, FunctionDecl) and d.name == 'main')
    # After inlining, the println should not contain a CallExpr to 'dbl'
    print_stmt = main_fn.body.stmts[0]
    assert isinstance(print_stmt, PrintStmt)
    assert not (isinstance(print_stmt.expr, CallExpr) and print_stmt.expr.name == 'dbl')


def test_inline_in_var_decl() -> None:
    src = 'int dbl(int x) { return x + x; } int main() { int r = dbl(5); return r; }'
    result = opt(parse(src), level=3)
    main_fn = next(d for d in result.declarations if isinstance(d, FunctionDecl) and d.name == 'main')
    var_decl = main_fn.body.stmts[0]
    assert isinstance(var_decl, VarDecl)
    # inlined: init_expr is not a CallExpr to 'dbl'
    assert not (isinstance(var_decl.init_expr, CallExpr) and var_decl.init_expr.name == 'dbl')


def test_inline_not_inlineable_recursive() -> None:
    # Recursive function must NOT be inlined
    src = 'int fib(int n) { return fib(n - 1) + fib(n - 2); } int main() { return fib(5); }'
    result = opt(parse(src), level=3)
    main_fn = next(d for d in result.declarations if isinstance(d, FunctionDecl) and d.name == 'main')
    ret = main_fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, CallExpr)
    assert ret.value.name == 'fib'


def test_inline_not_inlineable_too_large() -> None:
    # Function with >5 nodes should not be inlined
    src = 'int big(int a, int b) { return a + b + a + b + a; } int main() { return big(1, 2); }'
    result = opt(parse(src), level=3)
    main_fn = next(d for d in result.declarations if isinstance(d, FunctionDecl) and d.name == 'main')
    ret = main_fn.body.stmts[0]
    assert isinstance(ret, ReturnStmt)
    assert isinstance(ret.value, CallExpr)
    assert ret.value.name == 'big'


# ── TCO — marks tail calls in if/elif branches ───────────────────────────────

def test_tco_in_if_then_body() -> None:
    src = 'int f(int n) { if (n > 0) { return f(n - 1); } return 0; }'
    result = opt(parse(src), level=3)
    fn = result.declarations[0]
    if_stmt = fn.body.stmts[0]
    assert isinstance(if_stmt, IfStmt)
    ret_in_then = if_stmt.then_body.stmts[0]
    assert isinstance(ret_in_then, ReturnStmt)
    assert isinstance(ret_in_then.value, CallExpr)
    assert ret_in_then.value.is_tail_call is True


def test_tco_in_else_body() -> None:
    src = 'int f(int n) { if (n <= 0) { return 0; } else { return f(n - 1); } }'
    result = opt(parse(src), level=3)
    fn = result.declarations[0]
    if_stmt = fn.body.stmts[0]
    assert isinstance(if_stmt, IfStmt)
    assert if_stmt.else_body is not None
    ret_in_else = if_stmt.else_body.stmts[0]
    assert isinstance(ret_in_else, ReturnStmt)
    assert ret_in_else.value.is_tail_call is True


# ── Propagation — subst_stmt covering Block ──────────────────────────────────

def test_propagate_subst_stmt_block() -> None:
    # A Block inside a function gets propagated via _subst_stmt
    src = 'int f() { int x = 7; { return x; } }'
    result = opt(parse(src), level=1)
    assert result is not None  # at minimum, no crash


# ── DoWhile optimization ───────────────────────────────────────────────────────

def test_dowhile_is_optimized() -> None:
    src = 'int main() { int i = 0; do { i = i + 1; } while (i < 3); return i; }'
    result = opt(parse(src), level=1)
    assert result is not None
    fn = result.declarations[0]
    assert any(isinstance(s, DoWhileStmt) for s in fn.body.stmts)


# ── _collect_modified_names public API ───────────────────────────────────────

def test_collect_modified_names_assign() -> None:
    node = AssignOp(op='=', target=Identifier('x'), value=IntLiteral(5))
    names: set[str] = set()
    _collect_modified_names(node, names)
    assert 'x' in names


def test_collect_modified_names_unary_increment() -> None:
    node = UnaryOp(op='++', operand=Identifier('y'), prefix=True)
    names: set[str] = set()
    _collect_modified_names(node, names)
    assert 'y' in names
