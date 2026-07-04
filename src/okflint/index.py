"""OKF §6 index.md generation.

Pure computation only: no file is written here. ``cli.py`` owns the
dry-run/diff/write orchestration (see ``okflint index``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from beartype import beartype

from okflint.manifest import Manifest
from okflint.scanner import _is_excluded, parse_frontmatter


@dataclass
class IndexEntry:
    """A single concept file to list in an index.md."""

    filename: str
    title: str
    description: str | None


@beartype
def build_index_content(
    dir_path: Path,
    entries: list[IndexEntry],
    subdirs: list[str],
) -> str:
    """Build the OKF §6 markdown body of an index.md for one directory.

    No frontmatter is emitted (safe default with respect to R001).
    Sub-directories are listed before files, both in case-insensitive
    alphabetical order.

    Args:
        dir_path: Directory this index.md belongs to (kept for signature
            symmetry with ``generate_indexes``; the content only depends
            on ``entries``/``subdirs``).
        entries: Concept files to list.
        subdirs: Names of sub-directories that own their own index.md.

    Returns:
        The markdown body (no frontmatter).
    """
    del dir_path  # content is fully determined by entries/subdirs
    lines: list[str] = [
        f"- [{name}/]({name}/index.md)" for name in sorted(subdirs, key=str.lower)
    ]
    for entry in sorted(entries, key=lambda e: e.filename.lower()):
        if entry.description:
            lines.append(f"- [{entry.title}]({entry.filename}) — {entry.description}")
        else:
            lines.append(f"- [{entry.title}]({entry.filename})")

    return "\n".join(lines) + ("\n" if lines else "")


@beartype
def generate_indexes(manifest: Manifest) -> dict[Path, str]:
    """Compute the expected index.md content for every directory in the base.

    Walks every manifest root, respecting ``exclude_patterns`` and skipping
    the reserved index/log files. One entry is produced per directory that
    contains at least one (non-excluded) ``.md`` file, directly or in a
    sub-directory. Performs no write.

    Args:
        manifest: Loaded and validated OKF manifest.

    Returns:
        Mapping from each directory's expected index.md path to its
        expected content.
    """
    index_name = manifest.base.reserved_files.get("index", "index.md")
    log_name = manifest.base.reserved_files.get("log", "log.md")
    reserved = {index_name, log_name}

    result: dict[Path, str] = {}

    for root_cfg in manifest.base.roots:
        root = root_cfg.path
        patterns = root_cfg.exclude_patterns

        dirs: set[Path] = {root}
        for md_file in root.rglob("*.md"):
            if patterns and _is_excluded(md_file, root, patterns):
                continue
            current = md_file.parent
            while True:
                dirs.add(current)
                if current == root:
                    break
                current = current.parent

        for d in dirs:
            entries: list[IndexEntry] = []
            subdirs: list[str] = []

            for child in d.iterdir():
                if child.is_dir():
                    if child in dirs:
                        subdirs.append(child.name)
                    continue
                if child.suffix != ".md" or child.name in reserved:
                    continue
                if patterns and _is_excluded(child, root, patterns):
                    continue
                content = child.read_text(encoding="utf-8")
                fm, _ = parse_frontmatter(content)
                title = str(fm["title"]) if fm and fm.get("title") else child.stem
                description = (
                    str(fm["description"]) if fm and fm.get("description") else None
                )
                entries.append(
                    IndexEntry(
                        filename=child.name, title=title, description=description
                    )
                )

            result[d / index_name] = build_index_content(d, entries, subdirs)

    return result
