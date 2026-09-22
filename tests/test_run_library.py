from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maolang import MaoLangError, run, run_file


class RunLibraryTests(unittest.TestCase):
    def test_child_scripts_share_environment_without_changing_filepath(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child_dir = root / "child"
            child_dir.mkdir()
            main = root / "main.maolang"
            child = child_dir / "child.maolang"
            nested = child_dir / "nested.maolang"

            main.write_text(
                "shared := parent\n"
                "! run {child/child.maolang}\n"
                "after := {${nestedValue}}\n",
                encoding="utf-8",
            )
            child.write_text(
                "childValue := {${shared}-child}\n"
                "childFilepath := {${_FILEPATH}}\n"
                "! run nested.maolang\n",
                encoding="utf-8",
            )
            nested.write_text(
                "nestedValue := nested\n"
                "nestedFilepath := {${_FILEPATH}}\n",
                encoding="utf-8",
            )

            result = run_file(main)
            main_path = str(main.resolve())

        self.assertEqual(result["childValue"], "parent-child")
        self.assertEqual(result["nestedValue"], "nested")
        self.assertEqual(result["after"], "nested")
        self.assertEqual(result["_FILEPATH"], main_path)
        self.assertEqual(result["childFilepath"], main_path)
        self.assertEqual(result["nestedFilepath"], main_path)

    def test_run_rejects_absolute_paths(self) -> None:
        absolute = Path(__file__).resolve()

        with self.assertRaises(MaoLangError) as raised:
            run(f"! run {{{absolute}}}")

        self.assertIn("only accepts a relative script path", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
