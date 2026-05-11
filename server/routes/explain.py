from __future__ import annotations

import flask.typing as ft
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from compiler.error_reporter import ErrorReporter
from compiler.explainer import Explainer
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from server.validators import ExplainRequest

explain_bp = Blueprint('explain', __name__)


@explain_bp.post('/explain')
def explain() -> ft.ResponseReturnValue:
    try:
        req = ExplainRequest.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({'ok': False, 'errors': e.errors()}), 422

    reporter = ErrorReporter()

    tokens = Lexer(req.source, reporter).tokenize()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    program = Parser(tokens, reporter).parse()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    SemanticAnalyzer(reporter).analyze(program, mode='check')
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    explanation = Explainer().explain(program)
    return jsonify({'ok': True, 'data': {'explanation': explanation}}), 200
