from pathlib import Path

from maolang import LibraryCall, LibraryResult, LibrarySource


def maolang_library(call: LibraryCall) -> LibraryResult:
    if len(call.arguments) != 1:
        raise ValueError("run expects exactly one relative script path")

    relative_path = Path(call.arguments[0])
    if relative_path.is_absolute() or relative_path.drive:
        raise ValueError("run only accepts a relative script path")

    base_dir = (
        call.source_path.parent if call.source_path is not None else Path.cwd()
    )
    target = (base_dir / relative_path).resolve()
    return LibrarySource(
        source=target.read_text(encoding="utf-8"),
        source_name=str(target),
        source_path=target,
    )
