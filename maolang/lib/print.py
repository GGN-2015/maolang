from maolang import LibraryCall, LibraryResult


def maolang_library(call: LibraryCall) -> LibraryResult:
    return {"_PRINT": " ".join(call.arguments)}
