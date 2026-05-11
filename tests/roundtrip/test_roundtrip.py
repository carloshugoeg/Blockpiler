from __future__ import annotations

import pytest
from compiler.ast_to_blocks import ast_to_blocks
from compiler.ast_to_c import ast_to_c
from compiler.blocks_to_ast import blocks_to_ast
from compiler.error_reporter import ErrorReporter
from compiler.lexer import Lexer
from compiler.parser import Parser

FIB = '''int fib(int n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}
int main() {
    println(fib(10));
    return 0;
}'''

FACTORIAL = '''int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
int main() {
    println(factorial(5));
    return 0;
}'''

BUBBLE_SORT = '''int main() {
    int arr[8] = {64, 34, 25, 12, 22, 11, 90, 7};
    int n = 8;
    int tmp = 0;
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                tmp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = tmp;
            }
        }
    }
    for (int i = 0; i < n; i++) {
        println(arr[i]);
    }
    return 0;
}'''

COLLATZ = '''int main() {
    int n = 27;
    int pasos = 0;
    while (n != 1) {
        if (n % 2 == 0) {
            n = n / 2;
        } else {
            n = n * 3 + 1;
        }
        pasos = pasos + 1;
    }
    println(pasos);
    return 0;
}'''

FIZZBUZZ = '''int main() {
    for (int i = 1; i <= 30; i++) {
        if (i % 15 == 0) {
            println("FizzBuzz");
        } else if (i % 3 == 0) {
            println("Fizz");
        } else if (i % 5 == 0) {
            println("Buzz");
        } else {
            println(i);
        }
    }
    return 0;
}'''

ARRAY_SUM = '''int main() {
    int nums[10] = {5, 12, 8, 3, 17, 6, 21, 9, 14, 2};
    int suma = 0;
    for (int i = 0; i < 10; i++) {
        suma += nums[i];
    }
    println(suma);
    return 0;
}'''

LINEAR_SEARCH = '''int main() {
    int arr[10] = {3, 7, 1, 9, 4, 6, 8, 2, 5, 10};
    int objetivo = 7;
    int resultado = -1;
    for (int i = 0; i < 10; i++) {
        if (arr[i] == objetivo) {
            resultado = i;
            break;
        }
    }
    println(resultado);
    return 0;
}'''

CALCULATOR = '''int main() {
    int a = 15;
    int b = 4;
    int op = 2;
    if (op == 1) {
        println(a + b);
    } else if (op == 2) {
        println(a - b);
    } else if (op == 3) {
        println(a * b);
    } else if (op == 4) {
        if (b != 0) {
            println(a / b);
        } else {
            println(0);
        }
    } else {
        println(0);
    }
    return 0;
}'''

ROUNDTRIP_PROGRAMS = [
    FIB, FACTORIAL, BUBBLE_SORT, COLLATZ,
    FIZZBUZZ, ARRAY_SUM, LINEAR_SEARCH, CALCULATOR,
]


def _parse(src: str):  # type: ignore[return]
    rep = ErrorReporter()
    tokens = Lexer(src, rep).tokenize()
    return Parser(tokens, rep).parse()


def _strip_preprocessor(c: str) -> str:
    """Remove #include lines that ast_to_c emits but our parser can't handle."""
    return '\n'.join(line for line in c.split('\n') if not line.startswith('#'))


@pytest.mark.parametrize("source", ROUNDTRIP_PROGRAMS)
def test_c_roundtrip_idempotent(source: str) -> None:
    """ast_to_c(parse(strip(ast_to_c(parse(src))))) == ast_to_c(parse(src))

    The #include directives emitted by ast_to_c are not part of our language
    grammar, so we strip them before the second parse. The includes are
    re-added by ast_to_c itself in _visit_program, making the result identical.
    """
    first_pass = ast_to_c(_parse(source))
    second_pass = ast_to_c(_parse(_strip_preprocessor(first_pass)))
    assert first_pass == second_pass, (
        "C roundtrip not idempotent.\n"
        f"First:\n{first_pass[:300]}\nSecond:\n{second_pass[:300]}"
    )


@pytest.mark.parametrize("source", ROUNDTRIP_PROGRAMS)
def test_blocks_roundtrip_preserves_c(source: str) -> None:
    """ast_to_c(blocks_to_ast(ast_to_blocks(parse(src)))) == ast_to_c(parse(src))"""
    original_ast = _parse(source)
    expected_c = ast_to_c(original_ast)

    workspace = ast_to_blocks(original_ast)
    rep = ErrorReporter()
    reconstructed_ast = blocks_to_ast(workspace, rep)
    assert not rep.has_errors, f"blocks_to_ast errors: {rep.errors}"
    reconstructed_c = ast_to_c(reconstructed_ast)

    assert reconstructed_c == expected_c, (
        "Blocks roundtrip produced different C.\n"
        f"Expected:\n{expected_c[:300]}\nGot:\n{reconstructed_c[:300]}"
    )
