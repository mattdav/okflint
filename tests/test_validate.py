"""OKF validation tests — 18 rules (F001, F002, R001, R002,
F101-F106, S101, S102, L001-L003, S201, R201, F201)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from okflint.manifest import load_manifest
from okflint.scanner import Header, MarkdownLink, WikiLink, build_file_index
from okflint.validate import (
    Diagnostic,
    check_core_concept,
    check_core_reserved_index,
    check_core_reserved_log,
    check_hygiene_links,
    check_hygiene_reserved,
    check_hygiene_structure,
    check_hygiene_unknown_fields,
    check_profile,
    run_validate,
    validate_file,
)


def _codes(diags: list[Diagnostic]) -> list[str]:
    return [d.code for d in diags]


# ---------------------------------------------------------------------------
# F001 — frontmatter absent
# ---------------------------------------------------------------------------


class TestF001:
    def test_triggers_on_no_frontmatter(self) -> None:
        diags = check_core_concept("test.md", None)
        assert "F001" in _codes(diags)

    def test_passes_with_frontmatter(self) -> None:
        diags = check_core_concept("test.md", {"type": "Reference"})
        assert "F001" not in _codes(diags)

    def test_f001_blocks_f002(self) -> None:
        diags = check_core_concept("test.md", None)
        assert "F002" not in _codes(diags)


# ---------------------------------------------------------------------------
# F002 — type field absent
# ---------------------------------------------------------------------------


class TestF002:
    def test_triggers_on_missing_type(self) -> None:
        diags = check_core_concept("test.md", {"title": "No type"})
        assert "F002" in _codes(diags)

    def test_triggers_on_empty_type(self) -> None:
        diags = check_core_concept("test.md", {"type": ""})
        assert "F002" in _codes(diags)

    def test_passes_with_type_present(self) -> None:
        diags = check_core_concept("test.md", {"type": "Reference"})
        assert not diags


# ---------------------------------------------------------------------------
# R001 — frontmatter forbidden in index.md
# ---------------------------------------------------------------------------


class TestR001:
    def test_triggers_on_non_root_index_with_frontmatter(self) -> None:
        content = "---\ntype: Reference\n---\n# Index\n"
        diags = check_core_reserved_index(
            "sub/index.md", content, is_root_index=False
        )
        assert "R001" in _codes(diags)

    def test_triggers_on_root_index_with_extra_keys(self) -> None:
        content = "---\nokf_version: '0.1'\ntype: Reference\n---\n"
        diags = check_core_reserved_index("index.md", content, is_root_index=True)
        assert "R001" in _codes(diags)

    def test_passes_on_index_without_frontmatter(self) -> None:
        content = "# Index\nNo frontmatter here\n"
        diags = check_core_reserved_index(
            "index.md", content, is_root_index=False
        )
        assert not diags

    def test_passes_on_root_index_with_only_okf_version(self) -> None:
        content = "---\nokf_version: '0.1'\n---\n# Root Index\n"
        diags = check_core_reserved_index("index.md", content, is_root_index=True)
        assert not diags


# ---------------------------------------------------------------------------
# R002 — non-ISO date heading in log.md
# ---------------------------------------------------------------------------


class TestR002:
    def test_triggers_on_non_iso_date_heading(self) -> None:
        content = "## 22 May 2026\n\nSome content\n"
        diags = check_core_reserved_log("log.md", content)
        assert "R002" in _codes(diags)

    def test_passes_on_iso_date_heading(self) -> None:
        content = "## 2026-05-22\n\nSome content\n"
        diags = check_core_reserved_log("log.md", content)
        assert not diags

    def test_passes_on_log_without_h2(self) -> None:
        content = "# Journal\n\nSome content\n"
        diags = check_core_reserved_log("log.md", content)
        assert not diags


# ---------------------------------------------------------------------------
# F101 — type not in declared types
# ---------------------------------------------------------------------------


class TestF101:
    def test_triggers_on_unknown_type(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md", {"type": "Unknown"}, m.profile, m.base.status_field
        )
        assert "F101" in _codes(diags)

    def test_passes_on_known_type(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "JournalEntry", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F101" not in _codes(diags)


# ---------------------------------------------------------------------------
# F102 — missing required field
# ---------------------------------------------------------------------------


class TestF102:
    def test_triggers_on_missing_required_field(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        # Decision requires type, statut, created — omit created
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté"},
            m.profile,
            m.base.status_field,
        )
        assert "F102" in _codes(diags)

    def test_passes_with_all_required_fields(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F102" not in _codes(diags)


# ---------------------------------------------------------------------------
# F103 — status present but forbidden
# ---------------------------------------------------------------------------


class TestF103:
    def test_triggers_when_status_present_on_forbidden_type(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        # JournalEntry has status_values=False → statut forbidden
        diags = check_profile(
            "doc.md",
            {
                "type": "JournalEntry",
                "created": "2026-01-01",
                "statut": "Accepté",
            },
            m.profile,
            m.base.status_field,
        )
        assert "F103" in _codes(diags)

    def test_passes_when_status_absent_on_forbidden_type(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "JournalEntry", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F103" not in _codes(diags)


# ---------------------------------------------------------------------------
# F104 — required status missing
# ---------------------------------------------------------------------------


class TestF104:
    def test_triggers_when_status_required_but_absent(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F104" in _codes(diags)

    def test_passes_when_status_present(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F104" not in _codes(diags)


# ---------------------------------------------------------------------------
# F105 — status value outside vocabulary
# ---------------------------------------------------------------------------


class TestF105:
    def test_triggers_on_invalid_status_value(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {
                "type": "Decision",
                "statut": "InProgress",  # not in [Accepté, Proposé, Déprécié]
                "created": "2026-01-01",
            },
            m.profile,
            m.base.status_field,
        )
        assert "F105" in _codes(diags)

    def test_passes_on_valid_status_value(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F105" not in _codes(diags)


# ---------------------------------------------------------------------------
# F106 — non-normalised type spelling (alias)
# ---------------------------------------------------------------------------


class TestF106:
    def test_triggers_on_alias_type(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        # "adr" is an alias of "Decision"
        diags = check_profile(
            "doc.md",
            {"type": "adr", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F106" in _codes(diags)

    def test_passes_on_canonical_type(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "F106" not in _codes(diags)


# ---------------------------------------------------------------------------
# S101 — incorrectly named status field
# ---------------------------------------------------------------------------


class TestS101:
    def test_triggers_when_wrong_field_name_used(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        # status_field is "statut", doc uses "status"
        diags = check_profile(
            "doc.md",
            {
                "type": "Decision",
                "status": "Accepté",
                "created": "2026-01-01",
            },
            m.profile,
            m.base.status_field,
        )
        assert "S101" in _codes(diags)

    def test_passes_with_correct_field_name(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "S101" not in _codes(diags)


# ---------------------------------------------------------------------------
# S102 — incorrectly formatted date
# ---------------------------------------------------------------------------


class TestS102:
    def test_triggers_on_non_iso_date(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {
                "type": "Decision",
                "statut": "Accepté",
                "created": "01/01/2026",
            },
            m.profile,
            m.base.status_field,
        )
        assert "S102" in _codes(diags)

    def test_passes_on_iso_date(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
            m.base.status_field,
        )
        assert "S102" not in _codes(diags)


# ---------------------------------------------------------------------------
# L001 — broken wikilink
# ---------------------------------------------------------------------------


class TestL001:
    def test_triggers_on_broken_wikilink(self) -> None:
        wl = WikiLink("[[Missing]]", "Missing", None, None, None, True, False)
        diags = check_hygiene_links("doc.md", [wl], [], set(), "warn")
        assert "L001" in _codes(diags)

    def test_passes_when_target_in_external_refs(self) -> None:
        wl = WikiLink("[[Wikipedia]]", "Wikipedia", None, None, None, True, False)
        diags = check_hygiene_links("doc.md", [wl], [], {"wikipedia"}, "warn")
        assert "L001" not in _codes(diags)

    def test_off_level_returns_empty(self) -> None:
        wl = WikiLink("[[Missing]]", "Missing", None, None, None, True, False)
        diags = check_hygiene_links("doc.md", [wl], [], set(), "off")
        assert not diags

    def test_error_level_sets_severity(self) -> None:
        wl = WikiLink("[[Missing]]", "Missing", None, None, None, True, False)
        diags = check_hygiene_links("doc.md", [wl], [], set(), "error")
        assert diags[0].severity == "error"


# ---------------------------------------------------------------------------
# L002 — broken markdown link
# ---------------------------------------------------------------------------


class TestL002:
    def test_triggers_on_broken_md_link(self) -> None:
        ml = MarkdownLink("text", "missing.md", False, True)
        diags = check_hygiene_links("doc.md", [], [ml], set(), "warn")
        assert "L002" in _codes(diags)

    def test_passes_on_working_md_link(self) -> None:
        ml = MarkdownLink("text", "present.md", False, False)
        diags = check_hygiene_links("doc.md", [], [ml], set(), "warn")
        assert "L002" not in _codes(diags)

    def test_external_broken_not_flagged(self) -> None:
        ml = MarkdownLink("text", "https://gone.example.com", True, True)
        diags = check_hygiene_links("doc.md", [], [ml], set(), "warn")
        assert "L002" not in _codes(diags)


# ---------------------------------------------------------------------------
# L003 — ambiguous wikilink
# ---------------------------------------------------------------------------


class TestL003:
    def test_triggers_on_ambiguous_wikilink(self) -> None:
        wl = WikiLink("[[Note]]", "Note", None, None, "a/Note.md", False, True)
        diags = check_hygiene_links("doc.md", [wl], [], set(), "warn")
        assert "L003" in _codes(diags)

    def test_passes_on_unambiguous_wikilink(self) -> None:
        wl = WikiLink("[[Note]]", "Note", None, None, "Note.md", False, False)
        diags = check_hygiene_links("doc.md", [wl], [], set(), "warn")
        assert "L003" not in _codes(diags)


# ---------------------------------------------------------------------------
# S201 — split candidate
# ---------------------------------------------------------------------------


class TestS201:
    def test_triggers_on_multiple_h1(self) -> None:
        headers = [Header(1, "A", 1), Header(1, "B", 2)]
        diags = check_hygiene_structure("doc.md", headers, None, "warn")
        assert "S201" in _codes(diags)

    def test_passes_on_single_h1(self) -> None:
        headers = [Header(1, "A", 1)]
        diags = check_hygiene_structure("doc.md", headers, None, "warn")
        assert "S201" not in _codes(diags)

    def test_off_level_returns_empty(self) -> None:
        headers = [Header(1, "A", 1), Header(1, "B", 2)]
        diags = check_hygiene_structure("doc.md", headers, None, "off")
        assert not diags


# ---------------------------------------------------------------------------
# R201 — missing reserved file
# ---------------------------------------------------------------------------


class TestR201:
    def test_triggers_on_missing_reserved_files(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        diags = check_hygiene_reserved(
            [root], {"index": "index.md", "log": "log.md"}, "warn"
        )
        assert "R201" in _codes(diags)
        assert len(diags) == 2

    def test_passes_when_reserved_files_present(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (root / "index.md").write_text("# Index", encoding="utf-8")
        (root / "log.md").write_text("# Log", encoding="utf-8")
        diags = check_hygiene_reserved(
            [root], {"index": "index.md", "log": "log.md"}, "warn"
        )
        assert not diags

    def test_off_level_returns_empty(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        diags = check_hygiene_reserved(
            [root], {"index": "index.md", "log": "log.md"}, "off"
        )
        assert not diags


# ---------------------------------------------------------------------------
# F201 — unknown frontmatter field
# ---------------------------------------------------------------------------


class TestF201:
    def test_triggers_on_unknown_field(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        type_cfg = m.profile.types["Decision"]
        diags = check_hygiene_unknown_fields(
            "doc.md",
            {
                "type": "Decision",
                "statut": "Accepté",
                "created": "2026-01-01",
                "unknown_key": "val",
            },
            type_cfg,
            "warn",
        )
        assert "F201" in _codes(diags)

    def test_passes_on_known_fields_only(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        type_cfg = m.profile.types["Decision"]
        diags = check_hygiene_unknown_fields(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            type_cfg,
            "warn",
        )
        assert not diags

    def test_off_level_returns_empty(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        type_cfg = m.profile.types["Decision"]
        diags = check_hygiene_unknown_fields(
            "doc.md",
            {
                "type": "Decision",
                "statut": "Accepté",
                "created": "2026-01-01",
                "extra": "val",
            },
            type_cfg,
            "off",
        )
        assert not diags


# ---------------------------------------------------------------------------
# Integration: validate_file
# ---------------------------------------------------------------------------


class TestValidateFile:
    def test_conforming_file_returns_no_errors(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = profile_manifest
        m = load_manifest(manifest_path)
        base_index = build_file_index(m.base.roots)
        f = make_md(
            root / "concept.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n# Title\n",
        )
        diags = validate_file(f, m, base_index)
        assert not [d for d in diags if d.severity == "error"]

    def test_f001_on_no_frontmatter(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        m = load_manifest(manifest_path)
        base_index = build_file_index(m.base.roots)
        f = make_md(root / "bare.md", "# No frontmatter\n")
        diags = validate_file(f, m, base_index)
        assert "F001" in _codes(diags)


# ---------------------------------------------------------------------------
# Integration: run_validate
# ---------------------------------------------------------------------------


class TestRunValidate:
    def test_conforming_dir_returns_exit_0(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = profile_manifest
        make_md(
            root / "concept.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n",
        )
        diags, code = run_validate(manifest_path, [root])
        assert code == 0
        assert not [d for d in diags if d.severity == "error"]

    def test_nonconforming_dir_returns_exit_1(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = profile_manifest
        make_md(root / "bad.md", "# No frontmatter\n")
        _, code = run_validate(manifest_path, [root])
        assert code == 1

    def test_invalid_manifest_raises_manifest_error(
        self, tmp_path: Path
    ) -> None:
        from okflint.manifest import ManifestError

        bad_manifest = tmp_path / "bad.yaml"
        bad_manifest.write_text("okf_version: '0.1'\n", encoding="utf-8")
        with pytest.raises(ManifestError):
            run_validate(bad_manifest, [tmp_path])

    def test_warnings_only_returns_exit_0(
        self,
        hygiene_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = hygiene_manifest
        make_md(
            root / "doc.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n"
            "[[BrokenLink]]\n",
        )
        diags, code = run_validate(manifest_path, [root])
        assert code == 0
        assert any(d.code == "L001" for d in diags)
