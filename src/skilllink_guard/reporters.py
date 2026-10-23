import json
from dataclasses import asdict

from . import __version__
from .models import ScanResult


def single_line(value: str) -> str:
    return "".join({"\r": "\\r", "\n": "\\n", "\t": "\\t"}.get(c, f"\\x{ord(c):02x}") if ord(c) < 32 or ord(c) == 127 else c for c in value)


def _escape(value: str, *, property_value: bool = False) -> str:
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return value.replace(":", "%3A").replace(",", "%2C") if property_value else value


def render(result: ScanResult, format: str = "text") -> str:
    if format == "json":
        return json.dumps({
            "tool": "skilllink-guard", "version": __version__,
            "skills_scanned": result.skills_scanned,
            "summary": {"errors": result.errors, "warnings": result.warnings},
            "diagnostics": [asdict(d) for d in result.diagnostics],
        }, ensure_ascii=False, indent=2)
    if format == "github":
        return "\n".join(
            f"::{d.severity} file={_escape(d.file, property_value=True)},line={d.line}::"
            + _escape(f"{d.code}: {d.reference} - {d.message} {d.suggestion}")
            for d in result.diagnostics
        )
    if format != "text":
        raise ValueError(f"Unknown output format: {format}")
    lines = [f"SkillLink Guard {__version__}", f"Scanned {result.skills_scanned} skill(s)"]
    for d in result.diagnostics:
        # Keep each diagnostic on one physical terminal line as well.
        location = single_line(f"{d.file}:{d.line}")
        reference = single_line(d.reference)
        lines.append(f"{location}: {d.severity.upper()} {d.code} {reference} - {d.message}")
        lines.append(f"  Suggestion: {d.suggestion}")
    lines.append(f"Summary: {result.errors} error(s), {result.warnings} warning(s)")
    return "\n".join(lines)
