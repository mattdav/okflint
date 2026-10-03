"""OKF validation tests — 15 rules (F001, F002, R001, R002,
F101, F102, F105, F106, S102, L001-L003, S202, R201, F201)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from okflint.manifest import SplitConfig, TypeConfig, load_manifest
from okflint.scanner import MarkdownLink, WikiLink, build_file_index
from okflint.validate import (
    Diagnostic,
    check_core_concept,
    check_core_reserved_index,
    check_core_reserved_log,
    check_hygiene_legacy_forms,
    check_hygiene_links,
    check_hygiene_okf_v02_shapes,
    check_hygiene_reserved,
    check_hygiene_stale_content,
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
# F003 — `generated` present without `generated.by`
# ---------------------------------------------------------------------------


class TestF003:
    def test_triggers_on_generated_without_by(self) -> None:
        diags = check_core_concept(
            "test.md",
            {"type": "Reference", "generated": {"at": "2026-01-01T00:00:00Z"}},
        )
        assert "F003" in _codes(diags)

    def test_triggers_on_generated_not_a_mapping(self) -> None:
        diags = check_core_concept(
            "test.md", {"type": "Reference", "generated": "reference_agent/1.0"}
        )
        assert "F003" in _codes(diags)

    def test_passes_with_generated_by_present(self) -> None:
        diags = check_core_concept(
            "test.md", {"type": "Reference", "generated": {"by": "human:mdaviaud"}}
        )
        assert "F003" not in _codes(diags)

    def test_absent_generated_produces_nothing(self) -> None:
        diags = check_core_concept("test.md", {"type": "Reference"})
        assert "F003" not in _codes(diags)

    def test_does_not_fire_on_okf_version_01(self) -> None:
        diags = check_core_concept(
            "test.md",
            {"type": "Reference", "generated": {"at": "2026-01-01T00:00:00Z"}},
            okf_version="0.1",
        )
        assert "F003" not in _codes(diags)


# ---------------------------------------------------------------------------
# F004 — `sources` entry without `resource`
# ---------------------------------------------------------------------------


class TestF004:
    def test_triggers_on_entry_without_resource(self) -> None:
        diags = check_core_concept(
            "test.md", {"type": "Reference", "sources": [{"id": "s1"}]}
        )
        assert "F004" in _codes(diags)

    def test_triggers_on_non_list_shape(self) -> None:
        diags = check_core_concept(
            "test.md", {"type": "Reference", "sources": "not-a-list"}
        )
        assert "F004" in _codes(diags)

    def test_triggers_on_entry_not_a_mapping(self) -> None:
        diags = check_core_concept(
            "test.md", {"type": "Reference", "sources": ["not-a-mapping"]}
        )
        assert "F004" in _codes(diags)

    def test_passes_with_resource_present(self) -> None:
        diags = check_core_concept(
            "test.md",
            {"type": "Reference", "sources": [{"id": "s1", "resource": "/a.md"}]},
        )
        assert "F004" not in _codes(diags)

    def test_absent_sources_produces_nothing(self) -> None:
        diags = check_core_concept("test.md", {"type": "Reference"})
        assert "F004" not in _codes(diags)

    def test_does_not_fire_on_okf_version_01(self) -> None:
        diags = check_core_concept(
            "test.md",
            {"type": "Reference", "sources": [{"id": "s1"}]},
            okf_version="0.1",
        )
        assert "F004" not in _codes(diags)


# ---------------------------------------------------------------------------
# F005 — `Attested Computation` concept without `runtime`
# ---------------------------------------------------------------------------


class TestF005:
    def test_triggers_on_missing_runtime(self) -> None:
        diags = check_core_concept("test.md", {"type": "Attested Computation"})
        assert "F005" in _codes(diags)

    def test_passes_with_runtime_present(self) -> None:
        diags = check_core_concept(
            "test.md", {"type": "Attested Computation", "runtime": "dbt/1.8"}
        )
        assert "F005" not in _codes(diags)

    def test_absent_type_produces_nothing(self) -> None:
        diags = check_core_concept("test.md", {"type": "Reference"})
        assert "F005" not in _codes(diags)

    def test_does_not_fire_on_okf_version_01(self) -> None:
        diags = check_core_concept(
            "test.md", {"type": "Attested Computation"}, okf_version="0.1"
        )
        assert "F005" not in _codes(diags)


# ---------------------------------------------------------------------------
# R001 — frontmatter forbidden in index.md
# ---------------------------------------------------------------------------


class TestR001:
    def test_triggers_on_non_root_index_with_frontmatter(self) -> None:
        content = "---\ntype: Reference\n---\n# Index\n"
        diags = check_core_reserved_index("sub/index.md", content, is_root_index=False)
        assert "R001" in _codes(diags)

    def test_triggers_on_root_index_with_extra_keys(self) -> None:
        content = "---\nokf_version: '0.1'\ntype: Reference\n---\n"
        diags = check_core_reserved_index("index.md", content, is_root_index=True)
        assert "R001" in _codes(diags)

    def test_passes_on_index_without_frontmatter(self) -> None:
        content = "# Index\nNo frontmatter here\n"
        diags = check_core_reserved_index("index.md", content, is_root_index=False)
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
        diags = check_profile("doc.md", {"type": "Unknown"}, m.profile)
        assert "F101" in _codes(diags)

    def test_passes_on_known_type(self, profile_manifest: tuple[Path, Path]) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "JournalEntry", "created": "2026-01-01"},
            m.profile,
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
        )
        assert "F102" not in _codes(diags)


# ---------------------------------------------------------------------------
# F105 — value outside controlled vocabulary
# ---------------------------------------------------------------------------


class TestF105:
    def test_triggers_on_invalid_value(
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
        )
        assert "F105" in _codes(diags)

    def test_passes_on_valid_value(self, profile_manifest: tuple[Path, Path]) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
        )
        assert "F105" not in _codes(diags)

    def test_applies_to_optional_property(self, tmp_path: Path) -> None:
        # The controlled-vocabulary mechanism is orthogonal to required/optional:
        # an *optional* property carrying a `<prop>_values` declaration is still
        # checked when present.
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "profile:\n  types:\n    Note:\n"
            "      required: [type]\n"
            "      optional: [priority]\n"
            "      priority_values: [low, medium, high]\n"
            "      aliases: []\n"
            "  date_fields: []\n",
            encoding="utf-8",
        )
        m = load_manifest(f)
        assert m.profile is not None
        diags = check_profile(
            "doc.md", {"type": "Note", "priority": "urgent"}, m.profile
        )
        assert "F105" in _codes(diags)

    def test_impact_values_checked_on_task_type(self, tmp_path: Path) -> None:
        # AA-005: `impact` is a controlled vocabulary on the `Task` type.
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "profile:\n  types:\n    Task:\n"
            "      required: [created]\n"
            "      optional: [impact]\n"
            "      impact_values: [lecture, reversible, prod, destructif]\n"
            "      aliases: []\n"
            "  date_fields: []\n",
            encoding="utf-8",
        )
        m = load_manifest(f)
        assert m.profile is not None
        bad = check_profile(
            "doc.md",
            {"type": "Task", "created": "2026-10-03", "impact": "inconnu"},
            m.profile,
        )
        good = check_profile(
            "doc.md",
            {"type": "Task", "created": "2026-10-03", "impact": "prod"},
            m.profile,
        )
        assert "F105" in _codes(bad)
        assert "F105" not in _codes(good)

    def test_absent_optional_property_does_not_trigger(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "profile:\n  types:\n    Note:\n"
            "      required: [type]\n"
            "      optional: [priority]\n"
            "      priority_values: [low, medium, high]\n"
            "      aliases: []\n"
            "  date_fields: []\n",
            encoding="utf-8",
        )
        m = load_manifest(f)
        assert m.profile is not None
        diags = check_profile("doc.md", {"type": "Note"}, m.profile)
        assert "F105" not in _codes(diags)

    def test_triggers_on_invalid_element_in_list_value(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "profile:\n  types:\n    Note:\n"
            "      required: [type]\n"
            "      optional: [tags]\n"
            "      tags_values: [python, rust]\n"
            "      aliases: []\n"
            "  date_fields: []\n",
            encoding="utf-8",
        )
        m = load_manifest(f)
        assert m.profile is not None
        diags = check_profile(
            "doc.md", {"type": "Note", "tags": ["python", "cobol"]}, m.profile
        )
        assert "F105" in _codes(diags)


# ---------------------------------------------------------------------------
# F106 — non-normalised type spelling (alias)
# ---------------------------------------------------------------------------


class TestF106:
    def test_triggers_on_alias_type(self, profile_manifest: tuple[Path, Path]) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        # "adr" is an alias of "Decision"
        diags = check_profile(
            "doc.md",
            {"type": "adr", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
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
        )
        assert "F106" not in _codes(diags)


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
        )
        assert "S102" in _codes(diags)

    def test_passes_on_iso_date(self, profile_manifest: tuple[Path, Path]) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        diags = check_profile(
            "doc.md",
            {"type": "Decision", "statut": "Accepté", "created": "2026-01-01"},
            m.profile,
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
# S202 — split candidate (semantic cohesion)
# ---------------------------------------------------------------------------


_MULTI_CLUSTER_CONTENT = (
    "# Alpha\n\n"
    "This paragraph discusses cooking pasta with tomato sauce and basil "
    "leaves. The chef prepares pasta by boiling water, adding salt, and "
    "cooking the noodles until perfectly tender for dinner tonight.\n\n"
    "# Beta\n\n"
    "This paragraph discusses telescopes observing distant galaxies and "
    "stars. Astronomers use powerful telescopes to measure light from "
    "ancient galaxies across the vast universe every single night.\n"
)

_SINGLE_CLUSTER_CONTENT = (
    "# Alpha\n\n"
    "This paragraph discusses cooking pasta with tomato sauce and basil "
    "leaves in a warm kitchen every evening with friends and family "
    "gathered around the table for a long dinner.\n"
)

_DEFAULT_SPLIT_CONFIG = SplitConfig(
    min_lines=0, exempt_types=frozenset(), exempt_paths=[]
)

# Alpha-Gamma and Beta-Gamma share just enough vocabulary to form a
# transitive chain: at a low tau all three merge into one component, at the
# 0.15 default only Beta+Gamma merge, leaving Alpha separate (2 components).
_CHAINED_CONTENT = (
    "# Alpha\n\n"
    "The project team reviewed the quarterly budget process and updated "
    "the financial spreadsheet with new revenue numbers for the annual "
    "report.\n\n"
    "# Beta\n\n"
    "The finance team reviewed the quarterly budget process and updated "
    "the accounting timeline with new hiring plans for the coming year.\n\n"
    "# Gamma\n\n"
    "The hiring team reviewed the quarterly timeline process and updated "
    "the accounting plans with new budget numbers for the coming year.\n"
)


class TestS202:
    def test_triggers_on_multiple_cohesion_clusters(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _MULTI_CLUSTER_CONTENT,
            None,
            _DEFAULT_SPLIT_CONFIG,
            "warn",
        )
        assert "S202" in _codes(diags)

    def test_passes_on_single_cluster(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _SINGLE_CLUSTER_CONTENT,
            None,
            _DEFAULT_SPLIT_CONFIG,
            "warn",
        )
        assert "S202" not in _codes(diags)

    def test_off_level_returns_empty(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _MULTI_CLUSTER_CONTENT,
            None,
            _DEFAULT_SPLIT_CONFIG,
            "off",
        )
        assert not diags

    def test_min_lines_gate_suppresses_short_files(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        split_config = SplitConfig(
            min_lines=100, exempt_types=frozenset(), exempt_paths=[]
        )
        diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _MULTI_CLUSTER_CONTENT,
            None,
            split_config,
            "warn",
        )
        assert not diags

    def test_exempt_type_suppresses_check(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        split_config = SplitConfig(
            min_lines=0, exempt_types=frozenset({"Procedure"}), exempt_paths=[]
        )
        diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _MULTI_CLUSTER_CONTENT,
            {"type": "Procedure"},
            split_config,
            "warn",
        )
        assert not diags

    def test_exempt_path_suppresses_check(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        split_config = SplitConfig(
            min_lines=0, exempt_types=frozenset(), exempt_paths=["archive/**"]
        )
        diags = check_hygiene_structure(
            "archive/doc.md",
            root / "archive" / "doc.md",
            root,
            _MULTI_CLUSTER_CONTENT,
            None,
            split_config,
            "warn",
        )
        assert not diags

    def test_error_level_sets_severity(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _MULTI_CLUSTER_CONTENT,
            None,
            _DEFAULT_SPLIT_CONFIG,
            "error",
        )
        assert diags[0].severity == "error"

    def test_manifest_tau_is_honoured_not_hardcoded(self, tmp_path: Path) -> None:
        """A custom low split_config.tau must suppress a clustering that
        fires at the 0.15 default, proving check_hygiene_structure passes
        split_config.tau through to analyze_cohesion rather than a
        module-level constant."""
        root = tmp_path / "root"
        root.mkdir()

        default_diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _CHAINED_CONTENT,
            None,
            _DEFAULT_SPLIT_CONFIG,
            "warn",
        )
        assert "S202" in _codes(default_diags)

        low_tau_config = SplitConfig(
            min_lines=0, exempt_types=frozenset(), exempt_paths=[], tau=0.05
        )
        low_tau_diags = check_hygiene_structure(
            "doc.md",
            root / "doc.md",
            root,
            _CHAINED_CONTENT,
            None,
            low_tau_config,
            "warn",
        )
        assert "S202" not in _codes(low_tau_diags)


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

    def test_off_level_returns_empty(self, profile_manifest: tuple[Path, Path]) -> None:
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
# S203 — status outside draft|stable|deprecated
# ---------------------------------------------------------------------------


class TestS203:
    def test_triggers_on_unknown_status(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Reference", "status": "wip"}, "", "warn"
        )
        assert "S203" in _codes(diags)

    def test_passes_on_known_status(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Reference", "status": "stable"}, "", "warn"
        )
        assert "S203" not in _codes(diags)

    def test_neutralised_by_profile_status_values(self) -> None:
        type_cfg = TypeConfig(
            required=[],
            optional=["status"],
            controlled_values={"status": ["open", "closed"]},
            aliases=[],
        )
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {"type": "Reference", "status": "wip"},
            "",
            "warn",
            type_cfg=type_cfg,
        )
        assert "S203" not in _codes(diags)


# ---------------------------------------------------------------------------
# S204 — stale_after not YYYY-MM-DD
# ---------------------------------------------------------------------------


class TestS204:
    def test_triggers_on_malformed_stale_after(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Reference", "stale_after": "01/01/2026"}, "", "warn"
        )
        assert "S204" in _codes(diags)

    def test_passes_on_wellformed_stale_after(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Reference", "stale_after": "2026-01-01"}, "", "warn"
        )
        assert "S204" not in _codes(diags)

    def test_skipped_when_already_covered_by_s102(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {"type": "Reference", "stale_after": "01/01/2026"},
            "",
            "warn",
            date_fields=["stale_after"],
        )
        assert "S204" not in _codes(diags)


# ---------------------------------------------------------------------------
# S205 — generated.at / verified[].at not ISO 8601 datetime
# ---------------------------------------------------------------------------


class TestS205:
    def test_triggers_on_generated_at_date_only(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Reference",
                "generated": {"by": "human:mat", "at": "2026-01-01"},
            },
            "",
            "warn",
        )
        assert "S205" in _codes(diags)

    def test_passes_on_generated_at_iso_datetime(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Reference",
                "generated": {"by": "human:mat", "at": "2026-01-01T00:00:00Z"},
            },
            "",
            "warn",
        )
        assert "S205" not in _codes(diags)

    def test_triggers_on_verified_at_date_only(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Reference",
                "verified": [{"by": "human:mat", "at": "2026-01-01"}],
            },
            "",
            "warn",
        )
        assert "S205" in _codes(diags)


# ---------------------------------------------------------------------------
# S206 — generated.by / verified[].by outside the actor convention
# ---------------------------------------------------------------------------


class TestS206:
    def test_triggers_on_malformed_generated_by(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Reference", "generated": {"by": "someone"}}, "", "warn"
        )
        assert "S206" in _codes(diags)

    def test_passes_on_producer_version_form(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Reference",
                "generated": {"by": "reference_agent/gemini-2.5-pro"},
            },
            "",
            "warn",
        )
        assert "S206" not in _codes(diags)

    def test_passes_on_human_form(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {"type": "Reference", "generated": {"by": "human:mat"}},
            "",
            "warn",
        )
        assert "S206" not in _codes(diags)

    def test_triggers_on_malformed_verified_by(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {"type": "Reference", "verified": [{"by": "someone"}]},
            "",
            "warn",
        )
        assert "S206" in _codes(diags)


# ---------------------------------------------------------------------------
# `verified` shorthand (bare mapping) — never flagged for its own shape
# ---------------------------------------------------------------------------


class TestVerifiedShorthand:
    def test_bare_mapping_not_flagged_for_its_shape(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Reference",
                "verified": {"by": "human:mat", "at": "2026-01-01T00:00:00Z"},
            },
            "",
            "warn",
        )
        assert not diags

    def test_bare_mapping_contents_still_checked(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {"type": "Reference", "verified": {"by": "someone"}},
            "",
            "warn",
        )
        assert "S206" in _codes(diags)


# ---------------------------------------------------------------------------
# S210 — generated / verified present but not a structure
# ---------------------------------------------------------------------------


class TestS210:
    def test_triggers_on_verified_json_string(self) -> None:
        # Real case: a nested property typed in Obsidian's Properties panel.
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Task",
                "verified": '{"by": "human:matthieu", "at": "2026-10-02"}',
            },
            "",
            "warn",
        )
        assert "S210" in _codes(diags)

    def test_triggers_on_generated_string(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Task", "generated": "claude"}, "", "warn"
        )
        assert "S210" in _codes(diags)

    def test_triggers_on_verified_list_of_strings(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Task", "verified": ["human:mat"]}, "", "warn"
        )
        assert "S210" in _codes(diags)

    def test_passes_on_mapping_and_list_of_mappings(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Task",
                "generated": {"by": "human:mat", "at": "2026-01-01T00:00:00Z"},
                "verified": [{"by": "human:mat", "at": "2026-01-01T00:00:00Z"}],
            },
            "",
            "warn",
        )
        assert "S210" not in _codes(diags)

    def test_absent_optional_families_do_not_trigger(self) -> None:
        diags = check_hygiene_okf_v02_shapes("doc.md", {"type": "Task"}, "", "warn")
        assert "S210" not in _codes(diags)

    def test_silent_when_level_off(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Task", "verified": "x"}, "", "off"
        )
        assert not diags


# ---------------------------------------------------------------------------
# S207 — Attested Computation contract shape
# ---------------------------------------------------------------------------


class TestS207:
    def test_triggers_on_malformed_parameters(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Attested Computation",
                "runtime": "python3.12",
                "parameters": [{"name": "x"}],
                "computation": "/computation.md",
            },
            "",
            "warn",
        )
        assert "S207" in _codes(diags)

    def test_passes_on_wellformed_parameters(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Attested Computation",
                "runtime": "python3.12",
                "parameters": [{"name": "x", "type": "int", "required": True}],
                "computation": "/computation.md",
            },
            "",
            "warn",
        )
        assert "S207" not in _codes(diags)

    def test_triggers_on_executor_missing_receipt(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Attested Computation",
                "runtime": "python3.12",
                "executor": {"resource": "/exec.md"},
                "computation": "/computation.md",
            },
            "",
            "warn",
        )
        assert "S207" in _codes(diags)

    def test_triggers_on_attester_missing_resource(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Attested Computation",
                "runtime": "python3.12",
                "attester": {},
                "computation": "/computation.md",
            },
            "",
            "warn",
        )
        assert "S207" in _codes(diags)

    def test_triggers_on_computation_field_and_block_both_present(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Attested Computation",
                "runtime": "python3.12",
                "computation": "/computation.md",
            },
            "# Computation\n",
            "warn",
        )
        assert "S207" in _codes(diags)

    def test_triggers_on_computation_field_and_block_both_absent(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {"type": "Attested Computation", "runtime": "python3.12"},
            "",
            "warn",
        )
        assert "S207" in _codes(diags)

    def test_passes_on_computation_block_only(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {"type": "Attested Computation", "runtime": "python3.12"},
            "# Computation\n",
            "warn",
        )
        assert "S207" not in _codes(diags)


# ---------------------------------------------------------------------------
# S203-S207 family — level gating and okf_version non-regression
# ---------------------------------------------------------------------------


class TestOkfV02ShapesFamily:
    def test_off_level_returns_empty(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Reference", "status": "wip"}, "", "off"
        )
        assert not diags

    def test_clean_concept_produces_nothing(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md", {"type": "Reference", "status": "stable"}, "", "warn"
        )
        assert not diags

    def test_no_regression_on_okf_v01(self) -> None:
        diags = check_hygiene_okf_v02_shapes(
            "doc.md",
            {
                "type": "Attested Computation",
                "status": "wip",
                "stale_after": "01/01/2026",
                "generated": {"by": "someone", "at": "2026-01-01"},
            },
            "",
            "warn",
            okf_version="0.1",
        )
        assert not diags


# ---------------------------------------------------------------------------
# S208 — legacy OKF v0.1 forms (timestamp, # Citations)
# ---------------------------------------------------------------------------


class TestS208:
    def test_triggers_on_timestamp_not_declared_in_profile(self) -> None:
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference", "timestamp": "2026-01-01"},
            "",
            "warn",
            declared_okf_version="0.2",
        )
        assert "S208" in _codes(diags)

    def test_neutralised_when_timestamp_declared_in_profile(self) -> None:
        type_cfg = TypeConfig(
            required=[],
            optional=["timestamp"],
            controlled_values={},
            aliases=[],
        )
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference", "timestamp": "2026-01-01"},
            "",
            "warn",
            declared_okf_version="0.2",
            type_cfg=type_cfg,
        )
        assert "S208" not in _codes(diags)

    def test_silent_on_declared_okf_v01(self) -> None:
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference", "timestamp": "2026-01-01"},
            "",
            "warn",
            declared_okf_version="0.1",
        )
        assert not diags

    def test_silent_with_no_manifest_declared_version(self) -> None:
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference", "timestamp": "2026-01-01"},
            "",
            "warn",
            declared_okf_version=None,
        )
        assert not diags

    def test_triggers_on_citations_heading(self) -> None:
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference"},
            "# Citations\n\nSome source.\n",
            "warn",
            declared_okf_version="0.2",
        )
        assert "S208" in _codes(diags)

    def test_passes_without_citations_heading(self) -> None:
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference"},
            "# Sources\n\nSome source.\n",
            "warn",
            declared_okf_version="0.2",
        )
        assert "S208" not in _codes(diags)

    def test_citations_never_neutralised_by_profile(self) -> None:
        type_cfg = TypeConfig(
            required=[], optional=[], controlled_values={}, aliases=[]
        )
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference"},
            "# Citations\n",
            "warn",
            declared_okf_version="0.2",
            type_cfg=type_cfg,
        )
        assert "S208" in _codes(diags)

    def test_off_level_returns_empty(self) -> None:
        diags = check_hygiene_legacy_forms(
            "doc.md",
            {"type": "Reference", "timestamp": "2026-01-01"},
            "# Citations\n",
            "off",
            declared_okf_version="0.2",
        )
        assert not diags


# ---------------------------------------------------------------------------
# S209 — stale content (stale_after reached or passed)
# ---------------------------------------------------------------------------


class TestS209:
    def test_triggers_when_evaluation_date_reaches_stale_after(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference", "stale_after": "2026-06-01"},
            "warn",
            evaluation_date=date(2026, 6, 1),
        )
        assert "S209" in _codes(diags)

    def test_triggers_when_evaluation_date_passes_stale_after(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference", "stale_after": "2026-06-01"},
            "warn",
            evaluation_date=date(2026, 7, 1),
        )
        assert "S209" in _codes(diags)

    def test_passes_when_evaluation_date_precedes_stale_after(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference", "stale_after": "2026-06-01"},
            "warn",
            evaluation_date=date(2026, 1, 1),
        )
        assert "S209" not in _codes(diags)

    def test_evaluation_date_appears_in_message(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference", "stale_after": "2026-06-01"},
            "warn",
            evaluation_date=date(2026, 6, 1),
        )
        assert "2026-06-01" in diags[0].message

    def test_silent_when_stale_after_absent(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference"},
            "warn",
            evaluation_date=date(2026, 6, 1),
        )
        assert not diags

    def test_silent_when_stale_after_malformed(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference", "stale_after": "01/06/2026"},
            "warn",
            evaluation_date=date(2026, 6, 1),
        )
        assert not diags

    def test_off_level_returns_empty(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference", "stale_after": "2026-06-01"},
            "off",
            evaluation_date=date(2026, 6, 1),
        )
        assert not diags

    def test_no_regression_on_resolved_okf_v01(self) -> None:
        diags = check_hygiene_stale_content(
            "doc.md",
            {"type": "Reference", "stale_after": "2026-06-01"},
            "warn",
            okf_version="0.1",
            evaluation_date=date(2026, 6, 1),
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
        base_index = build_file_index([r.path for r in m.base.roots])
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
        base_index = build_file_index([r.path for r in m.base.roots])
        f = make_md(root / "bare.md", "# No frontmatter\n")
        diags = validate_file(f, m, base_index)
        assert "F001" in _codes(diags)

    def test_s202_fires_end_to_end_via_manifest_split_block(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        """Regression guard for the analyze_cohesion wiring: exercises
        load_manifest -> validate_file -> check_hygiene_structure ->
        analyze_cohesion end-to-end, driven by a manifest that declares
        the hygiene.split block, not cohesion.py in isolation."""
        root = tmp_path / "root"
        root.mkdir()
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            "okf_version: '0.1'\n"
            "base:\n"
            "  name: test-base\n"
            "  roots:\n"
            f"    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n"
            "    index: index.md\n"
            "    log: log.md\n"
            "profile:\n"
            "  date_fields: [created]\n"
            "  types:\n"
            "    JournalEntry:\n"
            "      required: [type, created]\n"
            "      optional: []\n"
            "hygiene:\n"
            "  split_candidates: warn\n"
            "  split:\n"
            "    min_lines: 0\n"
            "    exempt_types: []\n"
            "    exempt_paths: []\n",
            encoding="utf-8",
        )
        m = load_manifest(manifest_path)
        base_index = build_file_index([r.path for r in m.base.roots])
        f = make_md(
            root / "doc.md",
            "---\ntype: JournalEntry\ncreated: 2026-01-01\n---\n"
            + _MULTI_CLUSTER_CONTENT,
        )
        diags = validate_file(f, m, base_index)
        assert "S202" in _codes(diags)

    def test_absolute_link_resolves_across_multi_root_base(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        """Regression guard for L002 on multi-root bases: an absolute link
        owned by root A must resolve against root B too, mirroring how
        wikilinks already resolve at base scale via base_index."""
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            "okf_version: '0.1'\n"
            "base:\n"
            "  name: test-base\n"
            "  roots:\n"
            f"    - path: '{root_a.as_posix()}'\n"
            f"    - path: '{root_b.as_posix()}'\n"
            "  reserved_files:\n"
            "    index: index.md\n"
            "    log: log.md\n"
            "hygiene:\n"
            "  broken_links: warn\n",
            encoding="utf-8",
        )
        m = load_manifest(manifest_path)
        base_index = build_file_index([r.path for r in m.base.roots])
        make_md(root_b / "shared.md", "---\ntype: Reference\n---\n")
        f = make_md(
            root_a / "doc.md",
            "---\ntype: Reference\n---\n[Shared](/shared.md)\n",
        )
        diags = validate_file(f, m, base_index)
        assert "L002" not in _codes(diags)

    def test_absolute_link_missing_from_all_roots_still_flagged(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        root_a.mkdir()
        root_b.mkdir()
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            "okf_version: '0.1'\n"
            "base:\n"
            "  name: test-base\n"
            "  roots:\n"
            f"    - path: '{root_a.as_posix()}'\n"
            f"    - path: '{root_b.as_posix()}'\n"
            "  reserved_files:\n"
            "    index: index.md\n"
            "    log: log.md\n"
            "hygiene:\n"
            "  broken_links: warn\n",
            encoding="utf-8",
        )
        m = load_manifest(manifest_path)
        base_index = build_file_index([r.path for r in m.base.roots])
        f = make_md(
            root_a / "doc.md",
            "---\ntype: Reference\n---\n[Missing](/absent.md)\n",
        )
        diags = validate_file(f, m, base_index)
        assert "L002" in _codes(diags)


# ---------------------------------------------------------------------------
# `Attested Computation` — no-exemption matrix (SPEC-002 §7)
#
# F101 (profile, undeclared type) and F201 (hygiene, unknown fields) must
# never treat `Attested Computation` specially: a manifest that does not
# declare the type must still reject it like any other undeclared type,
# on top of (not instead of) F005 (core). A manifest that does declare it
# gets normal profile stacking, no special-casing either way.
# ---------------------------------------------------------------------------


class TestAttestedComputationExemptionMatrix:
    def test_undeclared_type_gets_f101_and_f005_together(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            "okf_version: '0.2'\n"
            "base:\n"
            "  name: test-base\n"
            "  roots:\n"
            f"    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n"
            "    index: index.md\n"
            "    log: log.md\n"
            "profile:\n"
            "  types:\n"
            "    Reference:\n"
            "      required: [type]\n"
            "      optional: []\n",
            encoding="utf-8",
        )
        m = load_manifest(manifest_path)
        base_index = build_file_index([r.path for r in m.base.roots])
        f = make_md(
            root / "computation.md",
            "---\ntype: Attested Computation\n---\n# Computation\n",
        )
        diags = validate_file(f, m, base_index)
        codes = _codes(diags)
        assert "F101" in codes
        assert "F005" in codes

    def test_declared_type_gets_normal_profile_stacking_no_exemption_needed(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            "okf_version: '0.2'\n"
            "base:\n"
            "  name: test-base\n"
            "  roots:\n"
            f"    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n"
            "    index: index.md\n"
            "    log: log.md\n"
            "profile:\n"
            "  types:\n"
            "    Attested Computation:\n"
            "      required: [type]\n"
            "      optional: [runtime]\n",
            encoding="utf-8",
        )
        m = load_manifest(manifest_path)
        base_index = build_file_index([r.path for r in m.base.roots])
        f = make_md(
            root / "computation.md",
            "---\ntype: Attested Computation\nruntime: python3.12\n---\n"
            "# Computation\n",
        )
        diags = validate_file(f, m, base_index)
        codes = _codes(diags)
        assert "F101" not in codes
        assert "F005" not in codes


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

    def test_invalid_manifest_raises_manifest_error(self, tmp_path: Path) -> None:
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

    def test_relative_dir_target_does_not_raise(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression guard: a CLI-style relative target (e.g. `okflint
        validate --manifest m.yaml docs/` run from the repo root) must not
        raise ValueError when compared against the manifest's resolved
        (absolute) roots."""
        manifest_path, root = profile_manifest
        make_md(
            root / "concept.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n",
        )
        monkeypatch.chdir(root.parent)
        diags, code = run_validate(manifest_path, [Path("root")])
        assert code == 0
        assert not [d for d in diags if d.severity == "error"]

    def test_relative_single_file_target_does_not_raise(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest_path, root = profile_manifest
        make_md(
            root / "concept.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n",
        )
        monkeypatch.chdir(root)
        diags, code = run_validate(manifest_path, [Path("concept.md")])
        assert code == 0
        assert not [d for d in diags if d.severity == "error"]

    def test_absolute_single_file_target_unchanged(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = profile_manifest
        f = make_md(
            root / "concept.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n",
        )
        diags, code = run_validate(manifest_path, [f])
        assert code == 0
        assert not [d for d in diags if d.severity == "error"]

    def test_multiroot_relative_target_matches_correct_root(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A relative target under the second declared root must resolve to
        that root (and its exclude_patterns), not silently fall back to the
        first root."""
        root_a = tmp_path / "root_a"
        root_b = tmp_path / "root_b"
        root_a.mkdir()
        root_b.mkdir()
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            "okf_version: '0.1'\n"
            "base:\n"
            "  name: test-base\n"
            "  roots:\n"
            f"    - path: '{root_a.as_posix()}'\n"
            f"    - path: '{root_b.as_posix()}'\n"
            "      exclude_patterns: ['skip/**']\n"
            "  reserved_files:\n"
            "    index: index.md\n"
            "    log: log.md\n",
            encoding="utf-8",
        )
        make_md(root_b / "concept.md", "---\ntype: Reference\n---\n# OK\n")
        make_md(root_b / "skip" / "ignored.md", "# No frontmatter\n")

        monkeypatch.chdir(tmp_path)
        diags, code = run_validate(manifest_path, [Path("root_b")])
        assert code == 0
        assert not any("ignored.md" in d.file for d in diags)
