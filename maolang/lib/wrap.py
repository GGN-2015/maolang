from maolang import LibraryCall, LibraryResult


def maolang_library(call: LibraryCall) -> LibraryResult:
    prefix = call.arguments[0]
    content = " ".join(call.arguments[1:])

    brace_count = 0
    escaped: list[str] = []
    for character in content:
        if character == "{":
            brace_count += 1
            escaped.append(character)
        elif character == "}":
            brace_count -= 1
            escaped.append(character)
        elif character == "\n" and brace_count > 0:
            escaped.append("\\n")
        else:
            escaped.append(character)

    return "\n".join(
        f"{prefix} {{{line}}}"
        for line in "".join(escaped).split("\n")
        if line.strip()
    )
