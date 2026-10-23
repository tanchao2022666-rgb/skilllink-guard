import json

from skilllink_guard.models import Diagnostic, ScanResult
from skilllink_guard.reporters import render


def result():
    return ScanResult(1, (Diagnostic("error", "LINK_MISSING", "C:/a,b%file\r\n::error::injected/SKILL.md", 7, "中文%\n::warning::bad", "missing\r\ntext", "fix%it"),))


def test_github_escaping():
    output = render(result(), "github")
    assert output.count("::error ") == 1
    assert len(output.splitlines()) == 1
    assert "file=C%3A/a%2Cb%25file%0D%0A" in output
    assert "line=7::" in output
    assert "中文%25%0A::warning::bad" in output
    assert "missing%0D%0Atext" in output
    assert "fix%25it" in output


def test_json_structure():
    obj = json.loads(render(result(), "json"))
    assert obj["tool"] == "skilllink-guard" and obj["version"] == "0.1.0"
    assert obj["skills_scanned"] == 1 and obj["summary"] == {"errors": 1, "warnings": 0}
    assert set(obj["diagnostics"][0]) == {"severity", "code", "file", "line", "reference", "message", "suggestion"}
    assert "中文" in obj["diagnostics"][0]["reference"]


def test_text_is_safe_and_empty_github():
    assert "\n::error::injected" not in render(result())
    assert "Summary: 1 error(s), 0 warning(s)" in render(result())
    assert render(ScanResult(1, ()), "github") == ""
