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

from maolang import Interpreter, run_repl
from maolang.cli import main


class TtyInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class ReplTests(unittest.TestCase):
    def run_session(
        self, source: str, *, env: dict[str, str] | None = None
    ) -> tuple[dict[str, str], str, str]:
        stdin = io.StringIO(source)
        stdout = io.StringIO()
        stderr = io.StringIO()
        interpreter = Interpreter(stdout=stdout, stderr=stderr)

        final_env = run_repl(
            interpreter,
            env,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            show_prompts=False,
        )
        return final_env, stdout.getvalue(), stderr.getvalue()

    def test_environment_persists_between_statements(self) -> None:
        env, stdout, stderr = self.run_session(
            "name := Mao\n! print {Hello, ${name}!}\n:quit\n"
        )

        self.assertEqual(env["name"], "Mao")
        self.assertNotIn("_FILEPATH", env)
        self.assertEqual(stdout, "Hello, Mao!\n")
        self.assertEqual(stderr, "")

    def test_multiline_statement_waits_for_balanced_braces(self) -> None:
        env, stdout, stderr = self.run_session(
            "message := {first\nsecond}\n! print {${message}}\n:quit\n"
        )

        self.assertEqual(env["message"], "first\nsecond")
        self.assertEqual(stdout, "first\nsecond\n")
        self.assertEqual(stderr, "")

    def test_run_resolves_from_working_directory_without_filepath(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory, "repl-child.maolang")
            child.write_text("fromChild := yes\n", encoding="utf-8")
            relative = os.path.relpath(child, Path.cwd())

            env, _, stderr = self.run_session(f"! run {{{relative}}}\n:quit\n")

        self.assertEqual(env["fromChild"], "yes")
        self.assertNotIn("_FILEPATH", env)
        self.assertEqual(stderr, "")

    def test_run_in_repl_ignores_preserved_filepath(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory, "cwd-child.maolang")
            child.write_text("fromCwd := yes\n", encoding="utf-8")
            relative = os.path.relpath(child, Path.cwd())
            preserved = str(Path(directory, "different", "main.maolang"))

            env, _, stderr = self.run_session(
                f"! run {{{relative}}}\n:quit\n",
                env={"_FILEPATH": preserved},
            )

        self.assertEqual(env["fromCwd"], "yes")
        self.assertEqual(env["_FILEPATH"], preserved)
        self.assertEqual(stderr, "")

    def test_error_does_not_end_session_or_mutate_previous_environment(self) -> None:
        env, _, stderr = self.run_session(
            "stable := yes\nvalue := {${missing}}\nafter := ok\n:quit\n"
        )

        self.assertEqual(env, {"stable": "yes", "after": "ok"})
        self.assertIn("identifier 'missing' is not defined", stderr)

    def test_meta_commands_inspect_and_clear_environment(self) -> None:
        env, stdout, stderr = self.run_session(
            ":env\n:clear\n:help\n:exit\n", env={"answer": "42"}
        )

        self.assertEqual(env, {})
        self.assertIn('"answer": "42"', stdout)
        self.assertIn("Environment cleared.", stdout)
        self.assertIn(":quit", stdout)
        self.assertEqual(stderr, "")

    def test_cli_without_arguments_enters_repl_on_a_terminal(self) -> None:
        stdin = TtyInput(":quit\n")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("sys.stdin", stdin), patch("sys.stdout", stdout), patch(
            "sys.stderr", stderr
        ):
            return_code = main([])

        self.assertEqual(return_code, 0)
        self.assertIn("MaoLang 0.1.0", stdout.getvalue())
        self.assertTrue(stdout.getvalue().endswith(">>> "))
        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
