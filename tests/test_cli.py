"""Tests for the okflint CLI dispatcher."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from okflint.cli import _cmd_audit, _cmd_validate, build_parser, main


def _write_manifest(path: Path, roots: list[Path]) -> None:
    """Write a minimal OKF manifest with the given roots."""
    data = {
        "okf_version": "0.1",
        "base": {
            "name": "test-base",
            "roots": [{"path": r.as_posix()} for r in roots],
            "reserved_files": {"index": "index.md", "log": "log.md"},
            "status_field": "statut",
        },
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_validate_subcommand_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["validate", "--manifest", "m.yaml", "file.md"])
        assert args.command == "validate"
        assert args.manifest == "m.yaml"
        assert args.targets == ["file.md"]

    def test_validate_default_manifest(self) -> None:
        # Default is None; _cmd_validate falls back to "okf-base.yaml" at runtime.
        # None is required to distinguish "not provided" from "explicitly set"
        # when --vault points to a JSON file (vault-mode detection).
        parser = build_parser()
        args = parser.parse_args(["validate", "file.md"])
        assert args.manifest is None

    def test_validate_json_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["validate", "--json", "file.md"])
        assert args.json_output is True


# ---------------------------------------------------------------------------
# _cmd_validate — exit codes
# ---------------------------------------------------------------------------


class TestCmdValidate:
    def test_exit_0_on_conforming_files(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = profile_manifest
        make_md(
            root / "doc.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n",
        )
        parser = build_parser()
        args = parser.parse_args(
            ["validate", "--manifest", str(manifest_path), str(root)]
        )
        assert _cmd_validate(args) == 0

    def test_exit_1_on_errors(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "bad.md", "# No frontmatter\n")
        parser = build_parser()
        args = parser.parse_args(
            ["validate", "--manifest", str(manifest_path), str(root)]
        )
        assert _cmd_validate(args) == 1

    def test_exit_2_on_invalid_manifest(self, tmp_path: Path) -> None:
        bad_manifest = tmp_path / "bad.yaml"
        bad_manifest.write_text("okf_version: '0.1'\n", encoding="utf-8")
        dummy = tmp_path / "dummy.md"
        dummy.write_text("# Dummy", encoding="utf-8")
        parser = build_parser()
        args = parser.parse_args(
            ["validate", "--manifest", str(bad_manifest), str(dummy)]
        )
        assert _cmd_validate(args) == 2

    def test_json_output_contains_diagnostics(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "bad.md", "# No frontmatter\n")
        parser = build_parser()
        args = parser.parse_args(
            ["validate", "--manifest", str(manifest_path), "--json", str(root)]
        )
        _cmd_validate(args)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["code"] == "F001"


# ---------------------------------------------------------------------------
# _cmd_audit
# ---------------------------------------------------------------------------


class TestCmdAudit:
    def test_audit_dry_run_returns_0(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "doc.md", "---\ntype: Reference\n---\n# Title\n")
        parser = build_parser()
        args = parser.parse_args(
            ["audit", "--bundle", str(bundle), "--vault", str(bundle)]
        )
        assert _cmd_audit(args) == 0

    def test_audit_with_apply_writes_json(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "doc.md", "---\ntype: Reference\n---\n# Title\n")
        monkeypatch.chdir(tmp_path)
        parser = build_parser()
        args = parser.parse_args(
            ["audit", "--bundle", str(bundle), "--vault", str(bundle), "--apply"]
        )
        code = _cmd_audit(args)
        assert code == 0
        assert any((tmp_path / ".okflint").glob("*.json"))


# ---------------------------------------------------------------------------
# main() — entry point
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_exits_with_code(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "bad.md", "# No frontmatter\n")
        monkeypatch.setattr(
            sys,
            "argv",
            ["okflint", "validate", "--manifest", str(manifest_path), str(root)],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# build_parser — audit manifest options
# ---------------------------------------------------------------------------


class TestBuildParserAudit:
    def test_audit_manifest_only_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["audit", "--manifest", "m.yaml"])
        assert args.manifest == "m.yaml"
        assert args.bundle is None
        assert args.vault is None

    def test_audit_no_args_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["audit"])
        assert args.manifest is None
        assert args.bundle is None
        assert args.vault is None

    def test_validate_no_targets_defaults_to_empty(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["validate", "--manifest", "m.yaml"])
        assert args.targets == []


# ---------------------------------------------------------------------------
# _cmd_audit — manifest resolution rules
# ---------------------------------------------------------------------------


class TestCmdAuditManifest:
    def test_manifest_only_exit_0(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        make_md(root / "doc.md", "---\ntype: Reference\n---\n# Title\n")
        manifest_path = tmp_path / "manifest.yaml"
        _write_manifest(manifest_path, [root])
        parser = build_parser()
        args = parser.parse_args(["audit", "--manifest", str(manifest_path)])
        assert _cmd_audit(args) == 0

    def test_no_args_exit_2(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        parser = build_parser()
        args = parser.parse_args(["audit"])
        assert _cmd_audit(args) == 2
        assert "Error:" in capsys.readouterr().err

    def test_bundle_without_vault_exit_2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        parser = build_parser()
        args = parser.parse_args(["audit", "--bundle", str(bundle)])
        assert _cmd_audit(args) == 2
        assert "Error:" in capsys.readouterr().err

    def test_manifest_and_bundle_warns_and_exits_0(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        make_md(root / "doc.md", "---\ntype: Reference\n---\n# Title\n")
        manifest_path = tmp_path / "manifest.yaml"
        _write_manifest(manifest_path, [root])
        parser = build_parser()
        args = parser.parse_args(
            ["audit", "--manifest", str(manifest_path), "--bundle", str(root)]
        )
        assert _cmd_audit(args) == 0
        assert "Warning:" in capsys.readouterr().err

    def test_bad_manifest_exit_2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bad_manifest = tmp_path / "bad.yaml"
        bad_manifest.write_text("okf_version: '0.1'\n", encoding="utf-8")
        parser = build_parser()
        args = parser.parse_args(["audit", "--manifest", str(bad_manifest)])
        assert _cmd_audit(args) == 2
        assert "error" in capsys.readouterr().err.lower()

    def test_multi_root_manifest_scan(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        root1 = tmp_path / "root1"
        root1.mkdir()
        root2 = tmp_path / "root2"
        root2.mkdir()
        make_md(root1 / "a.md", "---\ntype: Reference\n---\n")
        make_md(root2 / "b.md", "---\ntype: Reference\n---\n")
        manifest_path = tmp_path / "manifest.yaml"
        _write_manifest(manifest_path, [root1, root2])
        parser = build_parser()
        args = parser.parse_args(["audit", "--manifest", str(manifest_path)])
        assert _cmd_audit(args) == 0


# ---------------------------------------------------------------------------
# _cmd_validate — optional targets
# ---------------------------------------------------------------------------


class TestCmdValidateNoTargets:
    def test_no_targets_uses_manifest_roots_exit_0(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "doc.md", "---\ntype: Reference\n---\n# Title\n")
        parser = build_parser()
        args = parser.parse_args(["validate", "--manifest", str(manifest_path)])
        assert _cmd_validate(args) == 0

    def test_no_targets_exit_1_on_errors(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "bad.md", "# No frontmatter\n")
        parser = build_parser()
        args = parser.parse_args(["validate", "--manifest", str(manifest_path)])
        assert _cmd_validate(args) == 1

    def test_bad_manifest_no_targets_exit_2(self, tmp_path: Path) -> None:
        bad_manifest = tmp_path / "bad.yaml"
        bad_manifest.write_text("okf_version: '0.1'\n", encoding="utf-8")
        parser = build_parser()
        args = parser.parse_args(["validate", "--manifest", str(bad_manifest)])
        assert _cmd_validate(args) == 2
