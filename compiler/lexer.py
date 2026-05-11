from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from compiler.error_reporter import ErrorReporter
from compiler.limits import (
    INT64_MAX,
    INT64_MIN,
    MAX_IDENTIFIER_LEN,
    MAX_SOURCE_SIZE,
    MAX_STRING_LEN,
)


class TokenType(Enum):
    # Literals
    INT_LIT = auto()
    FLOAT_LIT = auto()
    STRING_LIT = auto()
    CHAR_LIT = auto()
    BOOL_LIT = auto()
    # Identifier
    IDENT = auto()
    # Keywords
    IF = auto()
    ELSE = auto()
    FOR = auto()
    WHILE = auto()
    DO = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    # Type keywords
    TYPE_KW = auto()
    # Builtins
    BUILTIN = auto()
    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    ASSIGN = auto()
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN = auto()
    SLASH_ASSIGN = auto()
    PERCENT_ASSIGN = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    INC = auto()
    DEC = auto()
    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    SEMICOLON = auto()
    COMMA = auto()
    # Special
    EOF = auto()
    ERROR = auto()


KEYWORDS: set[str] = {'if', 'else', 'for', 'while', 'do', 'return', 'break', 'continue'}
TYPE_KEYWORDS: set[str] = {'int', 'float', 'char', 'bool', 'void', 'string'}
BUILTINS: set[str] = {'print', 'println', 'input', 'input_int', 'input_float', 'true', 'false'}

_KEYWORD_MAP: dict[str, TokenType] = {
    'if': TokenType.IF,
    'else': TokenType.ELSE,
    'for': TokenType.FOR,
    'while': TokenType.WHILE,
    'do': TokenType.DO,
    'return': TokenType.RETURN,
    'break': TokenType.BREAK,
    'continue': TokenType.CONTINUE,
}

_ESCAPE_MAP: dict[str, str] = {
    'n': '\n',
    't': '\t',
    'r': '\r',
    '\\': '\\',
    '"': '"',
    "'": "'",
    '0': '\0',
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    length: int


class Lexer:
    def __init__(self, source: str, reporter: ErrorReporter) -> None:
        self._source = source
        self._reporter = reporter
        self._pos = 0
        self._line = 1
        self._col = 1

    def tokenize(self) -> list[Token]:
        # Validate UTF-8 via encoding check
        try:
            self._source.encode('utf-8').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            self._reporter.add('LEX009', 'Input no es texto UTF-8 válido', 1, 1)
            return [Token(TokenType.EOF, '', 1, 1, 0)]

        # Check source size
        if len(self._source.encode('utf-8')) > MAX_SOURCE_SIZE:
            self._reporter.add(
                'LEX010',
                f'Archivo fuente excede {MAX_SOURCE_SIZE} bytes',
                1, 1,
            )
            return [Token(TokenType.EOF, '', 1, 1, 0)]

        tokens: list[Token] = []

        while self._pos < len(self._source):
            tok = self._next_token()
            if tok is not None:
                tokens.append(tok)

        tokens.append(Token(TokenType.EOF, '', self._line, self._col, 0))
        return tokens

    def _cur(self) -> Optional[str]:
        if self._pos < len(self._source):
            return self._source[self._pos]
        return None

    def _peek_next(self) -> Optional[str]:
        if self._pos + 1 < len(self._source):
            return self._source[self._pos + 1]
        return None

    def _advance(self) -> str:
        ch = self._source[self._pos]
        self._pos += 1
        if ch == '\n':
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _next_token(self) -> Optional[Token]:
        ch = self._cur()
        if ch is None:
            return None

        # Whitespace
        if ch in ' \t\r\n':
            self._advance()
            return None

        # Comments
        if ch == '/' and self._peek_next() == '/':
            while self._cur() is not None and self._cur() != '\n':
                self._advance()
            return None

        # Preprocessor directives — skip entire line silently
        if ch == '#':
            while self._cur() is not None and self._cur() != '\n':
                self._advance()
            return None

        if ch == '/' and self._peek_next() == '*':
            start_line, start_col = self._line, self._col
            self._advance()  # /
            self._advance()  # *
            while True:
                c = self._cur()
                if c is None:
                    self._reporter.add(
                        'LEX004', "Comentario de bloque '/*' sin cerrar",
                        start_line, start_col,
                    )
                    return None
                if c == '*' and self._peek_next() == '/':
                    self._advance()
                    self._advance()
                    return None
                self._advance()

        # String
        if ch == '"':
            return self._lex_string()

        # Char
        if ch == "'":
            return self._lex_char()

        # Numbers
        if ch.isdigit() or (ch == '.' and self._peek_next() is not None and self._peek_next().isdigit()):  # type: ignore[union-attr]
            return self._lex_number()

        # Identifiers / keywords / builtins
        if ch.isalpha() or ch == '_':
            return self._lex_ident()

        # Two-char operators first
        nxt = self._peek_next()
        two = ch + (nxt if nxt is not None else '')
        start_line, start_col = self._line, self._col

        two_map: dict[str, TokenType] = {
            '==': TokenType.EQ,
            '!=': TokenType.NEQ,
            '<=': TokenType.LE,
            '>=': TokenType.GE,
            '&&': TokenType.AND,
            '||': TokenType.OR,
            '++': TokenType.INC,
            '--': TokenType.DEC,
            '+=': TokenType.PLUS_ASSIGN,
            '-=': TokenType.MINUS_ASSIGN,
            '*=': TokenType.STAR_ASSIGN,
            '/=': TokenType.SLASH_ASSIGN,
            '%=': TokenType.PERCENT_ASSIGN,
        }
        if two in two_map:
            self._advance()
            self._advance()
            return Token(two_map[two], two, start_line, start_col, 2)

        one_map: dict[str, TokenType] = {
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.STAR,
            '/': TokenType.SLASH,
            '%': TokenType.PERCENT,
            '<': TokenType.LT,
            '>': TokenType.GT,
            '=': TokenType.ASSIGN,
            '!': TokenType.NOT,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            ';': TokenType.SEMICOLON,
            ',': TokenType.COMMA,
        }
        if ch in one_map:
            self._advance()
            return Token(one_map[ch], ch, start_line, start_col, 1)

        # Illegal character
        self._reporter.add(
            'LEX001',
            f"Caracter ilegal '{ch}'",
            self._line, self._col,
        )
        self._advance()
        return Token(TokenType.ERROR, ch, start_line, start_col, 1)

    def _lex_string(self) -> Token:
        start_line, start_col = self._line, self._col
        self._advance()  # opening "
        chars: list[str] = []
        too_long = False

        while True:
            c = self._cur()
            if c is None or c == '\n':
                self._reporter.add('LEX002', 'String literal no cerrado', start_line, start_col)
                return Token(TokenType.STRING_LIT, ''.join(chars), start_line, start_col,
                             self._col - start_col)
            if c == '"':
                self._advance()
                break
            if c == '\\':
                self._advance()
                esc = self._cur()
                if esc is None:
                    self._reporter.add('LEX002', 'String literal no cerrado', start_line, start_col)
                    break
                if esc in _ESCAPE_MAP:
                    chars.append(_ESCAPE_MAP[esc])
                    self._advance()
                else:
                    self._reporter.add(
                        'LEX007',
                        f"Secuencia de escape inválida: '\\{esc}'",
                        self._line, self._col,
                    )
                    chars.append(esc)
                    self._advance()
            else:
                chars.append(c)
                self._advance()

            if len(chars) > MAX_STRING_LEN and not too_long:
                too_long = True
                self._reporter.add(
                    'LEX008',
                    f'String literal excede {MAX_STRING_LEN} caracteres',
                    start_line, start_col,
                )

        value = ''.join(chars)
        return Token(TokenType.STRING_LIT, value, start_line, start_col,
                     self._col - start_col)

    def _lex_char(self) -> Token:
        start_line, start_col = self._line, self._col
        self._advance()  # opening '
        chars: list[str] = []

        while True:
            c = self._cur()
            if c is None or c == '\n':
                self._reporter.add(
                    'LEX003', "Char literal inválido (no cerrado)", start_line, start_col
                )
                return Token(TokenType.CHAR_LIT, '', start_line, start_col, 1)
            if c == "'":
                self._advance()
                break
            if c == '\\':
                self._advance()
                esc = self._cur()
                if esc is not None and esc in _ESCAPE_MAP:
                    chars.append(_ESCAPE_MAP[esc])
                    self._advance()
                else:
                    escaped = esc if esc is not None else ''
                    self._reporter.add(
                        'LEX007',
                        f"Secuencia de escape inválida: '\\{escaped}'",
                        self._line, self._col,
                    )
                    chars.append(escaped)
                    if esc is not None:
                        self._advance()
            else:
                chars.append(c)
                self._advance()

        if len(chars) == 0:
            self._reporter.add('LEX003', 'Char literal inválido (vacío)', start_line, start_col)
        elif len(chars) > 1:
            self._reporter.add(
                'LEX003', 'Char literal inválido (más de un carácter)', start_line, start_col
            )

        value = chars[0] if len(chars) == 1 else ''.join(chars)
        return Token(TokenType.CHAR_LIT, value, start_line, start_col,
                     self._col - start_col)

    def _lex_number(self) -> Token:
        start_line, start_col = self._line, self._col
        start_pos = self._pos
        is_float = False

        # Collect all chars of the number
        while True:
            ch = self._cur()
            if ch is None:
                break
            if ch.isdigit() or ch == '_':
                self._advance()
                continue
            if ch in '.eE':
                is_float = True
                self._advance()
                continue
            if ch in '+-':
                prev = self._source[self._pos - 1] if self._pos > 0 else ''
                if prev in 'eE':
                    self._advance()
                    continue
            break

        text = self._source[start_pos:self._pos]
        # Remove underscores used as separators (not standard C but defensive)
        clean = text.replace('_', '')

        if is_float or '.' in clean or 'e' in clean.lower():
            try:
                val = float(clean)
                if math.isinf(val) or math.isnan(val):
                    self._reporter.add(
                        'LEX012', 'Literal float fuera de rango o produce Inf/NaN',
                        start_line, start_col,
                    )
            except ValueError:
                self._reporter.add('LEX005', f"Número mal formado: '{text}'", start_line, start_col)
            return Token(TokenType.FLOAT_LIT, clean, start_line, start_col, len(text))
        else:
            try:
                val_int = int(clean)
                if val_int < INT64_MIN or val_int > INT64_MAX:
                    self._reporter.add(
                        'LEX011',
                        f'Literal entero fuera de rango int64 ({INT64_MIN}..{INT64_MAX})',
                        start_line, start_col,
                    )
            except ValueError:
                self._reporter.add('LEX005', f"Número mal formado: '{text}'", start_line, start_col)
            return Token(TokenType.INT_LIT, clean, start_line, start_col, len(text))

    def _lex_ident(self) -> Token:
        start_line, start_col = self._line, self._col
        start_pos = self._pos

        while self._cur() is not None and (self._cur().isalnum() or self._cur() == '_'):  # type: ignore[union-attr]
            self._advance()

        value = self._source[start_pos:self._pos]
        length = len(value)

        if length > MAX_IDENTIFIER_LEN:
            self._reporter.add(
                'LEX006',
                f'Identificador excede {MAX_IDENTIFIER_LEN} caracteres',
                start_line, start_col,
            )

        if value in KEYWORDS:
            return Token(_KEYWORD_MAP[value], value, start_line, start_col, length)
        if value in TYPE_KEYWORDS:
            return Token(TokenType.TYPE_KW, value, start_line, start_col, length)
        if value in BUILTINS:
            return Token(TokenType.BUILTIN, value, start_line, start_col, length)

        return Token(TokenType.IDENT, value, start_line, start_col, length)
