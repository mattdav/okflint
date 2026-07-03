"""Tests for OKF manifest loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from okflint.manifest import ManifestError, RootConfig, _coerce_level, load_manifest


# ---------------------------------------------------------------------------
# _coerce_level
# ---------------------------------------------------------------------------


class TestCoerceLevel:
    def test_false_becomes_off(self) -> None:
        assert _coerce_level(False, "broken_links") == "off"

    def test_true_becomes_warn(self) -> None:
        assert _coerce_level(True, "broken_links") == "warn"

    def test_valid_string_off(self) -> None:
        assert _coerce_level("off", "split_candidates") == "off"

    def test_valid_string_warn(self) -> None:
        assert _coerce_level("warn", "split_candidates") == "warn"

    def test_valid_string_error(self) -> None:
        assert _coerce_level("error", "split_candidates") == "error"

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ManifestError, match="key"):
            _coerce_level("invalid", "key")


# ---------------------------------------------------------------------------
# load_manifest — errors
# ---------------------------------------------------------------------------


class TestLoadManifestErrors:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ManifestError, match="Cannot read"):
            load_manifest(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed\n", encoding="utf-8")
        with pytest.raises(ManifestError, match="Invalid YAML"):
            load_manifest(f)

    def test_missing_base_key_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "m.yaml"
        f.write_text("okf_version: '0.1'\n", encoding="utf-8")
        with pytest.raises(ManifestError, match="'base' absent"):
            load_manifest(f)

    def test_empty_roots_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "m.yaml"
        f.write_text(
            "base:\n  roots: []\n  reserved_files:\n    index: index.md\n    log: log.md\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="roots must be a non-empty list"):
            load_manifest(f)

    def test_missing_log_in_reserved_files_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="'index' and 'log'"):
            load_manifest(f)

    def test_required_optional_overlap_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "profile:\n  types:\n    Decision:\n"
            "      required: [type, statut]\n"
            "      optional: [statut]\n"
            "      statut_values: [Accepté]\n"
            "      aliases: []\n"
            "  date_fields: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="required and optional"):
            load_manifest(f)

    def test_values_suffix_for_undeclared_property_raises(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        # "statut" is not in required nor optional — statut_values is invalid.
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "profile:\n  types:\n    Decision:\n"
            "      required: [type]\n"
            "      optional: []\n"
            "      statut_values: [Accepté]\n"
            "      aliases: []\n"
            "  date_fields: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="undeclared"):
            load_manifest(f)

    def test_invalid_hygiene_value_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "hygiene:\n  broken_links: maybe\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="broken_links"):
            load_manifest(f)


# ---------------------------------------------------------------------------
# load_manifest — profile/type structural errors
# ---------------------------------------------------------------------------


class TestParseTypeConfigErrors:
    def _write(self, tmp_path: Path, profile_yaml: str) -> Path:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            f"{profile_yaml}",
            encoding="utf-8",
        )
        return f

    def test_profile_not_a_mapping_raises(self, tmp_path: Path) -> None:
        f = self._write(tmp_path, "profile: not-a-mapping\n")
        with pytest.raises(ManifestError, match="profile must be a mapping"):
            load_manifest(f)

    def test_types_not_a_mapping_raises(self, tmp_path: Path) -> None:
        f = self._write(tmp_path, "profile:\n  types: not-a-mapping\n")
        with pytest.raises(ManifestError, match="profile.types must be a mapping"):
            load_manifest(f)

    def test_type_config_not_a_mapping_raises(self, tmp_path: Path) -> None:
        f = self._write(tmp_path, "profile:\n  types:\n    Decision: not-a-mapping\n")
        with pytest.raises(ManifestError, match="must be a mapping"):
            load_manifest(f)

    def test_required_not_a_list_raises(self, tmp_path: Path) -> None:
        f = self._write(
            tmp_path, "profile:\n  types:\n    Decision:\n      required: not-a-list\n"
        )
        with pytest.raises(ManifestError, match="required must be a list"):
            load_manifest(f)

    def test_optional_not_a_list_raises(self, tmp_path: Path) -> None:
        f = self._write(
            tmp_path,
            "profile:\n  types:\n    Decision:\n"
            "      required: [type]\n"
            "      optional: not-a-list\n",
        )
        with pytest.raises(ManifestError, match="optional must be a list"):
            load_manifest(f)

    def test_values_not_a_list_raises(self, tmp_path: Path) -> None:
        f = self._write(
            tmp_path,
            "profile:\n  types:\n    Decision:\n"
            "      required: [type, statut]\n"
            "      optional: []\n"
            "      statut_values: not-a-list\n",
        )
        with pytest.raises(ManifestError, match="statut_values must be a list"):
            load_manifest(f)

    def test_aliases_not_a_list_raises(self, tmp_path: Path) -> None:
        f = self._write(
            tmp_path,
            "profile:\n  types:\n    Decision:\n"
            "      required: [type]\n"
            "      optional: []\n"
            "      aliases: not-a-list\n",
        )
        with pytest.raises(ManifestError, match="aliases must be a list"):
            load_manifest(f)


# ---------------------------------------------------------------------------
# load_manifest — success
# ---------------------------------------------------------------------------


class TestLoadManifestSuccess:
    def test_minimal_manifest_loads(self, minimal_manifest: tuple[Path, Path]) -> None:
        manifest_path, root = minimal_manifest
        m = load_manifest(manifest_path)
        assert m.base.roots == [RootConfig(path=root, exclude_patterns=[])]
        assert m.profile is None
        assert m.hygiene is None

    def test_profile_manifest_loads(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        assert "Decision" in m.profile.types
        assert "JournalEntry" in m.profile.types

    def test_journal_entry_has_no_controlled_values(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        je = m.profile.types["JournalEntry"]
        assert je.controlled_values == {}

    def test_decision_controlled_values_loaded(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        decision = m.profile.types["Decision"]
        assert decision.controlled_values == {
            "statut": ["Accepté", "Proposé", "Déprécié"]
        }

    def test_decision_aliases_loaded(
        self, profile_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = profile_manifest
        m = load_manifest(manifest_path)
        assert m.profile is not None
        assert "adr" in m.profile.types["Decision"].aliases

    def test_hygiene_manifest_loads(
        self, hygiene_manifest: tuple[Path, Path]
    ) -> None:
        manifest_path, _ = hygiene_manifest
        m = load_manifest(manifest_path)
        assert m.hygiene is not None
        assert m.hygiene.broken_links == "warn"

    def test_yaml_bool_off_coerced(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        # PyYAML parses YAML `off` as Python False; _coerce_level maps it to "off"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "hygiene:\n  broken_links: 'off'\n",
            encoding="utf-8",
        )
        m = load_manifest(f)
        assert m.hygiene is not None
        assert m.hygiene.broken_links == "off"

    def test_external_refs_loaded(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            "  reserved_files:\n    index: index.md\n    log: log.md\n"
            "  link_resolution:\n    external_refs: [Wikipedia, GitHub]\n",
            encoding="utf-8",
        )
        m = load_manifest(f)
        assert "wikipedia" in m.base.external_refs
        assert "github" in m.base.external_refs


# ---------------------------------------------------------------------------
# load_manifest — exclude_patterns
# ---------------------------------------------------------------------------


class TestLoadManifestExcludePatterns:
    def _write(self, tmp_path: Path, patterns_yaml: str) -> Path:
        root = tmp_path / "root"
        root.mkdir()
        f = tmp_path / "m.yaml"
        patterns_block = f"      {patterns_yaml}" if patterns_yaml else ""
        f.write_text(
            f"base:\n  roots:\n    - path: '{root.as_posix()}'\n"
            f"{patterns_block}"
            "  reserved_files:\n    index: index.md\n    log: log.md\n",
            encoding="utf-8",
        )
        return f

    def test_exclude_patterns_loaded(self, tmp_path: Path) -> None:
        f = self._write(
            tmp_path, "exclude_patterns:\n        - .venv/**\n        - src/**/data/**\n"
        )
        m = load_manifest(f)
        assert m.base.roots[0].exclude_patterns == [".venv/**", "src/**/data/**"]

    def test_no_exclude_patterns_defaults_to_empty(self, tmp_path: Path) -> None:
        f = self._write(tmp_path, "")
        m = load_manifest(f)
        assert m.base.roots[0].exclude_patterns == []

    def test_invalid_exclude_patterns_raises(self, tmp_path: Path) -> None:
        f = self._write(tmp_path, "exclude_patterns: not-a-list\n")
        with pytest.raises(ManifestError, match="exclude_patterns must be a list"):
            load_manifest(f)

    def test_exclude_patterns_non_string_element_raises(self, tmp_path: Path) -> None:
        f = self._write(tmp_path, "exclude_patterns:\n        - 42\n")
        with pytest.raises(ManifestError, match="exclude_patterns must be a list"):
            load_manifest(f)
