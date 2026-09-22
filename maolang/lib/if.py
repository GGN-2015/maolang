from maolang import LibraryCall, LibraryResult


def maolang_library(call: LibraryCall) -> LibraryResult:
    flag, true_value, false_value, destination = call.arguments[:4]
    if flag.lower() not in {"false", "none", "0"}:
        return {destination: true_value}
    return {destination: false_value}
