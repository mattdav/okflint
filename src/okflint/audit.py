"""OKF bundle audit — inventory and conformance diagnostic."""

from __future__ import annotations

import dataclasses
import datetime
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from beartype import beartype

from okflint.scanner import (
    MarkdownLink,
    WikiLink,
    blank_code_spans,
    build_file_index,
    extract_markdown_links,
    extract_wikilinks,
    parse_frontmatter,
)

OkfStatus = Literal["conformant", "partial", "non_conformant"]

# OKF v0.1 reserved names (not concepts)
RESERVED_NAMES: set[str] = {"index.md", "log.md"}


_HEADER_RE = re.compile(r"^(#{1,2})\s+(.+)$")


@dataclass
class Header:
    """Represents an H1 or H2 heading in a file."""

    level: int
    text: str
    line: int


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
    split_reason: str | None  # "multiple_h1" | "homogeneous_h2_list"
    split_entity_count: int | None
    headers: list[Header]


# Structural section keywords (ADR, Runbook, Journal, meta-docs).
# An H2 containing one of these words/phrases is a section of a single concept.
_STRUCTURAL_H2_KEYWORDS: frozenset[str] = frozenset(
    {
        # ADR / decision
        "context",
        "options",
        "considered",
        "decision",
        "consequences",
        "alternatives",
        "appendices",
        # Runbook / procedure
        "prerequisites",
        "dependencies",
        "installation",
        "configuration",
        "usage",
        "references",
        "results",
        "actions",
        "performed",
        "pitfalls",
        "encountered",
        "remaining",
        "next steps",
        "lessons",
        "summary",
        "diagnostic",
        "symptoms",
        "links",
        "troubleshooting",
        "rollback",
        "verification",
        "history",
        "maintenance",
        # Architecture / meta-document
        "architecture",
        "navigation",
        "objectives",
        "inventory",
        # Project statuses (kanban, TODO)
        "in progress",
        "on hold",
        "upcoming",
        "resolved",
        "ideas",
    }
)

# Pattern for sequential H2s (numbered procedures, steps)
_SEQUENTIAL_H2_RE = re.compile(
    r"^(?:\d+[\s.\-—]|[Éé]tape\s|Step\s|Partie\s|Part\s|Phase\s)",
    re.IGNORECASE,
)

# Frontmatter types that indicate a non-splittable document
_NONSPLIT_TYPES: frozenset[str] = frozenset(
    {
        "journal",
        "journalentry",
        "runbook",
        "procedure",
    }
)

# H1 starting with a date → session journal (even without frontmatter type)
_DATE_H1_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _is_structural_h2(text: str) -> bool:
    """Indicate whether an H2 heading is a structural section (not a listable entity).

    Args:
        text: H2 heading text.

    Returns:
        True if the H2 is a document section (ADR, runbook, journal).
    """
    # NFC to neutralise accent encoding variants
    lower = unicodedata.normalize("NFC", text).lower()
    return any(kw in lower for kw in _STRUCTURAL_H2_KEYWORDS)


def _is_nonsplit_type(frontmatter: dict[str, Any] | None) -> bool:
    """Indicate whether the frontmatter type excludes the file from splitting.

    Args:
        frontmatter: Parsed frontmatter, or None if absent.

    Returns:
        True if the type indicates a sequential non-splittable document.
    """
    if frontmatter is None:
        return False
    raw = str(frontmatter.get("type", "")).lower().replace("-", "").replace("_", "")
    return raw in _NONSPLIT_TYPES


def _is_sequential_h2(text: str) -> bool:
    """Indicate whether an H2 heading is a sequential list element (step, part).

    Args:
        text: H2 heading text.

    Returns:
        True if the H2 is a numbered or sequentially named step.
    """
    normalized = unicodedata.normalize("NFC", text)
    return bool(_SEQUENTIAL_H2_RE.match(normalized))


def _is_session_journal(headers: list[Header]) -> bool:
    """Indicate whether the file is a session journal (H1 starts with a date).

    Detects journals without a frontmatter type via their dated H1 (YYYY-MM-DD...).

    Args:
        headers: List of headers extracted from the file.

    Returns:
        True if the file is a session journal.
    """
    h1s = [h for h in headers if h.level == 1]
    return bool(h1s) and all(_DATE_H1_RE.match(h.text) for h in h1s)


def _evaluate_split(
    headers: list[Header],
    frontmatter: dict[str, Any] | None,
) -> tuple[bool, str | None, int | None]:
    """Determine whether a file is a split candidate based on semantic criteria.

    Trigger criteria (in order):
    - multiple_h1: ≥ 2 H1 with distinct texts
    - homogeneous_h2_list: ≥ 4 H2 of which < 2 are structural and < 50% sequential

    Pre-exclusions:
    - journal/runbook/procedure frontmatter type
    - Session journal detected by dated H1
    - Duplicate H1s (same text, copy-paste anomaly)

    Args:
        headers: List of headers extracted from the file.
        frontmatter: Parsed frontmatter, or None if absent.

    Returns:
        Tuple (split_candidate, split_reason, split_entity_count).
    """
    if _is_nonsplit_type(frontmatter):
        return False, None, None

    if _is_session_journal(headers):
        return False, None, None

    h1s = [h for h in headers if h.level == 1]
    h2s = [h for h in headers if h.level == 2]

    if len(h1s) >= 2:
        if len({h.text for h in h1s}) == 1:
            # Identical H1s: copy-paste anomaly, not a split
            return False, None, None
        return True, "multiple_h1", len(h1s)

    if len(h2s) >= 4:
        structural_count = sum(1 for h in h2s if _is_structural_h2(h.text))
        sequential_count = sum(1 for h in h2s if _is_sequential_h2(h.text))
        if structural_count < 2 and sequential_count * 2 < len(h2s):
            return True, "homogeneous_h2_list", len(h2s)

    return False, None, None


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
def extract_headers(content: str) -> list[Header]:
    """Extract H1 and H2 headings with their line number in the body.

    Must receive content pre-blanked via blank_code_spans to ignore
    `#` characters inside code blocks.

    Args:
        content: File body with code blocks masked.

    Returns:
        List of Header (levels 1 and 2 only).
    """
    headers: list[Header] = []
    for i, line in enumerate(content.splitlines(), start=1):
        m = _HEADER_RE.match(line)
        if m:
            headers.append(
                Header(level=len(m.group(1)), text=m.group(2).strip(), line=i)
            )
    return headers


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

    all_headers = extract_headers(safe_body)
    split_candidate, split_reason, split_entity_count = _evaluate_split(
        all_headers, frontmatter
    )
    headers = all_headers if split_candidate else []

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
        split_candidate=split_candidate,
        split_reason=split_reason,
        split_entity_count=split_entity_count,
        headers=headers,
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
    }


@beartype
def run_audit(bundle_path: Path, vault_path: Path) -> dict[str, Any]:
    """Orchestrate the full audit of an OKF bundle.

    Args:
        bundle_path: Root of the bundle to audit.
        vault_path: Root of the Obsidian vault (for the wikilinks index).

    Returns:
        Full audit report serialisable as JSON.
    """
    print(f"🔎 Indexing vault: {vault_path}")
    vault_index = build_file_index([vault_path])
    vault_total = sum(len(v) for v in vault_index.values())
    print(f"   {vault_total} .md files indexed")

    print(f"📦 Scanning bundle: {bundle_path}")
    md_files = sorted(bundle_path.rglob("*.md"))
    print(f"   {len(md_files)} files found")

    files: list[FileReport] = []
    for md_file in md_files:
        report = analyze_file(md_file, bundle_path, vault_index)
        files.append(report)

    stats = compute_stats(files, vault_total)

    return {
        "generated_at": datetime.datetime.now(datetime.UTC).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "bundle_path": bundle_path.as_posix(),
        "vault_path": vault_path.as_posix(),
        "stats": stats,
        "files": [dataclasses.asdict(f) for f in files],
    }
