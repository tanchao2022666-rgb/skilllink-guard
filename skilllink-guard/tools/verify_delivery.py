"""Verify a project-local delivery in a fresh environment; retain smoke evidence."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    archive_path = Path(os.path.abspath(ROOT / args.archive))
    dest = Path(os.path.abspath(ROOT / ".tmp" / args.label))
    output = Path(os.path.abspath(ROOT / args.output_dir))
    if not all(path.is_relative_to(ROOT) for path in (archive_path, dest, output)):
        parser.error("All paths must stay within this project")
    dest.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
                raise ValueError(f"Unsafe archive member: {name!r}")
        assert archive.testzip() is None
        archive.extractall(dest)
    source = dest / "skilllink-guard-0.1.0"
    for line in (source / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        member = source / name
        if not member.is_relative_to(source) or ".." in Path(name).parts:
            raise ValueError("Unsafe checksum member")
        assert hashlib.sha256(member.read_bytes()).hexdigest() == expected, name
    env = dict(os.environ, PYTHONUTF8="1", TEMP=str(ROOT / ".tmp"), TMP=str(ROOT / ".tmp"), PIP_CACHE_DIR=str(ROOT / ".cache/pip"))
    fresh = source / ".venv"
    python = fresh / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    cli = python.parent / ("skilllink.exe" if os.name == "nt" else "skilllink")
    empty = source / ".tmp/empty"
    empty.mkdir(parents=True)
    records = []
    def run(name, command, expected=0):
        completed = subprocess.run([str(p) for p in command], cwd=source, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (output / f"delivery-{name}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (output / f"delivery-{name}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        passed = completed.returncode == expected
        records.append({"name": name, "command": [str(p) for p in command], "cwd": str(source), "exit_code": completed.returncode, "expected": expected, "passed": passed})
        print(f"{name}: exit {completed.returncode}, expected {expected}, {'PASS' if passed else 'FAIL'}", flush=True)
        if not passed:
            raise RuntimeError(f"Delivery smoke failed at {name}")
    try:
        run("venv", [sys.executable, "-m", "venv", fresh])
        wheel = source / "dist/skilllink_guard-0.1.0-py3-none-any.whl"
        run("install", [python, "-m", "pip", "install", f"{wheel}[dev]"])
        origin = "import skilllink_guard, sys; from pathlib import Path; p=Path(skilllink_guard.__file__); assert p.is_relative_to(Path(sys.prefix)); print(p)"
        run("origin", [python, "-I", "-c", origin])
        run("help", [cli, "--help"])
        run("version", [cli, "--version"])
        run("good", [cli, "check", "examples/good-skill"])
        run("broken-json", [cli, "check", "examples/broken-skill", "--format", "json"], 1)
        obj = json.loads((output / "delivery-broken-json.stdout.txt").read_text(encoding="utf-8"))
        assert obj["summary"] == {"errors": 2, "warnings": 0}
        run("empty", [cli, "check", empty], 2)
        run("pytest", [python, "-m", "pytest", "-q"])
        run("pip-check", [python, "-m", "pip", "check"])
    finally:
        (output / "delivery-smoke.json").write_text(json.dumps({"archive": str(archive_path), "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "checks": records, "all_passed": len(records) == 10 and all(item["passed"] for item in records)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
