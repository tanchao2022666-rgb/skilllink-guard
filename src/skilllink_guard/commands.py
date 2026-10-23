"""A deliberately small, non-executing command recognizer."""

import re

from .paths import clean_path

# Unlike POSIX shlex, this does not consume Windows backslashes as escapes.
_WORD = re.compile(r'''\s*(?:"([^"\n]*)"[,;!.。；，]*|'([^'\n]*)'[,;!.。；，]*|([^\s"'`]+))(?=\s|$)''')
_PY_FLAGS = frozenset({"-b", "-B", "-d", "-E", "-i", "-I", "-O", "-OO", "-P", "-q", "-s", "-S", "-u", "-v", "-x"})


def command_target(text: str) -> str | None:
    text = text.strip()
    if text.startswith("$ "):
        text = text[2:]
    words = []
    pos = 0
    while pos < len(text):
        match = _WORD.match(text, pos)
        if not match:
            return None
        value = next(g for g in match.groups() if g is not None)
        quote = '"' if match.group(1) is not None else ("'" if match.group(2) is not None else "")
        words.append((value, quote))
        pos = match.end()
        # Stop once a potential target is known; script arguments are opaque.
        if len(words) > 1:
            if words[0][0] in {"python", "python3", "py"} and words[-1][0] in _PY_FLAGS:
                continue
            if words[0][0] in {"pwsh", "powershell"} and len(words) == 2 and words[1][0].lower() == "-file":
                continue
            break
        if words[0][0].startswith(("./", ".\\")):
            break
    if not words:
        return None
    command = words[0][0]
    if command.startswith(("./", ".\\")):
        target, quote = words[0]
        suffixes = (".sh", ".ps1")
    elif command in {"python", "python3", "py"}:
        index = 1
        while index < len(words) and words[index][0] in _PY_FLAGS:
            index += 1
        if index >= len(words) or words[index][0].startswith("-"):
            return None
        target, quote = words[index]
        suffixes = (".py",)
    elif command in {"bash", "sh", "node"} and len(words) > 1:
        target, quote = words[1]
        suffixes = (".js", ".mjs") if command == "node" else (".sh",)
    elif command in {"pwsh", "powershell"} and len(words) > 2 and words[1][0].lower() == "-file":
        target, quote = words[2]
        suffixes = (".ps1",)
    else:
        return None
    raw = quote + target + quote
    canonical = clean_path(raw)
    if canonical is None or canonical.startswith("-") or (not quote and any(c in canonical for c in "|;&")):
        return None
    return raw if canonical.lower().endswith(suffixes) else None
