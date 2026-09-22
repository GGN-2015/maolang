from maolang import LibraryCall, LibraryResult


def maolang_library(call: LibraryCall) -> LibraryResult:
    arguments = list(call.arguments)
    if not arguments:
        arguments.extend(["", "_ANS"])
    elif len(arguments) == 1:
        arguments.append("_ANS")

    expression = arguments[0].replace("\n", " ").strip()
    return {arguments[1]: str(eval(expression))}
