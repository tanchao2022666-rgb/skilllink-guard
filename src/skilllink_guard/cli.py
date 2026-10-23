import argparse
import sys
from pathlib import Path

from . import __version__
from .reporters import render, single_line
from .scanner import scan


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        super().error(single_line(message))


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            except (OSError, ValueError):
                pass  # Console reconfiguration is best effort.


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = _Parser(prog="skilllink", description="Statically check local Skill resources and script targets.")
    parser.add_argument("--version", action="version", version=f"SkillLink Guard {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check a SKILL.md, Skill directory, or repository")
    check.add_argument("path", type=Path)
    check.add_argument("--format", choices=("text", "json", "github"), default="text")
    check.add_argument("--strict", action="store_true", help="Treat warnings as scan failures")
    args = parser.parse_args(argv)
    try:
        result = scan(args.path)
        output = render(result, args.format)
        if output:
            print(output)
        sys.stdout.flush()
        return result.exit_code(args.strict)
    except Exception as error:
        # Public process boundary: a failed scan/reporter is never a success
        # or an uncaught traceback. argparse usage exits are handled above.
        print(f"skilllink: {single_line(str(error))}", file=sys.stderr)
        return 2
