from __future__ import annotations

from flask import request
from flask_socketio import SocketIO, emit
from pydantic import ValidationError

from compiler.ast_guard import validate_ast_limits
from compiler.error_reporter import ErrorReporter
from compiler.interpreter import DebugState, Interpreter
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from server.validators import DebugStartRequest

_sessions: dict[str, Interpreter] = {}


def _state_dict(state: DebugState) -> dict[str, object]:
    return {
        'line': state.line,
        'col': state.col,
        'variables': state.variables,
        'call_stack': state.call_stack,
        'stdout': state.stdout,
        'finished': state.finished,
        'return_code': state.return_code,
    }


def register_debug_events(socketio: SocketIO) -> None:
    @socketio.on('debug:start')  # type: ignore[untyped-decorator]
    def on_debug_start(data: dict[str, object]) -> None:
        try:
            req = DebugStartRequest.model_validate(data)
        except ValidationError as e:
            emit('debug:error', {'errors': e.errors()})
            return

        reporter = ErrorReporter()

        tokens = Lexer(req.source, reporter).tokenize()
        if reporter.has_errors:
            emit('debug:error', reporter.to_response(ok=False))
            return

        program = Parser(tokens, reporter).parse()
        if reporter.has_errors:
            emit('debug:error', reporter.to_response(ok=False))
            return
        if not validate_ast_limits(program, reporter):
            emit('debug:error', reporter.to_response(ok=False))
            return

        SemanticAnalyzer(reporter).analyze(program, mode='check')
        if reporter.has_errors:
            emit('debug:error', reporter.to_response(ok=False))
            return

        sid: str = request.sid  # type: ignore[attr-defined]
        interp = Interpreter(program)
        interp.start_debug()
        _sessions[sid] = interp
        emit('debug:state', _state_dict(interp.get_state()))

    @socketio.on('debug:step')  # type: ignore[untyped-decorator]
    def on_debug_step() -> None:
        sid: str = request.sid  # type: ignore[attr-defined]
        interp = _sessions.get(sid)
        if interp is None:
            emit('debug:error', {'message': 'No active debug session'})
            return
        emit('debug:state', _state_dict(interp.step()))

    @socketio.on('debug:continue')  # type: ignore[untyped-decorator]
    def on_debug_continue(data: dict[str, object]) -> None:
        sid: str = request.sid  # type: ignore[attr-defined]
        interp = _sessions.get(sid)
        if interp is None:
            emit('debug:error', {'message': 'No active debug session'})
            return
        raw = data.get('breakpoints', [])
        breakpoints: set[int] = set(raw) if isinstance(raw, list) else set()
        emit('debug:state', _state_dict(interp.continue_to_breakpoint(breakpoints)))

    @socketio.on('debug:stop')  # type: ignore[untyped-decorator]
    def on_debug_stop() -> None:
        sid: str = request.sid  # type: ignore[attr-defined]
        _sessions.pop(sid, None)

    @socketio.on('disconnect')  # type: ignore[untyped-decorator]
    def on_disconnect() -> None:
        sid: str = request.sid  # type: ignore[attr-defined]
        _sessions.pop(sid, None)
