from __future__ import annotations

from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from server.app import create_app

SIMPLE_PROG = 'int main() { return 0; }'


@pytest.fixture
def client() -> FlaskClient:
    app, _ = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c  # type: ignore[misc]


# ── /api/check ───────────────────────────────────────────────────────────────

def test_check_valid(client: FlaskClient) -> None:
    resp = client.post('/api/check', json={'source': SIMPLE_PROG})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['errors'] == []


def test_check_invalid(client: FlaskClient) -> None:
    resp = client.post('/api/check', json={'source': 'int x = "hello";'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert len(data['errors']) > 0


def test_check_returns_symbol_table(client: FlaskClient) -> None:
    resp = client.post('/api/check', json={'source': SIMPLE_PROG})
    data = resp.get_json()
    assert 'symbol_table' in data


def test_check_missing_source(client: FlaskClient) -> None:
    resp = client.post('/api/check', json={})
    assert resp.status_code == 422


# ── /api/compile ─────────────────────────────────────────────────────────────

def test_compile_simple(client: FlaskClient) -> None:
    resp = client.post('/api/compile', json={'source': SIMPLE_PROG})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert 'data' in data
    assert 'stdout' in data['data']
    assert 'assembly' in data['data']
    assert 'returncode' in data['data']


def test_compile_semantic_errors(client: FlaskClient) -> None:
    resp = client.post('/api/compile', json={'source': 'int x = "hello";'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert len(data['errors']) > 0


def test_compile_accepts_printf_builtin(client: FlaskClient) -> None:
    resp = client.post('/api/compile', json={
        'source': 'int main() { printf("Hola mundo"); return 0; }',
        'include_explanation': True,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert 'ast' in data['data']
    assert 'printf' in data['data']['assembly']


def test_compile_missing_source(client: FlaskClient) -> None:
    resp = client.post('/api/compile', json={})
    assert resp.status_code == 422


# ── /api/convert ─────────────────────────────────────────────────────────────

def test_run_accepts_printf_builtin(client: FlaskClient) -> None:
    resp = client.post('/api/run', json={
        'source': 'int main() { printf("Hola %d", 7); return 0; }',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['data']['stdout'] == 'Hola 7'


def test_convert_c_to_blocks(client: FlaskClient) -> None:
    resp = client.post('/api/convert', json={
        'direction': 'c_to_blocks',
        'source': SIMPLE_PROG,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert isinstance(data['data']['workspace'], dict)


def test_convert_function_params_emit_param_blocks(client: FlaskClient) -> None:
    resp = client.post('/api/convert', json={
        'direction': 'c_to_blocks',
        'source': 'int factorial(int n) { return n; }',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    blocks = data['data']['workspace']['blocks']['blocks']
    params = blocks[0]['inputs']['PARAMS']['block']
    assert params['type'] == 'c_param'


def test_convert_invalid_direction(client: FlaskClient) -> None:
    resp = client.post('/api/convert', json={
        'direction': 'unknown',
        'source': SIMPLE_PROG,
    })
    assert resp.status_code == 422


# ── /api/validate-file ───────────────────────────────────────────────────────

def test_validate_file_valid(client: FlaskClient) -> None:
    resp = client.post('/api/validate-file', json={
        'filename': 'prog.c',
        'content': SIMPLE_PROG,
        'file_type': 'c',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['content'] == SIMPLE_PROG


def test_validate_file_invalid_type(client: FlaskClient) -> None:
    resp = client.post('/api/validate-file', json={
        'filename': 'prog.exe',
        'content': '',
        'file_type': 'exe',
    })
    assert resp.status_code == 422


# ── /api/explain ─────────────────────────────────────────────────────────────

def test_explain(client: FlaskClient) -> None:
    resp = client.post('/api/explain', json={'source': SIMPLE_PROG})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert isinstance(data['data']['explanation'], str)
    assert len(data['data']['explanation']) > 0


def test_explain_missing_source(client: FlaskClient) -> None:
    resp = client.post('/api/explain', json={})
    assert resp.status_code == 422


# ── Global error handler ─────────────────────────────────────────────────────

def test_global_error_handler_returns_srv001(client: FlaskClient) -> None:
    with patch('server.routes.check.Lexer', side_effect=RuntimeError('boom')):
        resp = client.post('/api/check', json={'source': SIMPLE_PROG})
    assert resp.status_code == 500
    data = resp.get_json()
    assert data['ok'] is False
    assert data['errors'][0]['code'] == 'SRV001'
