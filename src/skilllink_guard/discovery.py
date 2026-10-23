"""Deterministic discovery; never descend into symbolic links or junctions."""

import os
import stat
from pathlib import Path

from .models import ScanError

EXCLUDED = frozenset({
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
})


def is_link(path: Path) -> bool:
    return is_link_info(path.lstat())


def is_link_info(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def discover(path: Path) -> list[Path]:
    path = Path(path)
    try:
        if path.drive and not path.is_absolute():
            raise ScanError(f"Drive-relative input is ambiguous: {path}")
        raw = path if path.is_absolute() else Path.cwd() / path
        # Do not normalize away a linked component followed by '..'.
        current = Path(raw.anchor)
        for part in raw.parts[1:]:
            current = current.parent if part == ".." else current / part
            if is_link(current):
                raise ScanError(f"Input must not traverse symbolic links or junctions: {current}")
        path = current
        if path.is_file():
            if path.name != "SKILL.md":
                raise ScanError("Input file must be named SKILL.md.")
            return [path]
        if not path.is_dir():
            raise ScanError(f"Input is not a readable file or directory: {path}")
        found = []
        pending = [path]
        while pending:
            root = pending.pop()
            with os.scandir(root) as entries:
                for entry in sorted(entries, key=lambda item: item.name):
                    if entry.name in EXCLUDED:
                        continue
                    # os.walk classifies links using is_dir() with following
                    # enabled. Inspect only the entry itself instead.
                    info = entry.stat(follow_symlinks=False)
                    if is_link_info(info):
                        continue
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(root / entry.name)
                    elif entry.name == "SKILL.md" and stat.S_ISREG(info.st_mode):
                        found.append(root / entry.name)
        if not found:
            raise ScanError(f"No SKILL.md found in: {path}")
        return sorted(found, key=lambda p: p.as_posix())
    except (OSError, ValueError) as error:
        raise ScanError(f"Cannot read input {path}: {error}") from error
