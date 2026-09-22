"""Interactive read-eval-print loop for MaoLang."""

from __future__ import annotations

import json
import sys
from typing import Mapping, TextIO

from .errors import MaoLangError
from .interpreter import Interpreter

_HELP = """REPL commands:
  :help   Show this help
  :env    Show the current environment as JSON
  :clear  Clear the current environment
  :quit   Exit the REPL
  :exit   Exit the REPL"""


def _brace_depth(source: str) -> int:
    """Count structural braces after applying MaoLang's comment rule."""

    depth = 0
    for line in source.split("\n"):
        code = line.split("//", 1)[0]
        depth += code.count("{") - code.count("}")
    return depth


def run_repl(
    interpreter: Interpreter | None = None,
    env: Mapping[str, str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    show_prompts: bool | None = None,
    banner: str | None = None,
) -> dict[str, str]:
    """Run a MaoLang REPL and return its final environment."""

    input_stream = stdin if stdin is not None else sys.stdin
    output_stream = stdout if stdout is not None else sys.stdout
    error_stream = stderr if stderr is not None else sys.stderr
    if interpreter is None:
        interpreter = Interpreter(
            stdin=input_stream, stdout=output_stream, stderr=error_stream
        )

    current_env = dict(env or {})
    if not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in current_env.items()
    ):
        raise TypeError("env keys and values must be strings")

    if show_prompts is None:
        show_prompts = input_stream.isatty()
    if show_prompts and banner:
        output_stream.write(f"{banner}\n")

    buffer: list[str] = []
    line_number = 1
    statement_start = 1

    while True:
        if show_prompts:
            output_stream.write("... " if buffer else ">>> ")
            output_stream.flush()

        try:
            raw_line = input_stream.readline()
        except KeyboardInterrupt:
            buffer.clear()
            output_stream.write("^C\n")
            output_stream.flush()
            statement_start = line_number
            continue

        if raw_line == "":
            if show_prompts:
                output_stream.write("\n")
            if buffer:
                source = "\n".join(buffer)
                try:
                    current_env = interpreter.execute(
                        source,
                        current_env,
                        source_name=f"<repl:{statement_start}>",
                    )
                except MaoLangError as error:
                    print(error, file=error_stream)
            return current_env

        line = raw_line.rstrip("\r\n")
        if not buffer and line.strip().startswith(":"):
            command = line.strip().lower()
            if command in {":quit", ":exit"}:
                return current_env
            if command == ":help":
                output_stream.write(f"{_HELP}\n")
            elif command == ":env":
                output_stream.write(
                    json.dumps(current_env, ensure_ascii=False, indent=2) + "\n"
                )
            elif command == ":clear":
                current_env.clear()
                output_stream.write("Environment cleared.\n")
            else:
                print(
                    f"unknown REPL command: {line.strip()}; use :help",
                    file=error_stream,
                )
            line_number += 1
            statement_start = line_number
            continue

        if not buffer and not line.strip():
            line_number += 1
            statement_start = line_number
            continue

        if not buffer:
            statement_start = line_number
        buffer.append(line)
        line_number += 1

        source = "\n".join(buffer)
        if _brace_depth(source) > 0:
            continue

        try:
            current_env = interpreter.execute(
                source,
                current_env,
                source_name=f"<repl:{statement_start}>",
            )
        except MaoLangError as error:
            print(error, file=error_stream)
        except KeyboardInterrupt:
            output_stream.write("^C\n")
            output_stream.flush()
        buffer.clear()
        statement_start = line_number
