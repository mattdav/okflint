"""Semantic cohesion scoring for markdown sections (S202 calibration core).

Pure functions only: no I/O, no printing, no CLI. See scripts/calibrate_cohesion.py
for the disposable scaffolding that drives this module on real files.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from okflint.scanner import blank_code_spans, parse_frontmatter

_HEADER_LINE_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass
class Section:
    """A document section after splitting and micro-section merging."""

    title: str | None
    level: int | None
    line: int
    body: str
    token_count: int


@dataclass
class Component:
    """A connected component of sections linked by cosine similarity > tau."""

    section_indices: list[int]


@dataclass
class CohesionResult:
    """Full output of a cohesion analysis for one document."""

    sections: list[Section]
    components: list[Component]


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric boundaries, drop single characters."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= 2]


def _make_section(
    title: str | None, level: int | None, line: int, body_lines: list[str]
) -> Section:
    body = "\n".join(body_lines).strip("\n")
    return Section(
        title=title, level=level, line=line, body=body, token_count=len(tokenize(body))
    )


def split_into_sections(
    safe_body: str, title_levels: set[int] | None = None
) -> list[Section]:
    """Split a code-fence-masked body into sections at every heading line.

    Args:
        safe_body: Document body with frontmatter removed and code fences blanked.
        title_levels: Heading levels that count as section boundaries. None means
            all levels (H1-H6) are boundaries.

    Returns:
        List of Section, including a leading preamble section (title=None).
    """
    lines = safe_body.split("\n")
    sections: list[Section] = []
    current_title: str | None = None
    current_level: int | None = None
    current_line = 1
    current_lines: list[str] = []

    for i, line in enumerate(lines, start=1):
        m = _HEADER_LINE_RE.match(line)
        if m and (title_levels is None or len(m.group(1)) in title_levels):
            sections.append(
                _make_section(current_title, current_level, current_line, current_lines)
            )
            current_title = m.group(2).strip()
            current_level = len(m.group(1))
            current_line = i
            current_lines = []
            continue
        current_lines.append(line)

    sections.append(
        _make_section(current_title, current_level, current_line, current_lines)
    )
    return sections


def _absorb(sections: list[Section], index: int, target: int) -> list[Section]:
    donor = sections[index]
    receiver = sections[target]
    if index < target:
        combined_body = f"{donor.body}\n{receiver.body}".strip("\n")
    else:
        combined_body = f"{receiver.body}\n{donor.body}".strip("\n")

    merged_section = Section(
        title=receiver.title,
        level=receiver.level,
        line=receiver.line,
        body=combined_body,
        token_count=len(tokenize(combined_body)),
    )
    result = list(sections)
    result[target] = merged_section
    del result[index]
    return result


def merge_micro_sections(sections: list[Section], min_tokens: int) -> list[Section]:
    """Fuse sections under the token floor into a neighbour until none remain.

    A section below the floor is attached to the previous section, or to the
    next one if it is the first section. Nothing is discarded.

    Args:
        sections: Sections as produced by split_into_sections.
        min_tokens: Minimum token count a section's body must reach.

    Returns:
        List of Section where every entry meets the floor (unless the whole
        document is a single section below it).
    """
    merged = list(sections)
    changed = True
    while changed and len(merged) > 1:
        changed = False
        for i, sec in enumerate(merged):
            if sec.token_count >= min_tokens:
                continue
            target = 1 if i == 0 else i - 1
            merged = _absorb(merged, i, target)
            changed = True
            break
    return merged


def compute_tfidf_vectors(bodies: list[str]) -> list[dict[str, float]]:
    """Compute a TF-IDF vector per section body (stdlib only, no stopwords).

    Args:
        bodies: Section body texts, in document order.

    Returns:
        List of term -> weight dicts, one per body, in the same order.
    """
    tokenized = [tokenize(b) for b in bodies]
    n = len(tokenized)
    df: Counter[str] = Counter()
    for tokens in tokenized:
        df.update(set(tokens))

    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        tf = Counter(tokens)
        vector: dict[str, float] = {}
        for term, count in tf.items():
            idf = math.log(n / df[term])
            vector[term] = count * idf
        vectors.append(vector)
    return vectors


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_similarity_matrix(vectors: list[dict[str, float]]) -> list[list[float]]:
    """Build a symmetric cosine similarity matrix, quantized to 6 decimals."""
    n = len(vectors)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            sim = round(_cosine(vectors[i], vectors[j]), 6)
            matrix[i][j] = sim
            matrix[j][i] = sim
    return matrix


def _find(parent: list[int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: list[int], a: int, b: int) -> None:
    root_a, root_b = _find(parent, a), _find(parent, b)
    if root_a != root_b:
        parent[root_b] = root_a


def find_components(matrix: list[list[float]], tau: float) -> list[list[int]]:
    """Return connected components (as sorted index lists) linked by cos > tau."""
    n = len(matrix)
    parent = list(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] > tau:
                _union(parent, i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = _find(parent, i)
        groups.setdefault(root, []).append(i)
    return [sorted(indices) for indices in sorted(groups.values(), key=lambda g: g[0])]


def analyze_cohesion(
    content: str,
    *,
    tau: float = 0.15,
    min_tokens: int = 20,
    title_levels: set[int] | None = None,
) -> CohesionResult:
    """Run the full cohesion pipeline on one markdown file's raw content.

    Args:
        content: Full raw file content, frontmatter included.
        tau: Cosine similarity threshold above which two sections are linked.
        min_tokens: Token floor for micro-section merging.
        title_levels: Heading levels treated as section boundaries (None = all).

    Returns:
        CohesionResult with merged sections and their connected components.
    """
    _, body = parse_frontmatter(content)
    safe_body = blank_code_spans(body)
    raw_sections = split_into_sections(safe_body, title_levels)
    sections = merge_micro_sections(raw_sections, min_tokens)

    vectors = compute_tfidf_vectors([s.body for s in sections])
    matrix = build_similarity_matrix(vectors)
    groups = find_components(matrix, tau)
    components = [Component(section_indices=g) for g in groups]
    return CohesionResult(sections=sections, components=components)
