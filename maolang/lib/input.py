from maolang import LibraryCall, LibraryResult


def maolang_library(call: LibraryCall) -> LibraryResult:
    destination = call.arguments[0].strip()
    value = call.stdin.readline()
    if value == "":
        raise EOFError("input reached end-of-file")
    return {destination: value.rstrip("\r\n")}
