from pathlib import Path

from test_cli import run

ROOT = Path(__file__).resolve().parents[1]


def test_composite_untrusted_input_only_in_environment():
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "using: composite" in action
    assert "SKILLLINK_INPUT_PATH: ${{ inputs.path }}" in action
    assert 'check --format github -- "$SKILLLINK_INPUT_PATH"' in action
    assert 'pip install -- "$SKILLLINK_ACTION_PATH"' in action
    for line in action.splitlines():
        if "run:" in line:
            assert "${{" not in line


def test_ci_restricted_permissions_and_matrix():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "on: [push, pull_request]" in ci
    assert "pull_request_target" not in ci and "secrets." not in ci
    assert "contents: read" in ci and "contents: write" not in ci
    assert "ubuntu-latest" in ci and "windows-latest" in ci
    assert "'3.11'" in ci and "'3.12'" in ci
    assert "pytest -q" in ci and "python -m build" in ci


def test_leading_dash_and_shell_metacharacters_are_path_data(skill, tmp_path):
    file = skill("", name="-weird; echo injected")
    result = run("check", "--format", "json", "--", file.parent)
    assert result.returncode == 0
    assert not (tmp_path / "injected").exists()
