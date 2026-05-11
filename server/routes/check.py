from __future__ import annotations

import flask.typing as ft
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from server.validators import CheckRequest

check_bp = Blueprint('check', __name__)


@check_bp.post('/check')
def check_source() -> ft.ResponseReturnValue:
    try:
        req = CheckRequest.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({'ok': False, 'errors': e.errors()}), 422

    reporter = ErrorReporter()

    tokens = Lexer(req.source, reporter).tokenize()
    if reporter.has_errors:
        return jsonify(reporter.to_response()), 200

    program = Parser(tokens, reporter).parse()
    if reporter.has_errors:
        return jsonify(reporter.to_response()), 200

    symbol_table = SemanticAnalyzer(reporter).analyze(program, mode='check')

    resp = reporter.to_response()
    if not reporter.has_errors:
        resp['symbol_table'] = symbol_table.to_dict()
    return jsonify(resp), 200
