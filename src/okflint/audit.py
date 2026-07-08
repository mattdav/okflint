"""OKF bundle audit — inventory and conformance diagnostic."""

from __future__ import annotations

import dataclasses
import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from beartype import beartype

from okflint.manifest import Manifest, RootConfig
from okflint.scanner import (
    MarkdownLink,
    WikiLink,
    _is_excluded,
    blank_code_spans,
    build_file_index,
    extract_markdown_links,
    extract_wikilinks,
    parse_frontmatter,
)
from okflint.validate import Diagnostic, check_core_concept, validate_file

OkfStatus = Literal["conformant", "partial", "non_conformant"]

# OKF v0.1 reserved names (not concepts)
RESERVED_NAMES: set[str] = {"index.md", "log.md"}


@dataclass
class FileReport:
    """Analysis report for a .md file in the bundle."""

    path: str
    depth: int
    lines: int
    chars: int
    is_reserved: bool
    okf_status: OkfStatus
    frontmatter: dict[str, Any] | None
    wikilinks: list[WikiLink]
    markdown_links: list[MarkdownLink]
    split_candidate: bool
    diagnostics: list[Diagnostic] = dataclasses.field(default_factory=list)


@beartype
def get_okf_status(frontmatter: dict[str, Any] | None) -> OkfStatus:
    """Determine the OKF status of a concept from its frontmatter.

    Args:
        frontmatter: Parsed frontmatter, or None if absent.

    Returns:
        'conformant' | 'partial' | 'non_conformant'
    """
    if frontmatter is None:
        return "non_conformant"
    if frontmatter.get("type"):
        return "conformant"
    return "partial"


@beartype
def analyze_file(
    file_path: Path,
    bundle_path: Path,
    vault_index: dict[str, list[str]],
) -> FileReport:
    """Full analysis of a .md file in the bundle.

    Args:
        file_path: Absolute path of the file.
        bundle_path: Bundle root.
        vault_index: Vault index for wikilink resolution.

    Returns:
        FileReport with all fields populated.
    """
    rel_path = file_path.relative_to(bundle_path).as_posix()
    depth = len(file_path.relative_to(bundle_path).parts) - 1
    is_reserved = file_path.name.lower() in RESERVED_NAMES

    content = file_path.read_text(encoding="utf-8")
    lines = len(content.splitlines())
    chars = len(content)

    frontmatter, body = parse_frontmatter(content)
    okf_status = get_okf_status(frontmatter)

    safe_body = blank_code_spans(body)
    wikilinks = extract_wikilinks(safe_body, vault_index)
    markdown_links = extract_markdown_links(safe_body, file_path, bundle_path)

    return FileReport(
        path=rel_path,
        depth=depth,
        lines=lines,
        chars=chars,
        is_reserved=is_reserved,
        okf_status=okf_status,
        frontmatter=frontmatter,
        wikilinks=wikilinks,
        markdown_links=markdown_links,
        # Overwritten in run_audit once diagnostics are known (S202 is
        # gated by a manifest and derived from the emitted diagnostics).
        split_candidate=False,
    )


@beartype
def compute_stats(files: list[FileReport], vault_total: int) -> dict[str, Any]:
    """Aggregate global statistics for the report.

    Only non-reserved files are counted in by_okf_status.

    Args:
        files: List of individual file reports.
        vault_total: Total number of .md files in the entire vault.

    Returns:
        Statistics dictionary.
    """
    concept_files = [f for f in files if not f.is_reserved]

    by_status: dict[str, int] = {"conformant": 0, "partial": 0, "non_conformant": 0}
    for f in concept_files:
        by_status[f.okf_status] += 1

    total_wikilinks = sum(len(f.wikilinks) for f in files)
    broken_wikilinks = sum(1 for f in files for w in f.wikilinks if w.broken)
    ambiguous_wikilinks = sum(1 for f in files for w in f.wikilinks if w.ambiguous)
    total_md_links = sum(len(f.markdown_links) for f in files)
    broken_md_links = sum(1 for f in files for ml in f.markdown_links if ml.broken)
    split_candidates = sum(1 for f in files if f.split_candidate)
    total_lines = sum(f.lines for f in files)
    total_chars = sum(f.chars for f in files)

    by_severity: dict[str, int] = {"error": 0, "warning": 0}
    by_tier: dict[str, int] = {"core": 0, "profile": 0, "hygiene": 0}
    by_code: dict[str, int] = {}
    for f in files:
        for d in f.diagnostics:
            by_severity[d.severity] = by_severity.get(d.severity, 0) + 1
            by_tier[d.tier] = by_tier.get(d.tier, 0) + 1
            by_code[d.code] = by_code.get(d.code, 0) + 1

    return {
        "total_files": len(files),
        "total_concept_files": len(concept_files),
        "total_reserved_files": len(files) - len(concept_files),
        "total_lines": total_lines,
        "total_chars": total_chars,
        "by_okf_status": by_status,
        "total_wikilinks": total_wikilinks,
        "broken_wikilinks": broken_wikilinks,
        "ambiguous_wikilinks": ambiguous_wikilinks,
        "total_markdown_links": total_md_links,
        "broken_markdown_links": broken_md_links,
        "split_candidates": split_candidates,
        "vault_total_files": vault_total,
        "diagnostics_summary": {
            "by_severity": by_severity,
            "by_tier": by_tier,
            "by_code": by_code,
        },
    }


@beartype
def run_audit(
    bundle_paths: Sequence[RootConfig | Path] | RootConfig | Path,
    vault_paths: list[Path] | Path,
    *,
    target_filter: Path | None = None,
    vault_index: dict[str, list[str]] | None = None,
    manifest: Manifest | None = None,
) -> dict[str, Any]:
    """Orchestrate the full audit of one or more OKF bundle roots.

    Accepts RootConfig objects (with exclusion patterns), plain Paths, or a
    mix thereof. Single-value forms are accepted for backward compatibility.

    When ``vault_index`` is provided it is reused directly and ``vault_paths``
    is ignored, allowing the caller to build the index union once for a whole
    vault and then call ``run_audit`` per-bundle without rebuilding.

    Args:
        bundle_paths: Root(s) of the bundle(s) to audit. RootConfig carries
            per-root exclusion patterns; plain Path implies no exclusions.
        vault_paths: Root(s) of the Obsidian vault(s) (for the wikilinks index).
            Ignored when ``vault_index`` is supplied.
        target_filter: If set, restrict scanning to files under this path.
            Used when --bundle is combined with --manifest as a sub-filter.
        vault_index: Pre-built file index (stem → list of relative paths).
            When provided, vault indexing is skipped entirely.
        manifest: When provided, each file is validated through the same
            engine as ``validate`` (core + profile + hygiene diagnostics).
            When None, diagnostics are core-only (F001/F002).

    Returns:
        Full audit report serialisable as JSON.
    """
    # Normalise bundle_paths to list[RootConfig]
    _bundle_roots: list[RootConfig]
    if isinstance(bundle_paths, RootConfig):
        _bundle_roots = [bundle_paths]
    elif isinstance(bundle_paths, Path):
        _bundle_roots = [RootConfig(path=bundle_paths, exclude_patterns=[])]
    else:
        _bundle_roots = [
            p if isinstance(p, RootConfig) else RootConfig(path=p, exclude_patterns=[])
            for p in bundle_paths
        ]

    _vault_paths: list[Path] = (
        [vault_paths] if isinstance(vault_paths, Path) else list(vault_paths)
    )

    _vault_index: dict[str, list[str]]
    if vault_index is None:
        n_vault = len(_vault_paths)
        vault_label = f"{n_vault} root{'s' if n_vault > 1 else ''}"
        print(f"🔎 Indexing vault: {vault_label}")
        _vault_index = build_file_index(_vault_paths)
        vault_total = sum(len(v) for v in _vault_index.values())
        print(f"   {vault_total} .md files indexed")
    else:
        _vault_index = vault_index
        vault_total = sum(len(v) for v in _vault_index.values())

    n_bundle = len(_bundle_roots)
    bundle_label = f"{n_bundle} root{'s' if n_bundle > 1 else ''}"
    print(f"📦 Scanning bundle: {bundle_label}")

    # Collect (file, its_bundle_root) pairs across all roots, respecting exclusions
    all_md_files: list[tuple[Path, Path]] = []
    for root_cfg in _bundle_roots:
        patterns = root_cfg.exclude_patterns
        for md_file in sorted(root_cfg.path.rglob("*.md")):
            if patterns and _is_excluded(md_file, root_cfg.path, patterns):
                continue
            if target_filter is None or md_file.is_relative_to(target_filter):
                all_md_files.append((md_file, root_cfg.path))

    print(f"   {len(all_md_files)} files found")

    files: list[FileReport] = []
    for md_file, bundle_root in all_md_files:
        report = analyze_file(md_file, bundle_root, _vault_index)
        if manifest is not None:
            report.diagnostics = validate_file(md_file, manifest, _vault_index)
        else:
            report.diagnostics = check_core_concept(report.path, report.frontmatter)
        report.split_candidate = any(d.code == "S202" for d in report.diagnostics)
        files.append(report)

    stats = compute_stats(files, vault_total)
    diagnostics_summary = stats.pop("diagnostics_summary")

    # Per-root file counts for CI consumers
    root_counts: dict[str, int] = {r.path.as_posix(): 0 for r in _bundle_roots}
    for _, bundle_root in all_md_files:
        root_counts[bundle_root.as_posix()] += 1
    roots_info = [
        {"path": path_str, "file_count": count}
        for path_str, count in root_counts.items()
    ]

    return {
        "generated_at": datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "bundle_paths": [r.path.as_posix() for r in _bundle_roots],
        "vault_paths": [p.as_posix() for p in _vault_paths],
        "roots": roots_info,
        "stats": stats,
        "diagnostics_summary": diagnostics_summary,
        "files": [dataclasses.asdict(f) for f in files],
    }
