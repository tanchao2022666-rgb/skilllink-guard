# Contributing

Use Python 3.11 or newer. From this repository root, Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force .tmp,.cache/pip | Out-Null
$env:TEMP = Join-Path $PWD '.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $PWD '.cache/pip'
$env:PYTHONUTF8 = '1'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build
```

Linux/macOS:

```sh
mkdir -p .tmp .cache/pip
export TMPDIR="$PWD/.tmp" PIP_CACHE_DIR="$PWD/.cache/pip"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m build
```

The test temporary root and pytest cache are configured inside the checkout.
Symlink tests require real symlink creation: Windows needs Developer Mode or
appropriate link privilege. Tests deliberately fail rather than silently skip
the required boundary checks. No real global Skill installation is needed.

Before submitting a PR: add a focused synthetic fixture for changed behavior,
run pytest and build, preserve the intentionally broken example's exit code 1,
and update user-facing syntax/limitations. Never execute input document commands
or read escaped targets to check existence. Keep Windows path handling and actual
line numbers covered. Use small modules and the existing minimal dependencies.

Use the future repository's Issues for bugs/feature requests and PRs for changes.
No remote repository has been set up by local development; publishing is a
separate maintainer action. Do not include private Skills or real secrets.

Release checklist (performed by the maintainer after local review):

1. Confirm the intended GitHub owner/repository and PyPI name are available.
2. Review the files to publish; local initialization/handoff/verification files
   may contain workspace paths and should be reviewed separately.
3. Create the public GitHub repository, commit the reviewed source, set its
   remote, and push only when authorized. Do not upload `.venv`, caches or temp.
4. Verify all four Windows/Ubuntu 3.11/3.12 CI jobs and the composite smoke step.
5. Tag the reviewed commit `v0.1.0`, push the tag, then replace the README OWNER
   example with the confirmed repository identity and preferably a commit SHA.
6. Enable private vulnerability reporting. PyPI publication is optional and
   needs its own authorization, account/name confirmation and artifact review.
