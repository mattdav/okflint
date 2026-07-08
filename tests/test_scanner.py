"""Tests for Markdown file scanning primitives."""

from __future__ import annotations

from pathlib import Path

from okflint.scanner import (
    MarkdownLink,
    WikiLink,
    blank_code_spans,
    build_file_index,
    extract_headers,
    extract_markdown_links,
    extract_wikilinks,
    parse_frontmatter,
)


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter_returns_dict_and_body(self) -> None:
        content = "---\ntype: Reference\n---\n# Body\n"
        fm, body = parse_frontmatter(content)
        assert fm == {"type": "Reference"}
        assert "# Body" in body

    def test_no_frontmatter_returns_none(self) -> None:
        content = "# No frontmatter\n"
        fm, body = parse_frontmatter(content)
        assert fm is None
        assert body == content

    def test_invalid_yaml_returns_none(self) -> None:
        # colons inside a plain scalar can confuse PyYAML
        content = "---\nkey: [unclosed\n---\n# Body\n"
        fm, _ = parse_frontmatter(content)
        assert fm is None

    def test_non_dict_yaml_returns_none(self) -> None:
        content = "---\n- item1\n- item2\n---\n# Body\n"
        fm, _ = parse_frontmatter(content)
        assert fm is None

    def test_date_coerced_to_iso_string(self) -> None:
        content = "---\ntype: JournalEntry\ncreated: 2026-05-01\n---\n"
        fm, _ = parse_frontmatter(content)
        assert fm is not None
        assert fm["created"] == "2026-05-01"


# ---------------------------------------------------------------------------
# blank_code_spans
# ---------------------------------------------------------------------------


class TestBlankCodeSpans:
    def test_inline_code_masked(self) -> None:
        content = "See `[[wikilink]]` here"
        result = blank_code_spans(content)
        assert "[[wikilink]]" not in result

    def test_fenced_code_block_masked(self) -> None:
        content = "```\n[[NotALink]]\n```\n# Real"
        result = blank_code_spans(content)
        assert "[[NotALink]]" not in result
        assert "# Real" in result

    def test_unclosed_fence_masked_to_eof(self) -> None:
        content = "Before\n```\n[[Link]]\nmore content"
        result = blank_code_spans(content)
        assert "[[Link]]" not in result

    def test_tilde_fence_masked(self) -> None:
        content = "~~~\n[[TildeLink]]\n~~~\nOutside"
        result = blank_code_spans(content)
        assert "[[TildeLink]]" not in result
        assert "Outside" in result

    def test_regular_content_preserved(self) -> None:
        content = "Normal [[wikilink]] here"
        result = blank_code_spans(content)
        assert "[[wikilink]]" in result


# ---------------------------------------------------------------------------
# extract_wikilinks
# ---------------------------------------------------------------------------


class TestExtractWikilinks:
    def test_simple_wikilink_resolved(self) -> None:
        index = {"Note": ["Note.md"]}
        links = extract_wikilinks("See [[Note]] here", index)
        assert len(links) == 1
        assert links[0].target == "Note"
        assert not links[0].broken
        assert not links[0].ambiguous

    def test_broken_wikilink(self) -> None:
        links = extract_wikilinks("[[Missing]]", {})
        assert links[0].broken

    def test_ambiguous_wikilink(self) -> None:
        index = {"Note": ["a/Note.md", "b/Note.md"]}
        links = extract_wikilinks("[[Note]]", index)
        assert links[0].ambiguous

    def test_wikilink_with_alias(self) -> None:
        index = {"Target": ["Target.md"]}
        links = extract_wikilinks("[[Target|Alias]]", index)
        assert links[0].alias == "Alias"
        assert links[0].target == "Target"

    def test_wikilink_with_section(self) -> None:
        index = {"Doc": ["Doc.md"]}
        links = extract_wikilinks("[[Doc#Section]]", index)
        assert links[0].section == "Section"


# ---------------------------------------------------------------------------
# extract_markdown_links
# ---------------------------------------------------------------------------


class TestExtractMarkdownLinks:
    def test_external_link_not_broken(self, tmp_path: Path) -> None:
        file = tmp_path / "doc.md"
        file.touch()
        links = extract_markdown_links(
            "[Google](https://google.com)", file, tmp_path
        )
        assert len(links) == 1
        assert links[0].is_external
        assert not links[0].broken

    def test_relative_link_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "other.md"
        target.touch()
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links("[Other](other.md)", src, tmp_path)
        assert not links[0].broken

    def test_relative_link_broken(self, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links("[Missing](missing.md)", src, tmp_path)
        assert links[0].broken

    def test_anchor_link_ignored(self, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links("[Section](#my-section)", src, tmp_path)
        assert len(links) == 0

    def test_relative_link_with_anchor_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "other.md"
        target.touch()
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links("[Other](other.md#anchor)", src, tmp_path)
        assert not links[0].broken

    def test_relative_link_with_anchor_broken(self, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links("[Other](other.md#anchor)", src, tmp_path)
        assert links[0].broken

    def test_absolute_link_with_anchor_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "abs" / "path.md"
        target.parent.mkdir()
        target.touch()
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links("[Abs](/abs/path.md#frag)", src, tmp_path)
        assert not links[0].broken

    def test_link_without_fragment_still_resolved(self, tmp_path: Path) -> None:
        target = tmp_path / "existing.md"
        target.touch()
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links("[Existing](existing.md)", src, tmp_path)
        assert not links[0].broken

    def test_ticket_case_anchor_with_special_chars(self, tmp_path: Path) -> None:
        target = tmp_path / "fichier.md"
        target.touch()
        src = tmp_path / "src.md"
        src.touch()
        links = extract_markdown_links(
            "[A](fichier.md#dax001-use-simple-...-arguments) "
            "[B](fichier.md#qry002-...-__valuefilterdm)",
            src,
            tmp_path,
        )
        assert not links[0].broken
        assert not links[1].broken


# ---------------------------------------------------------------------------
# build_file_index
# ---------------------------------------------------------------------------


class TestBuildFileIndex:
    def test_indexes_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "Note.md").write_text("# Note", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "Other.md").write_text("# Other", encoding="utf-8")
        index = build_file_index([tmp_path])
        assert "Note" in index
        assert "Other" in index

    def test_duplicate_names_lists_multiple(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "Note.md").write_text("# Note", encoding="utf-8")
        (tmp_path / "b" / "Note.md").write_text("# Note", encoding="utf-8")
        index = build_file_index([tmp_path])
        assert len(index["Note"]) == 2


class TestBuildFileIndexExclude:
    def _make_tree(self, root: Path) -> None:
        (root / ".venv" / "lib").mkdir(parents=True)
        (root / ".venv" / "lib" / "x.md").write_text("x", encoding="utf-8")
        (root / "src" / "pkg" / "data").mkdir(parents=True)
        (root / "src" / "pkg" / "data" / "report.md").write_text("r", encoding="utf-8")
        (root / "src" / "pkg" / "data" / "plans").mkdir()
        (root / "src" / "pkg" / "data" / "plans" / "plan.md").write_text(
            "p", encoding="utf-8"
        )
        (root / "src" / "venv_utils.md").write_text("v", encoding="utf-8")
        (root / "notes.md").write_text("n", encoding="utf-8")

    def test_venv_pattern_excludes_nested_file(self, tmp_path: Path) -> None:
        self._make_tree(tmp_path)
        index = build_file_index([tmp_path], {tmp_path: [".venv/**"]})
        assert "x" not in index

    def test_venv_pattern_keeps_non_venv_file(self, tmp_path: Path) -> None:
        self._make_tree(tmp_path)
        index = build_file_index([tmp_path], {tmp_path: [".venv/**"]})
        assert "venv_utils" in index
        assert "notes" in index

    def test_data_glob_excludes_nested_files(self, tmp_path: Path) -> None:
        self._make_tree(tmp_path)
        index = build_file_index([tmp_path], {tmp_path: ["src/**/data/**"]})
        assert "report" not in index
        assert "plan" not in index

    def test_data_glob_keeps_root_note(self, tmp_path: Path) -> None:
        self._make_tree(tmp_path)
        index = build_file_index([tmp_path], {tmp_path: ["src/**/data/**"]})
        assert "notes" in index

    def test_cookiecutter_pattern_excludes_template(self, tmp_path: Path) -> None:
        tpl = tmp_path / "{{cookiecutter.project_name}}"
        tpl.mkdir()
        (tpl / "README.md").write_text("r", encoding="utf-8")
        (tmp_path / "outside.md").write_text("o", encoding="utf-8")
        index = build_file_index([tmp_path], {tmp_path: ["{{cookiecutter.*}}/**"]})
        assert "README" not in index
        assert "outside" in index

    def test_no_exclude_patterns_unchanged(self, tmp_path: Path) -> None:
        self._make_tree(tmp_path)
        index_plain = build_file_index([tmp_path])
        index_empty = build_file_index([tmp_path], {tmp_path: []})
        assert set(index_plain.keys()) == set(index_empty.keys())

    def test_root_without_patterns_unaffected(self, tmp_path: Path) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        (root_a / ".venv").mkdir()
        (root_a / ".venv" / "x.md").write_text("x", encoding="utf-8")
        (root_b / "note.md").write_text("n", encoding="utf-8")
        # Only root_a has exclusion; root_b should be fully indexed
        index = build_file_index([root_a, root_b], {root_a: [".venv/**"]})
        assert "x" not in index
        assert "note" in index


# ---------------------------------------------------------------------------
# extract_headers
# ---------------------------------------------------------------------------


class TestExtractHeaders:
    def test_extracts_h1_and_h2(self) -> None:
        content = "# Title\n## Section\n### Ignored\n"
        blanked = blank_code_spans(content)
        headers = extract_headers(blanked)
        assert len(headers) == 2
        assert headers[0].level == 1
        assert headers[1].level == 2

    def test_header_in_code_not_extracted(self) -> None:
        content = "```\n# NotAHeader\n```\n# RealHeader"
        blanked = blank_code_spans(content)
        headers = extract_headers(blanked)
        assert len(headers) == 1
        assert headers[0].text == "RealHeader"
