from __future__ import annotations

import dataclasses
import uuid
from typing import Any

import flask.typing as ft
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from compiler.codegen import CodeGenerator
from compiler.error_reporter import ErrorReporter
from compiler.executor import Executor
from compiler.explainer import Explainer
from compiler.lexer import Lexer
from compiler.optimizer import Optimizer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from server.validators import CompileRequest

compile_bp = Blueprint('compile', __name__)


def _serialize_node(obj: Any) -> Any:
    """Recursively convert AST dataclass nodes to JSON-serialisable dicts.
    Each dataclass node gets a 'type' key with its class name so the
    frontend ASTViewer can build a labelled D3 tree."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result: dict[str, Any] = {'type': type(obj).__name__}
        for f in dataclasses.fields(obj):
            result[f.name] = _serialize_node(getattr(obj, f.name))
        return result
    if isinstance(obj, list):
        return [_serialize_node(item) for item in obj]
    if isinstance(obj, tuple):
        return [_serialize_node(item) for item in obj]
    return obj


@compile_bp.post('/compile')
def compile_source() -> ft.ResponseReturnValue:
    try:
        req = CompileRequest.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({'ok': False, 'errors': e.errors()}), 422

    reporter = ErrorReporter()

    tokens = Lexer(req.source, reporter).tokenize()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    program = Parser(tokens, reporter).parse()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    SemanticAnalyzer(reporter).analyze(program, mode='compile')
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    ast_data = _serialize_node(program)

    program = Optimizer(level=req.optimization_level).optimize(program)
    assembly, line_map = CodeGenerator().generate(program)

    result = Executor().assemble_and_run(assembly, str(uuid.uuid4()), req.stdin or '')

    explanation: str | None = Explainer().explain(program) if req.include_explanation else None

    return jsonify({
        'ok': True,
        'data': {
            'assembly': assembly,
            'ast': ast_data,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'line_map': {str(k): v for k, v in line_map.items()},
            'warnings': [w.to_dict() for w in reporter.warnings],
            'explanation': explanation,
        },
    }), 200
