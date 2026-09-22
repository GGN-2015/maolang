"""Public Python API for the MaoLang interpreter."""

from .errors import Diagnostic, MaoLangError
from .interpreter import Interpreter, get_builtin_lib_dir, resolve_lib_dirs, run, run_file
from .library import LibraryCall, LibraryHandler, LibraryResult, LibrarySource
from .repl import run_repl

__all__ = [
    "Diagnostic",
    "Interpreter",
    "LibraryCall",
    "LibraryHandler",
    "LibraryResult",
    "LibrarySource",
    "MaoLangError",
    "get_builtin_lib_dir",
    "resolve_lib_dirs",
    "run",
    "run_file",
    "run_repl",
]

__version__ = "0.1.0"
