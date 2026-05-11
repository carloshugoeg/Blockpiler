import pytest
from pydantic import ValidationError

from server.validators import (
    CheckRequest,
    CompileRequest,
    ConvertRequest,
    ValidateFileRequest,
)


def test_compile_request_valid() -> None:
    req = CompileRequest(source='int main() { return 0; }')
    assert req.source == 'int main() { return 0; }'
    assert req.optimization_level == 1
    assert req.stdin == ''
    assert req.include_explanation is False


def test_compile_request_empty_source_ok() -> None:
    req = CompileRequest(source='')
    assert req.source == ''


def test_compile_request_source_too_long() -> None:
    with pytest.raises(ValidationError):
        CompileRequest(source='x' * (524_288 + 1))


def test_compile_request_optimization_level_out_of_range() -> None:
    with pytest.raises(ValidationError):
        CompileRequest(source='int main(){}', optimization_level=4)
    with pytest.raises(ValidationError):
        CompileRequest(source='int main(){}', optimization_level=-1)


def test_convert_request_invalid_direction() -> None:
    with pytest.raises(ValidationError):
        ConvertRequest(direction='invalid_direction')


def test_validate_file_request_invalid_file_type() -> None:
    with pytest.raises(ValidationError):
        ValidateFileRequest(filename='test.py', content='print(1)', file_type='py')


def test_check_request_valid() -> None:
    req = CheckRequest(source='int main() { return 0; }')
    assert req.source == 'int main() { return 0; }'
