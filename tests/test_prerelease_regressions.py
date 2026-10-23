"""Adversarial synthetic cases found during the pre-release review."""

from pathlib import Path
from types import SimpleNamespace
import stat

import pytest

from skilllink_guard.cli import main
from skilllink_guard.discovery import discover
from skilllink_guard.paths import inspect_target
from skilllink_guard.scanner import scan_file


@pytest.mark.parametrize("text", [
    '`python "scripts/missing.py"${SUFFIX}`',
    '`python "scripts/missing.py"extra`',
    '`python scripts/missing.py"${SUFFIX}"`',
    '`scripts/missing.py --help`',
    '`scripts/missing.py is an example`',
])
def test_uncertain_concatenation_or_non_independent_path_skipped(skill, text):
    assert scan_file(skill(text)) == []


@pytest.mark.parametrize("name", ["a.py,", "a.py.", "a.py;", "a.py!"])
def test_quoted_inline_path_preserves_literal_punctuation(skill, name):
    # Legal on Linux and Windows (trailing-dot spelling is OS-dependent).
    file = skill(f'`"scripts/{name}"`', [f"scripts/{name}"])
    assert scan_file(file) == []


@pytest.mark.parametrize("directory", [False, True])
def test_discovery_never_follows_entry_metadata(skill, tmp_path, symlink, monkeypatch, directory):
    good = skill(name="repo/good")
    outside = skill(name="outside")
    symlink(good.parent.parent / "escape", outside.parent if directory else outside, directory=directory)
    import skilllink_guard.discovery as discovery
    real_scandir = discovery.os.scandir

    class GuardEntry:
        def __init__(self, entry):
            self.entry = entry
            self.name = entry.name
            self.path = entry.path
        def is_dir(self, *, follow_symlinks=True):
            assert not follow_symlinks, "discovery followed entry metadata"
            return self.entry.is_dir(follow_symlinks=False)
        def is_file(self, *, follow_symlinks=True):
            assert not follow_symlinks, "discovery followed entry metadata"
            return self.entry.is_file(follow_symlinks=False)
        def stat(self, *, follow_symlinks=True):
            assert not follow_symlinks, "discovery followed entry metadata"
            return self.entry.stat(follow_symlinks=False)
        def is_symlink(self):
            return self.entry.is_symlink()

    class GuardScan:
        def __init__(self, path):
            self.scan = real_scandir(path)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.scan.close()
        def __iter__(self):
            return self
        def __next__(self):
            return GuardEntry(next(self.scan))
        def close(self):
            self.scan.close()

    monkeypatch.setattr(discovery.os, "scandir", GuardScan)
    assert discover(good.parent.parent) == [good]


def test_symlink_target_dotdot_not_collapsed_before_link_checks(skill, tmp_path, symlink, monkeypatch):
    file = skill("[escape](alias.md)", ["safe.md"])
    external = tmp_path / "outside"
    external.mkdir()
    symlink(file.parent / "jump", external, directory=True)
    # Lexically this looks like root/safe.md, but resolution passes jump first.
    symlink(file.parent / "alias.md", Path("jump") / ".." / "safe.md")
    original = Path.lstat
    def guard(path, *args, **kwargs):
        assert path.is_relative_to(file.parent), f"External access: {path}"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", guard)
    ds = scan_file(file)
    assert len(ds) == 1 and ds[0].code == "OUTSIDE_SKILL"


def test_internal_symlink_depth_with_dotdot_not_false_warning(skill, symlink):
    file = skill("[ok](alias/../../ok.md)", ["deep/nested/child.txt", "ok.md"])
    symlink(file.parent / "alias", file.parent / "deep/nested", directory=True)
    assert scan_file(file) == []


def test_dotdot_does_not_hide_an_escaped_prefix(skill, tmp_path, symlink):
    file = skill("[external](jump/../safe.md)", ["safe.md"])
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink(file.parent / "jump", outside, directory=True)
    assert scan_file(file)[0].code == "OUTSIDE_SKILL"


def test_missing_prefix_with_lexical_escape_warns(skill):
    file = skill("[external](absent/../../outside.md)")
    assert scan_file(file)[0].code == "OUTSIDE_SKILL"


@pytest.mark.parametrize("raw", ["C:outside.md", "C:../outside.md"])
def test_drive_relative_path_does_not_use_process_drive_cwd(skill, raw):
    file = skill()
    assert inspect_target(file.parent, raw).outside


def test_cli_error_newline_cannot_inject_workflow_command(skill, monkeypatch, capsys):
    file = skill()
    def failed(*args, **kwargs):
        raise OSError("untrusted\n::error file=owned,line=1::injected\r\nend")
    monkeypatch.setattr("skilllink_guard.cli.scan", failed)
    assert main(["check", str(file), "--format", "github"]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert len(captured.err.splitlines()) == 1
    assert not any(line.startswith("::") for line in captured.err.splitlines())


def test_cli_usage_error_newline_cannot_inject_workflow_command(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["invalid\n::error::injected"])
    assert exc.value.code == 2
    assert not any(line.startswith("::error::") for line in capsys.readouterr().err.splitlines())


def test_linked_input_dotdot_not_normalized_away(skill, tmp_path, symlink):
    file = skill(name="repo/skill")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = file.parent.parent / "jump"
    symlink(link, outside, directory=True)
    from skilllink_guard.models import ScanError
    with pytest.raises(ScanError, match="symbolic links"):
        discover(link / ".." / "skill")


def test_symlink_resolution_keeps_two_distinct_missing_targets(skill, symlink):
    file = skill("[a](alias/../missing.md) [b](missing.md)", ["deep/nested/child"])
    symlink(file.parent / "alias", file.parent / "deep/nested", directory=True)
    ds = scan_file(file)
    assert len(ds) == 2
    assert {d.reference for d in ds} == {"deep/missing.md", "missing.md"}


@pytest.mark.parametrize("raw", ["C:other.md", "\\outside.md"])
def test_ambiguous_windows_symlink_target_never_accessed(skill, monkeypatch, raw):
    import os
    if os.name != "nt":
        # POSIX permits these as literal filenames; its platform-specific
        # normalization is tested separately without skipping this test.
        assert not Path(raw).is_absolute()
        return
    file = skill()
    link = file.parent / "link"
    original = Path.lstat
    def guard(path, *args, **kwargs):
        assert path.is_relative_to(file.parent)
        if path == link:
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", guard)
    monkeypatch.setattr("skilllink_guard.paths.os.readlink", lambda path: raw)
    assert inspect_target(file.parent, "link").outside


@pytest.mark.parametrize("value", [".. /outside.md", "scripts/D:/outside.md", "references/NUL", "references/CON.txt"])
def test_windows_ambiguous_aliases_skipped_without_metadata(skill, monkeypatch, value):
    import os
    file = skill(f"[ambiguous](<{value}>)")
    if os.name == "nt":
        def forbidden(*args, **kwargs):
            raise AssertionError("Ambiguous Windows target must not be inspected")
        monkeypatch.setattr("skilllink_guard.scanner.inspect_target", forbidden)
        assert scan_file(file) == []
    else:
        assert len(scan_file(file)) == 1
