from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maolang import (
    Interpreter,
    LibraryCall,
    MaoLangError,
    get_builtin_lib_dir,
    run,
    run_file,
)


class ApiTests(unittest.TestCase):
    def test_assignment_and_input_environment_are_independent(self) -> None:
        initial = {"name": "Mao"}

        result = run("greeting := {Hello, ${name}!}", env=initial)

        self.assertEqual(result["greeting"], "Hello, Mao!")
        self.assertEqual(initial, {"name": "Mao"})

    def test_bundled_print_library_is_automatic(self) -> None:
        output = io.StringIO()

        result = run("! print {Hello world}", stdout=output)

        self.assertEqual(output.getvalue(), "Hello world\n")
        self.assertEqual(result, {})
        self.assertTrue((get_builtin_lib_dir() / "print.py").is_file())

    def test_bundled_libraries_do_not_start_subprocesses(self) -> None:
        output = io.StringIO()
        source = """
! eval {6 * 7} answer
! if true {${answer}} {} selected
! late {! wrap {! print} {$_{selected}}}
""".strip()

        with patch("subprocess.run", side_effect=AssertionError("unexpected subprocess")):
            result = run(source, stdout=output)

        self.assertEqual(result["answer"], "42")
        self.assertEqual(result["selected"], "42")
        self.assertEqual(output.getvalue(), "42\n")

    def test_bundled_input_accepts_an_injected_stream(self) -> None:
        result = run("! input name", stdin=io.StringIO("Mao\n"))

        self.assertEqual(result["name"], "Mao")

    def test_callable_library_can_return_environment_values(self) -> None:
        def multiply(call: LibraryCall) -> dict[str, str]:
            left, right, destination = call.arguments
            return {destination: str(int(left) * int(right))}

        result = run(
            "! multiply 6 7 answer",
            libraries={"multiply": multiply},
        )

        self.assertEqual(result["answer"], "42")

    def test_library_decorator_can_return_generated_source(self) -> None:
        output = io.StringIO()
        interpreter = Interpreter(stdout=output)

        @interpreter.library("greet")
        def greet(call: LibraryCall) -> str:
            return f"_PRINT := {{Hello, {call.arguments[0]}!}}"

        interpreter.execute("! greet Mao")

        self.assertEqual(output.getvalue(), "Hello, Mao!\n")

    def test_callable_library_failure_becomes_maolang_error(self) -> None:
        def broken(call: LibraryCall) -> None:
            del call
            raise ValueError("broken on purpose")

        with self.assertRaises(MaoLangError) as raised:
            run("! broken", libraries={"broken": broken})

        self.assertIn("library handler 'broken' failed", str(raised.exception))
        self.assertIn("broken on purpose", str(raised.exception))

    def test_custom_library_has_priority_over_bundled_library(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            custom_print = Path(directory, "print.py")
            custom_print.write_text(
                "def maolang_library(call):\n"
                "    return {'_PRINT': 'custom'}\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            interpreter = Interpreter([directory], stdout=output)
            with patch(
                "subprocess.run", side_effect=AssertionError("unexpected subprocess")
            ):
                interpreter.execute("! print {ignored}")

        self.assertEqual(output.getvalue(), "custom\n")
        self.assertEqual(interpreter.lib_dirs[-1], get_builtin_lib_dir())

    def test_directory_library_module_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory, "counter.py")
            library.write_text(
                "count = 0\n"
                "def maolang_library(call):\n"
                "    global count\n"
                "    count += 1\n"
                "    return {'count': str(count)}\n",
                encoding="utf-8",
            )

            result = Interpreter([directory]).execute("! counter\n! counter")

        self.assertEqual(result["count"], "2")

    def test_directory_library_module_reloads_after_file_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory, "dynamic.py")
            library.write_text(
                "def maolang_library(call):\n"
                "    return {'value': 'first'}\n",
                encoding="utf-8",
            )
            interpreter = Interpreter([directory])
            first = interpreter.execute("! dynamic")

            previous_mtime = library.stat().st_mtime_ns
            library.write_text(
                "def maolang_library(call):\n"
                "    return {'value': 'second'}\n",
                encoding="utf-8",
            )
            updated_mtime = previous_mtime + 2_000_000_000
            os.utime(library, ns=(updated_mtime, updated_mtime))
            second = interpreter.execute("! dynamic")

        self.assertEqual(first["value"], "first")
        self.assertEqual(second["value"], "second")

    def test_legacy_script_without_handler_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory, "legacy.py")
            library.write_text("value = 42\n", encoding="utf-8")

            with self.assertRaises(MaoLangError) as raised:
                Interpreter([directory]).execute("! legacy")

        self.assertIn("must define a callable named 'maolang_library'", str(raised.exception))

    def test_bundled_wrap_generates_one_command_per_line(self) -> None:
        output = io.StringIO()

        run("! wrap {! print} {alpha\nbeta}", stdout=output)

        self.assertEqual(output.getvalue(), "alpha\nbeta\n")

    def test_run_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory, "example.maolang")
            source_path.write_text(
                "answer := {42}\nseenPath := {${_FILEPATH}}\n",
                encoding="utf-8",
            )
            initial = {"_FILEPATH": "not-the-file"}

            result = run_file(source_path, env=initial)

        self.assertEqual(result["answer"], "42")
        self.assertEqual(result["seenPath"], str(source_path.resolve()))
        self.assertEqual(result["_FILEPATH"], str(source_path.resolve()))
        self.assertEqual(initial, {"_FILEPATH": "not-the-file"})

    def test_source_string_does_not_receive_filepath(self) -> None:
        result = run("answer := 42")

        self.assertNotIn("_FILEPATH", result)

    def test_error_exposes_diagnostic(self) -> None:
        with self.assertRaises(MaoLangError) as raised:
            run("value := {${missing}}", source_name="example.maolang")

        diagnostic = raised.exception.diagnostics[0]
        self.assertEqual(diagnostic.source_name, "example.maolang")
        self.assertEqual(diagnostic.line_start, 1)
        self.assertIn("identifier 'missing' is not defined", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
