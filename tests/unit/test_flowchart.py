from compiler.error_reporter import ErrorReporter
from compiler.flowchart import FlowchartGenerator
from compiler.lexer import Lexer
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer


def flowchart_for(source: str) -> str:
    reporter = ErrorReporter()
    tokens = Lexer(source, reporter).tokenize()
    program = Parser(tokens, reporter).parse()
    SemanticAnalyzer(reporter).analyze(program, mode='check')
    assert reporter.errors == []
    return FlowchartGenerator().generate(program)


def test_print_and_println_are_rendered() -> None:
    chart = flowchart_for(
        'int main() { print(1); println(2); return 0; }',
    )
    assert 'flowchart TD' in chart
    assert 'print(1)' in chart
    assert 'println(2)' in chart
    assert 'return 0' in chart


def test_if_else_creates_decision_and_join() -> None:
    chart = flowchart_for(
        'int main() { if (true) { println(1); } else { println(0); } return 0; }',
    )
    assert 'if: true' in chart
    assert 'Fin if' in chart
    assert '-- "Si" -->' in chart
    assert '-- "No" -->' in chart


def test_while_creates_loop_back_edge() -> None:
    chart = flowchart_for(
        'int main() { int i = 0; while (i < 3) { println(i); i = i + 1; } return 0; }',
    )
    assert 'while: (i &lt; 3)' in chart
    assert 'Cuerpo while' in chart
    assert 'Fin while' in chart


def test_for_creates_init_condition_update_and_body() -> None:
    chart = flowchart_for(
        'int main() { for (int i = 0; i < 3; i++) { println(i); } return 0; }',
    )
    assert 'for init: int i = 0' in chart
    assert 'for: (i &lt; 3)' in chart
    assert 'for update: (i++)' in chart
    assert 'Cuerpo for' in chart
