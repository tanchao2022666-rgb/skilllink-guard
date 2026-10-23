from pathlib import Path

import pytest

from skilllink_guard.discovery import EXCLUDED, discover
from skilllink_guard.models import ScanError


def test_file_and_directory(skill):
    file = skill()
    assert discover(file) == [file]
    assert discover(file.parent) == [file]


def test_hidden_and_stable_order(skill, tmp_path):
    z = skill(name="z")
    a = skill(name=".agents/skills/a")
    assert discover(tmp_path) == [a, z]
    assert discover(tmp_path) == discover(tmp_path)


@pytest.mark.parametrize("excluded", sorted(EXCLUDED))
def test_exclusions(skill, tmp_path, excluded):
    good = skill(name="valid")
    skill(name=f"{excluded}/bad")
    assert discover(tmp_path) == [good]


@pytest.mark.parametrize("kind", ["missing", "empty", "other-file"])
def test_invalid_inputs(tmp_path, kind):
    path = tmp_path / kind
    if kind == "empty":
        path.mkdir()
    elif kind == "other-file":
        path.write_text("", encoding="utf-8")
    with pytest.raises(ScanError):
        discover(path)


def test_linked_directory_not_followed(skill, tmp_path, symlink):
    good = skill(name="repo/good")
    outside = skill(name="elsewhere/hidden")
    symlink(tmp_path / "repo" / "linked", outside.parent.parent, directory=True)
    assert discover(tmp_path / "repo") == [good]


def test_linked_skill_file_not_read(skill, tmp_path, symlink):
    file = skill(name="outside")
    repo = tmp_path / "repo"
    repo.mkdir()
    symlink(repo / "SKILL.md", file)
    with pytest.raises(ScanError, match="No SKILL"):
        discover(repo)
    with pytest.raises(ScanError, match="symbolic links"):
        discover(repo / "SKILL.md")


def test_linked_input_ancestor_rejected(skill, tmp_path, symlink):
    file = skill(name="real/skill")
    link = tmp_path / "alias"
    symlink(link, file.parent.parent, directory=True)
    with pytest.raises(ScanError, match="symbolic links"):
        discover(link / "skill")


def test_discovery_permission_error(skill, monkeypatch):
    file = skill()
    def denied(*args, **kwargs):
        raise PermissionError("fixture denied")
    monkeypatch.setattr("skilllink_guard.discovery.os.scandir", denied)
    with pytest.raises(ScanError, match="fixture denied"):
        discover(file.parent)
