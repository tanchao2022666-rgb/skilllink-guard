"""Reproducible local acceptance; creates only project-local verification data.

Run with the editable-install virtual environment's Python from project root.
No commands from scanned input are executed by this verification program.
"""

import importlib.metadata
import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", default="verification")
parser.add_argument("--dist-dir", default="dist")
args = parser.parse_args()
OUT = Path(os.path.abspath(ROOT / args.output_dir))
DIST = Path(os.path.abspath(ROOT / args.dist_dir))
if not OUT.is_relative_to(ROOT) or not DIST.is_relative_to(ROOT):
    parser.error("Output and distribution directories must stay within the project.")
OUT.mkdir(parents=True, exist_ok=True)
temporary = ROOT / ".tmp" / "acceptance"
temporary.mkdir(parents=True, exist_ok=True)
empty = temporary / "no-skills"
empty.mkdir(exist_ok=True)
warning = temporary / "warning-skill"
warning.mkdir(exist_ok=True)
(warning / "SKILL.md").write_text("[outside](../external.md)\n", encoding="utf-8")
env = dict(os.environ, PYTHONUTF8="1", TEMP=str(ROOT / ".tmp"), TMP=str(ROOT / ".tmp"), PIP_CACHE_DIR=str(ROOT / ".cache" / "pip"))
cli = Path(sys.executable).parent / ("skilllink.exe" if os.name == "nt" else "skilllink")
module = [sys.executable, "-m", "skilllink_guard"]
checks = [
    ("cli-help", [str(cli), "--help"], 0),
    ("cli-version", [str(cli), "--version"], 0),
    ("module-help", [*module, "--help"], 0),
    ("module-version", [*module, "--version"], 0),
    ("check-help", [str(cli), "check", "--help"], 0),
    ("good", [str(cli), "check", "examples/good-skill"], 0),
    ("good-file", [str(cli), "check", "examples/good-skill/SKILL.md"], 0),
    ("broken", [str(cli), "check", "examples/broken-skill"], 1),
    ("empty", [str(cli), "check", str(empty)], 2),
    ("missing-input", [str(cli), "check", str(temporary / "does-not-exist")], 2),
    ("json", [str(cli), "check", "examples/broken-skill", "--format", "json"], 1),
    ("github", [str(cli), "check", "examples/broken-skill", "--format", "github"], 1),
    ("warning", [str(cli), "check", str(warning)], 0),
    ("strict-warning", [str(cli), "check", str(warning), "--strict"], 1),
    ("pytest", [sys.executable, "-m", "pytest", "-q"], 0),
    ("build", [sys.executable, "-m", "build", "--outdir", str(DIST)], 0),
    ("pip-check", [sys.executable, "-m", "pip", "check"], 0),
]
records = []
for name, command, expected in checks:
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / f"{name}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (OUT / f"{name}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    passed = completed.returncode == expected
    if name == "json":
        obj = json.loads(completed.stdout)
        passed = passed and obj["summary"] == {"errors": 2, "warnings": 0} and obj["skills_scanned"] == 1
    if name == "github":
        lines = completed.stdout.splitlines()
        passed = passed and len(lines) == 2 and all(line.startswith("::error file=") for line in lines) and ",line=9::" in lines[0] and ",line=12::" in lines[1]
    records.append({"name": name, "command": command, "cwd": str(ROOT), "exit_code": completed.returncode, "expected_exit_code": expected, "passed": passed})
    print(f"{name}: exit {completed.returncode}, expected {expected}, {'PASS' if passed else 'FAIL'}", flush=True)
report = {
    "platform": platform.platform(), "python": sys.version,
    "dependencies": {name: importlib.metadata.version(name) for name in ("skilllink-guard", "markdown-it-py", "pytest", "build", "setuptools")},
    "checks": records, "all_passed": all(record["passed"] for record in records),
    "not_executed": ["Linux", "macOS", "Python 3.11", "remote GitHub CI", "remote GitHub composite action", "publishing"],
}
(OUT / "acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if report["all_passed"] else 1)
