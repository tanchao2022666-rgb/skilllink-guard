from dataclasses import dataclass


class ScanError(Exception):
    """The scan could not reliably complete (CLI exit code 2)."""


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    file: str
    line: int
    reference: str
    message: str
    suggestion: str


@dataclass(frozen=True)
class ScanResult:
    skills_scanned: int
    diagnostics: tuple[Diagnostic, ...]

    @property
    def errors(self) -> int:
        return sum(d.severity == "error" for d in self.diagnostics)

    @property
    def warnings(self) -> int:
        return sum(d.severity == "warning" for d in self.diagnostics)

    def exit_code(self, strict: bool = False) -> int:
        return int(bool(self.errors or (strict and self.warnings)))
