from __future__ import annotations

import flask.typing as ft
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO


def create_app() -> tuple[Flask, SocketIO]:
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    from .routes.compile import compile_bp
    from .routes.check import check_bp
    from .routes.convert import convert_bp
    from .routes.files import files_bp
    from .routes.explain import explain_bp
    from .routes.run import run_bp
    from .routes.debug import register_debug_events

    app.register_blueprint(compile_bp, url_prefix='/api')
    app.register_blueprint(check_bp, url_prefix='/api')
    app.register_blueprint(convert_bp, url_prefix='/api')
    app.register_blueprint(files_bp, url_prefix='/api')
    app.register_blueprint(explain_bp, url_prefix='/api')
    app.register_blueprint(run_bp, url_prefix='/api')
    register_debug_events(socketio)

    @app.errorhandler(Exception)
    def global_error_handler(e: Exception) -> ft.ResponseReturnValue:
        return jsonify({
            'ok': False,
            'errors': [{
                'code': 'SRV001',
                'message': str(e),
                'line': 0,
                'column': 0,
                'severity': 'error',
            }],
        }), 500

    return app, socketio
