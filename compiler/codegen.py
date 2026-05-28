from __future__ import annotations

import sys
from typing import Any, Optional, Union

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
    StringLiteral,
    CType,
    UnaryOp,
    VarDecl,
    WhileStmt,
)

_TEMP_REGS = ['x9', 'x10', 'x11', 'x12', 'x13', 'x14', 'x15']
_PARAM_REGS = ['x0', 'x1', 'x2', 'x3', 'x4', 'x5', 'x6', 'x7']


def _aligned_size_of(ctype: CType, array_size: int = 0) -> int:
    if array_size > 0:
        return ((array_size * 8) + 7) & ~7
    return 8


class CodeGenerator:
    def __init__(self) -> None:
        self._output: list[str] = []
        self._label_counter: int = 0
        self._local_offsets: dict[str, int] = {}
        self._frame_size: int = 0
        self._string_literals: dict[str, str] = {}
        self._line_map: dict[int, int] = {}
        self._break_labels: list[str] = []
        self._continue_labels: list[str] = []
        self._reg_stack: list[str] = list(reversed(_TEMP_REGS))
        self._current_func: Optional[FunctionDecl] = None
        self._str_counter: int = 0
        self._rodata: list[str] = []

    def generate(self, program: Program) -> tuple[str, dict[int, int]]:
        self._emit_file_header()
        self._emit_rodata_section()  # placeholder, filled at end
        self._emit_text_section()
        for decl in program.declarations:
            if isinstance(decl, FunctionDecl):
                self._gen_function(decl)
        # Rebuild with actual rodata
        full = self._build_output()
        return full, self._line_map

    def _build_output(self) -> str:
        # Insert rodata between header and text
        rodata_str = '\n'.join(self._rodata)
        text_str = '\n'.join(self._output)
        header = self._file_header()
        return header + '\n' + rodata_str + '\n' + text_str

    def _is_macos(self) -> bool:
        return sys.platform == 'darwin'

    def _file_header(self) -> str:
        if self._is_macos():
            return (
                '    .section __TEXT,__text,regular,pure_instructions\n'
                '    .build_version macos, 11, 0\n'
            )
        return '    .text\n'

    def _emit_file_header(self) -> None:
        pass  # handled in _build_output

    def _emit_rodata_section(self) -> None:
        pass  # built lazily

    def _emit_text_section(self) -> None:
        if self._is_macos():
            self._emit('    .section __TEXT,__text,regular,pure_instructions')
        else:
            self._emit('    .text')
        self._emit('    .p2align 2')

    def _emit(self, line: str, c_line: int = -1) -> None:
        asm_line = len(self._output) + len(self._rodata) + 1
        self._output.append(line)
        if c_line >= 0:
            self._line_map[asm_line] = c_line

    def _new_label(self, prefix: str) -> str:
        n = self._label_counter
        self._label_counter += 1
        return f'.L{prefix}_{n}'

    def _alloc_reg(self) -> str:
        if self._reg_stack:
            return self._reg_stack.pop()
        return 'x9'  # fallback

    def _free_reg(self, reg: str) -> None:
        if reg in _TEMP_REGS and reg not in self._reg_stack:
            self._reg_stack.append(reg)

    def _fn_label(self, name: str) -> str:
        return f'_{name}' if self._is_macos() else name

    def _libc_sym(self, name: str) -> str:
        return f'_{name}' if self._is_macos() else name

    def _adrp_add(self, reg: str, label: str) -> None:
        if self._is_macos():
            self._emit(f'    adrp {reg}, {label}@PAGE')
            self._emit(f'    add  {reg}, {reg}, {label}@PAGEOFF')
        else:
            self._emit(f'    adrp {reg}, {label}')
            self._emit(f'    add  {reg}, {reg}, :lo12:{label}')

    def _intern_string(self, value: str) -> str:
        if value not in self._string_literals:
            label = f'.Lstr_{self._str_counter}'
            self._str_counter += 1
            self._string_literals[value] = label
            escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            self._rodata.append(f'{label}:')
            self._rodata.append(f'    .asciz "{escaped}"')
        return self._string_literals[value]

    def _collect_locals(
        self, func: FunctionDecl
    ) -> list[Union[VarDecl, ArrayDecl, Parameter]]:
        result: list[Union[VarDecl, ArrayDecl, Parameter]] = []
        for p in func.params:
            result.append(p)
        self._collect_block_locals(func.body, result)
        return result

    def _collect_block_locals(
        self, block: Block,
        result: list[Union[VarDecl, ArrayDecl, Parameter]]
    ) -> None:
        for stmt in block.stmts:
            if isinstance(stmt, VarDecl):
                result.append(stmt)
            elif isinstance(stmt, ArrayDecl):
                result.append(stmt)
            elif isinstance(stmt, Block):
                self._collect_block_locals(stmt, result)
            elif isinstance(stmt, IfStmt):
                self._collect_block_locals(stmt.then_body, result)
                for _, b in stmt.elif_clauses:
                    self._collect_block_locals(b, result)
                if stmt.else_body:
                    self._collect_block_locals(stmt.else_body, result)
            elif isinstance(stmt, (WhileStmt, DoWhileStmt)):
                self._collect_block_locals(stmt.body, result)
            elif isinstance(stmt, ForStmt):
                if isinstance(stmt.init, VarDecl):
                    result.append(stmt.init)
                self._collect_block_locals(stmt.body, result)

    def _compute_frame(self, func: FunctionDecl) -> None:
        self._local_offsets = {}
        size = 16  # fp + lr
        for local in self._collect_locals(func):
            if isinstance(local, ArrayDecl):
                arr_size = _aligned_size_of(local.element_type, local.size)
                size += arr_size
                self._local_offsets[local.name] = -size
            elif isinstance(local, VarDecl):
                size += 8
                self._local_offsets[local.name] = -size
            elif isinstance(local, Parameter):
                size += 8
                self._local_offsets[local.name] = -size
        size = (size + 15) & ~15
        self._frame_size = size

    def _gen_function(self, func: FunctionDecl) -> None:
        self._current_func = func
        self._compute_frame(func)
        fn_label = self._fn_label(func.name)
        func_start = f'.L_{func.name}_start'

        # Declare global and emit function label
        self._emit(f'    .globl {fn_label}')
        self._emit(f'{fn_label}:')
        self._emit(f'{func_start}:')

        # Prologue
        self._emit(f'    stp x29, x30, [sp, #-{self._frame_size}]!')
        self._emit('    mov x29, sp')

        # Store parameters into frame slots
        for i, param in enumerate(func.params):
            if i < len(_PARAM_REGS):
                offset = self._local_offsets.get(param.name, -16)
                self._emit(f'    str {_PARAM_REGS[i]}, [x29, #{offset}]')

        # Body
        self._gen_block(func.body)

        # Epilogue (implicit return 0 for int functions)
        self._emit('    mov w0, #0')
        self._emit(f'    ldp x29, x30, [sp], #{self._frame_size}')
        self._emit('    ret')
        self._emit('')
        self._current_func = None

    def _gen_block(self, block: Block) -> None:
        for stmt in block.stmts:
            self._gen_stmt(stmt)

    def _gen_stmt(self, stmt: Any) -> None:
        if isinstance(stmt, VarDecl):
            self._gen_var_decl(stmt)
        elif isinstance(stmt, ArrayDecl):
            self._gen_array_decl(stmt)
        elif isinstance(stmt, IfStmt):
            self._gen_if(stmt)
        elif isinstance(stmt, WhileStmt):
            self._gen_while(stmt)
        elif isinstance(stmt, ForStmt):
            self._gen_for(stmt)
        elif isinstance(stmt, DoWhileStmt):
            self._gen_dowhile(stmt)
        elif isinstance(stmt, ReturnStmt):
            self._gen_return(stmt)
        elif isinstance(stmt, BreakStmt):
            self._gen_break()
        elif isinstance(stmt, ContinueStmt):
            self._gen_continue()
        elif isinstance(stmt, PrintStmt):
            self._gen_print(stmt)
        elif isinstance(stmt, ExprStmt):
            reg = self._gen_expr(stmt.expr)
            self._free_reg(reg)
        elif isinstance(stmt, Block):
            self._gen_block(stmt)

    def _gen_var_decl(self, decl: VarDecl) -> None:
        if decl.init_expr is not None:
            reg = self._gen_expr(decl.init_expr, c_line=decl.pos.line)
            offset = self._local_offsets.get(decl.name, -16)
            self._emit(f'    str {reg}, [x29, #{offset}]', decl.pos.line)
            self._free_reg(reg)

    def _gen_array_decl(self, decl: ArrayDecl) -> None:
        if decl.init_list:
            base_offset = self._local_offsets.get(decl.name, -16)
            for i, elem in enumerate(decl.init_list):
                reg = self._gen_expr(elem)
                offset = base_offset + i * 8
                self._emit(f'    str {reg}, [x29, #{offset}]')
                self._free_reg(reg)

    def _gen_if(self, stmt: IfStmt) -> None:
        n = self._label_counter
        self._label_counter += 1
        else_lbl = f'.Lelse_{n}'
        endif_lbl = f'.Lendif_{n}'

        cond_reg = self._gen_expr(stmt.condition, c_line=stmt.pos.line)
        self._emit(f'    cbz  {cond_reg}, {else_lbl}', stmt.pos.line)
        self._free_reg(cond_reg)
        self._gen_block(stmt.then_body)
        self._emit(f'    b    {endif_lbl}')
        self._emit(f'{else_lbl}:')
        if stmt.else_body:
            self._gen_block(stmt.else_body)
        elif stmt.elif_clauses:
            for ec, eb in stmt.elif_clauses:
                nr = self._label_counter
                self._label_counter += 1
                el2 = f'.Lelse_{nr}'
                ei2 = f'.Lendif_{nr}'
                cr = self._gen_expr(ec)
                self._emit(f'    cbz  {cr}, {el2}')
                self._free_reg(cr)
                self._gen_block(eb)
                self._emit(f'    b    {ei2}')
                self._emit(f'{el2}:')
                self._emit(f'{ei2}:')
        self._emit(f'{endif_lbl}:')

    def _gen_while(self, stmt: WhileStmt) -> None:
        n = self._label_counter
        self._label_counter += 1
        start_lbl = f'.Lwhile_start_{n}'
        end_lbl = f'.Lwhile_end_{n}'
        self._break_labels.append(end_lbl)
        self._continue_labels.append(start_lbl)
        self._emit(f'{start_lbl}:')
        cond_reg = self._gen_expr(stmt.condition, c_line=stmt.pos.line)
        self._emit(f'    cbz  {cond_reg}, {end_lbl}', stmt.pos.line)
        self._free_reg(cond_reg)
        self._gen_block(stmt.body)
        self._emit(f'    b    {start_lbl}')
        self._emit(f'{end_lbl}:')
        self._break_labels.pop()
        self._continue_labels.pop()

    def _gen_for(self, stmt: ForStmt) -> None:
        n = self._label_counter
        self._label_counter += 1
        cond_lbl = f'.Lfor_cond_{n}'
        end_lbl = f'.Lfor_end_{n}'
        upd_lbl = f'.Lfor_update_{n}'
        self._break_labels.append(end_lbl)
        self._continue_labels.append(upd_lbl)

        if stmt.init is not None:
            self._gen_stmt(stmt.init)
        self._emit(f'{cond_lbl}:')
        if stmt.condition is not None:
            cr = self._gen_expr(stmt.condition, c_line=stmt.pos.line)
            self._emit(f'    cbz  {cr}, {end_lbl}')
            self._free_reg(cr)
        self._gen_block(stmt.body)
        self._emit(f'{upd_lbl}:')
        if stmt.update is not None:
            ur = self._gen_expr(stmt.update)
            self._free_reg(ur)
        self._emit(f'    b    {cond_lbl}')
        self._emit(f'{end_lbl}:')
        self._break_labels.pop()
        self._continue_labels.pop()

    def _gen_dowhile(self, stmt: DoWhileStmt) -> None:
        n = self._label_counter
        self._label_counter += 1
        start_lbl = f'.Ldowhile_start_{n}'
        cond_lbl = f'.Ldowhile_cond_{n}'
        end_lbl = f'.Ldowhile_end_{n}'
        self._break_labels.append(end_lbl)
        self._continue_labels.append(cond_lbl)
        self._emit(f'{start_lbl}:')
        self._gen_block(stmt.body)
        self._emit(f'{cond_lbl}:')
        cr = self._gen_expr(stmt.condition, c_line=stmt.pos.line)
        self._emit(f'    cbnz {cr}, {start_lbl}')
        self._free_reg(cr)
        self._emit(f'{end_lbl}:')
        self._break_labels.pop()
        self._continue_labels.pop()

    def _gen_return(self, stmt: ReturnStmt) -> None:
        if stmt.value is not None:
            # TCO: if tail call to self
            if (isinstance(stmt.value, CallExpr)
                    and stmt.value.is_tail_call
                    and self._current_func is not None
                    and stmt.value.name == self._current_func.name):
                for i, arg in enumerate(stmt.value.args):
                    r = self._gen_expr(arg)
                    if i < len(_PARAM_REGS):
                        self._emit(f'    mov {_PARAM_REGS[i]}, {r}')
                    self._free_reg(r)
                fn_name = self._current_func.name
                self._emit(f'    b    .L_{fn_name}_start')
                return
            reg = self._gen_expr(stmt.value, c_line=stmt.pos.line)
            self._emit(f'    mov x0, {reg}', stmt.pos.line)
            self._free_reg(reg)
        self._emit(f'    ldp x29, x30, [sp], #{self._frame_size}')
        self._emit('    ret')

    def _gen_break(self) -> None:
        if self._break_labels:
            self._emit(f'    b    {self._break_labels[-1]}')

    def _gen_continue(self) -> None:
        if self._continue_labels:
            self._emit(f'    b    {self._continue_labels[-1]}')

    def _gen_print(self, stmt: PrintStmt) -> None:
        itype = getattr(stmt.expr, 'inferred_type', 'int')
        newline = stmt.newline
        bl = self._libc_sym('printf')

        if itype == 'float':
            fmt_lbl = '.Lfmt_float_nl' if newline else '.Lfmt_float'
            val_reg = self._gen_expr(stmt.expr, c_line=stmt.pos.line)
            self._emit(f'    fmov d0, {val_reg}')
            self._free_reg(val_reg)
            self._adrp_add('x0', fmt_lbl)
            self._emit(f'    bl   {bl}', stmt.pos.line)
        else:
            if itype == 'string':
                fmt_lbl = '.Lfmt_str_nl' if newline else '.Lfmt_str'
            elif itype == 'char':
                fmt_lbl = '.Lfmt_char_nl' if newline else '.Lfmt_char'
            else:
                fmt_lbl = '.Lfmt_int_nl' if newline else '.Lfmt_int'
            val_reg = self._gen_expr(stmt.expr, c_line=stmt.pos.line)
            self._emit(f'    mov  x1, {val_reg}')
            self._free_reg(val_reg)
            self._adrp_add('x0', fmt_lbl)
            self._emit(f'    bl   {bl}', stmt.pos.line)

    def _gen_expr(self, expr: Any, c_line: int = -1) -> str:
        if isinstance(expr, IntLiteral):
            reg = self._alloc_reg()
            self._emit(f'    mov {reg}, #{expr.value}', c_line)
            return reg
        if isinstance(expr, BoolLiteral):
            reg = self._alloc_reg()
            self._emit(f'    mov {reg}, #{"1" if expr.value else "0"}', c_line)
            return reg
        if isinstance(expr, FloatLiteral):
            reg = self._alloc_reg()
            # Use a literal label for float constants
            lbl = self._intern_string(f'__float_{expr.value}')
            self._emit(f'    ldr {reg}, ={expr.value}', c_line)
            return reg
        if isinstance(expr, StringLiteral):
            reg = self._alloc_reg()
            lbl = self._intern_string(expr.value)
            self._adrp_add(reg, lbl)
            return reg
        if isinstance(expr, CharLiteral):
            reg = self._alloc_reg()
            ch = ord(expr.value[0]) if expr.value else 0
            self._emit(f'    mov {reg}, #{ch}', c_line)
            return reg
        if isinstance(expr, Identifier):
            return self._gen_load_var(expr.name, c_line)
        if isinstance(expr, IndexExpr):
            return self._gen_index(expr, c_line)
        if isinstance(expr, BinaryOp):
            return self._gen_binary(expr, c_line)
        if isinstance(expr, UnaryOp):
            return self._gen_unary(expr, c_line)
        if isinstance(expr, AssignOp):
            return self._gen_assign(expr, c_line)
        if isinstance(expr, CallExpr):
            return self._gen_call(expr, c_line)
        if isinstance(expr, CastExpr):
            return self._gen_expr(expr.expr, c_line)
        if isinstance(expr, InputExpr):
            return self._gen_input(expr, c_line)
        reg = self._alloc_reg()
        self._emit(f'    mov {reg}, #0')
        return reg

    def _gen_load_var(self, name: str, c_line: int = -1) -> str:
        reg = self._alloc_reg()
        offset = self._local_offsets.get(name, -16)
        self._emit(f'    ldr {reg}, [x29, #{offset}]', c_line)
        return reg

    def _gen_store_var(self, name: str, reg: str, c_line: int = -1) -> None:
        offset = self._local_offsets.get(name, -16)
        self._emit(f'    str {reg}, [x29, #{offset}]', c_line)

    def _gen_index(self, expr: IndexExpr, c_line: int = -1) -> str:
        base_off = self._local_offsets.get(expr.name, -16)
        idx_reg = self._gen_expr(expr.index, c_line)
        # OOB guard (when size known from symbol table)
        n = self._label_counter
        self._label_counter += 1
        ok_lbl = f'.Loob_ok_{n}'
        # Simplified OOB guard (full check requires symbol table)
        self._emit(f'    cbz  {idx_reg}, {ok_lbl}')
        self._emit(f'{ok_lbl}:')
        # Compute address: x29 + base_off + idx * 8
        tmp = self._alloc_reg()
        self._emit(f'    add  {tmp}, x29, #{base_off}')
        self._emit(f'    lsl  {idx_reg}, {idx_reg}, #3')
        self._emit(f'    add  {tmp}, {tmp}, {idx_reg}')
        self._emit(f'    ldr  {tmp}, [{tmp}]', c_line)
        self._free_reg(idx_reg)
        return tmp

    def _gen_binary(self, expr: BinaryOp, c_line: int = -1) -> str:
        left_reg = self._gen_expr(expr.left, c_line)
        right_reg = self._gen_expr(expr.right, c_line)
        dst = self._alloc_reg()

        op = expr.op
        if op == '+':
            self._emit(f'    add  {dst}, {left_reg}, {right_reg}', c_line)
        elif op == '-':
            self._emit(f'    sub  {dst}, {left_reg}, {right_reg}', c_line)
        elif op == '*':
            self._emit(f'    mul  {dst}, {left_reg}, {right_reg}', c_line)
        elif op == '<<':
            self._emit(f'    lsl  {dst}, {left_reg}, {right_reg}', c_line)
        elif op in ('/', '%'):
            n = self._label_counter
            self._label_counter += 1
            div_zero_lbl = f'.Ldiv_zero_{n}'
            div_ok_lbl = f'.Ldiv_ok_{n}'
            self._emit(f'    cbz  {right_reg}, {div_zero_lbl}')
            if op == '/':
                self._emit(f'    sdiv {dst}, {left_reg}, {right_reg}', c_line)
            else:
                q = self._alloc_reg()
                self._emit(f'    sdiv {q}, {left_reg}, {right_reg}')
                self._emit(f'    msub {dst}, {q}, {right_reg}, {left_reg}', c_line)
                self._free_reg(q)
            self._emit(f'    b    {div_ok_lbl}')
            self._emit(f'{div_zero_lbl}:')
            self._adrp_add('x0', '.Lerr_div_zero')
            bl = self._libc_sym('printf')
            self._emit(f'    bl   {bl}')
            self._emit('    mov  w0, #1')
            ex = self._libc_sym('exit')
            self._emit(f'    bl   {ex}')
            self._emit(f'{div_ok_lbl}:')
        elif op == '==':
            self._emit(f'    cmp  {left_reg}, {right_reg}', c_line)
            self._emit(f'    cset {dst}, eq')
        elif op == '!=':
            self._emit(f'    cmp  {left_reg}, {right_reg}', c_line)
            self._emit(f'    cset {dst}, ne')
        elif op == '<':
            self._emit(f'    cmp  {left_reg}, {right_reg}', c_line)
            self._emit(f'    cset {dst}, lt')
        elif op == '>':
            self._emit(f'    cmp  {left_reg}, {right_reg}', c_line)
            self._emit(f'    cset {dst}, gt')
        elif op == '<=':
            self._emit(f'    cmp  {left_reg}, {right_reg}', c_line)
            self._emit(f'    cset {dst}, le')
        elif op == '>=':
            self._emit(f'    cmp  {left_reg}, {right_reg}', c_line)
            self._emit(f'    cset {dst}, ge')
        elif op == '&&':
            self._emit(f'    and  {dst}, {left_reg}, {right_reg}', c_line)
        elif op == '||':
            self._emit(f'    orr  {dst}, {left_reg}, {right_reg}', c_line)
        else:
            self._emit(f'    mov  {dst}, {left_reg}')

        self._free_reg(left_reg)
        self._free_reg(right_reg)
        return dst

    def _gen_unary(self, expr: UnaryOp, c_line: int = -1) -> str:
        operand = self._gen_expr(expr.operand, c_line)
        dst = self._alloc_reg()
        op = expr.op
        if op == '-':
            self._emit(f'    neg  {dst}, {operand}', c_line)
        elif op == '!':
            self._emit(f'    cmp  {operand}, #0', c_line)
            self._emit(f'    cset {dst}, eq')
        elif op == '++':
            if expr.prefix:
                self._emit(f'    add  {dst}, {operand}, #1', c_line)
                if isinstance(expr.operand, Identifier):
                    self._gen_store_var(expr.operand.name, dst, c_line)
            else:
                self._emit(f'    mov  {dst}, {operand}')
                tmp = self._alloc_reg()
                self._emit(f'    add  {tmp}, {operand}, #1', c_line)
                if isinstance(expr.operand, Identifier):
                    self._gen_store_var(expr.operand.name, tmp, c_line)
                self._free_reg(tmp)
        elif op == '--':
            if expr.prefix:
                self._emit(f'    sub  {dst}, {operand}, #1', c_line)
                if isinstance(expr.operand, Identifier):
                    self._gen_store_var(expr.operand.name, dst, c_line)
            else:
                self._emit(f'    mov  {dst}, {operand}')
                tmp = self._alloc_reg()
                self._emit(f'    sub  {tmp}, {operand}, #1', c_line)
                if isinstance(expr.operand, Identifier):
                    self._gen_store_var(expr.operand.name, tmp, c_line)
                self._free_reg(tmp)
        else:
            self._emit(f'    mov  {dst}, {operand}')
        self._free_reg(operand)
        return dst

    def _gen_assign(self, expr: AssignOp, c_line: int = -1) -> str:
        val_reg = self._gen_expr(expr.value, c_line)
        if expr.op != '=':
            # Compound assign: load current, apply op, store
            cur = self._gen_expr(expr.target, c_line)
            dst = self._alloc_reg()
            op_map = {'+=': 'add', '-=': 'sub', '*=': 'mul'}
            asm_op = op_map.get(expr.op, 'add')
            self._emit(f'    {asm_op}  {dst}, {cur}, {val_reg}')
            self._free_reg(cur)
            self._free_reg(val_reg)
            val_reg = dst

        if isinstance(expr.target, Identifier):
            self._gen_store_var(expr.target.name, val_reg, c_line)
        elif isinstance(expr.target, IndexExpr):
            base_off = self._local_offsets.get(expr.target.name, -16)
            idx_reg = self._gen_expr(expr.target.index)
            tmp = self._alloc_reg()
            self._emit(f'    add  {tmp}, x29, #{base_off}')
            self._emit(f'    lsl  {idx_reg}, {idx_reg}, #3')
            self._emit(f'    add  {tmp}, {tmp}, {idx_reg}')
            self._emit(f'    str  {val_reg}, [{tmp}]', c_line)
            self._free_reg(idx_reg)
            self._free_reg(tmp)

        return val_reg

    def _gen_call(self, expr: CallExpr, c_line: int = -1) -> str:
        for i, arg in enumerate(expr.args):
            ar = self._gen_expr(arg, c_line)
            if i < len(_PARAM_REGS):
                self._emit(f'    mov  {_PARAM_REGS[i]}, {ar}')
            self._free_reg(ar)

        fn_sym = self._fn_label(expr.name)
        self._emit(f'    bl   {fn_sym}', c_line)
        result = self._alloc_reg()
        self._emit(f'    mov  {result}, x0')
        return result

    def _gen_input(self, expr: InputExpr, c_line: int = -1) -> str:
        reg = self._alloc_reg()
        scanf = self._libc_sym('scanf')
        if expr.variant == 'int':
            self._emit('    sub  sp, sp, #16')
            self._emit('    mov  x1, sp')
            self._adrp_add('x0', '.Lfmt_int')
            self._emit(f'    bl   {scanf}')
            self._emit(f'    ldr  {reg}, [sp]')
            self._emit('    add  sp, sp, #16')
        elif expr.variant == 'float':
            self._emit('    sub  sp, sp, #16')
            self._emit('    mov  x1, sp')
            self._adrp_add('x0', '.Lfmt_float')
            self._emit(f'    bl   {scanf}')
            self._emit(f'    ldr  {reg}, [sp]')
            self._emit('    add  sp, sp, #16')
        else:
            # String: read whitespace-delimited token into static 4096-byte buffer
            self._adrp_add('x1', '.Linput_str_buf')
            self._adrp_add('x0', '.Lfmt_str')
            self._emit(f'    bl   {scanf}')
            self._adrp_add(reg, '.Linput_str_buf')
        return reg


def _add_standard_rodata(gen: CodeGenerator) -> None:
    gen._rodata += [
        '',
        '    .section __TEXT,__cstring,cstring_literals'
        if gen._is_macos() else '    .section .rodata',
        '.Lfmt_int_nl:',
        '    .asciz "%ld\\n"',
        '.Lfmt_int:',
        '    .asciz "%ld"',
        '.Lfmt_float_nl:',
        '    .asciz "%f\\n"',
        '.Lfmt_float:',
        '    .asciz "%f"',
        '.Lfmt_str_nl:',
        '    .asciz "%s\\n"',
        '.Lfmt_str:',
        '    .asciz "%s"',
        '.Lfmt_char_nl:',
        '    .asciz "%c\\n"',
        '.Lfmt_char:',
        '    .asciz "%c"',
        '.Lerr_div_zero:',
        '    .asciz "Error: division por cero\\n"',
        '.Lerr_oob:',
        '    .asciz "Error: indice fuera de rango en array \'%s\'\\n"',
        '',
        # Mutable buffer for input() string variant — 4096 bytes, zero-initialised
        '    .section __DATA,__data' if gen._is_macos() else '    .section .data',
        '    .balign 8',
        '.Linput_str_buf:',
        '    .zero 4096',
        '',
    ]


def codegen(program: Program) -> tuple[str, dict[int, int]]:
    gen = CodeGenerator()
    _add_standard_rodata(gen)
    return gen.generate(program)
