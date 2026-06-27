"""Shared Markdown file scanning primitives for OKF."""

from __future__ import annotations

import datetime
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from beartype import beartype

_WIKILINK_RE = re.compile(r"\[\[([^\[\]#|]+?)(?:#([^\[\]|]*?))?(?:\|([^\[\]]*?))?\]\]")
_MD_LINK_RE = re.compile(r"\[([^\[\]]*)\]\(([^()]+)\)")
_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_HEADER_RE = re.compile(r"^(#{1,2})\s+(.+)$")

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


@dataclass
class Header:
    """Represents an H1 or H2 heading in a file."""

    level: int
    text: str
    line: int


@dataclass
class WikiLink:
    """Represents an Obsidian wikilink [[...]] in a file."""

    raw: str
    target: str
    alias: str | None
    section: str | None
    resolved_path: str | None
    broken: bool
    ambiguous: bool


@dataclass
class MarkdownLink:
    """Represents a markdown link [text](url) in a file."""

    text: str
    target: str
    is_external: bool
    broken: bool


@beartype
def blank_code_spans(content: str) -> str:
    """Blank out fenced code blocks and inline code spans.

    Allows link extraction without false positives inside code zones.
    Replaces code zone content with spaces while preserving character
    positions (line numbers unchanged). An unclosed fence at end of file
    is treated as open until EOF.

    Args:
        content: Raw file body (after frontmatter).

    Returns:
        Content with code blocks masked by spaces.
    """
    lines = content.split("\n")
    result: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent < 4 and (stripped.startswith("```") or stripped.startswith("~~~")):
            in_fence = not in_fence
            result.append(" " * len(line))
            continue
        if in_fence:
            result.append(" " * len(line))
        else:
            result.append(_INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), line))
    return "\n".join(result)


def _to_json_safe(obj: Any) -> Any:
    """Convert non-JSON-serialisable types from YAML parsing.

    Args:
        obj: Arbitrary value returned by yaml.safe_load.

    Returns:
        Equivalent JSON-serialisable value.
    """
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    return obj


@beartype
def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Extract the YAML frontmatter from a markdown file.

    Args:
        content: Full file content.

    Returns:
        Tuple (frontmatter_dict, body) or (None, content) if absent or invalid.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None, content
    try:
        fm = yaml.safe_load(match.group(1))
        if not isinstance(fm, dict):
            return None, content
        body = content[match.end() :]
        return _to_json_safe(fm), body
    except yaml.YAMLError:
        return None, content


@beartype
def build_file_index(roots: list[Path]) -> dict[str, list[str]]:
    """Index all .md files under a list of roots for wikilink resolution.

    Args:
        roots: List of roots to index.

    Returns:
        Dictionary stem → list of paths relative to the first root.
    """
    index: dict[str, list[str]] = {}
    for root in roots:
        for md_file in root.rglob("*.md"):
            name = md_file.stem
            rel = md_file.relative_to(root).as_posix()
            if name not in index:
                index[name] = []
            index[name].append(rel)
    return index


@beartype
def extract_wikilinks(
    content: str,
    vault_index: dict[str, list[str]],
) -> list[WikiLink]:
    """Extract and resolve [[...]] wikilinks in the content.

    Args:
        content: Markdown file body.
        vault_index: Vault index (stem → relative paths).

    Returns:
        List of WikiLink with broken/ambiguous status.
    """
    results: list[WikiLink] = []
    for m in _WIKILINK_RE.finditer(content):
        target = m.group(1).strip()
        section = m.group(2).strip() if m.group(2) is not None else None
        alias = m.group(3).strip() if m.group(3) is not None else None

        candidates = vault_index.get(target, [])
        broken = len(candidates) == 0
        ambiguous = len(candidates) > 1
        resolved_path = candidates[0] if candidates else None

        results.append(
            WikiLink(
                raw=m.group(0),
                target=target,
                alias=alias,
                section=section,
                resolved_path=resolved_path,
                broken=broken,
                ambiguous=ambiguous,
            )
        )
    return results


@beartype
def extract_markdown_links(
    content: str,
    file_path: Path,
    bundle_path: Path,
) -> list[MarkdownLink]:
    """Extract [text](target) markdown links and verify internal links.

    External URLs (http:// / https://) are not checked.

    Args:
        content: Markdown file body.
        file_path: Absolute path of the current file.
        bundle_path: Bundle root (for resolving absolute paths).

    Returns:
        List of MarkdownLink.
    """
    results: list[MarkdownLink] = []
    for m in _MD_LINK_RE.finditer(content):
        text = m.group(1)
        target = m.group(2).strip()
        # Ignore pure anchors (#section)
        if target.startswith("#"):
            continue
        is_external = target.startswith(("http://", "https://", "ftp://"))

        if is_external:
            broken = False
        elif target.startswith("/"):
            # Absolute path relative to the bundle
            resolved = bundle_path / target.lstrip("/")
            broken = not resolved.exists()
        else:
            # Path relative to the current file
            resolved = file_path.parent / target
            broken = not resolved.exists()

        results.append(
            MarkdownLink(
                text=text, target=target, is_external=is_external, broken=broken
            )
        )
    return results


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


@beartype
def evaluate_split(
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
