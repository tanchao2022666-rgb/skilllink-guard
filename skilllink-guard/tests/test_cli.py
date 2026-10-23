import json
import subprocess
import sys
from pathlib import Path

import pytest

from skilllink_guard.cli import main


def run(*args):
    return subprocess.run([sys.executable, "-m", "skilllink_guard", *map(str, args)], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8")


@pytest.mark.parametrize("file_input", [False, True])
def test_valid_exit(skill, file_input):
    file = skill("[guide](references/guide.md)\n\n`python scripts/hello.py`", ["references/guide.md", "scripts/hello.py"])
    result = run("check", file if file_input else file.parent)
    assert result.returncode == 0
    assert "Scanned 1 skill(s)" in result.stdout
    assert "0 error(s), 0 warning(s)" in result.stdout
    assert result.stderr == ""


def test_broken_and_json(skill):
    file = skill("[中文](references/不存在.md)\n`python scripts/broken.py`")
    result = run("check", file, "--format", "json")
    assert result.returncode == 1 and result.stderr == ""
    obj = json.loads(result.stdout)
    assert obj["summary"] == {"errors": 2, "warnings": 0}
    assert obj["diagnostics"][0]["line"] == 1
    assert obj["diagnostics"][1]["line"] == 2
    assert "\\" not in obj["diagnostics"][0]["file"]
    assert "不存在" in result.stdout


def test_multi_skill_sort_and_count(skill, tmp_path):
    skill("[z](missing)", name="z")
    skill("[a](missing)", name="a")
    a = run("check", tmp_path, "--format", "json")
    b = run("check", tmp_path, "--format", "json")
    assert a.returncode == 1 and a.stdout == b.stdout
    obj = json.loads(a.stdout)
    assert obj["skills_scanned"] == 2
    assert "/a/SKILL.md" in obj["diagnostics"][0]["file"]


@pytest.mark.parametrize("kind", ["missing", "empty", "invalid-utf8"])
def test_scan_failures_exit_2(tmp_path, skill, kind):
    path = tmp_path / kind
    if kind == "empty":
        path.mkdir()
    elif kind == "invalid-utf8":
        path = skill()
        path.write_bytes(b"\xff\xfe")
    result = run("check", path, "--format", "json")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "skilllink:" in result.stderr and "Traceback" not in result.stderr


def test_strict_warning(skill):
    file = skill("[external](../external.md)")
    assert run("check", file).returncode == 0
    assert run("check", file, "--strict").returncode == 1


@pytest.mark.parametrize("arguments", [("--help",), ("--version",), ("check", "--help")])
def test_help_version(arguments):
    result = run(*arguments)
    assert result.returncode == 0 and result.stdout and not result.stderr


@pytest.mark.parametrize("arguments", [(), ("bad-command",), ("check",), ("check", ".", "--format", "bad")])
def test_usage_errors(arguments):
    result = run(*arguments)
    assert result.returncode == 2 and "usage:" in result.stderr


def test_unreadable_file_exit_2(skill, monkeypatch, capsys):
    file = skill()
    def fail(*args, **kwargs):
        raise PermissionError("fixture cannot read")
    monkeypatch.setattr(type(file), "read_text", fail)
    assert main(["check", str(file)]) == 2
    captured = capsys.readouterr()
    assert not captured.out and "fixture cannot read" in captured.err


@pytest.mark.parametrize("exception", [ValueError, RuntimeError, TypeError])
def test_output_internal_failure_exit_2(skill, monkeypatch, capsys, exception):
    file = skill()
    def fail(*args, **kwargs):
        raise exception("fixture output failure")
    monkeypatch.setattr("skilllink_guard.cli.render", fail)
    assert main(["check", str(file), "--format", "json"]) == 2
    captured = capsys.readouterr()
    assert not captured.out and "fixture output failure" in captured.err


def test_github_cli(skill):
    file = skill("[missing](missing.md)")
    result = run("check", file, "--format", "github")
    assert result.returncode == 1
    assert result.stdout.startswith("::error file=")
    assert ",line=1::LINK_MISSING: missing.md" in result.stdout
