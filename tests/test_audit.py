"""Tests for the OKF audit module."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from okflint.audit import (
    FileReport,
    Header,
    MarkdownLink,
    WikiLink,
    _evaluate_split,
    _is_nonsplit_type,
    _is_sequential_h2,
    _is_session_journal,
    _is_structural_h2,
    analyze_file,
    compute_stats,
    extract_headers,
    get_okf_status,
    run_audit,
)


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
# _is_structural_h2
# ---------------------------------------------------------------------------


class TestIsStructuralH2:
    def test_structural_keyword_detected(self) -> None:
        assert _is_structural_h2("Context")
        assert _is_structural_h2("Decision")
        assert _is_structural_h2("Prerequisites")

    def test_non_structural_h2(self) -> None:
        assert not _is_structural_h2("My Alpha Service")
        assert not _is_structural_h2("Kubernetes Project")


# ---------------------------------------------------------------------------
# _is_nonsplit_type
# ---------------------------------------------------------------------------


class TestIsNonsplitType:
    def test_procedure_type_excluded(self) -> None:
        assert _is_nonsplit_type({"type": "Procedure"})
        assert _is_nonsplit_type({"type": "JournalEntry"})

    def test_unknown_type_not_excluded(self) -> None:
        assert not _is_nonsplit_type({"type": "Reference"})

    def test_none_frontmatter_not_excluded(self) -> None:
        assert not _is_nonsplit_type(None)


# ---------------------------------------------------------------------------
# _is_sequential_h2
# ---------------------------------------------------------------------------


class TestIsSequentialH2:
    def test_numbered_step_is_sequential(self) -> None:
        assert _is_sequential_h2("1. Installation")
        assert _is_sequential_h2("2 - Configuration")

    def test_step_prefix_is_sequential(self) -> None:
        assert _is_sequential_h2("Step 1: init")

    def test_regular_h2_not_sequential(self) -> None:
        assert not _is_sequential_h2("My Service")
        assert not _is_sequential_h2("General Overview")


# ---------------------------------------------------------------------------
# _is_session_journal
# ---------------------------------------------------------------------------


class TestIsSessionJournal:
    def test_dated_h1_is_journal(self) -> None:
        headers = [Header(1, "2026-05-01 Session", 1)]
        assert _is_session_journal(headers)

    def test_non_dated_h1_not_journal(self) -> None:
        headers = [Header(1, "Introduction", 1)]
        assert not _is_session_journal(headers)

    def test_empty_headers_not_journal(self) -> None:
        assert not _is_session_journal([])


# ---------------------------------------------------------------------------
# extract_headers (local version in audit.py)
# ---------------------------------------------------------------------------


class TestExtractHeadersAudit:
    def test_extracts_h1_and_h2(self) -> None:
        content = "# Title\n## Section\n### Ignored\n"
        headers = extract_headers(content)
        assert len(headers) == 2
        assert headers[0].level == 1
        assert headers[1].level == 2


# ---------------------------------------------------------------------------
# _evaluate_split
# ---------------------------------------------------------------------------


class TestEvaluateSplitAudit:
    def test_multiple_h1_triggers(self) -> None:
        headers = [Header(1, "Alpha", 1), Header(1, "Beta", 2)]
        split, reason, count = _evaluate_split(headers, None)
        assert split
        assert reason == "multiple_h1"

    def test_homogeneous_h2_triggers(self) -> None:
        headers = [
            Header(2, "Alpha", 1),
            Header(2, "Beta", 2),
            Header(2, "Gamma", 3),
            Header(2, "Delta", 4),
        ]
        split, reason, _ = _evaluate_split(headers, None)
        assert split
        assert reason == "homogeneous_h2_list"

    def test_nonsplit_type_excluded(self) -> None:
        headers = [Header(1, "A", 1), Header(1, "B", 2)]
        split, _, _ = _evaluate_split(headers, {"type": "Procedure"})
        assert not split

    def test_session_journal_excluded(self) -> None:
        headers = [
            Header(1, "2026-05-01 Session", 1),
            Header(1, "2026-05-02 Session", 2),
        ]
        split, _, _ = _evaluate_split(headers, None)
        assert not split

    def test_duplicate_h1_excluded(self) -> None:
        headers = [Header(1, "Same", 1), Header(1, "Same", 2)]
        split, _, _ = _evaluate_split(headers, None)
        assert not split

    def test_too_few_h2_no_split(self) -> None:
        headers = [Header(2, "A", 1), Header(2, "B", 2)]
        split, _, _ = _evaluate_split(headers, None)
        assert not split


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
        report = analyze_file(f, bundle, {})
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
        report = analyze_file(f, bundle, {})
        assert report.is_reserved

    def test_non_conformant_without_frontmatter(
        self, tmp_path: Path, make_md: Callable[[Path, str], Path]
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        f = make_md(bundle / "bare.md", "# Bare content\n")
        report = analyze_file(f, bundle, {})
        assert report.okf_status == "non_conformant"

    def test_split_candidate_detected(
        self, tmp_path: Path, make_md: Callable[[Path, str], Path]
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        content = "# Alpha\n\n# Beta\n"
        f = make_md(bundle / "multi.md", content)
        report = analyze_file(f, bundle, {})
        assert report.split_candidate
        assert report.split_reason == "multiple_h1"

    def test_subdirectory_depth(
        self, tmp_path: Path, make_md: Callable[[Path, str], Path]
    ) -> None:
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        f = make_md(bundle / "sub" / "doc.md", "---\ntype: Reference\n---\n")
        report = analyze_file(f, bundle, {})
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
        split_reason=None,
        split_entity_count=None,
        headers=[],
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
