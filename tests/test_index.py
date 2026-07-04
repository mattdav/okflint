"""Tests for OKF §6 index.md generation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from okflint.cli import _cmd_index, build_parser
from okflint.index import IndexEntry, build_index_content, generate_indexes
from okflint.manifest import load_manifest
from okflint.validate import run_validate

# ---------------------------------------------------------------------------
# build_index_content
# ---------------------------------------------------------------------------


class TestBuildIndexContent:
    def test_title_from_frontmatter(self, tmp_path: Path) -> None:
        entries = [IndexEntry(filename="a.md", title="My Title", description=None)]
        content = build_index_content(tmp_path, entries, [])
        assert content == "- [My Title](a.md)\n"

    def test_filename_fallback_when_no_title(self, tmp_path: Path) -> None:
        entries = [IndexEntry(filename="my-file.md", title="my-file", description=None)]
        content = build_index_content(tmp_path, entries, [])
        assert content == "- [my-file](my-file.md)\n"

    def test_description_present(self, tmp_path: Path) -> None:
        entries = [
            IndexEntry(filename="a.md", title="A", description="Some description")
        ]
        content = build_index_content(tmp_path, entries, [])
        assert content == "- [A](a.md) — Some description\n"

    def test_description_absent_no_orphan_dash(self, tmp_path: Path) -> None:
        entries = [IndexEntry(filename="a.md", title="A", description=None)]
        content = build_index_content(tmp_path, entries, [])
        assert "—" not in content

    def test_deterministic_sort_subdirs_then_files(self, tmp_path: Path) -> None:
        entries = [
            IndexEntry(filename="Zebra.md", title="Zebra", description=None),
            IndexEntry(filename="apple.md", title="Apple", description=None),
        ]
        subdirs = ["Charlie", "bravo"]
        content = build_index_content(tmp_path, entries, subdirs)
        lines = content.splitlines()
        assert lines == [
            "- [bravo/](bravo/index.md)",
            "- [Charlie/](Charlie/index.md)",
            "- [Apple](apple.md)",
            "- [Zebra](Zebra.md)",
        ]

    def test_empty_directory_yields_empty_content(self, tmp_path: Path) -> None:
        assert build_index_content(tmp_path, [], []) == ""


# ---------------------------------------------------------------------------
# generate_indexes
# ---------------------------------------------------------------------------


class TestGenerateIndexes:
    def test_one_index_per_directory(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "a.md", "---\ntype: Reference\ntitle: A\n---\n")
        make_md(root / "sub" / "b.md", "---\ntype: Reference\ntitle: B\n---\n")
        manifest = load_manifest(manifest_path)

        indexes = generate_indexes(manifest)

        assert root / "index.md" in indexes
        assert root / "sub" / "index.md" in indexes
        assert "[sub/](sub/index.md)" in indexes[root / "index.md"]
        assert "[B](b.md)" in indexes[root / "sub" / "index.md"]

    def test_respects_exclude_patterns(self, tmp_path: Path) -> None:
        import yaml

        root = tmp_path / "root"
        root.mkdir()
        (root / "keep.md").write_text(
            "---\ntype: Reference\ntitle: Keep\n---\n", encoding="utf-8"
        )
        excluded_dir = root / "excluded"
        excluded_dir.mkdir()
        (excluded_dir / "skip.md").write_text(
            "---\ntype: Reference\ntitle: Skip\n---\n", encoding="utf-8"
        )
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            yaml.dump(
                {
                    "okf_version": "0.1",
                    "base": {
                        "name": "test-base",
                        "roots": [
                            {
                                "path": root.as_posix(),
                                "exclude_patterns": ["excluded/**"],
                            }
                        ],
                        "reserved_files": {"index": "index.md", "log": "log.md"},
                    },
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        manifest = load_manifest(manifest_path)

        indexes = generate_indexes(manifest)

        assert root / "excluded" / "index.md" not in indexes
        assert "excluded" not in indexes[root / "index.md"]

    def test_respects_exclude_patterns_single_file(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "keep.md", "---\ntype: Reference\ntitle: Keep\n---\n")
        make_md(root / "skip.md", "---\ntype: Reference\ntitle: Skip\n---\n")
        manifest = load_manifest(manifest_path)
        manifest.base.roots[0].exclude_patterns.append("skip.md")

        content = generate_indexes(manifest)[root / "index.md"]

        assert "Keep" in content
        assert "Skip" not in content

    def test_ignores_reserved_index_and_log(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "index.md", "old content\n")
        make_md(root / "log.md", "## 2026-01-01\n\nEntry.\n")
        make_md(root / "a.md", "---\ntype: Reference\ntitle: A\n---\n")
        manifest = load_manifest(manifest_path)

        indexes = generate_indexes(manifest)

        content = indexes[root / "index.md"]
        assert "log.md" not in content
        assert "index.md" not in content
        assert "[A](a.md)" in content


# ---------------------------------------------------------------------------
# R001 conformance of generated indexes
# ---------------------------------------------------------------------------


class TestGeneratedIndexesAreR001Conformant:
    def test_validate_raises_no_r001(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "a.md", "---\ntype: Reference\ntitle: A\n---\n")
        make_md(root / "sub" / "b.md", "---\ntype: Reference\ntitle: B\n---\n")
        manifest = load_manifest(manifest_path)

        for path, content in generate_indexes(manifest).items():
            path.write_text(content, encoding="utf-8")

        errors, code = run_validate(manifest_path, [root])
        assert all(e.code != "R001" for e in errors)
        assert code == 0


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


class TestIdempotence:
    def test_generate_twice_is_identical(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "a.md", "---\ntype: Reference\ntitle: A\n---\n")
        make_md(root / "sub" / "b.md", "---\ntype: Reference\ntitle: B\n---\n")
        manifest = load_manifest(manifest_path)

        first = generate_indexes(manifest)
        second = generate_indexes(manifest)

        assert first == second


# ---------------------------------------------------------------------------
# _cmd_index — dry-run and --apply
# ---------------------------------------------------------------------------


class TestCmdIndex:
    def test_dry_run_writes_nothing(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "a.md", "---\ntype: Reference\ntitle: A\n---\n")
        parser = build_parser()
        args = parser.parse_args(["index", "--manifest", str(manifest_path)])

        assert _cmd_index(args) == 0
        assert not (root / "index.md").exists()

    def test_apply_writes_then_second_apply_writes_nothing(
        self,
        minimal_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        manifest_path, root = minimal_manifest
        make_md(root / "a.md", "---\ntype: Reference\ntitle: A\n---\n")
        parser = build_parser()

        args = parser.parse_args(
            ["index", "--manifest", str(manifest_path), "--apply"]
        )
        assert _cmd_index(args) == 0
        assert (root / "index.md").exists()
        written_first = (root / "index.md").read_text(encoding="utf-8")

        args_again = parser.parse_args(
            ["index", "--manifest", str(manifest_path), "--apply"]
        )
        assert _cmd_index(args_again) == 0
        written_second = (root / "index.md").read_text(encoding="utf-8")

        assert written_first == written_second

    def test_no_manifest_no_vault_exit_2(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["index"])
        assert _cmd_index(args) == 2

    def test_bad_manifest_exit_2(self, tmp_path: Path) -> None:
        bad_manifest = tmp_path / "bad.yaml"
        bad_manifest.write_text("okf_version: '0.1'\n", encoding="utf-8")
        parser = build_parser()
        args = parser.parse_args(["index", "--manifest", str(bad_manifest)])
        assert _cmd_index(args) == 2

    def test_vault_json_mode_applies_each_bundle(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
    ) -> None:
        import json

        import yaml

        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "a.md", "---\ntype: Reference\ntitle: A\n---\n")
        manifest_path = bundle / "okf-base.yaml"
        manifest_path.write_text(
            yaml.dump(
                {
                    "okf_version": "0.1",
                    "base": {
                        "name": "b",
                        "roots": [{"path": bundle.as_posix()}],
                        "reserved_files": {"index": "index.md", "log": "log.md"},
                    },
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        vault_path = tmp_path / "okf-vault.json"
        vault_path.write_text(
            json.dumps(
                {
                    "okf_vault_version": "0.1",
                    "name": "v",
                    "bundles": [{"path": bundle.as_posix()}],
                }
            ),
            encoding="utf-8",
        )
        parser = build_parser()
        args = parser.parse_args(
            ["index", "--vault", str(vault_path), "--apply"]
        )

        assert _cmd_index(args) == 0
        assert (bundle / "index.md").exists()

    def test_vault_json_skips_bundle_with_bad_manifest(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import json

        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "okf-base.yaml").write_text(
            "okf_version: '0.1'\n", encoding="utf-8"
        )
        vault_path = tmp_path / "okf-vault.json"
        vault_path.write_text(
            json.dumps(
                {
                    "okf_vault_version": "0.1",
                    "name": "v",
                    "bundles": [{"path": bundle.as_posix()}],
                }
            ),
            encoding="utf-8",
        )
        parser = build_parser()
        args = parser.parse_args(["index", "--vault", str(vault_path)])

        assert _cmd_index(args) == 0
        assert "Warning:" in capsys.readouterr().err
