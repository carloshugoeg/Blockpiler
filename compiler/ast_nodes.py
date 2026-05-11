from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

CType = Literal['int', 'float', 'char', 'bool', 'string', 'void', 'unknown']


@dataclass
class SourcePos:
    line: int
    col: int
    length: int = 1


# ─── Top-level ─────────────────────────────────────────────────────────────────

@dataclass
class Program:
    declarations: list[Any]   # FunctionDecl | VarDecl | ArrayDecl
    pos: SourcePos


# ─── Declaraciones ─────────────────────────────────────────────────────────────

@dataclass
class FunctionDecl:
    name: str
    return_type: CType
    params: list[Parameter]
    body: Block
    pos: SourcePos


@dataclass
class Parameter:
    name: str
    type: CType
    pos: SourcePos


@dataclass
class VarDecl:
    name: str
    type: CType
    init_expr: Optional[Any]
    pos: SourcePos


@dataclass
class ArrayDecl:
    name: str
    element_type: CType
    size: int
    init_list: list[Any]
    pos: SourcePos


# ─── Statements ────────────────────────────────────────────────────────────────

@dataclass
class Block:
    stmts: list[Any]
    pos: SourcePos


@dataclass
class IfStmt:
    condition: Any
    then_body: Block
    elif_clauses: list[tuple[Any, Block]]
    else_body: Optional[Block]
    pos: SourcePos


@dataclass
class WhileStmt:
    condition: Any
    body: Block
    pos: SourcePos


@dataclass
class ForStmt:
    init: Optional[Any]        # VarDecl | AssignOp | ExprStmt | None
    condition: Optional[Any]
    update: Optional[Any]
    body: Block
    pos: SourcePos


@dataclass
class DoWhileStmt:
    body: Block
    condition: Any
    pos: SourcePos


@dataclass
class ReturnStmt:
    value: Optional[Any]
    pos: SourcePos


@dataclass
class BreakStmt:
    pos: SourcePos


@dataclass
class ContinueStmt:
    pos: SourcePos


@dataclass
class PrintStmt:
    expr: Any
    newline: bool
    pos: SourcePos


@dataclass
class ExprStmt:
    expr: Any
    pos: SourcePos


# ─── Expresiones ───────────────────────────────────────────────────────────────

@dataclass
class BinaryOp:
    op: str   # '+','-','*','/','%','==','!=','<','>','<=','>=','&&','||'
              # Internos del optimizador: '<<','>>','&'
    left: Any
    right: Any
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class UnaryOp:
    op: str          # '!','-','++','--'
    operand: Any
    prefix: bool
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class AssignOp:
    op: str          # '=','+=','-=','*=','/=','%='
    target: Any      # Identifier | IndexExpr
    value: Any
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class CallExpr:
    name: str
    args: list[Any]
    inferred_type: CType = 'unknown'
    is_tail_call: bool = False
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class IndexExpr:
    name: str
    index: Any
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class Identifier:
    name: str
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class IntLiteral:
    value: int
    inferred_type: CType = 'int'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class FloatLiteral:
    value: float
    inferred_type: CType = 'float'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class StringLiteral:
    value: str
    inferred_type: CType = 'string'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class CharLiteral:
    value: str       # exactamente 1 carácter
    inferred_type: CType = 'char'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class BoolLiteral:
    value: bool
    inferred_type: CType = 'bool'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class InputExpr:
    variant: Literal['string', 'int', 'float'] = 'string'
    inferred_type: CType = 'string'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


@dataclass
class CastExpr:
    target_type: CType
    expr: Any
    inferred_type: CType = 'unknown'
    pos: SourcePos = field(default_factory=lambda: SourcePos(0, 0))


# ─── Utilitarios ───────────────────────────────────────────────────────────────

EXPR_TYPES = (
    BinaryOp, UnaryOp, AssignOp, CallExpr, IndexExpr, Identifier,
    IntLiteral, FloatLiteral, StringLiteral, CharLiteral,
    BoolLiteral, InputExpr, CastExpr,
)


def is_expression(node: Any) -> bool:
    return isinstance(node, EXPR_TYPES)


def get_pos(node: Any) -> SourcePos:
    return getattr(node, 'pos', SourcePos(0, 0))


def node_type_name(node: Any) -> str:
    return type(node).__name__


def is_lvalue(node: Any) -> bool:
    return isinstance(node, (Identifier, IndexExpr))


def is_pure_expr(node: Any) -> bool:
    """True si evaluar `node` no tiene side effects.

    Literales y Identifiers son puros. BinaryOp/UnaryOp son puros si sus
    hijos lo son, EXCEPTO UnaryOp con '++' o '--'. CallExpr e InputExpr
    NUNCA son puros (asumimos peor caso). AssignOp nunca es puro.
    """
    if isinstance(node, (IntLiteral, FloatLiteral, StringLiteral,
                         CharLiteral, BoolLiteral, Identifier)):
        return True
    if isinstance(node, UnaryOp):
        if node.op in ('++', '--'):
            return False
        return is_pure_expr(node.operand)
    if isinstance(node, BinaryOp):
        return is_pure_expr(node.left) and is_pure_expr(node.right)
    if isinstance(node, CastExpr):
        return is_pure_expr(node.expr)
    if isinstance(node, IndexExpr):
        return is_pure_expr(node.index)
    # CallExpr, InputExpr, AssignOp: impuros
    return False
