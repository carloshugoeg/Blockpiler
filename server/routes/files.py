from __future__ import annotations

import flask.typing as ft
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from server.validators import ValidateFileRequest

files_bp = Blueprint('files', __name__)


@files_bp.post('/validate-file')
def validate_file() -> ft.ResponseReturnValue:
    try:
        req = ValidateFileRequest.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({'ok': False, 'errors': e.errors()}), 422

    return jsonify({'ok': True, 'content': req.content}), 200
