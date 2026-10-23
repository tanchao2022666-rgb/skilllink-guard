from pathlib import Path

import pytest


@pytest.fixture
def skill(tmp_path):
    def create(text="", files=(), *, name="sample"):
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        file = root / "SKILL.md"
        file.write_text(text, encoding="utf-8")
        for resource in files:
            target = root / resource
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture", encoding="utf-8")
        return file
    return create


@pytest.fixture
def symlink():
    """Require a real link: do not skip a mandated safety test on Windows."""
    def create(link: Path, target: Path, *, directory=False):
        link.symlink_to(target, target_is_directory=directory)
    return create
