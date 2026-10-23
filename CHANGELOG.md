# Changelog

## 0.1.0 — 2026-10-23 (local implementation; publication pending)

Pre-release review fixes:

- Discover resources with non-following entry metadata instead of os.walk's
  default link classification; preserve links before `..` in input paths.
- Resolve symlink target components before collapsing `..`; distinguish resolved
  target identities and reject ambiguous drive/root-relative link targets.
- Skip ambiguous Windows aliases/device paths before metadata lookup.
- Preserve quoted literal punctuation, skip shell word concatenation and
  non-independent inline path prose, and escape input-derived CLI error lines.
- Add delivery ZIP generation, checksums and clean-environment verification.

- Deterministic `SKILL.md` discovery with excluded build/dependency directories.
- Local Markdown links/images/references and explicit inline resource paths.
- Static common shell launcher targets with actual source line diagnostics.
- Skill-root traversal and symlink boundary warnings; no command execution.
- Text, JSON and escaped GitHub annotations, strict mode and fixed exit codes.
- CLI/module entry points, synthetic tests, examples, composite action and CI.

No remote release or cross-platform CI execution is implied by this entry.
