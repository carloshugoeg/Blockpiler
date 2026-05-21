from __future__ import annotations

import flask.typing as ft
from flask import Blueprint, jsonify, request

from compiler.ast_guard import validate_ast_limits
from compiler.error_reporter import ErrorReporter
from compiler.interpreter import Interpreter, InterpreterError
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer

run_bp = Blueprint('run', __name__)


@run_bp.post('/run')
def run_source() -> ft.ResponseReturnValue:
    data = request.get_json(force=True) or {}
    source: str = data.get('source', '')
    stdin_data: str = data.get('stdin', '')

    reporter = ErrorReporter()

    tokens = Lexer(source, reporter).tokenize()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    program = Parser(tokens, reporter).parse()
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200
    if not validate_ast_limits(program, reporter):
        return jsonify(reporter.to_response(ok=False)), 200

    SemanticAnalyzer(reporter).analyze(program, mode='compile')
    if reporter.has_errors:
        return jsonify(reporter.to_response(ok=False)), 200

    lines = iter(stdin_data.split('\n')) if stdin_data.strip() else iter([])

    def input_fn() -> str:
        try:
            return next(lines)
        except StopIteration:
            return ''

    try:
        stdout, returncode = Interpreter(program, input_fn=input_fn).run()
        return jsonify({
            'ok': True,
            'data': {
                'stdout': stdout,
                'returncode': returncode,
                'warnings': [w.to_dict() for w in reporter.warnings],
            },
        }), 200
    except InterpreterError as e:
        return jsonify({
            'ok': False,
            'errors': [{'code': 'INT001', 'message': str(e),
                        'line': 0, 'column': 0, 'severity': 'error'}],
        }), 200
