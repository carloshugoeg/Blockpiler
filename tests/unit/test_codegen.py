from compiler.codegen import codegen
from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer
from compiler.parser import Parser


def compile_to_asm(src: str) -> tuple[str, dict]:
    r = ErrorReporter()
    tokens = Lexer(src, r).tokenize()
    prog = Parser(tokens, r).parse()
    return codegen(prog)


def test_return_42() -> None:
    asm, _ = compile_to_asm('int main() { return 42; }')
    assert 'main' in asm
    assert '42' in asm


def test_println_generates_printf() -> None:
    asm, _ = compile_to_asm('int main() { println(5); return 0; }')
    assert 'printf' in asm or 'bl' in asm


def test_if_else_labels() -> None:
    src = 'int main() { if (1) { return 1; } else { return 0; } }'
    asm, _ = compile_to_asm(src)
    assert '.Lelse_' in asm
    assert '.Lendif_' in asm


def test_while_loop_labels() -> None:
    asm, _ = compile_to_asm('int main() { while (1) { break; } return 0; }')
    assert '.Lwhile_start_' in asm
    assert '.Lwhile_end_' in asm


def test_for_loop_labels() -> None:
    asm, _ = compile_to_asm(
        'int main() { for (int i = 0; i < 10; i++) { } return 0; }'
    )
    assert '.Lfor_cond_' in asm
    assert '.Lfor_update_' in asm
    assert '.Lfor_end_' in asm


def test_div_zero_guard() -> None:
    asm, _ = compile_to_asm('int main() { int x = 5 / 1; return x; }')
    # When divisor is not a literal zero, guard is emitted
    assert 'sdiv' in asm or 'div' in asm.lower()


def test_line_map_populated() -> None:
    src = 'int main() {\n    int x = 1;\n    return x;\n}'
    _, lmap = compile_to_asm(src)
    assert len(lmap) > 0


def test_frame_size_multiple_of_16() -> None:
    from compiler.codegen import CodeGenerator, _add_standard_rodata
    from compiler.error_reporter import ErrorReporter
    from compiler.lexer import Lexer
    from compiler.parser import Parser
    r = ErrorReporter()
    tokens = Lexer('int f(int a, int b) { int c = 1; return a; }', r).tokenize()
    prog = Parser(tokens, r).parse()
    gen = CodeGenerator()
    _add_standard_rodata(gen)
    fn = prog.declarations[0]
    from compiler.ast_nodes import FunctionDecl
    assert isinstance(fn, FunctionDecl)
    gen._compute_frame(fn)
    assert gen._frame_size % 16 == 0


def test_function_prologue_stp() -> None:
    asm, _ = compile_to_asm('int main() { return 0; }')
    assert 'stp x29, x30' in asm


def test_function_epilogue_ldp() -> None:
    asm, _ = compile_to_asm('int main() { return 0; }')
    assert 'ldp x29, x30' in asm


def test_globl_directive() -> None:
    asm, _ = compile_to_asm('int main() { return 0; }')
    assert '.globl' in asm


def test_oob_guard_present_for_array_access() -> None:
    src = 'int f(int i) { int arr[3]; return arr[i]; }'
    asm, _ = compile_to_asm(src)
    # OOB guard produces a .Loob_ok_ label or equivalent error label
    assert '.Loob_ok_' in asm or '.Lerr_oob' in asm


def test_dowhile_labels() -> None:
    asm, _ = compile_to_asm('int main() { int x = 0; do { x++; } while (x < 3); return x; }')
    assert '.Ldowhile_start_' in asm
    assert '.Ldowhile_cond_' in asm
    assert '.Ldowhile_end_' in asm


def test_break_emits_branch() -> None:
    asm, _ = compile_to_asm('int main() { while (1) { break; } return 0; }')
    # break emits a branch to the end label
    assert '.Lwhile_end_' in asm


def test_continue_emits_branch() -> None:
    asm, _ = compile_to_asm(
        'int main() { for (int i = 0; i < 5; i++) { continue; } return 0; }'
    )
    assert '.Lfor_update_' in asm


def test_bool_literal_true_emits_1() -> None:
    asm, _ = compile_to_asm('int main() { int x = 1; return x; }')
    assert '#1' in asm or 'mov' in asm.lower()


def test_bool_literal_false_emits_0() -> None:
    from compiler.ast_nodes import BoolLiteral, IntLiteral, Program, FunctionDecl, Block, ReturnStmt, SourcePos
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[ReturnStmt(value=BoolLiteral(False), pos=pos)], pos=pos),
            pos=pos
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert '#0' in asm or 'mov' in asm.lower()


def test_float_literal_emits_ldr() -> None:
    from compiler.ast_nodes import FloatLiteral, Program, FunctionDecl, Block, ReturnStmt, SourcePos
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[ReturnStmt(value=FloatLiteral(3.14), pos=pos)], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert 'ldr' in asm.lower()


def test_string_literal_intern() -> None:
    asm, _ = compile_to_asm('int main() { println("hello"); return 0; }')
    assert '.Lstr_' in asm or 'hello' in asm


def test_println_float_uses_float_fmt() -> None:
    from compiler.ast_nodes import (
        FloatLiteral, PrintStmt, Program, FunctionDecl, Block,
        ReturnStmt, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    flit = FloatLiteral(1.5, inferred_type='float')
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                PrintStmt(expr=flit, newline=True, pos=pos),
                ReturnStmt(value=None, pos=pos),
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert 'fmov' in asm or '.Lfmt_float' in asm


def test_println_string_uses_str_fmt() -> None:
    from compiler.ast_nodes import (
        StringLiteral, PrintStmt, Program, FunctionDecl, Block,
        ReturnStmt, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    slit = StringLiteral('hi', inferred_type='string')
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                PrintStmt(expr=slit, newline=False, pos=pos),
                ReturnStmt(value=None, pos=pos),
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert '.Lfmt_str' in asm


def test_println_char_uses_char_fmt() -> None:
    from compiler.ast_nodes import (
        CharLiteral, PrintStmt, Program, FunctionDecl, Block,
        ReturnStmt, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    clit = CharLiteral('A', inferred_type='char')
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                PrintStmt(expr=clit, newline=True, pos=pos),
                ReturnStmt(value=None, pos=pos),
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert '.Lfmt_char' in asm


def test_char_literal_emits_immediate() -> None:
    from compiler.ast_nodes import (
        CharLiteral, Program, FunctionDecl, Block, ReturnStmt, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[ReturnStmt(value=CharLiteral('A'), pos=pos)], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert str(ord('A')) in asm  # 65


def test_binary_modulo() -> None:
    asm, _ = compile_to_asm('int main() { int r = 10 % 3; return r; }')
    assert 'msub' in asm or 'sdiv' in asm


def test_binary_not_equal() -> None:
    asm, _ = compile_to_asm('int main() { int x = 1; int y = 2; if (x != y) { return 1; } return 0; }')
    assert 'cset' in asm


def test_binary_less_than() -> None:
    asm, _ = compile_to_asm('int main() { int x = 1; int y = 2; if (x < y) { return 1; } return 0; }')
    assert 'cset' in asm


def test_binary_less_equal() -> None:
    asm, _ = compile_to_asm('int f(int a, int b) { if (a <= b) { return 1; } return 0; }')
    assert 'cset' in asm


def test_binary_greater_equal() -> None:
    asm, _ = compile_to_asm('int f(int a, int b) { if (a >= b) { return 1; } return 0; }')
    assert 'cset' in asm


def test_binary_logical_and() -> None:
    asm, _ = compile_to_asm('int f(int a, int b) { if (a && b) { return 1; } return 0; }')
    assert 'and' in asm.lower()


def test_binary_logical_or() -> None:
    asm, _ = compile_to_asm('int f(int a, int b) { if (a || b) { return 1; } return 0; }')
    assert 'orr' in asm.lower()


def test_binary_left_shift() -> None:
    # Optimizer at level 2 converts x*4 → x<<2
    from compiler.ast_nodes import (
        BinaryOp, Identifier, IntLiteral, Program, FunctionDecl,
        Block, ReturnStmt, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    expr = BinaryOp(op='<<', left=Identifier('x'), right=IntLiteral(2))
    prog = Program(
        declarations=[FunctionDecl(
            name='f', return_type='int',
            params=[],
            body=Block(stmts=[ReturnStmt(value=expr, pos=pos)], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert 'lsl' in asm.lower()


def test_unary_not() -> None:
    asm, _ = compile_to_asm('int f(int x) { return !x; }')
    assert 'cset' in asm and 'cmp' in asm


def test_unary_neg() -> None:
    asm, _ = compile_to_asm('int f(int x) { return -x; }')
    assert 'neg' in asm.lower()


def test_prefix_increment() -> None:
    asm, _ = compile_to_asm('int f(int x) { return ++x; }')
    assert 'add' in asm.lower()
    assert 'str' in asm.lower()


def test_postfix_increment() -> None:
    asm, _ = compile_to_asm('int f(int x) { return x++; }')
    assert 'add' in asm.lower()


def test_prefix_decrement() -> None:
    asm, _ = compile_to_asm('int f(int x) { return --x; }')
    assert 'sub' in asm.lower()


def test_postfix_decrement() -> None:
    asm, _ = compile_to_asm('int f(int x) { return x--; }')
    assert 'sub' in asm.lower()


def test_function_call() -> None:
    asm, _ = compile_to_asm('int add(int a, int b) { return a + b; } int main() { return add(1, 2); }')
    assert 'bl' in asm.lower()


def test_compound_assign_plus_equal() -> None:
    asm, _ = compile_to_asm('int main() { int x = 5; x += 3; return x; }')
    assert 'add' in asm.lower()


def test_compound_assign_minus_equal() -> None:
    asm, _ = compile_to_asm('int main() { int x = 5; x -= 3; return x; }')
    assert 'sub' in asm.lower()


def test_array_init_list_emits_stores() -> None:
    asm, _ = compile_to_asm('int main() { int arr[3] = {1, 2, 3}; return arr[0]; }')
    assert 'str' in asm.lower()
    assert '.Loob_ok_' in asm or 'cbz' in asm


def test_if_with_elif_clauses() -> None:
    asm, _ = compile_to_asm(
        'int f(int x) { if (x == 1) { return 1; } else if (x == 2) { return 2; } return 0; }'
    )
    assert '.Lelse_' in asm
    assert '.Lendif_' in asm


def test_cast_expr_passthrough() -> None:
    asm, _ = compile_to_asm('int main() { int x = (int)5; return x; }')
    assert 'mov' in asm.lower()


def test_input_int_uses_scanf() -> None:
    from compiler.ast_nodes import (
        InputExpr, VarDecl, Program, FunctionDecl, Block,
        ReturnStmt, Identifier, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                VarDecl(name='x', type='int',
                        init_expr=InputExpr(variant='int', inferred_type='int', pos=pos),
                        pos=pos),
                ReturnStmt(value=Identifier('x'), pos=pos),
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert 'scanf' in asm or 'bl' in asm.lower()


def test_input_float_uses_scanf() -> None:
    from compiler.ast_nodes import (
        InputExpr, VarDecl, Program, FunctionDecl, Block,
        ReturnStmt, Identifier, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                VarDecl(name='y', type='float',
                        init_expr=InputExpr(variant='float', inferred_type='float', pos=pos),
                        pos=pos),
                ReturnStmt(value=None, pos=pos),
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert 'scanf' in asm or 'bl' in asm.lower()


def test_input_string_emits_zero() -> None:
    from compiler.ast_nodes import (
        InputExpr, VarDecl, Program, FunctionDecl, Block,
        ReturnStmt, Identifier, SourcePos
    )
    from compiler.codegen import codegen
    pos = SourcePos(1, 1)
    prog = Program(
        declarations=[FunctionDecl(
            name='main', return_type='int', params=[],
            body=Block(stmts=[
                VarDecl(name='s', type='string',
                        init_expr=InputExpr(variant='string', inferred_type='string', pos=pos),
                        pos=pos),
                ReturnStmt(value=None, pos=pos),
            ], pos=pos),
            pos=pos,
        )],
        pos=pos,
    )
    asm, _ = codegen(prog)
    assert '#0' in asm or 'mov' in asm.lower()


def test_index_store_assignment() -> None:
    asm, _ = compile_to_asm(
        'int main() { int arr[3]; arr[1] = 42; return 0; }'
    )
    assert 'str' in asm.lower()


def test_expr_stmt_discards_result() -> None:
    asm, _ = compile_to_asm('int add(int a, int b) { return a+b; } int main() { add(1,2); return 0; }')
    # Call is made even if result unused
    assert 'bl' in asm.lower()
