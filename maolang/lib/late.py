from maolang import LibraryCall, LibraryResult


def maolang_library(call: LibraryCall) -> LibraryResult:
    source = call.arguments[0] if call.arguments else ""
    return source.replace("$_", "$").replace("\\n", "\n")
