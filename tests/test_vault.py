"""Tests for okflint.vault — load_vault, VaultConfig, BundleEntry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from okflint.audit import run_audit
from okflint.cli import _cmd_audit, _cmd_validate, build_parser
from okflint.vault import BundleEntry, VaultConfig, VaultError, load_vault


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MINIMAL_MANIFEST = """\
okf_version: "0.1"
base:
  name: test-bundle
  roots:
    - path: {root}
  reserved_files:
    index: index.md
    log: log.md
"""


def _make_bundle(tmp_path: Path, name: str = "bundle") -> Path:
    """Return a bundle directory containing a minimal okf-base.yaml."""
    bundle = tmp_path / name
    bundle.mkdir()
    manifest_content = _MINIMAL_MANIFEST.format(root=bundle.as_posix())
    (bundle / "okf-base.yaml").write_text(manifest_content, encoding="utf-8")
    return bundle


def _write_vault(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write a vault JSON file and return its path."""
    vault_file = tmp_path / "okf-vault.json"
    vault_file.write_text(json.dumps(data), encoding="utf-8")
    return vault_file


def _vault_data(bundles: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """Build minimal vault JSON data with the given bundles."""
    base: dict[str, Any] = {"okf_vault_version": "0.1", "name": "test-vault"}
    base.update(extra)
    base["bundles"] = bundles
    return base


# ---------------------------------------------------------------------------
# Nominal / happy-path tests
# ---------------------------------------------------------------------------


class TestLoadVaultNominal:
    def test_returns_vault_config_type(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        cfg = load_vault(vault_file)
        assert isinstance(cfg, VaultConfig)

    def test_version_field(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        cfg = load_vault(vault_file)
        assert cfg.okf_vault_version == "0.1"

    def test_name_field(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        cfg = load_vault(vault_file)
        assert cfg.name == "test-vault"

    def test_single_bundle_path(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        cfg = load_vault(vault_file)
        assert len(cfg.bundles) == 1
        assert cfg.bundles[0].path == bundle

    def test_single_bundle_manifest(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        cfg = load_vault(vault_file)
        assert cfg.bundles[0].manifest_path == bundle / "okf-base.yaml"

    def test_multiple_bundles(self, tmp_path: Path) -> None:
        b1 = _make_bundle(tmp_path, "b1")
        b2 = _make_bundle(tmp_path, "b2")
        vault_file = _write_vault(
            tmp_path,
            _vault_data([{"path": str(b1)}, {"path": str(b2)}]),
        )
        cfg = load_vault(vault_file)
        assert len(cfg.bundles) == 2
        assert cfg.bundles[0].path == b1
        assert cfg.bundles[1].path == b2

    def test_bundle_entry_type(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        cfg = load_vault(vault_file)
        assert isinstance(cfg.bundles[0], BundleEntry)

    def test_explicit_manifest_field(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(
            tmp_path,
            _vault_data([{"path": str(bundle), "manifest": "okf-base.yaml"}]),
        )
        cfg = load_vault(vault_file)
        assert cfg.bundles[0].manifest_path == bundle / "okf-base.yaml"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestLoadVaultErrors:
    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(VaultError, match="Cannot read"):
            load_vault(tmp_path / "nonexistent.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "okf-vault.json"
        vault_file.write_text("not { valid json", encoding="utf-8")
        with pytest.raises(VaultError, match="Invalid JSON"):
            load_vault(vault_file)

    def test_not_a_json_object(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "okf-vault.json"
        vault_file.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(VaultError, match="not a JSON object"):
            load_vault(vault_file)

    def test_bundles_key_absent(self, tmp_path: Path) -> None:
        vault_file = _write_vault(tmp_path, {"okf_vault_version": "0.1", "name": "v"})
        with pytest.raises(VaultError, match="bundles must be a non-empty list"):
            load_vault(vault_file)

    def test_bundles_empty_list(self, tmp_path: Path) -> None:
        vault_file = _write_vault(
            tmp_path, {"okf_vault_version": "0.1", "name": "v", "bundles": []}
        )
        with pytest.raises(VaultError, match="bundles must be a non-empty list"):
            load_vault(vault_file)

    def test_bundle_missing_path_key(self, tmp_path: Path) -> None:
        vault_file = _write_vault(
            tmp_path, {"bundles": [{"manifest": "x.yaml"}]}
        )
        with pytest.raises(VaultError, match="must be a mapping with at least a 'path' key"):
            load_vault(vault_file)

    def test_bundle_not_a_mapping(self, tmp_path: Path) -> None:
        vault_file = _write_vault(tmp_path, {"bundles": ["not-a-dict"]})
        with pytest.raises(VaultError, match="must be a mapping"):
            load_vault(vault_file)

    def test_bundle_path_not_exists(self, tmp_path: Path) -> None:
        vault_file = _write_vault(
            tmp_path, {"bundles": [{"path": str(tmp_path / "ghost_dir")}]}
        )
        with pytest.raises(VaultError, match="does not exist"):
            load_vault(vault_file)

    def test_default_manifest_not_exists(self, tmp_path: Path) -> None:
        bundle = tmp_path / "bundle_no_manifest"
        bundle.mkdir()
        # No okf-base.yaml created → default lookup should fail
        vault_file = _write_vault(tmp_path, {"bundles": [{"path": str(bundle)}]})
        with pytest.raises(VaultError, match="does not exist"):
            load_vault(vault_file)

    def test_custom_manifest_not_exists(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(
            tmp_path,
            {"bundles": [{"path": str(bundle), "manifest": "missing.yaml"}]},
        )
        with pytest.raises(VaultError, match="does not exist"):
            load_vault(vault_file)


# ---------------------------------------------------------------------------
# Default-value behaviour
# ---------------------------------------------------------------------------


class TestLoadVaultDefaults:
    def test_absent_manifest_defaults_to_okf_base_yaml(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, {"bundles": [{"path": str(bundle)}]})
        cfg = load_vault(vault_file)
        assert cfg.bundles[0].manifest_path.name == "okf-base.yaml"

    def test_name_defaults_to_empty_when_absent(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(
            tmp_path,
            {"okf_vault_version": "0.1", "bundles": [{"path": str(bundle)}]},
        )
        cfg = load_vault(vault_file)
        assert cfg.name == ""


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestLoadVaultPathResolution:
    def test_absolute_bundle_path_preserved(self, tmp_path: Path) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        cfg = load_vault(vault_file)
        assert cfg.bundles[0].path.is_absolute()
        assert cfg.bundles[0].path == bundle

    def test_relative_bundle_path_resolved_to_vault_parent(
        self, tmp_path: Path
    ) -> None:
        """A relative bundle path is resolved relative to the vault file's directory."""
        bundle = _make_bundle(tmp_path)
        rel_name = bundle.name  # just the directory name
        vault_file = _write_vault(tmp_path, _vault_data([{"path": rel_name}]))
        cfg = load_vault(vault_file)
        assert cfg.bundles[0].path == bundle.resolve()

    def test_manifest_resolved_relative_to_bundle(self, tmp_path: Path) -> None:
        """manifest field is resolved relative to the bundle path."""
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(
            tmp_path,
            _vault_data([{"path": str(bundle), "manifest": "okf-base.yaml"}]),
        )
        cfg = load_vault(vault_file)
        assert cfg.bundles[0].manifest_path == bundle / "okf-base.yaml"
        assert cfg.bundles[0].manifest_path.is_absolute()


# ---------------------------------------------------------------------------
# Version warnings
# ---------------------------------------------------------------------------


class TestLoadVaultVersionWarnings:
    def test_absent_version_sets_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, {"bundles": [{"path": str(bundle)}]})
        cfg = load_vault(vault_file)
        assert cfg.okf_vault_version is None

    def test_absent_version_prints_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, {"bundles": [{"path": str(bundle)}]})
        load_vault(vault_file)
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "okf_vault_version" in captured.err

    def test_unknown_version_stores_value(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(
            tmp_path,
            {"okf_vault_version": "99.9", "bundles": [{"path": str(bundle)}]},
        )
        cfg = load_vault(vault_file)
        assert cfg.okf_vault_version == "99.9"

    def test_unknown_version_prints_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(
            tmp_path,
            {"okf_vault_version": "99.9", "bundles": [{"path": str(bundle)}]},
        )
        load_vault(vault_file)
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "99.9" in captured.err

    def test_known_version_no_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = _make_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        load_vault(vault_file)
        captured = capsys.readouterr()
        assert "Warning" not in captured.err


# ---------------------------------------------------------------------------
# run_audit integration — vault_index parameter
# ---------------------------------------------------------------------------


class TestRunAuditVaultIndex:
    def _make_md_bundle(self, tmp_path: Path, name: str = "bundle") -> Path:
        """Bundle with an index.md and a concept file containing a wikilink."""
        bundle = tmp_path / name
        bundle.mkdir()
        (bundle / "index.md").write_text("# Index\n", encoding="utf-8")
        (bundle / "alpha.md").write_text(
            "---\ntype: concept\n---\n# Alpha\n\nSee [[beta]].\n",
            encoding="utf-8",
        )
        (bundle / "beta.md").write_text(
            "---\ntype: concept\n---\n# Beta\n", encoding="utf-8"
        )
        return bundle

    def test_vault_index_resolves_wikilink(self, tmp_path: Path) -> None:
        """When vault_index is provided, wikilinks are resolved from it."""
        bundle = self._make_md_bundle(tmp_path)
        vault_index = {"beta": ["beta.md"]}
        report = run_audit(bundle, [], vault_index=vault_index)
        alpha_report = next(f for f in report["files"] if "alpha" in f["path"])
        wikilinks = alpha_report["wikilinks"]
        assert len(wikilinks) == 1
        assert not wikilinks[0]["broken"]

    def test_vault_index_skips_index_build(self, tmp_path: Path) -> None:
        """Empty vault_paths should not matter when vault_index is supplied."""
        bundle = self._make_md_bundle(tmp_path)
        # vault_paths is empty — index build from it would yield nothing
        # but vault_index resolves [[beta]] correctly
        vault_index = {"beta": ["beta.md"]}
        report = run_audit(bundle, [], vault_index=vault_index)
        stats = report["stats"]
        assert stats["total_files"] == 3  # index.md + alpha.md + beta.md

    def test_none_vault_index_builds_from_vault_paths(self, tmp_path: Path) -> None:
        """When vault_index is None, it is built from vault_paths as before."""
        bundle = self._make_md_bundle(tmp_path)
        # vault_paths = bundle itself so beta.md is in the index
        report = run_audit(bundle, bundle)
        alpha_report = next(f for f in report["files"] if "alpha" in f["path"])
        assert not alpha_report["wikilinks"][0]["broken"]


# ---------------------------------------------------------------------------
# CLI vault mode — _cmd_audit / _cmd_validate with --vault JSON
# ---------------------------------------------------------------------------


def _make_cli_bundle(tmp_path: Path, name: str = "bundle") -> Path:
    """Bundle directory with a valid manifest, index.md, and log.md."""
    bundle = tmp_path / name
    bundle.mkdir()
    data: dict[str, Any] = {
        "okf_version": "0.1",
        "base": {
            "name": name,
            "roots": [{"path": bundle.as_posix()}],
            "reserved_files": {"index": "index.md", "log": "log.md"},
        },
    }
    (bundle / "okf-base.yaml").write_text(
        yaml.dump(data, allow_unicode=True), encoding="utf-8"
    )
    (bundle / "index.md").write_text("# Index\n", encoding="utf-8")
    (bundle / "log.md").write_text("# Log\n", encoding="utf-8")
    return bundle


class TestCmdAuditVault:
    def test_full_vault_exit_0(self, tmp_path: Path) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        parser = build_parser()
        args = parser.parse_args(["audit", "--vault", str(vault_file)])
        assert _cmd_audit(args) == 0

    def test_vault_error_exit_2(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "bad.json"
        vault_file.write_text('{"bundles": []}', encoding="utf-8")
        parser = build_parser()
        args = parser.parse_args(["audit", "--vault", str(vault_file)])
        assert _cmd_audit(args) == 2

    def test_vault_json_with_bundle_exit_0(self, tmp_path: Path) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        parser = build_parser()
        args = parser.parse_args(
            ["audit", "--vault", str(vault_file), "--bundle", str(bundle)]
        )
        assert _cmd_audit(args) == 0

    def test_full_vault_with_apply_writes_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        args = parser.parse_args(["audit", "--vault", str(vault_file), "--apply"])
        assert _cmd_audit(args) == 0
        assert any((tmp_path / ".okflint").glob("*vault_audit*.json"))

    def test_apply_twice_creates_v2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        args = parser.parse_args(["audit", "--vault", str(vault_file), "--apply"])
        _cmd_audit(args)
        _cmd_audit(args)  # second run same day → v2
        assert len(list((tmp_path / ".okflint").glob("*vault_audit*.json"))) == 2


class TestCmdValidateVault:
    def test_full_vault_exit_0(self, tmp_path: Path) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        parser = build_parser()
        args = parser.parse_args(["validate", "--vault", str(vault_file)])
        assert _cmd_validate(args) == 0

    def test_vault_error_exit_2(self, tmp_path: Path) -> None:
        vault_file = tmp_path / "bad.json"
        vault_file.write_text('{"bundles": []}', encoding="utf-8")
        parser = build_parser()
        args = parser.parse_args(["validate", "--vault", str(vault_file)])
        assert _cmd_validate(args) == 2

    def test_ambiguous_targets_exit_2(self, tmp_path: Path) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        parser = build_parser()
        args = parser.parse_args(
            ["validate", "--vault", str(vault_file), str(bundle / "index.md")]
        )
        assert _cmd_validate(args) == 2

    def test_explicit_manifest_with_vault(self, tmp_path: Path) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        manifest = bundle / "okf-base.yaml"
        parser = build_parser()
        args = parser.parse_args(
            ["validate", "--vault", str(vault_file), "--manifest", str(manifest)]
        )
        assert _cmd_validate(args) == 0

    def test_explicit_manifest_with_targets_and_vault(self, tmp_path: Path) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        manifest = bundle / "okf-base.yaml"
        parser = build_parser()
        args = parser.parse_args(
            [
                "validate",
                "--vault", str(vault_file),
                "--manifest", str(manifest),
                str(bundle / "index.md"),
            ]
        )
        assert _cmd_validate(args) in {0, 1}

    def test_full_vault_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = _make_cli_bundle(tmp_path)
        vault_file = _write_vault(tmp_path, _vault_data([{"path": str(bundle)}]))
        parser = build_parser()
        args = parser.parse_args(["validate", "--vault", str(vault_file), "--json"])
        _cmd_validate(args)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
