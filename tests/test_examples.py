from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maolang import run_file


class ExampleTests(unittest.TestCase):
    def run_example(self, name: str) -> list[str]:
        output = io.StringIO()
        run_file(ROOT / "examples" / name, stdout=output)
        return output.getvalue().splitlines()

    def test_small_fibonacci_sequence(self) -> None:
        self.assertEqual(
            self.run_example("fibonacci.maolang"),
            ["First 8 Fibonacci numbers:", "0", "1", "1", "2", "3", "5", "8", "13"],
        )

    def test_small_prime_table(self) -> None:
        self.assertEqual(
            self.run_example("primes.maolang"),
            ["Prime numbers up to 10:", "2", "3", "5", "7"],
        )


if __name__ == "__main__":
    unittest.main()
