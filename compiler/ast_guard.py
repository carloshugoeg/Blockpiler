from __future__ import annotations

import dataclasses
from typing import Any

from compiler.ast_nodes import SourcePos
from compiler.error_reporter import ErrorReporter
from compiler.limits import MAX_NESTING_DEPTH


def validate_ast_limits(program: Any, reporter: ErrorReporter) -> bool:
    """Validate AST shape without recursion so hostile inputs cannot crash later passes."""
    stack: list[tuple[Any, int]] = [(program, 0)]

    while stack:
        node, depth = stack.pop()
        if depth > MAX_NESTING_DEPTH:
            pos = _node_pos(node)
            reporter.add(
                'PAR009',
                f'Profundidad de anidamiento excede el máximo ({MAX_NESTING_DEPTH})',
                pos.line,
                pos.col,
            )
            return False

        if isinstance(node, SourcePos):
            continue
        if isinstance(node, (str, int, float, bool, type(None))):
            continue
        if isinstance(node, (list, tuple)):
            for item in reversed(node):
                stack.append((item, depth + 1))
            continue
        if dataclasses.is_dataclass(node) and not isinstance(node, type):
            for field in reversed(dataclasses.fields(node)):
                stack.append((getattr(node, field.name), depth + 1))

    return not reporter.has_errors


def _node_pos(node: Any) -> SourcePos:
    pos = getattr(node, 'pos', None)
    return pos if isinstance(pos, SourcePos) else SourcePos(0, 0)
