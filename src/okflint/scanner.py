"""Shared Markdown file scanning primitives for OKF."""

from __future__ import annotations

import datetime
import fnmatch
import re
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


def _is_excluded(file: Path, root: Path, patterns: list[str]) -> bool:
    """Return True if the file matches any exclusion pattern relative to root.

    Args:
        file: Absolute path of the file to test.
        root: Root from which the relative path is computed.
        patterns: Glob patterns (fnmatch-style, supports **).

    Returns:
        True if the file should be excluded.
    """
    rel = file.relative_to(root).as_posix()
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


@beartype
def build_file_index(
    roots: list[Path],
    exclude_patterns: dict[Path, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Index all .md files under a list of roots for wikilink resolution.

    Args:
        roots: List of roots to index.
        exclude_patterns: Optional per-root exclusion globs. Files matching any
            pattern for their root are omitted from the index.

    Returns:
        Dictionary stem → list of paths relative to the first root.
    """
    index: dict[str, list[str]] = {}
    for root in roots:
        patterns = (exclude_patterns or {}).get(root, [])
        for md_file in root.rglob("*.md"):
            if patterns and _is_excluded(md_file, root, patterns):
                continue
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
        path_part, _, _fragment = target.partition("#")
        # Ignore same-file anchors (#section)
        if path_part == "":
            continue
        is_external = path_part.startswith(("http://", "https://", "ftp://"))

        if is_external:
            broken = False
        elif path_part.startswith("/"):
            # Absolute path relative to the bundle
            resolved = bundle_path / path_part.lstrip("/")
            broken = not resolved.exists()
        else:
            # Path relative to the current file
            resolved = file_path.parent / path_part
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
