import pytest

from skilllink_guard.scanner import scan_file


@pytest.mark.parametrize("value", ["scripts/missing.py", "./references/README.md", "assets/photo.png", r".\scripts\missing.py", r"scripts\\missing.py", '"scripts/with space.py"', "'scripts/with space.py'", "scripts/missing.py,"])
def test_explicit_inline_path(skill, value):
    ds = scan_file(skill(f"intro\n`{value}`"))
    assert len(ds) == 1
    assert (ds[0].line, ds[0].code) == (2, "INLINE_PATH_MISSING")
    assert "\\" not in ds[0].reference


@pytest.mark.parametrize("text", [
    "scripts/missing.py", "plain words `hello.py`", "`look at scripts/foo.py please`",
    "`https://example.com/scripts/foo.py`", "`foo.py`", "`other/foo.md`",
    "    python scripts/missing.py", "```python\nprint('scripts/missing.py')\n```",
])
def test_not_explicit_inline_path(skill, text):
    assert scan_file(skill(text)) == []


@pytest.mark.parametrize("value", ["scripts/$VAR.py", "scripts/${VAR}.py", "scripts/%VAR%.py", "scripts/*.py", "scripts/?.py", "scripts/<name>.py", "~/scripts/a.py", "scripts/{{name}}.py", "scripts/[ab].py"])
def test_dynamic_inline_paths_ignored(skill, value):
    assert scan_file(skill(f"`{value}`")) == []


def test_multiline_inline_actual_start_line(skill):
    ds = scan_file(skill("first\nsecond\n`python scripts/missing.py`"))
    assert ds[0].line == 3


def test_trailing_period_existing_inline_path(skill):
    assert scan_file(skill('`"scripts/a.py".`', ["scripts/a.py"])) == []


def test_parentheses_and_punctuation_inline_path(skill):
    ds = scan_file(skill('`(scripts/missing.py),`'))
    assert len(ds) == 1 and ds[0].reference == "scripts/missing.py"
