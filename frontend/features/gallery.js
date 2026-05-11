const EXAMPLES = [
    {
        name: 'Hola Mundo',
        source: `int main() {
    println("Hola, mundo!");
    return 0;
}`,
    },
    {
        name: 'Fibonacci (recursivo)',
        source: `int fib(int n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

int main() {
    println(fib(10));
    return 0;
}`
    },
    {
        name: 'Factorial (recursivo)',
        source: `int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

int main() {
    println(factorial(5));
    return 0;
}`
    },
    {
        name: 'Bubble Sort',
        source: `int main() {
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
}`
    },
    {
        name: 'Collatz',
        source: `int main() {
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
}`
    },
    {
        name: 'FizzBuzz',
        source: `int main() {
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
}`
    },
    {
        name: 'Suma de array',
        source: `int main() {
    int nums[10] = {5, 12, 8, 3, 17, 6, 21, 9, 14, 2};
    int suma = 0;
    for (int i = 0; i < 10; i++) {
        suma += nums[i];
    }
    println(suma);
    return 0;
}`
    },
    {
        name: 'Busqueda lineal',
        source: `int main() {
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
}`
    },
    {
        name: 'Calculadora',
        source: `int main() {
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
}`
    }
];

export class Gallery {
    constructor(monacoEditor) {
        this._editor = monacoEditor;
    }

    getExamples() {
        return EXAMPLES.map(e => ({ name: e.name, source: e.source }));
    }

    load(index) {
        if (index < 0 || index >= EXAMPLES.length) return;
        if (this._editor) this._editor.setValue(EXAMPLES[index].source);
    }
}
