"""Tests for the okflint CLI dispatcher."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from okflint.cli import _cmd_audit, _cmd_validate, build_parser, main


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
        parser = build_parser()
        args = parser.parse_args(["validate", "file.md"])
        assert args.manifest == "okf-base.yaml"

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
