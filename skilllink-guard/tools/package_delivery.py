"""Build a local delivery ZIP from an explicit allowlist; never publish it."""

import argparse
import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "skilllink-guard-0.1.0"


def local(value: str) -> Path:
    path = Path(os.path.abspath(ROOT / value))
    if not path.is_relative_to(ROOT):
        raise ValueError("All package inputs and outputs must stay in the project")
    for part in (path, *path.parents):
        if part == ROOT.parent:
            break
        if part.is_symlink():
            raise ValueError(f"Linked package input refused: {part}")
    return path


def files(directory: Path):
    with os.scandir(directory) as entries:
        for entry in sorted(entries, key=lambda item: item.name):
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Linked package entry refused: {entry.name}")
            path = directory / entry.name
            if stat.S_ISDIR(info.st_mode):
                if entry.name != "__pycache__":
                    yield from files(path)
            elif stat.S_ISREG(info.st_mode):
                yield path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("label must contain only ASCII letters, digits, underscores or dashes")
    artifact_dir, evidence = local(args.artifact_dir), local(args.evidence_dir)
    output = local("delivery")
    output.mkdir(exist_ok=True)
    archive_path = output / f"{BASE}-{args.label}.zip"
    if archive_path.exists():
        raise FileExistsError(f"Preserve existing delivery; choose a new label: {archive_path}")
    payload = {}
    for name in ("pyproject.toml", "MANIFEST.in", ".gitignore", "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE", "action.yml"):
        payload[name] = local(name).read_bytes()
    for directory in ("src", "tests", "tools", "examples", ".github"):
        for path in files(local(directory)):
            if path.suffix in {".py", ".md", ".yml", ".yaml"}:
                payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ("skilllink_guard-0.1.0-py3-none-any.whl", "skilllink_guard-0.1.0.tar.gz"):
        payload[f"dist/{name}"] = (artifact_dir / name).read_bytes()
    for path in files(evidence):
        if path.suffix in {".txt", ".json", ".md"}:
            payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    payload["verification/PRE_RELEASE_REVIEW.md"] = local("verification/PRE_RELEASE_REVIEW.md").read_bytes()
    spec = local("SkillLink_Guard_Codex_开发任务书_v0.1.0.md")
    payload["docs/开发任务书_v0.1.0.md"] = spec.read_bytes()
    start = """# SkillLink Guard 0.1.0 本地交付包

此包包含修复后的源码、测试、示例、文档、Composite Action、CI、wheel/sdist 与本地验证记录。
未上传或发布；GitHub/PyPI 名称及远端 CI 待确认。未包含虚拟环境、缓存、Git 历史或凭据。

Windows PowerShell：解压后进入包含本文件的目录，使用已安装的 Python 3.11+：

```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -e '.[dev]'
.\\.venv\\Scripts\\python.exe -m pytest -q
.\\.venv\\Scripts\\skilllink.exe check .\\examples\\good-skill
.\\.venv\\Scripts\\skilllink.exe check .\\examples\\broken-skill --format json
```

好样本退出 0，故意损坏的样本退出 1。无 Skill 输入退出 2。
仅安装运行包时可在虚拟环境中 pip install dist/skilllink_guard-0.1.0-py3-none-any.whl。
本包未捆绑 Python 或第三方依赖；首次安装需要正常依赖下载或可用的本地缓存。
扫描本身离线、不执行输入命令。Linux/macOS 命令与语法限制见 README。

最新自查：verification/PRE_RELEASE_REVIEW.md；精确命令与退出码在同目录下该轮记录中。
SHA256SUMS.txt 校验包内所有交付文件，DELIVERY_MANIFEST.json 列明大小及哈希。
提交到 GitHub 前须另外审阅本地验证记录中的机器路径，再由维护者授权发布。
"""
    payload["START_HERE.md"] = start.encode("utf-8")
    manifest = {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in sorted(payload.items())}
    payload["DELIVERY_MANIFEST.json"] = (json.dumps({"version": "0.1.0", "published": False, "files": manifest}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    payload["SHA256SUMS.txt"] = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(payload.items())).encode("utf-8")
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(f"{BASE}/{name}", data)
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        for name, data in payload.items():
            assert archive.read(f"{BASE}/{name}") == data
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive_path.name}\n", encoding="utf-8")
    print(json.dumps({"path": str(archive_path), "files": len(payload), "bytes": archive_path.stat().st_size, "sha256": checksum}, indent=2))


if __name__ == "__main__":
    main()
