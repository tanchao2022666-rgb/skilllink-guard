from pathlib import Path

import pytest

from skilllink_guard.models import ScanError
from skilllink_guard.paths import clean_path
from skilllink_guard.scanner import scan_file


@pytest.mark.parametrize("value", ["../external.md", "../../absent.md", "references/../../external.md", "%2E%2E/external.md"])
def test_traversal_warning_before_external_access(skill, tmp_path, monkeypatch, value):
    file = skill(f"[external]({value})")
    outside = tmp_path / "external.md"
    outside.write_text("must not be read", encoding="utf-8")
    original_lstat = Path.lstat
    original_read = Path.read_text
    def guarded_stat(path, *args, **kwargs):
        assert path.is_relative_to(file.parent), f"Outside stat: {path}"
        return original_lstat(path, *args, **kwargs)
    def guarded_read(path, *args, **kwargs):
        assert path == file, f"Unexpected content read: {path}"
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", guarded_stat)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    ds = scan_file(file)
    assert len(ds) == 1
    assert (ds[0].code, ds[0].severity) == ("OUTSIDE_SKILL", "warning")


@pytest.mark.parametrize("directory", [False, True])
def test_external_symlink_never_stat_target(skill, tmp_path, symlink, monkeypatch, directory):
    file = skill("[external](references/escape)")
    external = tmp_path / "outside"
    if directory:
        external.mkdir()
    else:
        external.write_text("private", encoding="utf-8")
    (file.parent / "references").mkdir()
    symlink(file.parent / "references/escape", external, directory=directory)
    original = Path.lstat
    def guard(path, *args, **kwargs):
        assert path.is_relative_to(file.parent), f"External metadata access: {path}"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", guard)
    ds = scan_file(file)
    assert len(ds) == 1 and ds[0].code == "OUTSIDE_SKILL"


def test_broken_external_symlink_is_warning(skill, tmp_path, symlink):
    file = skill("[link](escape.md)")
    symlink(file.parent / "escape.md", tmp_path / "nonexistent")
    assert scan_file(file)[0].code == "OUTSIDE_SKILL"


def test_internal_symlink_and_loop(skill, symlink):
    file = skill("[ok](alias.md)", ["references/a.md"])
    symlink(file.parent / "alias.md", file.parent / "references/a.md")
    assert scan_file(file) == []
    symlink(file.parent / "loop.md", file.parent / "loop.md")
    file.write_text("[loop](loop.md)", encoding="utf-8")
    with pytest.raises(ScanError, match="loop"):
        scan_file(file)


def test_command_escape_and_local_name_not_satisfied_by_sibling(skill, tmp_path):
    file = skill("`python ../outside.py`\n\n`python scripts/a.py`")
    (tmp_path / "outside.py").write_text("", encoding="utf-8")
    other = tmp_path / "scripts"
    other.mkdir()
    (other / "a.py").write_text("", encoding="utf-8")
    assert [d.code for d in scan_file(file)] == ["OUTSIDE_SKILL", "COMMAND_TARGET_MISSING"]


def test_decode_does_not_allow_control_characters():
    assert clean_path("references/a%00b.md", link=True) is None
    assert clean_path("references/a%0A.md", link=True) is None


def test_relative_to_skill_not_cwd(skill, monkeypatch, tmp_path):
    file = skill("`python scripts/a.py`", ["scripts/a.py"])
    cwd = tmp_path / "other-cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    assert scan_file(file) == []
