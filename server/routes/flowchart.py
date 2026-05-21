from __future__ import annotations

import flask.typing as ft
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from compiler.ast_guard import validate_ast_limits
from compiler.error_reporter import ErrorReporter
from compiler.flowchart import FlowchartGenerator
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from server.validators import FlowchartRequest

flowchart_bp = Blueprint('flowchart', __name__)


@flowchart_bp.post('/flowchart')
def flowchart_source() -> ft.ResponseReturnValue:
    try:
        req = FlowchartRequest.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({'ok': False, 'errors': e.errors()}), 422

    reporter = ErrorReporter()
    tokens = Lexer(req.source, reporter).tokenize()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    program = Parser(tokens, reporter).parse()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200
    if not validate_ast_limits(program, reporter):
        return jsonify(reporter.to_response(ok=False)), 200

    SemanticAnalyzer(reporter).analyze(program, mode='check')
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    mermaid = FlowchartGenerator().generate(program)
    return jsonify({
        'ok': True,
        'data': {
            'mermaid': mermaid,
            'warnings': [w.to_dict() for w in reporter.warnings],
        },
    }), 200
