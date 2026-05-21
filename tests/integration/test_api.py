from __future__ import annotations

from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from server.app import create_app

SIMPLE_PROG = 'int main() { return 0; }'
DEEP_EXPR_PROG = 'int main() { int x = ' + '1 + ' * 600 + '1; return 0; }'


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


@pytest.mark.parametrize('endpoint', ['/api/check', '/api/run', '/api/compile', '/api/explain'])
def test_deep_expression_returns_par009_not_500(client: FlaskClient, endpoint: str) -> None:
    resp = client.post(endpoint, json={'source': DEEP_EXPR_PROG})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert data['errors'][0]['code'] == 'PAR009'


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


def test_compile_rejects_printf_builtin(client: FlaskClient) -> None:
    resp = client.post('/api/compile', json={
        'source': 'int main() { printf("Hola mundo"); return 0; }',
        'include_explanation': True,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert len(data['errors']) > 0


def test_compile_missing_source(client: FlaskClient) -> None:
    resp = client.post('/api/compile', json={})
    assert resp.status_code == 422


# ── /api/convert ─────────────────────────────────────────────────────────────

def test_run_rejects_printf_builtin(client: FlaskClient) -> None:
    resp = client.post('/api/run', json={
        'source': 'int main() { printf("Hola %d", 7); return 0; }',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert len(data['errors']) > 0


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


def test_convert_c_to_blocks_deep_expression_returns_par009_not_500(
    client: FlaskClient,
) -> None:
    resp = client.post('/api/convert', json={
        'direction': 'c_to_blocks',
        'source': DEEP_EXPR_PROG,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert data['errors'][0]['code'] == 'PAR009'


def test_convert_blocks_to_c_deep_expression_returns_par009_not_500(
    client: FlaskClient,
) -> None:
    expr = {'type': 'c_lit_int', 'fields': {'VALUE': 1}}
    for _ in range(600):
        expr = {
            'type': 'c_binary_arith',
            'fields': {'OP': '+'},
            'inputs': {
                'LEFT': {'block': expr},
                'RIGHT': {'block': {'type': 'c_lit_int', 'fields': {'VALUE': 1}}},
            },
        }
    workspace = {
        'blocks': {
            'blocks': [{
                'type': 'c_func_decl',
                'fields': {'NAME': 'main', 'TYPE': 'int'},
                'inputs': {
                    'BODY': {
                        'block': {
                            'type': 'c_return',
                            'inputs': {'VALUE': {'block': expr}},
                        },
                    },
                },
            }],
        },
    }
    resp = client.post('/api/convert', json={
        'direction': 'blocks_to_c',
        'workspace': workspace,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert data['errors'][0]['code'] == 'PAR009'


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


# ── /api/flowchart ───────────────────────────────────────────────────────────

def test_flowchart_generates_mermaid(client: FlaskClient) -> None:
    resp = client.post('/api/flowchart', json={
        'source': 'int main() { for (int i = 0; i < 2; i++) { println(i); } return 0; }',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['data']['mermaid'].startswith('flowchart TD')
    assert 'for init' in data['data']['mermaid']
    assert 'println(i)' in data['data']['mermaid']


def test_flowchart_reports_compile_errors(client: FlaskClient) -> None:
    resp = client.post('/api/flowchart', json={'source': 'int main() { println("x") '})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert len(data['errors']) > 0


# ── Global error handler ─────────────────────────────────────────────────────

def test_global_error_handler_returns_srv001(client: FlaskClient) -> None:
    with patch('server.routes.check.Lexer', side_effect=RuntimeError('boom')):
        resp = client.post('/api/check', json={'source': SIMPLE_PROG})
    assert resp.status_code == 500
    data = resp.get_json()
    assert data['ok'] is False
    assert data['errors'][0]['code'] == 'SRV001'
