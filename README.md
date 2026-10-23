# SkillLink Guard

Static checks for missing local resources and common script targets in Agent
Skills `SKILL.md` files. Python 3.11+, Windows / Linux / macOS design, no accounts
or API keys, and offline scanning after installation.

The distinctive check is `python scripts/missing.py` in shell fences or inline
code: it reports the actual document line before an agent tries to run it.
It also checks local Markdown links, images, reference links and explicit inline
paths. Each Skill resolves resources against its own directory, regardless of
the current terminal directory.

The 2026-10-23 pre-release review added regressions for symlink resolution,
non-following discovery, quoted literal paths, uncertain command concatenation,
and GitHub-safe CLI errors. See `verification/PRE_RELEASE_REVIEW.md` for current
local evidence; earlier acceptance records are historical snapshots.

This complements broader format tools such as
[skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) and
[skill-validator](https://github.com/agent-ecosystem/skill-validator). It is **not
a complete Agent Skills specification validator, vulnerability scanner, or
reliability audit**. See the [Agent Skills specification](https://agentskills.io/specification)
for the directory format and normative requirements.

## Quick start (from this source checkout)

Windows PowerShell (Python 3.11 or newer; no Bash required):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\skilllink.exe check .\examples\good-skill
.\.venv\Scripts\skilllink.exe check .\examples\broken-skill
```

Use `py -3.12` instead if that is your installed version. Activation is optional.
To keep installation caches and temporary files in this checkout, create `.tmp`
and `.cache/pip`, and set process-level `TEMP`, `TMP` and `PIP_CACHE_DIR` to their
absolute paths before installation (see [CONTRIBUTING.md](CONTRIBUTING.md)).

Linux / macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
skilllink check examples/good-skill
skilllink check examples/broken-skill
```

Installation needs access to Python dependencies unless they are already cached.
Scanning itself makes no network requests.

## CLI

```text
skilllink --help
skilllink --version
skilllink check <path> [--format {text,json,github}] [--strict]
python -m skilllink_guard check <path>
```

Input can be a single `SKILL.md`, a Skill directory, or a repository. Hidden
`.agents/skills` directories are included. Discovery excludes `.git`, `.venv`,
`venv`, `node_modules`, `dist`, `build` and `__pycache__`. It never follows linked
directories (including Windows junctions) or linked `SKILL.md` files. An explicitly
selected input traversing links is rejected rather than followed.

| Exit | Meaning |
| --- | --- |
| 0 | Scan completed without errors; warnings allowed unless `--strict` |
| 1 | Scan completed with errors, or warnings under `--strict` |
| 2 | Usage/input/read/encoding/output failure, or no `SKILL.md` found |

Help and version exit 0. An incomplete scan produces an explanation on stderr;
it never emits a partial success report. JSON stdout on a completed scan is
one JSON object, including on exit 1. Diagnostic file paths use `/` and are
relative to the working directory when possible, absolute otherwise. Ordering
is stable for the same input and working directory.

## Checks and supported syntax

| Rule | Severity | Source |
| --- | --- | --- |
| `LINK_MISSING` | error | `[guide](references/guide.md)`, images, reference-style links |
| `INLINE_PATH_MISSING` | error | Independent backtick paths starting with `scripts/`, `references/`, `assets/`, optionally `./` |
| `COMMAND_TARGET_MISSING` | error | First static script target of a supported command |
| `OUTSIDE_SKILL` | warning | Traversal or symbolic link escaping the Skill directory |

Recognized shell fence languages: `bash`, `sh`, `shell`, `console`, `terminal`.
Commands are also recognized inside inline code:

```text
python scripts/run.py
python3 -B scripts/run.py
py -u scripts/run.py
bash scripts/run.sh
sh scripts/run.sh
node scripts/run.js
node scripts/run.mjs
./scripts/run.sh
.\scripts\run.ps1
pwsh -File scripts/run.ps1
```

Python switches supported before the script are `-b -B -d -E -i -I -O -OO -P
-q -s -S -u -v -x`; unknown or value-taking options are skipped conservatively.
Quoted paths with spaces, Windows separators, and `$ ` console prompts are
supported. Script arguments are ignored. Only `.py`, `.sh`, `.js`, `.mjs`, `.ps1`
targets appropriate to each launcher are recognized. Command targets must be
files; ordinary links and inline paths may refer to directories.
An independent inline path containing spaces must be quoted inside its backticks;
unquoted prose or command arguments after a path are skipped. Quoted literal
punctuation is preserved. Concatenated shell word fragments such as
`"scripts/run.py"${SUFFIX}` are uncertain and skipped.

Local links discard query/fragment parts and decode URL escapes. Prefer
`[guide](<references/my guide.md>)` or `%20` for spaces; a simple single-line
unquoted destination with spaces is also accepted as a small extension.
Reference links report the line of their use, not their definition. Repeated
diagnostics for the same line, rule and normalized target are merged. Inside
one inline link, a script command takes priority over an inline path, which
takes priority over the link interpretation of the same target.
Internal symlinks are resolved component by component before normalizing the
reported target; `..` is never collapsed ahead of a link check. This also keeps
distinct resolved targets from being merged by lexical normalization alone.

Ignored: HTTP(S), other URI schemes, mailto and pure anchors; natural-language
paths; Python/other non-shell fences; `python -m`, `python -c`, `echo`; variables,
templates, wildcards, home expansion and placeholders. No recursive analysis of
`references/*.md`, YAML schema validation, external URL checking or automatic
repair is performed. No full Bash/PowerShell evaluation, pipelines, command
substitutions, control flow, continuation lines or arbitrary launcher syntax is
promised. Unusual nested Markdown/HTML and multiline code spans can be skipped.
Frontmatter is ignored while preserving document line numbers.
Drive-relative targets such as `C:file.py` are warned about without using the
process's per-drive working directory. Ambiguous Windows resource spellings
(trailing dots/spaces, embedded drives/streams, and reserved device names) are
skipped without metadata access. Root-relative/drive-relative symlink targets
are treated as outside. CLI error and usage messages escape control characters,
so an input-derived error cannot introduce a new workflow command line.

## Read-only boundary

The scanner only parses text and checks local filesystem metadata. It contains
no subprocess, shell, import or eval path for document commands. It never opens
referenced resource contents, writes to the scanned Skill, or checks an escaped
target for existence. Symlink targets are checked component by component, with
outside links warned about before any target metadata lookup. A link loop or
unreadable resource makes the scan incomplete (exit 2).

This is static checking, not an OS sandbox. Do not scan a tree concurrently
modified by an untrusted process: filesystem replacement races are outside the
v0.1 guarantee. A missing file is not proof that a Skill is malicious, and an
existing file is not proof that it is safe to run.

## Real example output

Captured locally from this checkout; commands and full results are retained in
`verification/` after acceptance testing. The deliberately broken example must
continue to fail.

```text
skilllink check examples/good-skill
SkillLink Guard 0.1.0
Scanned 1 skill(s)
Summary: 0 error(s), 0 warning(s)
```

```text
skilllink check examples/broken-skill
SkillLink Guard 0.1.0
Scanned 1 skill(s)
examples/broken-skill/SKILL.md:9: ERROR COMMAND_TARGET_MISSING scripts/build.py - Command references a missing local script.
  Suggestion: Add the script or correct the path relative to the Skill root.
examples/broken-skill/SKILL.md:12: ERROR LINK_MISSING references/setup.md - Referenced file does not exist.
  Suggestion: Add the resource or correct the path relative to the Skill root.
Summary: 2 error(s), 0 warning(s)
```

For machine output, use `skilllink check examples/broken-skill --format json`.
GitHub output emits escaped `::error` / `::warning` annotations with file and
line properties. `%`, CR/LF, and property colons/commas are escaped.

## GitHub Actions

This is a local v0.1.0 implementation. No public repository/tag or remote CI
result is claimed. After publishing, replace the **OWNER placeholder** below
with the actual owner; prefer a reviewed commit SHA for production workflows.
The action requires checkout and Python 3.11+; it uses the runner Python and
installs its own source via `github.action_path`. The scan path is passed via
an environment variable and quoted as a single argument, never interpolated
into shell code. On Windows GitHub-hosted runners the composite uses their
bundled Bash; the local CLI does not require Bash.

```yaml
name: Check Agent Skill resources
on: [push, pull_request]
permissions:
  contents: read
jobs:
  check-skills:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@v7
        with:
          python-version: '3.11'
      - uses: OWNER/skilllink-guard@v0.1.0
        with:
          path: .
```

The official [checkout](https://github.com/actions/checkout) and
[setup-python](https://github.com/actions/setup-python) repositories were
consulted for the action versions. Self-hosted runners must meet those actions'
runtime requirements. CI is configured for Ubuntu and Windows, Python 3.11 and
3.12; local test evidence is separate from unexecuted remote CI.

## Contributing, security and release status

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and
[CHANGELOG.md](CHANGELOG.md). After a repository is published, report bugs and
feature requests in its Issues tab, with a minimal synthetic Skill, tool/Python/OS
versions, command, actual and expected output. Submit focused PRs with tests.
Keep sensitive documents and credentials out of public reports.

GitHub repository availability under the intended owner and PyPI distribution
name availability are **pending maintainer confirmation before publishing**.
The local package name reserves nothing. No remote, upload, release, adoption,
download or popularity claim is made here. MIT licensed; copyright Contributors.

## 中文速览

本工具静态检查 `SKILL.md` 中的本地链接、明确行内路径和常见脚本命令目标，
按每个 Skill 自身目录解析并报告真实行号。不会运行文档命令，不需要账号，
扫描时不联网。`--format json` 适合自动化，`--format github` 用于 Actions 注解。
退出码为成功 `0`、发现错误 `1`、无法完成扫描 `2`；`--strict` 会把警告也作为失败。
本工具通过不代表通过 Agent Skills 全量规范、安全性或可靠性审核。
