"""Errors and source diagnostics produced by MaoLang."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    """A single error location and message."""

    source_name: str
    source: str
    line_start: int
    line_end: int
    message: str

    def format(self) -> str:
        """Render the diagnostic for a terminal."""

        lines = self.source.split("\n")
        first = max(1, self.line_start - 2)
        last = min(len(lines), max(self.line_start, self.line_end))
        width = len(str(last))
        excerpt = []
        for line_number in range(first, last + 1):
            marker = ">" if self.line_start <= line_number <= self.line_end else " "
            excerpt.append(
                f"{marker} {line_number:0{width}d} | {lines[line_number - 1].strip()}"
            )
        header = f"{self.source_name}:{self.line_start}: {self.message}"
        return "\n".join([header, *excerpt])


class MaoLangError(Exception):
    """Raised when parsing or executing MaoLang source fails."""

    def __init__(self, diagnostics: Diagnostic | tuple[Diagnostic, ...]):
        if isinstance(diagnostics, Diagnostic):
            diagnostics = (diagnostics,)
        if not diagnostics:
            raise ValueError("MaoLangError requires at least one diagnostic")
        self.diagnostics = diagnostics
        super().__init__(diagnostics[0].message)

    def with_context(self, diagnostic: Diagnostic) -> "MaoLangError":
        """Return an error with an additional outer source context."""

        return MaoLangError((*self.diagnostics, diagnostic))

    def __str__(self) -> str:
        return "\n\n".join(diagnostic.format() for diagnostic in self.diagnostics)
