"""Markdown parsing with source offsets and conservative command extraction."""

from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.rules_inline.backticks import backtick
from markdown_it.rules_inline.image import image
from markdown_it.rules_inline.link import link

from .commands import command_target
from .discovery import discover
from .models import Diagnostic, ScanError, ScanResult
from .paths import clean_path, inspect_target

_SHELLS = {"bash", "sh", "shell", "console", "terminal"}
_PRIORITY = {"COMMAND_TARGET_MISSING": 0, "INLINE_PATH_MISSING": 1, "LINK_MISSING": 2}


@dataclass(frozen=True)
class Candidate:
    code: str
    value: str
    line: int
    group: tuple[int, ...]


def _positioned(rule):
    def wrapped(state, silent):
        start, count = state.pos, len(state.tokens)
        result = rule(state, silent)
        if result and not silent:
            for token in state.tokens[count:]:
                token.meta.setdefault("offset", start)
                if rule is link:
                    token.meta["group"] = (start, state.pos)
        return result
    return wrapped


def _spaced_link(state, silent):
    """Small extension for [label](local path with spaces), also images.

    CommonMark requires <...> or %20. Only extend single-line destinations
    containing spaces; leave standard links and reference definitions alone.
    """
    start = state.pos
    image_link = state.src.startswith("![", start)
    label_start = start + (2 if image_link else 1)
    if not image_link and not state.src.startswith("[", start):
        return False
    end = state.src.find("](", label_start)
    if end < 0:
        return False
    close = state.src.find(")", end + 2)
    if close < 0:
        return False
    label, value = state.src[label_start:end], state.src[end + 2:close].strip()
    if " " not in value or any(c in value + label for c in "\n()\"'<>[]`"):
        return False
    if not silent:
        token = state.push("image" if image_link else "link_open", "img" if image_link else "a", 0 if image_link else 1)
        token.attrSet("src" if image_link else "href", value)
        token.meta.update(offset=start, group=(start, close + 1))
        if not image_link:
            state.push("text", "", 0).content = label
            state.push("link_close", "a", -1)
    state.pos = close + 1
    return True


def _parser() -> MarkdownIt:
    md = MarkdownIt("commonmark")
    md.inline.ruler.at("link", _positioned(link))
    md.inline.ruler.at("image", _positioned(image))
    md.inline.ruler.at("backticks", _positioned(backtick))
    # Standard syntax has priority (in particular, links with quoted titles).
    def link_or_spaced(state, silent):
        return _positioned(link)(state, silent) or _spaced_link(state, silent)
    def image_or_spaced(state, silent):
        return _positioned(image)(state, silent) or _spaced_link(state, silent)
    md.inline.ruler.at("link", link_or_spaced)
    md.inline.ruler.at("image", image_or_spaced)
    return md


def _without_frontmatter(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() in {"---", "..."}:
                return "\n" * (index + 1) + "".join(lines[index + 1:])
    return text


def extract(text: str) -> list[Candidate]:
    candidates = []
    for token in _parser().parse(_without_frontmatter(text)):
        if token.type == "fence" and token.info.split() and token.info.split()[0].lower() in _SHELLS:
            for offset, line in enumerate(token.content.splitlines()):
                target = command_target(line)
                if target:
                    line_no = token.map[0] + offset + 2
                    candidates.append(Candidate("COMMAND_TARGET_MISSING", target, line_no, (line_no, -1)))
        elif token.type == "inline":
            for child in token.children or []:
                offset = child.meta.get("offset", 0)
                line_no = token.map[0] + 1 + token.content[:offset].count("\n")
                group = child.meta.get("group", (offset, offset + 1))
                # Include block identity, so two separate inline blocks never merge.
                group = (token.map[0], *group)
                if child.type in {"link_open", "image"}:
                    value = child.attrGet("href" if child.type == "link_open" else "src")
                    if value:
                        candidates.append(Candidate("LINK_MISSING", value, line_no, group))
                elif child.type == "code_inline":
                    target = command_target(child.content)
                    if target:
                        candidates.append(Candidate("COMMAND_TARGET_MISSING", target, line_no, group))
                    else:
                        value = clean_path(child.content)
                        if value and value.removeprefix("./").startswith(("scripts/", "references/", "assets/")):
                            raw = child.content.strip().rstrip(",;!.。；，")
                            quoted = len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'"
                            if any(c.isspace() for c in value) and not quoted:
                                continue
                            # Keep original quotes so literal punctuation is
                            # not stripped a second time during path checking.
                            candidates.append(Candidate("INLINE_PATH_MISSING", child.content, line_no, group))
    return candidates


def scan_file(path: Path, *, display: str | None = None) -> list[Diagnostic]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        checked = []
        for candidate in extract(text):
            value = clean_path(candidate.value, link=candidate.code == "LINK_MISSING")
            if value is None:
                continue
            target = inspect_target(path.parent, value)
            checked.append((candidate, target))
        # Suppress lower-priority interpretations only in the same inline syntax.
        winners = {}
        for candidate, target in checked:
            key = (candidate.group, target.reference)
            winners[key] = min(winners.get(key, 9), _PRIORITY[candidate.code])
        diagnostics = {}
        for candidate, target in checked:
            if _PRIORITY[candidate.code] != winners[(candidate.group, target.reference)]:
                continue
            if target.outside:
                code, severity = "OUTSIDE_SKILL", "warning"
                message = "Referenced path leaves the Skill root; external target was not inspected."
                suggestion = "Use a static resource inside this Skill directory."
            elif not target.exists or (candidate.code == "COMMAND_TARGET_MISSING" and not target.is_file):
                code, severity = candidate.code, "error"
                message = "Command references a missing local script." if code == "COMMAND_TARGET_MISSING" else "Referenced file does not exist."
                suggestion = "Add the script or correct the path relative to the Skill root." if code == "COMMAND_TARGET_MISSING" else "Add the resource or correct the path relative to the Skill root."
            else:
                continue
            diagnostic = Diagnostic(severity, code, display or path.as_posix(), candidate.line, target.reference, message, suggestion)
            diagnostics[(candidate.line, code, target.reference)] = diagnostic
        return sorted(diagnostics.values(), key=lambda d: (d.line, d.code, d.reference))
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise ScanError(f"Cannot scan {path}: {error}") from error


def scan(path: Path) -> ScanResult:
    files = discover(path)
    diagnostics = []
    for file in files:
        try:
            display = file.relative_to(Path.cwd()).as_posix()
        except ValueError:
            display = file.as_posix()
        diagnostics.extend(scan_file(file, display=display))
    return ScanResult(len(files), tuple(diagnostics))
