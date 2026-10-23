import pytest

from skilllink_guard.scanner import scan_file


def test_link_real_line_after_frontmatter(skill):
    file = skill('---\nname: sample\ndescription: sample\n---\n\n# Intro\n\nFirst line\n[bad](references/missing.md)\n')
    diagnostics = scan_file(file)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert (d.code, d.line, d.reference, d.severity) == ("LINK_MISSING", 9, "references/missing.md", "error")


@pytest.mark.parametrize("text,line", [
    ("[guide][ref]\n\n[ref]: references/guide.md\n", 1),
    ("\n\n![image](assets/missing.png)", 3),
    ("[ref][]\n\n[ref]: references/guide.md", 1),
    ("\n[ref]\n\n[ref]: references/guide.md", 2),
    ("![ref][img]\n\n[img]: assets/missing.png", 1),
    ("- first\n  [bad](missing.md)", 2),
    ("> intro\n> [bad](missing.md)", 2),
    ("## [bad](missing.md)", 1),
    ("first\n[bad](missing.md)", 2),
])
def test_link_forms_and_line_numbers(skill, text, line):
    diagnostics = scan_file(skill(text))
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "LINK_MISSING"
    assert diagnostics[0].line == line


@pytest.mark.parametrize("url", ["https://example.com/scripts/x.py", "http://example.com/a", "mailto:a@example.com", "#intro", "//example.com/a", "data:text/plain,example"])
def test_nonlocal_links_ignored(skill, url):
    assert scan_file(skill(f"[link]({url})")) == []


@pytest.mark.parametrize("target", ["references/guide.md#section", "references/guide.md?view=1", "references/guide.md?view=1#section"])
def test_query_fragment(skill, target):
    assert scan_file(skill(f"[ok]({target})", ["references/guide.md"])) == []


@pytest.mark.parametrize("target", ["references/a%20b.md", "<references/a b.md>", "references/a b.md"])
def test_spaces_in_links(skill, target):
    assert scan_file(skill(f"[ok]({target})", ["references/a b.md"])) == []
    diagnostics = scan_file(skill(f"[bad]({target})", name="missing"))
    assert len(diagnostics) == 1
    assert diagnostics[0].reference == "references/a b.md"


def test_link_with_title(skill):
    assert scan_file(skill('[ok](references/guide.md "My title")', ["references/guide.md"])) == []


def test_directory_allowed(skill):
    file = skill("[self](.) [self again](./) [scripts](scripts/)", ["scripts/a.py"])
    assert scan_file(file) == []


def test_two_targets_and_same_rule_dedup(skill):
    ds = scan_file(skill("[a](missing.md) [a2](./missing.md) [b](another.md)"))
    assert [(d.line, d.reference) for d in ds] == [(1, "another.md"), (1, "missing.md")]


def test_same_inline_syntax_priority(skill):
    ds = scan_file(skill("[`scripts/missing.py`](scripts/missing.py)\n\n[`python scripts/run.py`](scripts/run.py)"))
    assert [(d.line, d.code) for d in ds] == [(1, "INLINE_PATH_MISSING"), (3, "COMMAND_TARGET_MISSING")]


def test_different_inline_syntax_keeps_rules(skill):
    ds = scan_file(skill("`scripts/missing.py` [link](scripts/missing.py)"))
    assert {d.code for d in ds} == {"INLINE_PATH_MISSING", "LINK_MISSING"}


def test_bom_crlf(skill):
    file = skill()
    file.write_bytes(b"\xef\xbb\xbf# Title\r\n\r\n[bad](missing.md)\r\n")
    assert scan_file(file)[0].line == 3
