"""Tests for the OKF audit module."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from okflint.audit import (
    FileReport,
    MarkdownLink,
    WikiLink,
    analyze_file,
    compute_stats,
    get_okf_status,
    run_audit,
)
from okflint.manifest import RootConfig, load_manifest
from okflint.validate import DEFAULT_RESERVED_FILES, run_validate


# ---------------------------------------------------------------------------
# get_okf_status
# ---------------------------------------------------------------------------


class TestGetOkfStatus:
    def test_none_returns_non_conformant(self) -> None:
        assert get_okf_status(None) == "non_conformant"

    def test_with_type_returns_conformant(self) -> None:
        assert get_okf_status({"type": "Reference"}) == "conformant"

    def test_without_type_returns_partial(self) -> None:
        assert get_okf_status({"title": "No type"}) == "partial"


# ---------------------------------------------------------------------------
# analyze_file
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    def test_conformant_file(
        self, tmp_path: Path, make_md: Callable[[Path, str], Path]
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        f = make_md(bundle / "doc.md", "---\ntype: Reference\n---\n# Title\n")
        report = analyze_file(f, bundle, {}, DEFAULT_RESERVED_FILES)
        assert report.path == "doc.md"
        assert report.okf_status == "conformant"
        assert not report.is_reserved
        assert report.depth == 0

    def test_reserved_index_detected(
        self, tmp_path: Path, make_md: Callable[[Path, str], Path]
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        f = make_md(bundle / "index.md", "# Index\n")
        report = analyze_file(f, bundle, {}, DEFAULT_RESERVED_FILES)
        assert report.is_reserved

    def test_non_conformant_without_frontmatter(
        self, tmp_path: Path, make_md: Callable[[Path, str], Path]
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        f = make_md(bundle / "bare.md", "# Bare content\n")
        report = analyze_file(f, bundle, {}, DEFAULT_RESERVED_FILES)
        assert report.okf_status == "non_conformant"

    def test_subdirectory_depth(
        self, tmp_path: Path, make_md: Callable[[Path, str], Path]
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        f = make_md(bundle / "sub" / "doc.md", "---\ntype: Reference\n---\n")
        report = analyze_file(f, bundle, {}, DEFAULT_RESERVED_FILES)
        assert report.depth == 1
        assert report.path == "sub/doc.md"


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------


def _make_report(
    path: str = "doc.md",
    is_reserved: bool = False,
    okf_status: str = "conformant",
    wikilinks: list | None = None,
    markdown_links: list | None = None,
    split_candidate: bool = False,
) -> FileReport:
    return FileReport(
        path=path,
        depth=0,
        lines=10,
        chars=100,
        is_reserved=is_reserved,
        okf_status=okf_status,  # type: ignore[arg-type]
        frontmatter={"type": "Reference"},
        wikilinks=wikilinks or [],
        markdown_links=markdown_links or [],
        split_candidate=split_candidate,
    )


class TestComputeStats:
    def test_empty_files(self) -> None:
        stats = compute_stats([], 0)
        assert stats["total_files"] == 0
        assert stats["total_concept_files"] == 0
        assert stats["broken_wikilinks"] == 0

    def test_counts_concept_vs_reserved(self) -> None:
        files = [
            _make_report("doc.md", is_reserved=False),
            _make_report("index.md", is_reserved=True),
        ]
        stats = compute_stats(files, 10)
        assert stats["total_files"] == 2
        assert stats["total_concept_files"] == 1
        assert stats["total_reserved_files"] == 1

    def test_counts_by_okf_status(self) -> None:
        files = [
            _make_report(okf_status="conformant"),
            _make_report(okf_status="partial"),
            _make_report(okf_status="non_conformant"),
        ]
        stats = compute_stats(files, 3)
        assert stats["by_okf_status"]["conformant"] == 1
        assert stats["by_okf_status"]["partial"] == 1
        assert stats["by_okf_status"]["non_conformant"] == 1

    def test_counts_broken_wikilinks(self) -> None:
        wl_broken = WikiLink("[[X]]", "X", None, None, None, True, False)
        wl_ok = WikiLink("[[Y]]", "Y", None, None, "Y.md", False, False)
        files = [_make_report(wikilinks=[wl_broken, wl_ok])]
        stats = compute_stats(files, 2)
        assert stats["total_wikilinks"] == 2
        assert stats["broken_wikilinks"] == 1

    def test_counts_split_candidates(self) -> None:
        files = [
            _make_report(split_candidate=True),
            _make_report(split_candidate=False),
        ]
        stats = compute_stats(files, 2)
        assert stats["split_candidates"] == 1


# ---------------------------------------------------------------------------
# run_audit (smoke test)
# ---------------------------------------------------------------------------


class TestRunAudit:
    def test_run_audit_smoke(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "doc.md", "---\ntype: Reference\n---\n# Title\n")
        make_md(bundle / "index.md", "# Index\n")
        report = run_audit(bundle, bundle)
        assert "stats" in report
        assert "files" in report
        assert report["stats"]["total_files"] == 2
        assert report["stats"]["total_concept_files"] == 1
        # Regression guard: index.md has no frontmatter, which used to
        # trigger a spurious F001 in the manifest-less audit path because
        # diagnostics were computed via check_core_concept() without ever
        # consulting is_reserved.
        assert "F001" not in report["diagnostics_summary"]["by_code"]

    def test_manifest_less_reserved_files_at_multiple_depths_no_f001(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "index.md", "# Root index\n")
        make_md(bundle / "log.md", "# Log\n\n## 2026-01-01\n\nEntry.\n")
        make_md(bundle / "sub" / "index.md", "# Sub index\n")
        report = run_audit(bundle, bundle)
        assert report["stats"]["total_reserved_files"] == 3
        assert "F001" not in report["diagnostics_summary"]["by_code"]

    def test_manifest_driven_reserved_files_parity_with_manifest_less(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        """The manifest-driven and manifest-less audit paths must agree on
        reserved files: neither should ever emit F001 for them."""
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "index.md", "# Root index\n")
        make_md(bundle / "log.md", "# Log\n\n## 2026-01-01\n\nEntry.\n")
        make_md(bundle / "sub" / "index.md", "# Sub index\n")
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text(
            "okf_version: '0.1'\n"
            "base:\n"
            "  name: test-base\n"
            "  roots:\n"
            f"    - path: '{bundle.as_posix()}'\n"
            "  reserved_files:\n"
            "    index: index.md\n"
            "    log: log.md\n",
            encoding="utf-8",
        )
        manifest = load_manifest(manifest_path)
        report = run_audit(bundle, bundle, manifest=manifest)
        assert "F001" not in report["diagnostics_summary"]["by_code"]

    def test_manifest_less_non_reserved_file_still_triggers_f001(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        """The fix must not silence F001 for genuine concept files."""
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "bare.md", "# No frontmatter\n")
        report = run_audit(bundle, bundle)
        assert report["diagnostics_summary"]["by_code"].get("F001") == 1

    def test_manifest_less_non_root_index_with_frontmatter_triggers_r001(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "sub" / "index.md", "---\ntype: Reference\n---\n# Sub index\n")
        report = run_audit(bundle, bundle)
        assert report["diagnostics_summary"]["by_code"].get("R001") == 1

    def test_manifest_less_root_index_with_only_okf_version_passes(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "index.md", "---\nokf_version: '0.1'\n---\n# Root index\n")
        report = run_audit(bundle, bundle)
        assert report["diagnostics_summary"]["by_code"] == {}


# ---------------------------------------------------------------------------
# run_audit — multi-root and backward compatibility
# ---------------------------------------------------------------------------


class TestRunAuditMultiRoot:
    def test_multi_root_report_structure(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        root1 = tmp_path / "root1"
        root1.mkdir()
        root2 = tmp_path / "root2"
        root2.mkdir()
        make_md(root1 / "a.md", "---\ntype: Reference\n---\n")
        make_md(root2 / "b.md", "---\ntype: Reference\n---\n")
        make_md(root2 / "c.md", "---\ntype: Reference\n---\n")
        report = run_audit([root1, root2], [root1, root2])
        assert "bundle_paths" in report
        assert len(report["bundle_paths"]) == 2
        assert "roots" in report
        counts = {r["path"]: r["file_count"] for r in report["roots"]}
        assert counts[root1.as_posix()] == 1
        assert counts[root2.as_posix()] == 2
        assert report["stats"]["total_files"] == 3

    def test_single_path_backward_compat(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "doc.md", "---\ntype: Reference\n---\n")
        report = run_audit(bundle, bundle)
        assert "bundle_paths" in report
        assert len(report["bundle_paths"]) == 1
        assert report["stats"]["total_files"] == 1


# ---------------------------------------------------------------------------
# run_audit — exclude_patterns
# ---------------------------------------------------------------------------


class TestRunAuditExclude:
    def test_excluded_files_absent_from_stats_and_files(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "note.md", "---\ntype: Reference\n---\n# Keep\n")
        (bundle / "src" / "pkg" / "data").mkdir(parents=True)
        make_md(
            bundle / "src" / "pkg" / "data" / "report.md",
            "---\ntype: Reference\n---\n# Excluded\n",
        )
        root_cfg = RootConfig(path=bundle, exclude_patterns=["src/**/data/**"])
        report = run_audit(root_cfg, bundle)
        file_paths = [f["path"] for f in report["files"]]
        assert "note.md" in file_paths
        assert not any("report" in p for p in file_paths)
        assert report["stats"]["total_files"] == 1

    def test_venv_excluded_from_stats(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / ".venv" / "lib").mkdir(parents=True)
        make_md(bundle / ".venv" / "lib" / "x.md", "# venv file\n")
        make_md(bundle / "real.md", "---\ntype: Reference\n---\n# Real\n")
        root_cfg = RootConfig(path=bundle, exclude_patterns=[".venv/**"])
        report = run_audit(root_cfg, bundle)
        assert report["stats"]["total_files"] == 1
        file_paths = [f["path"] for f in report["files"]]
        assert not any(".venv" in p for p in file_paths)

    def test_target_filter_restricts_scan(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        root1 = tmp_path / "root1"
        root1.mkdir()
        root2 = tmp_path / "root2"
        root2.mkdir()
        make_md(root1 / "a.md", "---\ntype: Reference\n---\n")
        make_md(root2 / "b.md", "---\ntype: Reference\n---\n")
        report = run_audit([root1, root2], [root1, root2], target_filter=root1)
        assert report["stats"]["total_files"] == 1


# ---------------------------------------------------------------------------
# run_audit — diagnostics alignment with validate (Track I)
# ---------------------------------------------------------------------------


class TestRunAuditWithManifest:
    def test_manifest_diagnostics_present_without_gating(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        manifest_path, root = profile_manifest
        manifest = load_manifest(manifest_path)
        make_md(
            root / "doc.md",
            "---\ntype: Decision\nstatut: InProgress\ncreated: 2026-01-01\n---\n"
            "# Decision\n",
        )
        report = run_audit(root, root, manifest=manifest)
        file_codes = {d["code"] for f in report["files"] for d in f["diagnostics"]}
        assert "F105" in file_codes
        assert report["diagnostics_summary"]["by_code"]["F105"] == 1
        # audit stays descriptive: it never returns an exit code
        assert "code" not in report

    def test_diagnostics_match_validate(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        manifest_path, root = profile_manifest
        manifest = load_manifest(manifest_path)
        make_md(
            root / "ok.md",
            "---\ntype: Decision\nstatut: Accepté\ncreated: 2026-01-01\n---\n"
            "# Decision OK\n",
        )
        make_md(
            root / "bad.md",
            "---\ntype: Decision\nstatut: InProgress\ncreated: 2026-01-01\n---\n"
            "# Decision Bad\n",
        )
        make_md(root / "bare.md", "# No frontmatter\n")

        audit_report = run_audit(root, root, manifest=manifest)
        audit_codes = sorted(
            (d["file"], d["code"])
            for f in audit_report["files"]
            for d in f["diagnostics"]
        )

        validate_errors, _ = run_validate(manifest_path, [root])
        validate_codes = sorted((d.file, d.code) for d in validate_errors)

        assert audit_codes == validate_codes

    def test_without_manifest_diagnostics_are_core_only(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(bundle / "bare.md", "# Bare\n")
        report = run_audit(bundle, bundle)
        codes = {d["code"] for f in report["files"] for d in f["diagnostics"]}
        assert codes == {"F001"}

    def test_diagnostics_summary_consistent_with_per_file_sum(
        self,
        profile_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        manifest_path, root = profile_manifest
        manifest = load_manifest(manifest_path)
        make_md(
            root / "bad.md",
            "---\ntype: Decision\nstatut: InProgress\ncreated: 2026-01-01\n---\n"
            "# Decision Bad\n",
        )
        make_md(root / "bare.md", "# No frontmatter\n")

        report = run_audit(root, root, manifest=manifest)
        summary = report["diagnostics_summary"]
        all_diags = [d for f in report["files"] for d in f["diagnostics"]]

        assert sum(summary["by_severity"].values()) == len(all_diags)
        assert sum(summary["by_tier"].values()) == len(all_diags)
        assert sum(summary["by_code"].values()) == len(all_diags)

    def test_split_candidate_derived_from_s202_diagnostic(
        self,
        hygiene_manifest: tuple[Path, Path],
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        manifest_path, root = hygiene_manifest
        manifest = load_manifest(manifest_path)
        make_md(
            root / "multi.md",
            "---\ntype: JournalEntry\ncreated: 2026-01-01\n---\n"
            "# Alpha\n\n"
            "This paragraph discusses cooking pasta with tomato sauce and basil "
            "leaves. The chef prepares pasta by boiling water, adding salt, and "
            "cooking the noodles until perfectly tender for dinner tonight.\n\n"
            "# Beta\n\n"
            "This paragraph discusses telescopes observing distant galaxies and "
            "stars. Astronomers use powerful telescopes to measure light from "
            "ancient galaxies across the vast universe every single night.\n",
        )
        report = run_audit(root, root, manifest=manifest)
        files = report["files"]
        assert len(files) == 1
        assert files[0]["split_candidate"]
        assert any(d["code"] == "S202" for d in files[0]["diagnostics"])
        assert report["stats"]["split_candidates"] == 1

    def test_manifest_less_audit_reports_no_split_candidates(
        self,
        tmp_path: Path,
        make_md: Callable[[Path, str], Path],
        capsys: object,
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        make_md(
            bundle / "multi.md",
            "# Alpha\n\n"
            "This paragraph discusses cooking pasta with tomato sauce and basil "
            "leaves. The chef prepares pasta by boiling water, adding salt, and "
            "cooking the noodles until perfectly tender for dinner tonight.\n\n"
            "# Beta\n\n"
            "This paragraph discusses telescopes observing distant galaxies and "
            "stars. Astronomers use powerful telescopes to measure light from "
            "ancient galaxies across the vast universe every single night.\n",
        )
        report = run_audit(bundle, bundle)
        assert report["stats"]["split_candidates"] == 0
