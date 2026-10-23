"""Normalize candidates and inspect only metadata within the Skill boundary."""

import os
import posixpath
import re
import stat
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote

from .discovery import is_link_info


@dataclass(frozen=True)
class Target:
    reference: str
    outside: bool
    exists: bool
    is_file: bool


def clean_path(value: str, *, link: bool = False) -> str | None:
    value = value.strip()
    if not link:
        value = value.rstrip(",;!.。；，")
        if value.startswith("(") and value.endswith(")"):
            value = value[1:-1].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    elif value.startswith(("\"", "'")) or value.endswith(("\"", "'")):
        return None
    if not value or any(ord(c) < 32 for c in value):
        return None
    if value.startswith("#") or value.startswith("//"):
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and not re.match(r"^[a-zA-Z]:", value):
        return None
    if link:
        value = value.split("#", 1)[0].split("?", 1)[0]
        value = unquote(value)
    if not value or re.search(r"[$%~*?<>\[\]{}]", value) or "`" in value:
        return None
    if any(ord(c) < 32 for c in value):
        return None
    # Both single backslashes and Markdown's doubled Windows separators work.
    value = re.sub(r"\\+", "/", value)
    if os.name == "nt":
        # Win32 silently aliases trailing dots/spaces and device names. These
        # are not unambiguous Skill resources; do not query their metadata.
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"{prefix}{n}" for prefix in ("COM", "LPT") for n in "123456789¹²³")}
        for index, part in enumerate(value.split("/")):
            if part in {"", ".", ".."} or (index == 0 and re.fullmatch(r"[A-Za-z]:", part)):
                continue
            if part.rstrip(" .") != part or ":" in part or part.split(".", 1)[0].upper() in reserved:
                return None
    return value


def inspect_target(root: Path, value: str) -> Target:
    reference = posixpath.normpath(value)
    root = Path(os.path.abspath(root))
    foreign_drive = PureWindowsPath(value).drive
    if foreign_drive and (os.name != "nt" or not PureWindowsPath(value).is_absolute()):
        return Target(reference, True, False, False)
    if value.startswith("/") or foreign_drive:
        candidate = Path(value)
        if not candidate.is_relative_to(root):
            return Target(reference, True, False, False)
        pending = deque(candidate.relative_to(root).parts)
    else:
        pending = deque(value.split("/"))
    current = root
    hops = 0
    while pending:
        part = pending.popleft()
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent
            if not current.is_relative_to(root):
                return Target(reference, True, False, False)
            continue
        current = current / part
        if not current.is_relative_to(root):
            return Target(reference, True, False, False)
        try:
            info = current.lstat()
        except (FileNotFoundError, NotADirectoryError):
            outside = _remaining_escapes(root, current, pending)
            normalized = reference if outside else _resolved_reference(root, current, pending)
            return Target(normalized, outside, False, False)
        if is_link_info(info):
            hops += 1
            if hops > 40:
                raise OSError(f"Symbolic link loop in Skill target: {reference}")
            raw = os.readlink(current)
            # Windows junction readlink() may return an extended-length path.
            if raw.startswith("\\\\?\\UNC\\"):
                raw = "\\\\" + raw[8:]
            elif raw.startswith("\\\\?\\"):
                raw = raw[4:]
            target = Path(raw)
            if (target.drive or target.root) and not target.is_absolute():
                return Target(reference, True, False, False)
            if target.is_absolute():
                if not target.is_relative_to(root):
                    return Target(reference, True, False, False)
                pending = deque(target.relative_to(root).parts) + pending
                current = root
            else:
                # Preserve '..': an earlier component can itself be a link.
                pending = deque(target.parts) + pending
                current = current.parent
        elif pending and not stat.S_ISDIR(info.st_mode):
            return Target(reference, _remaining_escapes(root, current, pending), False, False)
    info = current.lstat()
    return Target(current.relative_to(root).as_posix(), False, True, stat.S_ISREG(info.st_mode))


def _resolved_reference(root: Path, current: Path, pending) -> str:
    return posixpath.normpath("/".join((current.relative_to(root).as_posix(), *pending)))


def _remaining_escapes(root: Path, current: Path, pending) -> bool:
    """A missing prefix cannot resolve, but lexical traversal still warns."""
    for part in pending:
        current = current.parent if part == ".." else current / part
        if not current.is_relative_to(root):
            return True
    return False
