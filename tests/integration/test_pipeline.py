from __future__ import annotations

from compiler.error_reporter import ErrorReporter
from compiler.interpreter import Interpreter
from compiler.lexer import Lexer
from compiler.optimizer import Optimizer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer

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


def _run_via_interp(source: str, opt_level: int = 1) -> tuple[str, int]:
    rep = ErrorReporter()
    tokens = Lexer(source, rep).tokenize()
    ast = Parser(tokens, rep).parse()
    SemanticAnalyzer(rep).analyze(ast)
    assert not rep.has_errors, f"Compile errors: {rep.errors}"
    optimized = Optimizer(level=opt_level).optimize(ast)
    return Interpreter(optimized).run()


def _fizzbuzz_expected() -> str:
    parts = []
    for i in range(1, 31):
        if i % 15 == 0:
            parts.append("FizzBuzz")
        elif i % 3 == 0:
            parts.append("Fizz")
        elif i % 5 == 0:
            parts.append("Buzz")
        else:
            parts.append(str(i))
    return "\n".join(parts) + "\n"


def test_pipeline_fibonacci() -> None:
    stdout, rc = _run_via_interp(FIB)
    assert stdout == "55\n"
    assert rc == 0


def test_pipeline_factorial() -> None:
    stdout, rc = _run_via_interp(FACTORIAL)
    assert stdout == "120\n"
    assert rc == 0


def test_pipeline_bubble_sort() -> None:
    stdout, rc = _run_via_interp(BUBBLE_SORT)
    assert stdout == "7\n11\n12\n22\n25\n34\n64\n90\n"
    assert rc == 0


def test_pipeline_collatz() -> None:
    stdout, rc = _run_via_interp(COLLATZ)
    assert stdout == "111\n"
    assert rc == 0


def test_pipeline_fizzbuzz() -> None:
    stdout, rc = _run_via_interp(FIZZBUZZ)
    assert stdout == _fizzbuzz_expected()
    assert rc == 0


def test_pipeline_array_sum() -> None:
    stdout, rc = _run_via_interp(ARRAY_SUM)
    assert stdout == "97\n"
    assert rc == 0


def test_pipeline_linear_search() -> None:
    stdout, rc = _run_via_interp(LINEAR_SEARCH)
    assert stdout == "1\n"
    assert rc == 0


def test_pipeline_calculator() -> None:
    stdout, rc = _run_via_interp(CALCULATOR)
    assert stdout == "11\n"
    assert rc == 0
