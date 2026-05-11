from __future__ import annotations

import flask.typing as ft
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from compiler.ast_to_blocks import ASTtoBlocks
from compiler.ast_to_c import ASTtoC
from compiler.blocks_to_ast import BlocksToAST
from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer
from compiler.parser import Parser
from server.validators import ConvertRequest

convert_bp = Blueprint('convert', __name__)


@convert_bp.post('/convert')
def convert() -> ft.ResponseReturnValue:
    try:
        req = ConvertRequest.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({'ok': False, 'errors': e.errors()}), 422

    if req.direction == 'c_to_blocks':
        reporter = ErrorReporter()

        tokens = Lexer(req.source, reporter).tokenize()
        if reporter.has_errors:
            return jsonify(reporter.to_response(ok=False)), 200

        program = Parser(tokens, reporter).parse()
        if reporter.has_errors:
            return jsonify(reporter.to_response(ok=False)), 200

        workspace = ASTtoBlocks().convert(program)
        return jsonify({'ok': True, 'data': {'workspace': workspace}}), 200

    else:  # blocks_to_c
        reporter = ErrorReporter()

        program = BlocksToAST(reporter).convert(req.workspace)
        if reporter.has_errors:
            return jsonify(reporter.to_response(ok=False)), 200

        source = ASTtoC().generate(program)
        return jsonify({'ok': True, 'data': {'source': source}}), 200
