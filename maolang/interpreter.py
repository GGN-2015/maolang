"""MaoLang interpreter implementation."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
from typing import Callable, Iterable, Mapping, TextIO

from .errors import Diagnostic, MaoLangError
from .library import LibraryCall, LibraryHandler, LibraryResult, LibrarySource

_VARIABLE_PATTERN = re.compile(r"\$\{[^{}\s]*\}")
_ASSIGNMENT_OPERATORS = (":=",)


def get_builtin_lib_dir() -> Path:
    """Return the directory containing MaoLang's bundled Python libraries."""

    return Path(__file__).resolve().with_name("lib")


def resolve_lib_dirs(lib_dirs: Iterable[os.PathLike[str] | str] | None = None) -> tuple[Path, ...]:
    """Return user library directories followed by MaoLang's bundled library."""

    candidates = [Path(path).expanduser().resolve() for path in (lib_dirs or ())]
    candidates.append(get_builtin_lib_dir())

    result: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            result.append(path)
    return tuple(result)


class Interpreter:
    """A reusable MaoLang interpreter configuration."""

    def __init__(
        self,
        lib_dirs: Iterable[os.PathLike[str] | str] | None = None,
        *,
        verbose: bool = False,
        libraries: Mapping[str, LibraryHandler] | None = None,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> None:
        self.lib_dirs = resolve_lib_dirs(lib_dirs)
        self.verbose = verbose
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout
        self.stderr = stderr if stderr is not None else sys.stderr
        self.library_handlers: dict[str, LibraryHandler] = {}
        self._module_cache: dict[Path, tuple[int, LibraryHandler]] = {}
        for name, handler in (libraries or {}).items():
            self.register_library(name, handler)

    @staticmethod
    def _library_key(name: str) -> str | None:
        if not name or "/" in name or "\\" in name:
            return None
        return name[:-3] if name.lower().endswith(".py") else name

    def register_library(self, name: str, handler: LibraryHandler) -> None:
        """Register or replace a high-priority in-process library command."""

        key = self._library_key(name)
        if key is None:
            raise ValueError("in-process library names must be simple file names")
        if not callable(handler):
            raise TypeError("library handler must be callable")
        self.library_handlers[key] = handler

    def library(
        self, name: str
    ) -> Callable[[LibraryHandler], LibraryHandler]:
        """Return a decorator that registers an in-process library command."""

        def decorator(handler: LibraryHandler) -> LibraryHandler:
            self.register_library(name, handler)
            return handler

        return decorator

    def execute(
        self,
        source: str,
        env: Mapping[str, str] | None = None,
        *,
        source_name: str = "<string>",
    ) -> dict[str, str]:
        """Execute source code and return a new environment dictionary."""

        initial_env = dict(env or {})
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in initial_env.items()):
            raise TypeError("env keys and values must be strings")
        return self._execute(source, initial_env, source_name, None)

    def execute_file(
        self,
        path: os.PathLike[str] | str,
        env: Mapping[str, str] | None = None,
        *,
        encoding: str = "utf-8",
    ) -> dict[str, str]:
        """Read and execute a MaoLang source file."""

        source_path = Path(path).expanduser().resolve()
        source = source_path.read_text(encoding=encoding)
        file_env = dict(env or {})
        file_env["_FILEPATH"] = str(source_path)
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in file_env.items()
        ):
            raise TypeError("env keys and values must be strings")
        return self._execute(source, file_env, str(source_path), source_path)

    def _diagnostic(
        self,
        source_name: str,
        source: str,
        line_start: int,
        line_end: int,
        message: str,
    ) -> Diagnostic:
        return Diagnostic(source_name, source, line_start, line_end, message)

    def _fail(
        self,
        source_name: str,
        source: str,
        line_start: int,
        line_end: int,
        message: str,
    ) -> None:
        raise MaoLangError(
            self._diagnostic(source_name, source, line_start, line_end, message)
        )

    def _trace(self, message: str) -> None:
        if self.verbose:
            self.stderr.write(f"VERBOSE: {message}\n")

    def _flush_print(self, env: dict[str, str]) -> None:
        value = env.pop("_PRINT", None)
        if value is not None:
            self.stdout.write(f"{value}\n")

    def _prepare_source(
        self, source: str, source_name: str
    ) -> tuple[list[str], dict[int, int]]:
        lines = source.split("\n")
        for index, line in enumerate(lines):
            line = line.rstrip()
            comment_at = line.find("//")
            if comment_at != -1:
                line = line[:comment_at].rstrip()
            lines[index] = line

        matching_braces: dict[tuple[int, int], tuple[int, int]] = {}
        left_braces: dict[int, list[int]] = {}
        stack: list[tuple[int, int]] = []

        for line_number, line in enumerate(lines, start=1):
            left_braces[line_number] = []
            for column_number, character in enumerate(line, start=1):
                if character == "{":
                    left_braces[line_number].append(column_number)
                    stack.append((line_number, column_number))
                elif character == "}":
                    if not stack:
                        self._fail(
                            source_name,
                            source,
                            line_number,
                            line_number,
                            "unpaired '}'.",
                        )
                    left = stack.pop()
                    right = (line_number, column_number)
                    matching_braces[left] = right
                    matching_braces[right] = left

        if stack:
            line_number, _ = stack[-1]
            self._fail(
                source_name,
                source,
                line_number,
                line_number,
                "unpaired '{'.",
            )

        real_end: dict[int, int] = {}

        def get_real_end(line_number: int) -> int:
            if not left_braces[line_number]:
                return line_number
            last_line = max(
                matching_braces[(line_number, column)][0]
                for column in left_braces[line_number]
            )
            if last_line <= line_number or not left_braces[last_line]:
                return last_line
            return get_real_end(last_line)

        line_number = 1
        while line_number <= len(lines):
            real_end[line_number] = get_real_end(line_number)
            line_number = real_end[line_number] + 1
        return lines, real_end

    def _interpolate(
        self,
        text: str,
        env: Mapping[str, str],
        source: str,
        source_name: str,
        line_start: int,
        line_end: int,
    ) -> str:
        seen: set[str] = set()
        while match := _VARIABLE_PATTERN.search(text):
            if text in seen:
                self._fail(
                    source_name,
                    source,
                    line_start,
                    line_end,
                    "cyclic variable interpolation.",
                )
            seen.add(text)
            name = text[match.start() + 2 : match.end() - 1].strip()
            if not name:
                text = text.replace("${}", "")
                continue
            if name not in env:
                self._fail(
                    source_name,
                    source,
                    line_start,
                    line_end,
                    f"identifier '{name}' is not defined.",
                )
            text = text.replace(f"${{{name}}}", env[name])
        return text

    def _split_values(
        self,
        text: str,
        source: str,
        source_name: str,
        line_start: int,
        line_end: int,
    ) -> list[str]:
        text = text.strip()
        if not text:
            return []

        stack: list[int] = []
        matching: dict[int, int] = {}
        for index, character in enumerate(text):
            if character == "{":
                stack.append(index)
            elif character == "}":
                if not stack:
                    self._fail(
                        source_name, source, line_start, line_end, "unpaired '}'."
                    )
                left = stack.pop()
                matching[left] = index
                matching[index] = left
        if stack:
            self._fail(source_name, source, line_start, line_end, "unpaired '{'.")

        values: list[str] = []
        current: list[str] = []
        index = 0
        while index < len(text):
            character = text[index]
            if character == "{":
                if current:
                    values.append("".join(current).strip())
                    current = []
                right = matching[index]
                values.append(text[index + 1 : right])
                index = right + 1
            elif character.isspace():
                if current:
                    values.append("".join(current).strip())
                    current = []
                index += 1
            else:
                current.append(character)
                index += 1
        if current:
            values.append("".join(current).strip())
        return values

    def _find_library(self, program: str) -> Path | None:
        for lib_dir in self.lib_dirs:
            candidate = lib_dir / program
            if not str(candidate).lower().endswith(".py"):
                candidate = Path(f"{candidate}.py")
            if candidate.is_file():
                return candidate
        return None

    def _load_library_handler(
        self,
        script: Path,
        program: str,
        source: str,
        source_name: str,
        line_start: int,
        line_end: int,
    ) -> LibraryHandler:
        script = script.resolve()
        try:
            modified_at = script.stat().st_mtime_ns
        except OSError as error:
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"cannot inspect library module '{program}': {error}",
            )

        cached = self._module_cache.get(script)
        if cached is not None and cached[0] == modified_at:
            return cached[1]

        digest = hashlib.sha256(os.fsencode(str(script))).hexdigest()
        module_name = f"_maolang_library_{digest}"
        spec = importlib.util.spec_from_file_location(module_name, script)
        if spec is None or spec.loader is None:
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"cannot load library module '{program}'.",
            )

        module = importlib.util.module_from_spec(spec)
        module_dir = str(script.parent)
        sys.modules[module_name] = module
        sys.path.insert(0, module_dir)
        self._trace(f"loading library module: {script}")
        try:
            spec.loader.exec_module(module)
        except Exception as error:
            sys.modules.pop(module_name, None)
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"cannot load library module '{program}': "
                f"{type(error).__name__}: {error}",
            )
        finally:
            if sys.path and sys.path[0] == module_dir:
                sys.path.pop(0)
            else:
                try:
                    sys.path.remove(module_dir)
                except ValueError:
                    pass

        handler = getattr(module, "maolang_library", None)
        if not callable(handler):
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"library module '{program}' must define a callable "
                "named 'maolang_library'.",
            )
        self._module_cache[script] = (modified_at, handler)
        return handler

    def _run_library(
        self,
        program: str,
        arguments: list[str],
        source: str,
        source_name: str,
        line_start: int,
        line_end: int,
        source_path: Path | None,
    ) -> LibraryResult:
        key = self._library_key(program)
        if key is not None and key in self.library_handlers:
            return self._run_library_handler(
                program,
                self.library_handlers[key],
                arguments,
                source,
                source_name,
                line_start,
                line_end,
                None,
                source_path,
            )

        script = self._find_library(program)
        if script is None:
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"cannot find library program '{program}'.",
            )

        handler = self._load_library_handler(
            script,
            program,
            source,
            source_name,
            line_start,
            line_end,
        )
        return self._run_library_handler(
            program,
            handler,
            arguments,
            source,
            source_name,
            line_start,
            line_end,
            script.resolve(),
            source_path,
        )

    def _run_library_handler(
        self,
        program: str,
        handler: LibraryHandler,
        arguments: list[str],
        source: str,
        source_name: str,
        line_start: int,
        line_end: int,
        path: Path | None,
        source_path: Path | None,
    ) -> LibraryResult:
        try:
            result = handler(
                LibraryCall(
                    name=program,
                    arguments=list(arguments),
                    stdin=self.stdin,
                    stdout=self.stdout,
                    stderr=self.stderr,
                    path=path,
                    source_path=source_path,
                )
            )
        except Exception as error:
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"library handler '{program}' failed: "
                f"{type(error).__name__}: {error}",
            )
        if result is not None and not isinstance(
            result, (str, Mapping, LibrarySource)
        ):
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"library handler '{program}' returned an unsupported value.",
            )
        return result

    def _execute_statement(
        self,
        statement: str,
        env: dict[str, str],
        source: str,
        source_name: str,
        line_start: int,
        line_end: int,
        source_path: Path | None,
    ) -> None:
        statement = statement.strip()
        if not statement:
            return

        self._trace(f"before interpolation: {statement}")
        statement = self._interpolate(
            statement, env, source, source_name, line_start, line_end
        )
        self._trace(f"after interpolation: {statement}")

        parts = statement.split(maxsplit=1)
        head = parts[0]
        rest = parts[1].strip() if len(parts) == 2 else ""

        if head in {"&", "!"}:
            if head == "&" and not rest.startswith("{"):
                self._fail(
                    source_name,
                    source,
                    line_start,
                    line_start,
                    "'&' must be followed by '{'.",
                )

            values = self._split_values(
                rest, source, source_name, line_start, line_end
            )
            if head == "!" and not values:
                self._fail(
                    source_name,
                    source,
                    line_start,
                    line_start,
                    "'!' must have at least one argument.",
                )

            if head == "&":
                nested_source = "\n".join(values)
                nested_name = f"{source_name} (block at line {line_start})"
                try:
                    env.update(
                        self._execute(
                            nested_source,
                            env,
                            nested_name,
                            source_path,
                        )
                    )
                except MaoLangError as error:
                    context = self._diagnostic(
                        source_name,
                        source,
                        line_start,
                        line_end,
                        "error in '&'.",
                    )
                    raise error.with_context(context) from None
                return

            program, *arguments = values
            library_result = self._run_library(
                program,
                arguments,
                source,
                source_name,
                line_start,
                line_end,
                source_path,
            )
            if library_result is None:
                return
            if isinstance(library_result, Mapping):
                if not all(
                    isinstance(key, str) and isinstance(value, str)
                    for key, value in library_result.items()
                ):
                    self._fail(
                        source_name,
                        source,
                        line_start,
                        line_end,
                        f"library handler '{program}' returned a mapping with "
                        "non-string keys or values.",
                    )
                env.update(library_result)
                return
            if isinstance(library_result, LibrarySource):
                generated_source = library_result.source
                generated_name = (
                    library_result.source_name
                    or f"<output from library '{program}'>"
                )
                generated_path = (
                    library_result.source_path
                    if library_result.source_path is not None
                    else source_path
                )
            else:
                generated_source = library_result
                generated_name = f"<output from library '{program}'>"
                generated_path = source_path
            try:
                env.update(
                    self._execute(
                        generated_source,
                        env,
                        generated_name,
                        generated_path,
                    )
                )
            except MaoLangError as error:
                context = self._diagnostic(
                    source_name,
                    source,
                    line_start,
                    line_end,
                    "error in '!'.",
                )
                raise error.with_context(context) from None
            return

        assignment = rest.split(maxsplit=1)
        operator = assignment[0] if assignment else ""
        value_source = assignment[1].strip() if len(assignment) == 2 else ""
        if operator not in _ASSIGNMENT_OPERATORS:
            expected = ", ".join(f"'{item}'" for item in _ASSIGNMENT_OPERATORS)
            self._fail(
                source_name,
                source,
                line_start,
                line_end,
                f"identifier must be followed by one of: {expected}.",
            )
        values = self._split_values(
            value_source, source, source_name, line_start, line_end
        )
        env[head] = "\n".join(values)

    def _execute(
        self,
        source: str,
        env: dict[str, str],
        source_name: str,
        source_path: Path | None,
    ) -> dict[str, str]:
        lines, real_end = self._prepare_source(source, source_name)
        line_number = 1
        while line_number <= len(lines):
            self._flush_print(env)
            end_line = real_end[line_number]
            statement = "\n".join(lines[line_number - 1 : end_line])
            self._execute_statement(
                statement,
                env,
                source,
                source_name,
                line_number,
                end_line,
                source_path,
            )
            line_number = end_line + 1
        self._flush_print(env)
        return env


def run(
    source: str,
    lib_dirs: Iterable[os.PathLike[str] | str] | None = None,
    env: Mapping[str, str] | None = None,
    *,
    verbose: bool = False,
    libraries: Mapping[str, LibraryHandler] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    source_name: str = "<string>",
) -> dict[str, str]:
    """Execute MaoLang source with a one-shot interpreter."""

    return Interpreter(
        lib_dirs,
        verbose=verbose,
        libraries=libraries,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    ).execute(source, env, source_name=source_name)


def run_file(
    path: os.PathLike[str] | str,
    lib_dirs: Iterable[os.PathLike[str] | str] | None = None,
    env: Mapping[str, str] | None = None,
    *,
    verbose: bool = False,
    libraries: Mapping[str, LibraryHandler] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    encoding: str = "utf-8",
) -> dict[str, str]:
    """Execute a MaoLang file with a one-shot interpreter."""

    return Interpreter(
        lib_dirs,
        verbose=verbose,
        libraries=libraries,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    ).execute_file(path, env, encoding=encoding)
