from __future__ import annotations

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
    InputExpr,
    IntLiteral,
    Parameter,
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
from compiler.lexer import Token, TokenType
from compiler.limits import MAX_NESTING_DEPTH, MAX_PARAMS

_ASSIGN_OPS = {
    TokenType.ASSIGN,
    TokenType.PLUS_ASSIGN,
    TokenType.MINUS_ASSIGN,
    TokenType.STAR_ASSIGN,
    TokenType.SLASH_ASSIGN,
    TokenType.PERCENT_ASSIGN,
}

_TYPE_MAP: dict[str, CType] = {
    'int': 'int',
    'float': 'float',
    'char': 'char',
    'bool': 'bool',
    'void': 'void',
    'string': 'string',
}


class Parser:
    def __init__(self, tokens: list[Token], reporter: ErrorReporter) -> None:
        self._tokens = tokens
        self._reporter = reporter
        self._pos = 0
        self._loop_depth: int = 0
        self._func_depth: int = 0
        self._nesting_depth: int = 0
        self._open_braces: list[SourcePos] = []
        self._current_func_type: Optional[CType] = None
        self._current_func_name: Optional[str] = None

    def parse(self) -> Program:
        prog = self._parse_program()
        for pos in self._open_braces:
            self._reporter.add(
                'PAR003',
                f"'{{' sin cerrar abierto en línea {pos.line}",
                pos.line, pos.col,
            )
        return prog

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _peek2(self) -> Token:
        idx = self._pos + 1
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def _check(self, tt: TokenType) -> bool:
        return self._peek().type == tt

    def _match(self, *types: TokenType) -> bool:
        if self._peek().type in types:
            self._advance()
            return True
        return False

    def _expect(self, tt: TokenType) -> Token:
        tok = self._peek()
        if tok.type == tt:
            return self._advance()
        if tt == TokenType.SEMICOLON:
            self._reporter.add(
                'PAR005',
                f"Se esperaba ';' al final de la declaración, se encontró '{tok.value}'",
                tok.line, tok.column,
            )
        elif tok.type == TokenType.EOF:
            self._reporter.add(
                'PAR002',
                f"Fin de archivo inesperado dentro de {tt.name}",
                tok.line, tok.column,
            )
        else:
            self._reporter.add(
                'PAR001',
                f"Se esperaba {tt.name}, se encontró '{tok.value}'",
                tok.line, tok.column,
            )
        return tok  # don't advance — let caller recover

    def _tok_pos(self, tok: Optional[Token] = None) -> SourcePos:
        t = tok or self._peek()
        return SourcePos(t.line, t.column)

    def _synchronize(self) -> None:
        while not self._check(TokenType.EOF):
            tt = self._peek().type
            if tt in (TokenType.SEMICOLON, TokenType.RBRACE, TokenType.LBRACE):
                if tt == TokenType.SEMICOLON:
                    self._advance()
                return
            self._advance()

    # ── Program ─────────────────────────────────────────────────────────────────

    def _parse_program(self) -> Program:
        decls: list[Any] = []
        pos = self._tok_pos()
        while not self._check(TokenType.EOF):
            if self._reporter.error_limit_reached:
                break
            try:
                decl = self._parse_top_decl()
                decls.append(decl)
            except _ParseError:
                self._synchronize()
        return Program(declarations=decls, pos=pos)

    def _parse_top_decl(self) -> Any:
        tok = self._peek()
        if tok.type == TokenType.ELSE:
            self._reporter.add(
                'PAR006',
                "'else' sin 'if' correspondiente",
                tok.line, tok.column,
            )
            self._advance()
            if self._check(TokenType.LBRACE):
                self._parse_block()
            raise _ParseError()
        if tok.type != TokenType.TYPE_KW:
            self._reporter.add(
                'PAR001',
                f"Se esperaba tipo, se encontró '{tok.value}'",
                tok.line, tok.column,
            )
            self._synchronize()
            raise _ParseError()

        type_tok = self._advance()
        ctype: CType = _TYPE_MAP[type_tok.value]
        name_tok = self._expect(TokenType.IDENT)

        if self._check(TokenType.LPAREN):
            return self._parse_function_decl(ctype, name_tok, type_tok)

        if self._check(TokenType.LBRACKET):
            return self._parse_array_decl_tail(ctype, name_tok, type_tok)

        return self._parse_var_decl_tail(ctype, name_tok, type_tok)

    def _parse_function_decl(
        self, ctype: CType, name_tok: Token, type_tok: Token
    ) -> FunctionDecl:
        if self._func_depth > 0:
            self._reporter.add('PAR004', 'No se permiten funciones anidadas',
                               name_tok.line, name_tok.column)
            raise _ParseError()

        self._func_depth += 1
        saved_type = self._current_func_type
        saved_name = self._current_func_name
        self._current_func_type = ctype
        self._current_func_name = name_tok.value

        self._expect(TokenType.LPAREN)
        params = self._parse_param_list()
        self._expect(TokenType.RPAREN)
        body = self._parse_block()

        self._func_depth -= 1
        self._current_func_type = saved_type
        self._current_func_name = saved_name

        return FunctionDecl(
            name=name_tok.value,
            return_type=ctype,
            params=params,
            body=body,
            pos=SourcePos(type_tok.line, type_tok.column),
        )

    def _parse_param_list(self) -> list[Parameter]:
        params: list[Parameter] = []
        if self._check(TokenType.RPAREN):
            return params
        params.append(self._parse_parameter())
        while self._check(TokenType.COMMA):
            self._advance()
            if len(params) >= MAX_PARAMS:
                self._reporter.add(
                    'PAR010',
                    f'Número de argumentos/parámetros excede el máximo ({MAX_PARAMS})',
                    self._peek().line, self._peek().column,
                )
                break
            params.append(self._parse_parameter())
        return params

    def _parse_parameter(self) -> Parameter:
        type_tok = self._expect(TokenType.TYPE_KW)
        name_tok = self._expect(TokenType.IDENT)
        ctype: CType = _TYPE_MAP.get(type_tok.value, 'unknown')
        return Parameter(
            name=name_tok.value,
            type=ctype,
            pos=SourcePos(type_tok.line, type_tok.column),
        )

    def _parse_var_decl(self) -> VarDecl:
        type_tok = self._expect(TokenType.TYPE_KW)
        ctype: CType = _TYPE_MAP[type_tok.value]
        if ctype == 'void':
            self._reporter.add(
                'PAR012',
                "Declaración de tipo 'void' solo permitida para funciones",
                type_tok.line, type_tok.column,
            )
        name_tok = self._expect(TokenType.IDENT)
        return self._parse_var_decl_tail(ctype, name_tok, type_tok)

    def _parse_var_decl_tail(
        self, ctype: CType, name_tok: Token, type_tok: Token
    ) -> VarDecl:
        if ctype == 'void':
            self._reporter.add(
                'PAR012',
                "Declaración de tipo 'void' solo permitida para funciones",
                type_tok.line, type_tok.column,
            )
        init = None
        if self._check(TokenType.ASSIGN):
            self._advance()
            init = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return VarDecl(
            name=name_tok.value,
            type=ctype,
            init_expr=init,
            pos=SourcePos(type_tok.line, type_tok.column),
        )

    def _parse_array_decl(self) -> ArrayDecl:
        type_tok = self._expect(TokenType.TYPE_KW)
        ctype: CType = _TYPE_MAP[type_tok.value]
        name_tok = self._expect(TokenType.IDENT)
        return self._parse_array_decl_tail(ctype, name_tok, type_tok)

    def _parse_array_decl_tail(
        self, ctype: CType, name_tok: Token, type_tok: Token
    ) -> ArrayDecl:
        self._expect(TokenType.LBRACKET)
        size_tok = self._expect(TokenType.INT_LIT)
        size = int(size_tok.value) if size_tok.value.isdigit() else 0
        self._expect(TokenType.RBRACKET)
        init_list: list[Any] = []
        if self._check(TokenType.ASSIGN):
            self._advance()
            self._expect(TokenType.LBRACE)
            init_list = self._parse_expr_list()
            self._expect(TokenType.RBRACE)
        self._expect(TokenType.SEMICOLON)
        return ArrayDecl(
            name=name_tok.value,
            element_type=ctype,
            size=size,
            init_list=init_list,
            pos=SourcePos(type_tok.line, type_tok.column),
        )

    def _parse_block(self) -> Block:
        tok = self._peek()
        if self._nesting_depth >= MAX_NESTING_DEPTH:
            self._reporter.add(
                'PAR009',
                f'Profundidad de anidamiento excede el máximo ({MAX_NESTING_DEPTH})',
                tok.line, tok.column,
            )
        open_tok = self._expect(TokenType.LBRACE)
        brace_pos = SourcePos(open_tok.line, open_tok.column)
        self._open_braces.append(brace_pos)
        self._nesting_depth += 1
        stmts: list[Any] = []

        while not self._check(TokenType.RBRACE) and not self._check(TokenType.EOF):
            if self._reporter.error_limit_reached:
                break
            try:
                s = self._parse_statement()
                stmts.append(s)
            except _ParseError:
                self._synchronize()

        if self._check(TokenType.EOF):
            pass
        else:
            self._advance()  # consume RBRACE
            if self._open_braces and self._open_braces[-1] is brace_pos:
                self._open_braces.pop()

        self._nesting_depth -= 1
        return Block(stmts=stmts, pos=brace_pos)

    def _parse_statement(self) -> Any:
        tok = self._peek()

        if tok.type == TokenType.ELSE:
            self._reporter.add(
                'PAR006',
                "'else' sin 'if' correspondiente",
                tok.line, tok.column,
            )
            self._advance()
            if self._check(TokenType.LBRACE):
                self._parse_block()  # consume orphan else body
            raise _ParseError()

        if tok.type == TokenType.IF:
            return self._parse_if_stmt()
        if tok.type == TokenType.WHILE:
            return self._parse_while_stmt()
        if tok.type == TokenType.FOR:
            return self._parse_for_stmt()
        if tok.type == TokenType.DO:
            return self._parse_dowhile_stmt()
        if tok.type == TokenType.RETURN:
            return self._parse_return_stmt()
        if tok.type == TokenType.BREAK:
            return self._parse_break_stmt()
        if tok.type == TokenType.CONTINUE:
            return self._parse_continue_stmt()
        if tok.type == TokenType.BUILTIN and tok.value in ('print', 'println'):
            return self._parse_print_stmt()
        if tok.type == TokenType.LBRACE:
            return self._parse_block()
        if tok.type == TokenType.TYPE_KW:
            # Var or array decl inside block (function decl = PAR004)
            type_tok = self._advance()
            ctype: CType = _TYPE_MAP[type_tok.value]
            name_tok = self._expect(TokenType.IDENT)
            if self._check(TokenType.LPAREN):
                self._reporter.add('PAR004', 'No se permiten funciones anidadas',
                                   name_tok.line, name_tok.column)
                raise _ParseError()
            if self._check(TokenType.LBRACKET):
                return self._parse_array_decl_tail(ctype, name_tok, type_tok)
            return self._parse_var_decl_tail(ctype, name_tok, type_tok)

        # Expression statement
        expr = self._parse_expression()
        self._expect(TokenType.SEMICOLON)
        return ExprStmt(expr=expr, pos=getattr(expr, 'pos', SourcePos(tok.line, tok.column)))

    def _parse_if_stmt(self) -> IfStmt:
        tok = self._advance()  # if
        pos = SourcePos(tok.line, tok.column)
        self._expect(TokenType.LPAREN)
        cond = self._parse_expression()
        self._expect(TokenType.RPAREN)
        then = self._parse_block()
        elif_clauses: list[tuple[Any, Block]] = []
        else_block: Optional[Block] = None

        while self._check(TokenType.ELSE):
            self._advance()  # else
            if self._check(TokenType.IF):
                self._advance()  # if
                self._expect(TokenType.LPAREN)
                ec = self._parse_expression()
                self._expect(TokenType.RPAREN)
                eb = self._parse_block()
                elif_clauses.append((ec, eb))
            else:
                else_block = self._parse_block()
                break

        return IfStmt(
            condition=cond,
            then_body=then,
            elif_clauses=elif_clauses,
            else_body=else_block,
            pos=pos,
        )

    def _parse_while_stmt(self) -> WhileStmt:
        tok = self._advance()  # while
        pos = SourcePos(tok.line, tok.column)
        self._expect(TokenType.LPAREN)
        cond = self._parse_expression()
        self._expect(TokenType.RPAREN)
        self._loop_depth += 1
        body = self._parse_block()
        self._loop_depth -= 1
        return WhileStmt(condition=cond, body=body, pos=pos)

    def _parse_for_stmt(self) -> ForStmt:
        tok = self._advance()  # for
        pos = SourcePos(tok.line, tok.column)
        self._expect(TokenType.LPAREN)

        # for_init
        init: Any = None
        if not self._check(TokenType.SEMICOLON):
            if self._check(TokenType.TYPE_KW):
                type_tok = self._advance()
                ctype: CType = _TYPE_MAP[type_tok.value]
                name_tok = self._expect(TokenType.IDENT)
                init_expr = None
                if self._check(TokenType.ASSIGN):
                    self._advance()
                    init_expr = self._parse_expression()
                init = VarDecl(
                    name=name_tok.value,
                    type=ctype,
                    init_expr=init_expr,
                    pos=SourcePos(type_tok.line, type_tok.column),
                )
            else:
                init = self._parse_expression()
        self._expect(TokenType.SEMICOLON)

        condition: Any = None
        if not self._check(TokenType.SEMICOLON):
            condition = self._parse_expression()
        self._expect(TokenType.SEMICOLON)

        update: Any = None
        if not self._check(TokenType.RPAREN):
            update = self._parse_expression()
        self._expect(TokenType.RPAREN)

        self._loop_depth += 1
        body = self._parse_block()
        self._loop_depth -= 1
        return ForStmt(init=init, condition=condition, update=update, body=body, pos=pos)

    def _parse_dowhile_stmt(self) -> DoWhileStmt:
        tok = self._advance()  # do
        pos = SourcePos(tok.line, tok.column)
        self._loop_depth += 1
        body = self._parse_block()
        self._loop_depth -= 1
        self._expect(TokenType.WHILE)
        self._expect(TokenType.LPAREN)
        cond = self._parse_expression()
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.SEMICOLON)
        return DoWhileStmt(condition=cond, body=body, pos=pos)

    def _parse_return_stmt(self) -> ReturnStmt:
        tok = self._advance()  # return
        pos = SourcePos(tok.line, tok.column)
        value: Any = None
        if not self._check(TokenType.SEMICOLON):
            value = self._parse_expression()
            if self._current_func_type == 'void':
                self._reporter.add(
                    'PAR008',
                    "'return' con valor en función de tipo 'void'",
                    tok.line, tok.column,
                )
        self._expect(TokenType.SEMICOLON)
        return ReturnStmt(value=value, pos=pos)

    def _parse_break_stmt(self) -> BreakStmt:
        tok = self._advance()  # break
        pos = SourcePos(tok.line, tok.column)
        if self._loop_depth == 0:
            self._reporter.add('PAR007', "'break' fuera de un bloque de loop",
                               tok.line, tok.column)
        self._expect(TokenType.SEMICOLON)
        return BreakStmt(pos=pos)

    def _parse_continue_stmt(self) -> ContinueStmt:
        tok = self._advance()  # continue
        pos = SourcePos(tok.line, tok.column)
        if self._loop_depth == 0:
            self._reporter.add('PAR007', "'continue' fuera de un bloque de loop",
                               tok.line, tok.column)
        self._expect(TokenType.SEMICOLON)
        return ContinueStmt(pos=pos)

    def _parse_print_stmt(self) -> PrintStmt:
        tok = self._advance()  # print/println
        builtin_name = tok.value
        pos = SourcePos(tok.line, tok.column)
        self._expect(TokenType.LPAREN)
        expr = self._parse_expression()
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.SEMICOLON)
        return PrintStmt(newline=(builtin_name == 'println'), expr=expr, pos=pos)

    # ── Expressions ─────────────────────────────────────────────────────────────

    def _parse_expression(self) -> Any:
        self._nesting_depth += 1
        if self._nesting_depth > MAX_NESTING_DEPTH:
            tok = self._peek()
            self._reporter.add(
                'PAR009',
                f'Profundidad de anidamiento excede el máximo ({MAX_NESTING_DEPTH})',
                tok.line, tok.column,
            )
            self._nesting_depth -= 1
            return IntLiteral(0, pos=SourcePos(tok.line, tok.column))
        try:
            return self._parse_assignment()
        finally:
            self._nesting_depth -= 1

    def _parse_assignment(self) -> Any:
        left = self._parse_logical_or()
        if self._peek().type in _ASSIGN_OPS:
            op_tok = self._advance()
            if not isinstance(left, (Identifier, IndexExpr)):
                self._reporter.add(
                    'PAR011',
                    'Target de asignación debe ser una variable o acceso a array',
                    op_tok.line, op_tok.column,
                )
            right = self._parse_assignment()
            return AssignOp(
                target=left,
                op=op_tok.value,
                value=right,
                pos=getattr(left, 'pos', SourcePos(op_tok.line, op_tok.column)),
            )
        return left

    def _parse_logical_or(self) -> Any:
        left = self._parse_logical_and()
        while self._check(TokenType.OR):
            op = self._advance()
            right = self._parse_logical_and()
            left = BinaryOp(op='||', left=left, right=right,
                            pos=getattr(left, 'pos', self._tok_pos(op)))
        return left

    def _parse_logical_and(self) -> Any:
        left = self._parse_equality()
        while self._check(TokenType.AND):
            op = self._advance()
            right = self._parse_equality()
            left = BinaryOp(op='&&', left=left, right=right,
                            pos=getattr(left, 'pos', self._tok_pos(op)))
        return left

    def _parse_equality(self) -> Any:
        left = self._parse_relational()
        while self._peek().type in (TokenType.EQ, TokenType.NEQ):
            op = self._advance()
            right = self._parse_relational()
            left = BinaryOp(op=op.value, left=left, right=right,
                            pos=getattr(left, 'pos', self._tok_pos(op)))
        return left

    def _parse_relational(self) -> Any:
        left = self._parse_additive()
        while self._peek().type in (TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE):
            op = self._advance()
            right = self._parse_additive()
            left = BinaryOp(op=op.value, left=left, right=right,
                            pos=getattr(left, 'pos', self._tok_pos(op)))
        return left

    def _parse_additive(self) -> Any:
        left = self._parse_multiplicative()
        while self._peek().type in (TokenType.PLUS, TokenType.MINUS):
            op = self._advance()
            right = self._parse_multiplicative()
            left = BinaryOp(op=op.value, left=left, right=right,
                            pos=getattr(left, 'pos', self._tok_pos(op)))
        return left

    def _parse_multiplicative(self) -> Any:
        left = self._parse_unary()
        while self._peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._advance()
            right = self._parse_unary()
            left = BinaryOp(op=op.value, left=left, right=right,
                            pos=getattr(left, 'pos', self._tok_pos(op)))
        return left

    def _parse_unary(self) -> Any:
        tok = self._peek()
        if tok.type == TokenType.NOT:
            self._advance()
            operand = self._parse_unary()
            return UnaryOp(op='!', operand=operand, prefix=True,
                           pos=SourcePos(tok.line, tok.column))
        if tok.type == TokenType.MINUS:
            self._advance()
            operand = self._parse_unary()
            return UnaryOp(op='-', operand=operand, prefix=True,
                           pos=SourcePos(tok.line, tok.column))
        if tok.type == TokenType.INC:
            self._advance()
            operand = self._parse_unary()
            return UnaryOp(op='++', operand=operand, prefix=True,
                           pos=SourcePos(tok.line, tok.column))
        if tok.type == TokenType.DEC:
            self._advance()
            operand = self._parse_unary()
            return UnaryOp(op='--', operand=operand, prefix=True,
                           pos=SourcePos(tok.line, tok.column))
        return self._parse_cast()

    def _parse_cast(self) -> Any:
        # Look-ahead: '(' type ')' → cast
        if (self._check(TokenType.LPAREN)
                and self._peek2().type == TokenType.TYPE_KW):
            saved_pos = self._pos
            self._advance()  # (
            type_tok = self._advance()  # type
            if self._check(TokenType.RPAREN):
                self._advance()  # )
                expr = self._parse_cast()
                ctype: CType = _TYPE_MAP[type_tok.value]
                return CastExpr(
                    target_type=ctype,
                    expr=expr,
                    pos=SourcePos(type_tok.line, type_tok.column),
                )
            # Not a cast — restore and fall through
            self._pos = saved_pos
        return self._parse_postfix()

    def _parse_postfix(self) -> Any:
        expr = self._parse_primary()
        tok = self._peek()
        if tok.type == TokenType.INC:
            self._advance()
            return UnaryOp(op='++', operand=expr, prefix=False,
                           pos=getattr(expr, 'pos', SourcePos(tok.line, tok.column)))
        if tok.type == TokenType.DEC:
            self._advance()
            return UnaryOp(op='--', operand=expr, prefix=False,
                           pos=getattr(expr, 'pos', SourcePos(tok.line, tok.column)))
        return expr

    def _parse_primary(self) -> Any:
        tok = self._peek()

        if tok.type == TokenType.INT_LIT:
            self._advance()
            val = int(tok.value) if tok.value.lstrip('-').isdigit() else 0
            return IntLiteral(value=val, pos=SourcePos(tok.line, tok.column))

        if tok.type == TokenType.FLOAT_LIT:
            self._advance()
            try:
                val_f = float(tok.value)
            except ValueError:
                val_f = 0.0
            return FloatLiteral(value=val_f, pos=SourcePos(tok.line, tok.column))

        if tok.type == TokenType.STRING_LIT:
            self._advance()
            return StringLiteral(value=tok.value, pos=SourcePos(tok.line, tok.column))

        if tok.type == TokenType.CHAR_LIT:
            self._advance()
            return CharLiteral(value=tok.value, pos=SourcePos(tok.line, tok.column))

        if tok.type == TokenType.BUILTIN and tok.value in ('true', 'false'):
            self._advance()
            return BoolLiteral(value=(tok.value == 'true'), pos=SourcePos(tok.line, tok.column))

        if tok.type == TokenType.BUILTIN and tok.value in ('input', 'input_int', 'input_float'):
            self._advance()
            self._expect(TokenType.LPAREN)
            self._expect(TokenType.RPAREN)
            variant_map = {'input': 'string', 'input_int': 'int', 'input_float': 'float'}
            var = variant_map[tok.value]
            ctype_map = {'string': 'string', 'int': 'int', 'float': 'float'}
            return InputExpr(
                variant=var,  # type: ignore[arg-type]
                inferred_type=ctype_map[var],  # type: ignore[arg-type]
                pos=SourcePos(tok.line, tok.column),
            )

        if tok.type == TokenType.IDENT:
            self._advance()
            name = tok.value
            pos = SourcePos(tok.line, tok.column)

            if self._check(TokenType.LBRACKET):
                self._advance()
                idx = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                return IndexExpr(name=name, index=idx, pos=pos)

            if self._check(TokenType.LPAREN):
                self._advance()
                args = self._parse_arg_list()
                self._expect(TokenType.RPAREN)
                return CallExpr(name=name, args=args, pos=pos)

            return Identifier(name=name, pos=pos)

        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        self._reporter.add(
            'PAR001',
            f"Se esperaba expresión, se encontró '{tok.value}'",
            tok.line, tok.column,
        )
        self._advance()
        raise _ParseError()

    def _parse_arg_list(self) -> list[Any]:
        args: list[Any] = []
        if self._check(TokenType.RPAREN):
            return args
        args.append(self._parse_expression())
        while self._check(TokenType.COMMA):
            self._advance()
            if len(args) >= MAX_PARAMS:
                self._reporter.add(
                    'PAR010',
                    f'Número de argumentos/parámetros excede el máximo ({MAX_PARAMS})',
                    self._peek().line, self._peek().column,
                )
                break
            args.append(self._parse_expression())
        return args

    def _parse_expr_list(self) -> list[Any]:
        exprs: list[Any] = []
        if self._check(TokenType.RBRACE):
            return exprs
        exprs.append(self._parse_expression())
        while self._check(TokenType.COMMA):
            self._advance()
            if self._check(TokenType.RBRACE):
                break
            exprs.append(self._parse_expression())
        return exprs


class _ParseError(Exception):
    pass
