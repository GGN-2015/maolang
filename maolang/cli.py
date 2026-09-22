"""Command-line interface for MaoLang."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from . import __version__
from .errors import MaoLangError
from .interpreter import Interpreter
from .repl import run_repl


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maolang",
        description="Execute MaoLang source code.",
    )
    parser.add_argument("file", nargs="?", help="source file, or '-' for standard input")
    parser.add_argument("-c", "--code", help="execute source passed on the command line")
    parser.add_argument(
        "-i",
        "--interactive",
        "--repl",
        action="store_true",
        help="enter the REPL, optionally after executing FILE or --code",
    )
    parser.add_argument(
        "-L",
        "--lib-dir",
        action="append",
        default=[],
        metavar="DIR",
        help="search DIR before the bundled library (repeatable)",
    )
    parser.add_argument(
        "-D",
        "--define",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="set an initial environment value (repeatable)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="source file encoding (default: utf-8)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="trace execution")
    parser.add_argument(
        "--dump-env",
        action="store_true",
        help="write the final environment as JSON to standard error",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _parse_definitions(
    parser: argparse.ArgumentParser, definitions: Sequence[str]
) -> dict[str, str]:
    env: dict[str, str] = {}
    for definition in definitions:
        if "=" not in definition:
            parser.error(f"invalid definition {definition!r}; expected NAME=VALUE")
        name, value = definition.split("=", 1)
        if not name:
            parser.error("definition name cannot be empty")
        env[name] = value
    return env


def main(argv: Sequence[str] | None = None) -> int:
    """Run the MaoLang CLI and return its process exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.code is not None and args.file is not None:
        parser.error("FILE and --code cannot be used together")

    env = _parse_definitions(parser, args.define)
    stdin_is_tty = sys.stdin.isatty()
    implicit_repl = args.code is None and args.file is None and stdin_is_tty
    start_repl = args.interactive or implicit_repl

    source: str | None
    source_name: str
    source_path: Path | None = None
    if args.code is not None:
        source = args.code
        source_name = "<command>"
    elif args.file == "-":
        source = sys.stdin.read()
        source_name = "<stdin>"
    elif args.file is not None:
        try:
            source_path = Path(args.file).expanduser().resolve()
        except OSError as error:
            parser.exit(1, f"maolang: cannot resolve {args.file}: {error}\n")
        source = None
        source_name = str(source_path)
    elif start_repl:
        source = None
        source_name = "<repl>"
    else:
        source = sys.stdin.read()
        source_name = "<stdin>"

    interpreter = Interpreter(args.lib_dir, verbose=args.verbose)
    try:
        final_env = env
        if source_path is not None:
            final_env = interpreter.execute_file(
                source_path,
                env,
                encoding=args.encoding,
            )
        elif source is not None:
            final_env = interpreter.execute(source, env, source_name=source_name)
        if start_repl:
            final_env = run_repl(
                interpreter,
                final_env,
                show_prompts=stdin_is_tty,
                banner=f"MaoLang {__version__}. Type :help for help.",
            )
    except MaoLangError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as error:
        print(f"maolang: cannot read {source_path}: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    if args.dump_env:
        print(json.dumps(final_env, ensure_ascii=False, indent=2), file=sys.stderr)
    return 0
