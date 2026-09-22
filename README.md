# MaoLang

MaoLang is a small interpreted language whose extension commands are ordinary
Python programs. The project provides a Python API, a command-line interface,
and a bundled standard library. Extra library directories can be supplied by an
application or on the command line without changing the installed package.

MaoLang is intentionally minimal. Every value is a string, code can be stored in
variables, and control flow is built by generating and executing more MaoLang
source. This makes the language easy to extend, but it is not designed for
high-performance numerical work.

## Requirements and installation

MaoLang requires Python 3.9 or newer and has no runtime dependencies.

Install the project from this repository:

```console
python -m pip install .
```

Use an editable install while developing the package:

```console
python -m pip install -e .
```

## Quick start

Create `hello.maolang`:

```maolang
name := {Mao}
! print {Hello, ${name}!}
```

Run it with either command:

```console
maolang hello.maolang
python -m maolang hello.maolang
```

The output is:

```text
Hello, Mao!
```

## Command-line interface

The general form is:

```text
maolang [OPTIONS] [FILE]
```

With no `FILE`, MaoLang starts the interactive REPL when standard input is a
terminal. Redirected or piped standard input remains a batch source. Passing `-`
as `FILE` also explicitly selects batch input. Use `-c` to execute inline source:

```console
maolang -c "! print {Hello from MaoLang}"
echo "! print {Hello from standard input}" | maolang
```

Available options:

| Option | Meaning |
| --- | --- |
| `-c CODE`, `--code CODE` | Execute `CODE` instead of reading a file |
| `-i`, `--interactive`, `--repl` | Enter the REPL, optionally after executing a file or `-c` code |
| `-L DIR`, `--lib-dir DIR` | Search an extra library directory before the bundled library; repeatable |
| `-D NAME=VALUE`, `--define NAME=VALUE` | Add a string to the initial environment; repeatable |
| `--encoding NAME` | Read source files with this encoding; defaults to UTF-8 |
| `-v`, `--verbose` | Write statement and interpolation traces to standard error |
| `--dump-env` | Write the final environment as JSON to standard error |
| `--version` | Print the installed MaoLang version |

For example, this injects `name` before execution:

```console
maolang -D name=Mao -c '! print {Hello, ${name}!}'
```

### Interactive REPL

Run `maolang` without arguments in a terminal to start an interactive session:

```text
$ maolang
MaoLang 0.1.0. Type :help for help.
>>> name := Mao
>>> ! print {Hello, ${name}!}
Hello, Mao!
>>> action := {
...     ! print {Running a stored block}
... }
>>> & {${action}}
Running a stored block
>>> :quit
```

The environment persists between statements. A statement with unmatched opening
braces continues at the `...` prompt until its braces balance. A failed statement
prints a diagnostic and returns to the prompt without discarding variables from
earlier successful statements. `Ctrl+C` cancels the current input or execution,
and end-of-file exits the session.

REPL commands are recognized when no multiline statement is being collected:

| Command | Meaning |
| --- | --- |
| `:help` | Show the REPL command list |
| `:env` | Print the current environment as JSON |
| `:clear` | Remove every value from the current environment |
| `:quit`, `:exit` | Leave the REPL |

Use `-i` to enter the REPL after executing a file or inline source. The REPL
inherits the resulting environment:

```console
maolang -i program.maolang
maolang -i -c 'answer := 42'
maolang --repl -D name=Mao
```

When `--repl` receives redirected input, it processes that input as an interactive
session without displaying prompts. This is useful for automation and tests. In
contrast, redirected input without `--repl` is parsed as one batch program and
does not recognize colon commands.

## Python API

### One-shot helpers

Use `run` for a source string and `run_file` for a UTF-8 source file:

```python
from maolang import run, run_file

environment = run(
    """
name := {Mao}
! eval {6 * 7} answer
! print {Hello, ${name}. The answer is ${answer}.}
""".strip(),
    env={"origin": "Python"},
)

file_environment = run_file(
    "program.maolang",
    lib_dirs=["./project_lib"],
    env={"name": "Mao"},
)
```

Both functions return the final `dict[str, str]` environment. The input `env` is
copied and is never mutated. `lib_dirs` is optional; the bundled standard library
is appended automatically. `run_file` injects the source file's absolute path as
`_FILEPATH`; `run` does not because a source string has no file path.

Optional `stdin`, `stdout`, and `stderr` text streams make input and output easy
to control. The `libraries` mapping registers fast in-process commands:

```python
from io import StringIO
from maolang import run

output = StringIO()
final_env = run(
    "! print {captured}",
    stdin=StringIO(""),
    stdout=output,
)
assert output.getvalue() == "captured\n"
```

### Reusable interpreter

Create an `Interpreter` when multiple runs share configuration:

```python
from maolang import Interpreter

interpreter = Interpreter(
    lib_dirs=["./project_lib"],
    verbose=False,
)

first = interpreter.execute("answer := {42}")
second = interpreter.execute_file("program.maolang", env=first)
```

`Interpreter.execute` accepts an optional `source_name` for diagnostics.
`Interpreter.execute_file` accepts an optional `encoding`; source files default to
UTF-8. Library modules are normal Python source files and follow Python's encoding
rules.

### REPL API

`run_repl` exposes the same persistent interactive loop to Python applications:

```python
from maolang import Interpreter, run_repl

interpreter = Interpreter(lib_dirs=["./project_lib"])
final_env = run_repl(
    interpreter,
    env={"name": "Mao"},
    banner="Embedded MaoLang console",
)
```

The function accepts optional `stdin`, `stdout`, and `stderr` text streams, making
an embedded console testable without a real terminal. `show_prompts` defaults to
the input stream's `isatty()` result. The returned dictionary is the environment
at the time the user exits.

### Errors

Syntax and execution failures raise `MaoLangError`:

```python
from maolang import MaoLangError, run

try:
    run("! missing-command")
except MaoLangError as error:
    print(error)
    first_location = error.diagnostics[0]
```

`str(error)` is formatted for a terminal. `error.diagnostics` contains structured
`Diagnostic` objects with the source name, source text, line range, and message.

## Language reference

### Execution model

A program is processed as a sequence of statements. A statement normally occupies
one line. Balanced braces can make a statement span multiple lines. Leading and
trailing statement whitespace is ignored.

The interpreter stores all variables in one environment mapping. Every key and
value is a string. Nested blocks and generated library code execute against the
same logical environment, so successful assignments remain visible afterward.

The core statement forms are:

| Form | Purpose |
| --- | --- |
| `name := VALUE` | Assign a string |
| `${name}` | Interpolate an environment value |
| `& {SOURCE}` | Execute grouped MaoLang source |
| `! command ARGUMENTS` | Run a Python library command |
| `// comment` | Ignore the remainder of the line |

### Predefined environment values

File execution injects one predefined value before the first statement:

| Name | Value |
| --- | --- |
| `_FILEPATH` | Absolute path of the MaoLang source file currently being run |

The value is available through normal interpolation:

```maolang
! print {Running ${_FILEPATH}}
```

`Interpreter.execute_file`, `run_file`, and CLI file execution all inject the
value. It overrides an `_FILEPATH` supplied in the initial environment, while the
caller's original mapping remains unchanged. Inline `run` calls, `-c`, batch
standard input, and a newly started REPL do not inject `_FILEPATH` because they do
not represent a source file.

When `maolang -i program.maolang` enters the REPL after running a file, the file's
final environment is preserved, so `_FILEPATH` remains available in that session.
The bundled `run` command also preserves `_FILEPATH` while executing child files.

### Values and grouping

Whitespace separates ungrouped values. Braces group spaces or newlines into one
value and may be nested:

```maolang
single := one-word
sentence := {one value with spaces}
block := {
    first line
    second line
}
```

For assignments, multiple parsed values are joined with newline characters. Use
braces whenever spaces must be preserved as spaces. Braces are structural; there
is no separate quoted-string or brace-escape syntax, so all braces must balance.

### Comments

`//` discards the rest of its physical line:

```maolang
answer := 42 // this text is ignored
```

Comment removal happens before brace parsing, including inside grouped text. A
literal `//` cannot currently be escaped.

### Assignment

The only core assignment operator is `:=`:

```maolang
name := {Mao Lang}
empty := {}
multiline := {first
second}
```

Assignment does not infer numbers or booleans. The strings `42`, `True`, and
`False` only gain those meanings when a library command interprets them.

### Interpolation

`${name}` is replaced with the current string value of `name` before a statement
is split into its command and arguments:

```maolang
name := Mao
greeting := {Hello, ${name}!}
! print {${greeting}}
```

Interpolation is recursive. An undefined identifier or a cyclic expansion raises
`MaoLangError`. `${}` expands to an empty string.

Because interpolation happens before execution, code stored for a later stage
often uses `$_{name}`. That spelling has no special meaning in the core parser;
the bundled `late` command converts `$_` to `$` one execution stage later.

### Executing a block

`&` executes one grouped value as MaoLang source:

```maolang
action := {
    result := {done}
    ! print {Action ${result}}
}

& {${action}}
```

The `&` command requires a following brace. Assignments made by the block are
merged into the current environment.

### Calling a library command

`!` dispatches an in-process Python library command. A command can be a callable
registered by the Python API or a module found in a library directory:

```maolang
! eval {20 + 22} answer
! print {The answer is ${answer}.}
```

The first value after `!` is the command name. Remaining values become
`LibraryCall.arguments`. The `.py` suffix is optional for module commands.
Resolution uses this order:

1. In-process handlers registered through `libraries`, `register_library`, or the
   `library` decorator.
2. Directories supplied through `lib_dirs` or `-L`, in the supplied order.
3. The bundled `maolang/lib` directory.

The first match wins. A project directory can therefore override a bundled name,
while an explicitly registered callable overrides both directory and bundled
commands. Every directory module must export `maolang_library(call)`. Modules are
loaded in the current process and cached by file path and modification time.

## Bundled standard library

The standard library is stored inside the installed package and needs no manual
path configuration. Its seven `maolang/lib/*.py` modules implement the same
`maolang_library(call)` protocol available to user libraries. They are imported
on first use and then reused by the interpreter.

### `print`

```text
! print [VALUE ...]
```

Joins its arguments with spaces and prints one line. Internally it assigns the
special `_PRINT` environment key; the interpreter writes and removes that key at
the next output boundary.

```maolang
! print {Hello world}
! print one two three
```

Output:

```text
Hello world
one two three
```

### `input`

```text
! input DESTINATION
```

Reads one line from standard input and assigns it to `DESTINATION`:

```maolang
! print {What is your name?}
! input name
! print {Hello, ${name}!}
```

### `eval`

```text
! eval EXPRESSION [DESTINATION]
```

Evaluates a Python expression, converts the result with `str`, and assigns it to
`DESTINATION`. The default destination is `_ANS` when only an expression is
provided. Embedded newlines in the expression are changed to spaces.

```maolang
! eval {6 * 7} answer
! eval {sum(range(1, 6))} total
! print {answer=${answer}, total=${total}}
```

`eval` is useful for arithmetic because MaoLang itself only stores strings. It is
not sandboxed and can execute arbitrary Python code. Only evaluate trusted source.

### `if`

```text
! if FLAG TRUE_VALUE FALSE_VALUE DESTINATION
```

Assigns one of two values to `DESTINATION`. Case-insensitive `false`, `none`, and
the string `0` are false; every other string is true.

`if` selects a value but does not directly execute it. Store code in the selected
value and use `&` when conditional execution is required:

```maolang
enabled := true
! if {${enabled}} {! print {enabled}} {! print {disabled}} selected
& {${selected}}
```

### `late`

```text
! late SOURCE
```

Delays interpolation by one library execution stage. It replaces every `$_` with
`$` and every literal `\n` sequence with a real newline, then returns the result
as generated MaoLang source.

```maolang
name := Mao
! late {! print {Hello, $_{name}!}}
```

The original statement does not recognize `$_{name}`. `late` emits a new statement
containing `${name}`, and that generated statement resolves the variable. This is
the key mechanism used by stored loop bodies and recursive examples.

### `wrap`

```text
! wrap PREFIX CONTENT...
```

Prefixes each nonempty top-level content line and wraps the line in braces. It is
useful for generating repeated commands:

```maolang
! wrap {! print} {alpha
beta
gamma}
```

Output:

```text
alpha
beta
gamma
```

Newlines inside nested brace blocks are emitted as literal `\n` sequences so they
can survive another generation stage and later be restored by `late`.

### `run`

```text
! run RELATIVE_PATH
```

Reads another UTF-8 MaoLang script and executes it directly in the current
environment. Assignments and other side effects made by the child script remain
available after `run` returns.

The command requires exactly one relative path. Use braces when the path contains
spaces. Absolute paths are rejected. In a file, the path is resolved relative to
the file containing the `run` statement. In the REPL or string-based `run()` API,
the first path is resolved relative to the current working directory.

For example:

```text
project/
|-- main.maolang
`-- setup/
    `-- values.maolang
```

`main.maolang`:

```maolang
name := Mao
! run {setup/values.maolang}
! print {${name}: ${answer}}
```

`setup/values.maolang`:

```maolang
! eval {6 * 7} answer
```

The output is `Mao: 42`. A child script may call `run` again; that nested path is
relative to the child script containing the call.

`run` never changes `_FILEPATH`. When execution started from `main.maolang`, the
main file's absolute path remains visible in the parent, child, and nested child
environments. A REPL session remains without `_FILEPATH` unless user code assigns
it explicitly.

## Complete examples

The examples below are deliberately small. Loops generate MaoLang code recursively,
so large numerical ranges are not a goal of the current interpreter even though
all library calls run in-process.

### Fibonacci sequence

[`examples/fibonacci.maolang`](examples/fibonacci.maolang) prints the first eight
Fibonacci numbers. `step` updates the state, while `loop` uses `eval` and `if` to
select either another step or an empty block.

```maolang
// Print the first eight Fibonacci numbers.
count := 8
index := 0
current := 0
next := 1

step := {
    ! late {! print {$_{current}}}
    ! late {! eval {$_{current} + $_{next}} sum}
    ! late {current := {$_{next}}}
    ! late {next := {$_{sum}}}
    ! late {! eval {$_{index} + 1} index}
    ! late {& {$_{loop}}}
}

loop := {
    ! late {! eval {$_{index} < $_{count}} keepGoing}
    ! late {! if {$_{keepGoing}} {$_{step}} {} selectedStep}
    ! late {& {$_{selectedStep}}}
}

! print {First ${count} Fibonacci numbers:}
& {${loop}}
```

Run it with:

```console
maolang examples/fibonacci.maolang
```

Expected output:

```text
First 8 Fibonacci numbers:
0
1
1
2
3
5
8
13
```

### Prime-number table

[`examples/primes.maolang`](examples/primes.maolang) tests candidates from 2
through 10. The Python expression checks divisors only through the square root of
the candidate, while MaoLang controls iteration and output.

```maolang
// Print every prime number up to ten.
limit := 10
candidate := 2

testAndAdvance := {
    ! late {! eval {all($_{candidate} % divisor != 0 for divisor in range(2, int($_{candidate} ** 0.5) + 1))} isPrime}
    ! late {! if {$_{isPrime}} {! print {$_{candidate}}} {} printStep}
    ! late {& {$_{printStep}}}
    ! late {! eval {$_{candidate} + 1} candidate}
    ! late {& {$_{loop}}}
}

loop := {
    ! late {! eval {$_{candidate} <= $_{limit}} keepGoing}
    ! late {! if {$_{keepGoing}} {$_{testAndAdvance}} {} selectedStep}
    ! late {& {$_{selectedStep}}}
}

! print {Prime numbers up to ${limit}:}
& {${loop}}
```

Run it with:

```console
maolang examples/primes.maolang
```

Expected output:

```text
Prime numbers up to 10:
2
3
5
7
```

## Writing a custom library command

All custom libraries use one in-process protocol. A handler receives a
`LibraryCall` and may return:

| Return value | Effect |
| --- | --- |
| `Mapping[str, str]` | Merge values directly into the environment |
| `str` | Execute the string as generated MaoLang source |
| `LibrarySource` | Execute generated source with optional diagnostic and relative-path context |
| `None` | Complete without generated source or environment changes |

All mapping keys and values must be strings. Handler exceptions and invalid
results become `MaoLangError` diagnostics at the calling source line.

`LibraryCall` exposes:

| Attribute | Meaning |
| --- | --- |
| `name` | Command name used after `!` |
| `arguments` | Parsed and interpolated `list[str]` arguments |
| `stdin` | Interpreter input text stream |
| `stdout` | Interpreter output text stream |
| `stderr` | Interpreter diagnostic text stream |
| `path` | Module path, or `None` for a directly registered callable |
| `source_path` | MaoLang source file containing the call, or `None` for a REPL/string source |

`source_path` tracks the currently interpreted source for relative child loading;
it may change during nested `run` calls. `_FILEPATH` remains the original entry
script's environment value. Custom loaders can return `LibrarySource` when they
need to provide a new source name or path context without changing `_FILEPATH`.

### Registering callables from Python

Register several handlers when constructing an interpreter:

```python
from maolang import Interpreter, LibraryCall


def multiply(call: LibraryCall) -> dict[str, str]:
    left, right, destination = call.arguments
    return {destination: str(int(left) * int(right))}


interpreter = Interpreter(libraries={"multiply": multiply})
environment = interpreter.execute("! multiply 6 7 answer")
assert environment["answer"] == "42"
```

The one-shot helpers also accept `libraries`:

```python
from maolang import run

environment = run(
    "! multiply 6 7 answer",
    libraries={"multiply": multiply},
)
```

Use the decorator API when building an interpreter incrementally. Returning source
allows a handler to use normal MaoLang execution and output behavior:

```python
from maolang import Interpreter, LibraryCall

interpreter = Interpreter()


@interpreter.library("greet")
def greet(call: LibraryCall) -> str:
    return f"_PRINT := {{Hello, {call.arguments[0]}!}}"


interpreter.execute("! greet Mao")
```

The equivalent non-decorator form is
`interpreter.register_library("greet", greet)`.

### Writing a directory module

The CLI cannot receive a Python callable directly, so `-L` loads command modules
from a directory. Each module must define exactly the same handler protocol under
the name `maolang_library`.

For example, create `project_lib/greet.py`:

```python
from maolang import LibraryCall, LibraryResult


def maolang_library(call: LibraryCall) -> LibraryResult:
    return {"_PRINT": f"Hello, {call.arguments[0]}!"}
```

Call it from MaoLang:

```maolang
! greet {Mao}
```

Then make the directory available through either interface:

```console
maolang -L project_lib program.maolang
```

```python
from maolang import run_file

run_file("program.maolang", lib_dirs=["project_lib"])
```

Modules are loaded lazily and cached inside each `Interpreter`. Module globals can
therefore hold reusable state or expensive initialized objects. When a module's
modification timestamp changes, the next call reloads it. Imports placed at module
scope may load helper modules from the same library directory.

Direct registration and directory modules use identical call and return values.
Direct registration only avoids the initial file lookup and module import. Library
modules run inside the host process and are not sandboxed, so only load trusted
code.

## Performance model

All library commands execute in-process. Modules are cached, and mapping results
update the environment without generating or reparsing assignment source.
Generated source from `late`, `wrap`, and custom handlers still passes through the
normal interpreter, preserving MaoLang's staged execution model.

The mathematical examples intentionally keep small ranges because recursive
generated code is still not intended to compete with native Python loops. For
heavy computation, place the algorithm inside a Python library handler and return
only its final strings to MaoLang.

## Development and verification

Run the complete test suite with:

```console
python -m unittest discover -s tests -v
```

The example tests execute both mathematical programs through the real interpreter
and compare their complete output. Their ranges intentionally remain small to
exercise recursion without turning the test suite into a stress test.

Build a wheel with:

```console
python -m pip wheel . --no-deps
```

The wheel includes `maolang/lib/*.py`, so the standard library remains available
after installation without an external data directory.
