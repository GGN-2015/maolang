"""Public protocol for in-process MaoLang library commands."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, TextIO, Union


@dataclass(frozen=True)
class LibrarySource:
    """Generated MaoLang source with an optional file context."""

    source: str
    source_name: Optional[str] = None
    source_path: Optional[Path] = None


LibraryResult = Optional[Union[str, Mapping[str, str], LibrarySource]]


@dataclass
class LibraryCall:
    """Arguments and streams available to a library command."""

    name: str
    arguments: list[str]
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO
    path: Optional[Path] = None
    source_path: Optional[Path] = None


LibraryHandler = Callable[[LibraryCall], LibraryResult]
