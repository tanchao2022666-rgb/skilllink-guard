import pytest

from skilllink_guard.scanner import scan_file


@pytest.mark.parametrize("language,command", [
    ("bash", "python scripts/missing.py"), ("sh", "python3 scripts/missing.py"),
    ("shell", "py scripts/missing.py"), ("console", "python -u scripts/missing.py"),
    ("terminal", "python3 -B scripts/missing.py"), ("bash", "python -u -B scripts/missing.py"),
    ("sh", "bash scripts/missing.sh"), ("sh", "sh scripts/missing.sh"),
    ("shell", "node scripts/missing.js"), ("shell", "node scripts/missing.mjs"),
    ("bash", "./scripts/missing.sh"), ("shell", r".\scripts\missing.ps1"),
    ("shell", r".\\scripts\\missing.ps1"), ("console", 'python "scripts/a b.py" --output ignored.json'),
    ("terminal", "python 'scripts/a b.py' arg.py"), ("bash", "$ python scripts/missing.py"),
    ("shell", "pwsh -File scripts/missing.ps1"), ("shell", "powershell -file scripts/missing.ps1"),
])
def test_shell_commands(skill, language, command):
    ds = scan_file(skill(f"# Title\n\n```{language}\n{command}\n```\n"))
    assert len(ds) == 1
    assert (ds[0].code, ds[0].line) == ("COMMAND_TARGET_MISSING", 4)
    assert "\\" not in ds[0].reference


@pytest.mark.parametrize("command", [
    "python -m module", "python -u -m module", "python -c 'print(1)'", "echo scripts/foo.py",
    "node -e 'console.log(1)'", "python --unknown scripts/a.py", "python -W ignore scripts/a.py",
    "python $ROOT/scripts/a.py", "python scripts/${NAME}.py", "python %ROOT%/a.py",
    "python ~/scripts/a.py", "python scripts/*.py", "python scripts/a?.py", "python <placeholder>.py",
    "python https://example.com/scripts/x.py", "npm scripts/a.js", "bash -c 'echo hi'",
])
def test_ignored_commands(skill, command):
    assert scan_file(skill(f"```bash\n{command}\n```\n\n`{command}`")) == []


def test_only_first_script_and_ignore_arguments(skill):
    text = "```bash\npython scripts/existing.py scripts/missing.py --output missing.json\n```"
    assert scan_file(skill(text, ["scripts/existing.py"])) == []


def test_many_or_opaque_arguments_do_not_hide_target(skill):
    command = "python scripts/missing.py " + "arg " * 40 + '"unclosed'
    ds = scan_file(skill(f"`{command}`"))
    assert len(ds) == 1 and ds[0].reference == "scripts/missing.py"


@pytest.mark.parametrize("command", ["python scripts/hello.py.", "python scripts/hello.py,", "python scripts/hello.py;", 'python "scripts/hello.py"', "python 'scripts/hello.py'"])
def test_quoted_or_punctuated_existing_command(skill, command):
    assert scan_file(skill(f"`{command}`", ["scripts/hello.py"])) == []


def test_command_directory_not_file(skill):
    file = skill("`python scripts/directory.py`", ["scripts/directory.py/inside.txt"])
    ds = scan_file(file)
    assert len(ds) == 1 and ds[0].code == "COMMAND_TARGET_MISSING"


def test_never_execute(skill):
    file = skill('```bash\npython scripts/mark.py\n```\n\n`python scripts/mark.py`', ["scripts/mark.py"])
    marker = file.parent / "EXECUTED"
    (file.parent / "scripts/mark.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n", encoding="utf-8")
    before = file.read_bytes()
    assert scan_file(file) == []
    assert not marker.exists()
    assert file.read_bytes() == before


def test_multiple_shell_lines_exact_line(skill):
    ds = scan_file(skill("```bash\n# comment\n\npython scripts/one.py\nnode scripts/two.js\n```"))
    assert [d.line for d in ds] == [4, 5]


@pytest.mark.parametrize("language", ["python", "javascript", "powershell", "", "text"])
def test_other_fences_not_shell(skill, language):
    assert scan_file(skill(f"```{language}\npython scripts/a.py\n```")) == []
