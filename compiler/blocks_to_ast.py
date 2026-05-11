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
from compiler.error_reporter import ErrorReporter

_UNKNOWN_BLOCK_CODE = 'BLK001'


class BlocksToAST:
    def __init__(self, reporter: ErrorReporter) -> None:
        self._reporter = reporter

    def convert(self, workspace: dict[str, Any]) -> Program:
        return self._convert_workspace(workspace)

    # ── Top-level ──────────────────────────────────────────────────────────────

    def _convert_workspace(self, ws: dict[str, Any]) -> Program:
        pos = SourcePos(0, 0)
        if not isinstance(ws, dict):
            return Program(declarations=[], pos=pos)
        blocks_root = ws.get('blocks', {})
        if not isinstance(blocks_root, dict):
            return Program(declarations=[], pos=pos)
        top_blocks: list[Any] = blocks_root.get('blocks', [])
        if not isinstance(top_blocks, list):
            return Program(declarations=[], pos=pos)
        declarations: list[Any] = []
        for block in top_blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get('type', '')
            if btype == 'c_func_decl':
                node = self._convert_function_def(block)
                if node is not None:
                    declarations.append(node)
            elif btype == 'c_var_decl':
                node2 = self._convert_var_decl(block)
                if node2 is not None:
                    declarations.append(node2)
            elif btype == 'c_array_decl':
                node3 = self._convert_array_decl(block)
                if node3 is not None:
                    declarations.append(node3)
            else:
                self._unknown(block)
        return Program(declarations=declarations, pos=pos)

    def _convert_function_def(self, block: dict[str, Any]) -> FunctionDecl | None:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'unnamed'))
        raw_type = fields.get('TYPE', fields.get('RETURN_TYPE', 'int'))
        return_type: CType = self._parse_ctype(str(raw_type))
        inputs = block.get('inputs', {}) or {}
        params = self._collect_params(inputs.get('PARAMS'))
        body_block = self._convert_input_to_block(inputs.get('BODY'), pos)
        return FunctionDecl(
            name=name,
            return_type=return_type,
            params=params,
            body=body_block,
            pos=pos,
        )

    def _collect_params(self, param_input: Any) -> list[Parameter]:
        params: list[Parameter] = []
        if not isinstance(param_input, dict):
            return params
        block = param_input.get('block')
        while isinstance(block, dict):
            btype = block.get('type', '')
            if btype == 'c_param':
                fields = block.get('fields', {}) or {}
                pname = str(fields.get('NAME', 'p'))
                ptype: CType = self._parse_ctype(str(fields.get('TYPE', 'int')))
                params.append(Parameter(name=pname, type=ptype, pos=self._get_pos_from_block(block)))
            nxt = block.get('next', {}) or {}
            block = nxt.get('block') if isinstance(nxt, dict) else None
        return params

    def _convert_var_decl(self, block: dict[str, Any]) -> VarDecl | None:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'x'))
        vtype: CType = self._parse_ctype(str(fields.get('TYPE', 'int')))
        inputs = block.get('inputs', {}) or {}
        init_expr: Any = None
        val_input = inputs.get('VALUE')
        if isinstance(val_input, dict):
            inner = val_input.get('block')
            if isinstance(inner, dict):
                init_expr = self._convert_expr(inner)
        return VarDecl(name=name, type=vtype, init_expr=init_expr, pos=pos)

    def _convert_array_decl(self, block: dict[str, Any]) -> ArrayDecl | None:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'arr'))
        etype: CType = self._parse_ctype(str(fields.get('TYPE', 'int')))
        inputs = block.get('inputs', {}) or {}
        try:
            size = int(fields.get('SIZE', 0))
        except (ValueError, TypeError):
            size = 0
        size_input = inputs.get('SIZE')
        if isinstance(size_input, dict):
            inner = size_input.get('block')
            if isinstance(inner, dict):
                try:
                    size = int((inner.get('fields') or {}).get('VALUE', 0))
                except (ValueError, TypeError):
                    size = 0
        init_list: list[Any] = self._collect_list_input(inputs.get('INIT'))
        return ArrayDecl(name=name, element_type=etype, size=size, init_list=init_list, pos=pos)

    # ── Statements ─────────────────────────────────────────────────────────────

    def _convert_statement(self, block: dict[str, Any]) -> Any:
        btype = block.get('type', '')
        if btype == 'c_var_decl':
            return self._convert_var_decl(block)
        if btype == 'c_array_decl':
            return self._convert_array_decl(block)
        if btype == 'c_if':
            return self._convert_if(block)
        if btype == 'c_while':
            return self._convert_while(block)
        if btype == 'c_for':
            return self._convert_for(block)
        if btype == 'c_dowhile':
            return self._convert_dowhile(block)
        if btype == 'c_return':
            return self._convert_return(block)
        if btype == 'c_break':
            return BreakStmt(pos=self._get_pos_from_block(block))
        if btype == 'c_continue':
            return ContinueStmt(pos=self._get_pos_from_block(block))
        if btype == 'c_print':
            return self._convert_print(block, newline=False)
        if btype == 'c_println':
            return self._convert_print(block, newline=True)
        if btype in ('c_assign', 'c_compound_assign'):
            return self._convert_assign_stmt(block)
        if btype == 'c_array_assign':
            return self._convert_array_assign_stmt(block)
        if btype == 'c_func_call_stmt':
            return self._convert_call_stmt(block)
        # Expression-blocks wrapped in a statement
        if btype.startswith('c_'):
            expr = self._convert_expr(block)
            if expr is not None:
                return ExprStmt(expr=expr, pos=self._get_pos_from_block(block))
        self._unknown(block)
        return None

    def _convert_if(self, block: dict[str, Any]) -> IfStmt:
        pos = self._get_pos_from_block(block)
        inputs = block.get('inputs', {}) or {}
        cond = self._convert_input_expr(inputs.get('COND'), pos)
        then_body = self._convert_input_to_block(inputs.get('THEN'), pos)
        elif_clauses: list[tuple[Any, Block]] = []
        # ELIF_N pattern: ELIF0, ELIF1, ...
        n = 0
        while True:
            elif_input = inputs.get(f'ELIF{n}')
            elif_cond_input = inputs.get(f'ELIF_COND{n}')
            if elif_input is None and elif_cond_input is None:
                break
            ec = self._convert_input_expr(elif_cond_input, pos)
            eb = self._convert_input_to_block(elif_input, pos)
            elif_clauses.append((ec, eb))
            n += 1
        else_body: Block | None = None
        if inputs.get('ELSE') is not None:
            else_body = self._convert_input_to_block(inputs.get('ELSE'), pos)
        return IfStmt(
            condition=cond,
            then_body=then_body,
            elif_clauses=elif_clauses,
            else_body=else_body,
            pos=pos,
        )

    def _convert_while(self, block: dict[str, Any]) -> WhileStmt:
        pos = self._get_pos_from_block(block)
        inputs = block.get('inputs', {}) or {}
        cond = self._convert_input_expr(inputs.get('COND'), pos)
        body = self._convert_input_to_block(inputs.get('BODY'), pos)
        return WhileStmt(condition=cond, body=body, pos=pos)

    def _convert_for(self, block: dict[str, Any]) -> ForStmt:
        pos = self._get_pos_from_block(block)
        inputs = block.get('inputs', {}) or {}
        init: Any = None
        init_input = inputs.get('INIT')
        if isinstance(init_input, dict):
            inner = init_input.get('block')
            if isinstance(inner, dict):
                init = self._convert_statement(inner)
        cond: Any = None
        cond_input = inputs.get('COND')
        if isinstance(cond_input, dict):
            inner2 = cond_input.get('block')
            if isinstance(inner2, dict):
                cond = self._convert_expr(inner2)
        update: Any = None
        update_input = inputs.get('UPDATE')
        if isinstance(update_input, dict):
            inner3 = update_input.get('block')
            if isinstance(inner3, dict):
                update = self._convert_expr(inner3)
        body = self._convert_input_to_block(inputs.get('BODY'), pos)
        return ForStmt(init=init, condition=cond, update=update, body=body, pos=pos)

    def _convert_dowhile(self, block: dict[str, Any]) -> DoWhileStmt:
        pos = self._get_pos_from_block(block)
        inputs = block.get('inputs', {}) or {}
        body = self._convert_input_to_block(inputs.get('BODY'), pos)
        cond = self._convert_input_expr(inputs.get('COND'), pos)
        return DoWhileStmt(body=body, condition=cond, pos=pos)

    def _convert_return(self, block: dict[str, Any]) -> ReturnStmt:
        pos = self._get_pos_from_block(block)
        inputs = block.get('inputs', {}) or {}
        val: Any = None
        val_input = inputs.get('VALUE')
        if isinstance(val_input, dict):
            inner = val_input.get('block')
            if isinstance(inner, dict):
                val = self._convert_expr(inner)
        return ReturnStmt(value=val, pos=pos)

    def _convert_print(self, block: dict[str, Any], newline: bool) -> PrintStmt:
        pos = self._get_pos_from_block(block)
        inputs = block.get('inputs', {}) or {}
        expr = self._convert_input_expr(inputs.get('VALUE'), pos)
        return PrintStmt(expr=expr, newline=newline, pos=pos)

    def _convert_assign_stmt(self, block: dict[str, Any]) -> ExprStmt:
        pos = self._get_pos_from_block(block)
        expr = self._convert_assign(block)
        return ExprStmt(expr=expr, pos=pos)

    def _convert_call_stmt(self, block: dict[str, Any]) -> ExprStmt:
        pos = self._get_pos_from_block(block)
        call = self._convert_call_expr(block)
        return ExprStmt(expr=call, pos=pos)

    # ── Expressions ────────────────────────────────────────────────────────────

    def _convert_expr(self, block: dict[str, Any]) -> Any:
        btype = block.get('type', '')
        if btype == 'c_binary_arith':
            return self._convert_binary_arith(block)
        if btype == 'c_binary_cmp':
            return self._convert_binary_cmp(block)
        if btype == 'c_binary_logic':
            return self._convert_binary_logic(block)
        if btype in ('c_unary_not', 'c_unary_neg'):
            return self._convert_unary(block)
        if btype in ('c_prefix_inc', 'c_prefix_dec'):
            return self._convert_prefix_incdec(block)
        if btype in ('c_postfix_inc', 'c_postfix_dec'):
            return self._convert_postfix_incdec(block)
        if btype in ('c_assign', 'c_compound_assign'):
            return self._convert_assign(block)
        if btype == 'c_array_assign':
            return self._convert_array_assign(block)
        if btype in ('c_func_call_expr', 'c_func_call_stmt'):
            return self._convert_call_expr(block)
        if btype == 'c_lit_int':
            return self._convert_literal_int(block)
        if btype == 'c_lit_float':
            return self._convert_literal_float(block)
        if btype == 'c_lit_bool':
            return self._convert_literal_bool(block)
        if btype == 'c_lit_string':
            return self._convert_literal_string(block)
        if btype == 'c_lit_char':
            return self._convert_literal_char(block)
        if btype == 'c_identifier':
            return self._convert_identifier(block)
        if btype == 'c_index_expr':
            return self._convert_index_expr(block)
        if btype == 'c_input':
            return self._convert_input(block)
        if btype == 'c_input_int':
            return self._convert_input_int(block)
        if btype == 'c_input_float':
            return self._convert_input_float(block)
        if btype == 'c_cast':
            return self._convert_cast(block)
        self._unknown(block)
        return IntLiteral(value=0, pos=self._get_pos_from_block(block))

    def _convert_binary_arith(self, block: dict[str, Any]) -> BinaryOp:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        op = str(fields.get('OP', '+'))
        inputs = block.get('inputs', {}) or {}
        left = self._convert_input_expr(inputs.get('LEFT'), pos)
        right = self._convert_input_expr(inputs.get('RIGHT'), pos)
        return BinaryOp(op=op, left=left, right=right, pos=pos)

    def _convert_binary_cmp(self, block: dict[str, Any]) -> BinaryOp:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        op = str(fields.get('OP', '=='))
        inputs = block.get('inputs', {}) or {}
        left = self._convert_input_expr(inputs.get('LEFT'), pos)
        right = self._convert_input_expr(inputs.get('RIGHT'), pos)
        return BinaryOp(op=op, left=left, right=right, pos=pos)

    def _convert_binary_logic(self, block: dict[str, Any]) -> BinaryOp:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        op = str(fields.get('OP', '&&'))
        inputs = block.get('inputs', {}) or {}
        left = self._convert_input_expr(inputs.get('LEFT'), pos)
        right = self._convert_input_expr(inputs.get('RIGHT'), pos)
        return BinaryOp(op=op, left=left, right=right, pos=pos)

    def _convert_unary(self, block: dict[str, Any]) -> UnaryOp:
        pos = self._get_pos_from_block(block)
        btype = block.get('type', '')
        op = '!' if btype == 'c_unary_not' else '-'
        inputs = block.get('inputs', {}) or {}
        operand = self._convert_input_expr(inputs.get('OPERAND'), pos)
        return UnaryOp(op=op, operand=operand, prefix=True, pos=pos)

    def _convert_prefix_incdec(self, block: dict[str, Any]) -> UnaryOp:
        pos = self._get_pos_from_block(block)
        btype = block.get('type', '')
        op = '++' if btype == 'c_prefix_inc' else '--'
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'x'))
        operand = Identifier(name=name, pos=pos)
        return UnaryOp(op=op, operand=operand, prefix=True, pos=pos)

    def _convert_postfix_incdec(self, block: dict[str, Any]) -> UnaryOp:
        pos = self._get_pos_from_block(block)
        btype = block.get('type', '')
        op = '++' if btype == 'c_postfix_inc' else '--'
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'x'))
        operand = Identifier(name=name, pos=pos)
        return UnaryOp(op=op, operand=operand, prefix=False, pos=pos)

    def _convert_assign(self, block: dict[str, Any]) -> AssignOp:
        pos = self._get_pos_from_block(block)
        btype = block.get('type', '')
        fields = block.get('fields', {}) or {}
        op = str(fields.get('OP', '=')) if btype == 'c_compound_assign' else '='
        name = str(fields.get('NAME', 'x'))
        target = Identifier(name=name, pos=pos)
        inputs = block.get('inputs', {}) or {}
        value = self._convert_input_expr(inputs.get('VALUE'), pos)
        return AssignOp(op=op, target=target, value=value, pos=pos)

    def _convert_array_assign_stmt(self, block: dict[str, Any]) -> ExprStmt:
        pos = self._get_pos_from_block(block)
        return ExprStmt(expr=self._convert_array_assign(block), pos=pos)

    def _convert_array_assign(self, block: dict[str, Any]) -> AssignOp:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'arr'))
        inputs = block.get('inputs', {}) or {}
        index = self._convert_input_expr(inputs.get('INDEX'), pos)
        value = self._convert_input_expr(inputs.get('VALUE'), pos)
        target = IndexExpr(name=name, index=index, pos=pos)
        return AssignOp(op='=', target=target, value=value, pos=pos)

    def _convert_call_expr(self, block: dict[str, Any]) -> CallExpr:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'f'))
        inputs = block.get('inputs', {}) or {}
        args = self._collect_list_input(inputs.get('ARGS'))
        return CallExpr(name=name, args=args, pos=pos)

    def _convert_literal_int(self, block: dict[str, Any]) -> IntLiteral:
        fields = block.get('fields', {}) or {}
        try:
            val = int(fields.get('VALUE', 0))
        except (ValueError, TypeError):
            val = 0
        return IntLiteral(value=val, pos=self._get_pos_from_block(block))

    def _convert_literal_float(self, block: dict[str, Any]) -> FloatLiteral:
        fields = block.get('fields', {}) or {}
        try:
            val = float(fields.get('VALUE', 0.0))
        except (ValueError, TypeError):
            val = 0.0
        return FloatLiteral(value=val, pos=self._get_pos_from_block(block))

    def _convert_literal_bool(self, block: dict[str, Any]) -> BoolLiteral:
        fields = block.get('fields', {}) or {}
        raw = fields.get('VALUE', 'false')
        val = str(raw).lower() in ('true', '1', 'yes')
        return BoolLiteral(value=val, pos=self._get_pos_from_block(block))

    def _convert_literal_string(self, block: dict[str, Any]) -> StringLiteral:
        fields = block.get('fields', {}) or {}
        val = str(fields.get('VALUE', ''))
        return StringLiteral(value=val, pos=self._get_pos_from_block(block))

    def _convert_literal_char(self, block: dict[str, Any]) -> CharLiteral:
        fields = block.get('fields', {}) or {}
        raw = str(fields.get('VALUE', '\0'))
        val = raw[0] if raw else '\0'
        return CharLiteral(value=val, pos=self._get_pos_from_block(block))

    def _convert_identifier(self, block: dict[str, Any]) -> Identifier:
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'x'))
        return Identifier(name=name, pos=self._get_pos_from_block(block))

    def _convert_index_expr(self, block: dict[str, Any]) -> IndexExpr:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        name = str(fields.get('NAME', 'arr'))
        inputs = block.get('inputs', {}) or {}
        index = self._convert_input_expr(inputs.get('INDEX'), pos)
        return IndexExpr(name=name, index=index, pos=pos)

    def _convert_input(self, block: dict[str, Any]) -> InputExpr:
        return InputExpr(variant='string', inferred_type='string', pos=self._get_pos_from_block(block))

    def _convert_input_int(self, block: dict[str, Any]) -> InputExpr:
        return InputExpr(variant='int', inferred_type='int', pos=self._get_pos_from_block(block))

    def _convert_input_float(self, block: dict[str, Any]) -> InputExpr:
        return InputExpr(variant='float', inferred_type='float', pos=self._get_pos_from_block(block))

    def _convert_cast(self, block: dict[str, Any]) -> CastExpr:
        pos = self._get_pos_from_block(block)
        fields = block.get('fields', {}) or {}
        target_type: CType = self._parse_ctype(str(fields.get('TYPE', 'int')))
        inputs = block.get('inputs', {}) or {}
        expr = self._convert_input_expr(inputs.get('VALUE'), pos)
        return CastExpr(target_type=target_type, expr=expr, pos=pos)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _convert_input_to_block(self, input_val: Any, default_pos: SourcePos) -> Block:
        """Convert a Blockly input dict to a Block by collecting chained statements."""
        stmts: list[Any] = []
        if not isinstance(input_val, dict):
            return Block(stmts=[], pos=default_pos)
        block = input_val.get('block')
        while isinstance(block, dict):
            stmt = self._convert_statement(block)
            if stmt is not None:
                stmts.append(stmt)
            nxt = block.get('next', {}) or {}
            block = nxt.get('block') if isinstance(nxt, dict) else None
        return Block(stmts=stmts, pos=default_pos)

    def _convert_input_expr(self, input_val: Any, default_pos: SourcePos) -> Any:
        if not isinstance(input_val, dict):
            return IntLiteral(value=0, pos=default_pos)
        inner = input_val.get('block')
        if not isinstance(inner, dict):
            return IntLiteral(value=0, pos=default_pos)
        return self._convert_expr(inner)

    def _collect_list_input(self, input_val: Any) -> list[Any]:
        """Collect a chain of argument/element blocks via 'next' linkage."""
        items: list[Any] = []
        if not isinstance(input_val, dict):
            return items
        block = input_val.get('block')
        while isinstance(block, dict):
            expr = self._convert_expr(block)
            items.append(expr)
            nxt = block.get('next', {}) or {}
            block = nxt.get('block') if isinstance(nxt, dict) else None
        return items

    def _get_pos_from_block(self, block: dict[str, Any]) -> SourcePos:
        data = block.get('data', {})
        if isinstance(data, dict):
            line = int(data.get('srcLine', 0))
        else:
            try:
                import json
                parsed = json.loads(str(data))
                line = int(parsed.get('srcLine', 0))
            except Exception:
                line = 0
        return SourcePos(line=line, col=0)

    def _parse_ctype(self, raw: str) -> CType:
        valid = {'int', 'float', 'char', 'bool', 'string', 'void'}
        return raw if raw in valid else 'int'  # type: ignore[return-value]

    def _unknown(self, block: dict[str, Any]) -> None:
        btype = block.get('type', '<unknown>') if isinstance(block, dict) else '<unknown>'
        pos = self._get_pos_from_block(block) if isinstance(block, dict) else SourcePos(0, 0)
        self._reporter.add(
            code=_UNKNOWN_BLOCK_CODE,
            message=f"Tipo de bloque desconocido: '{btype}'",
            line=pos.line,
            col=pos.col,
            severity='error',
        )


def blocks_to_ast(workspace: dict[str, Any], reporter: ErrorReporter) -> Program:
    return BlocksToAST(reporter).convert(workspace)
