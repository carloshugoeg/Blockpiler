from compiler.error_reporter import CompileError, ErrorReporter
from compiler.limits import MAX_ERRORS


def make_reporter() -> ErrorReporter:
    return ErrorReporter()


def test_add_error_goes_to_errors() -> None:
    r = make_reporter()
    r.add('E001', 'msg', 1, 1, severity='error')
    assert len(r.errors) == 1
    assert len(r.warnings) == 0


def test_add_warning_goes_to_warnings() -> None:
    r = make_reporter()
    r.add('W001', 'msg', 1, 1, severity='warning')
    assert len(r.warnings) == 1
    assert len(r.errors) == 0


def test_add_info_goes_to_warnings() -> None:
    r = make_reporter()
    r.add('I001', 'msg', 1, 1, severity='info')
    assert len(r.warnings) == 1
    assert len(r.errors) == 0


def test_max_errors_limit_reached() -> None:
    r = make_reporter()
    for i in range(MAX_ERRORS):
        r.add('E001', 'msg', i + 1, 1, severity='error')
    assert r.error_limit_reached is True
    assert len(r.errors) == MAX_ERRORS


def test_no_more_errors_after_limit() -> None:
    r = make_reporter()
    for i in range(MAX_ERRORS + 5):
        r.add('E001', 'msg', i + 1, 1, severity='error')
    assert len(r.errors) == MAX_ERRORS


def test_warnings_still_accumulate_after_limit() -> None:
    r = make_reporter()
    for i in range(MAX_ERRORS):
        r.add('E001', 'msg', i + 1, 1, severity='error')
    r.add('W001', 'warn', 999, 1, severity='warning')
    assert len(r.warnings) == 1


def test_has_errors_false_when_empty() -> None:
    r = make_reporter()
    assert r.has_errors is False


def test_has_errors_true_when_errors() -> None:
    r = make_reporter()
    r.add('E001', 'msg', 1, 1, severity='error')
    assert r.has_errors is True


def test_to_response_ok_false_with_errors() -> None:
    r = make_reporter()
    r.add('E001', 'msg', 1, 1, severity='error')
    resp = r.to_response()
    assert resp['ok'] is False
    assert len(resp['errors']) == 1  # type: ignore[arg-type]


def test_to_response_ok_true_no_errors() -> None:
    r = make_reporter()
    resp = r.to_response()
    assert resp['ok'] is True


def test_to_response_explicit_ok_override() -> None:
    r = make_reporter()
    r.add('E001', 'msg', 1, 1, severity='error')
    resp = r.to_response(ok=True)
    assert resp['ok'] is True


def test_all_issues_sorted_by_line_col() -> None:
    r = make_reporter()
    r.add('E001', 'msg', 5, 3, severity='error')
    r.add('W001', 'warn', 2, 1, severity='warning')
    r.add('E002', 'msg', 5, 1, severity='error')
    issues = r.all_issues
    assert issues[0].line == 2
    assert issues[1].line == 5 and issues[1].column == 1
    assert issues[2].line == 5 and issues[2].column == 3


def test_to_dict_without_suggestion() -> None:
    e = CompileError('E001', 'msg', 1, 1, 1, 'error')
    d = e.to_dict()
    assert 'suggestion' not in d
    assert d['code'] == 'E001'
    assert d['severity'] == 'error'


def test_to_dict_with_suggestion() -> None:
    e = CompileError('E001', 'msg', 1, 1, 1, 'error', suggestion='fix it')
    d = e.to_dict()
    assert d['suggestion'] == 'fix it'


def test_to_dict_exact_format() -> None:
    e = CompileError('LEX002', 'String literal no cerrado', 5, 12, 1, 'error',
                     suggestion='Agrega un cierre')
    d = e.to_dict()
    assert d == {
        'code': 'LEX002',
        'message': 'String literal no cerrado',
        'line': 5,
        'column': 12,
        'length': 1,
        'severity': 'error',
        'suggestion': 'Agrega un cierre',
    }
