from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        bootstrap = (
            "import sys; "
            f"sys.path.insert(0, {str(ROOT)!r}); "
            "from maolang.cli import main; "
            "raise SystemExit(main())"
        )
        return subprocess.run(
            [sys.executable, "-c", bootstrap, *arguments],
            cwd=ROOT,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_code_flag_and_definition(self) -> None:
        process = self.run_cli("-D", "name=Mao", "-c", "! print {Hello ${name}}")

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "Hello Mao\n")

    def test_standard_input_and_dump_env(self) -> None:
        process = self.run_cli("--dump-env", input_text="answer := {42}\n")

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stderr), {"answer": "42"})

    def test_explicit_repl_persists_environment(self) -> None:
        process = self.run_cli(
            "--repl",
            input_text="name := Mao\n! print {Hello, ${name}!}\n:quit\n",
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "Hello, Mao!\n")

    def test_interactive_mode_inherits_code_environment(self) -> None:
        process = self.run_cli(
            "-i",
            "-c",
            "name := Mao",
            input_text="! print {Hello, ${name}!}\n:quit\n",
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "Hello, Mao!\n")

    def test_file_and_library_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "program.maolang"
            source.write_text("! greeting {Mao}\n", encoding="utf-8")
            library = root / "lib"
            library.mkdir()
            (library / "greeting.py").write_text(
                "def maolang_library(call):\n"
                "    return {'_PRINT': 'Hello, %s' % call.arguments[0]}\n",
                encoding="utf-8",
            )

            process = self.run_cli("-L", str(library), str(source))

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "Hello, Mao\n")

    def test_file_receives_absolute_filepath(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "filepath.maolang")
            source.write_text("! print {${_FILEPATH}}\n", encoding="utf-8")

            process = self.run_cli(str(source))

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, f"{source.resolve()}\n")

    def test_file_can_run_relative_child_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.maolang"
            child = root / "child.maolang"
            main.write_text(
                "! run child.maolang\n! print {${message}}\n",
                encoding="utf-8",
            )
            child.write_text("message := {from child}\n", encoding="utf-8")

            process = self.run_cli(str(main))

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "from child\n")

    def test_bundled_input_reads_standard_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "input.maolang")
            source.write_text(
                "! input name\n! print {Hello, ${name}!}\n",
                encoding="utf-8",
            )

            process = self.run_cli(str(source), input_text="Mao\n")

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stdout, "Hello, Mao!\n")

    def test_language_error_has_nonzero_exit_code(self) -> None:
        process = self.run_cli("-c", "! missing")

        self.assertEqual(process.returncode, 1)
        self.assertIn("cannot find library program 'missing'", process.stderr)


if __name__ == "__main__":
    unittest.main()
