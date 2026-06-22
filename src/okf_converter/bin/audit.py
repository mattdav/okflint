"""Audit d'un bundle OKF Obsidian — inventaire et diagnostic de conformité."""

from __future__ import annotations

import dataclasses
import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

OkfStatus = Literal["conformant", "partial", "non_conformant"]

# Noms réservés OKF v0.1 (ne sont pas des concepts)
RESERVED_NAMES: set[str] = {"index.md", "log.md"}

# Seuil de lignes au-delà duquel un fichier est candidat au découpage
SPLIT_THRESHOLD: int = 100

_WIKILINK_RE = re.compile(r"\[\[([^\[\]#|]+?)(?:#([^\[\]|]*?))?(?:\|([^\[\]]*?))?\]\]")
_MD_LINK_RE = re.compile(r"\[([^\[\]]*)\]\(([^()]+)\)")
_HEADER_RE = re.compile(r"^(#{1,2})\s+(.+)$")
_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)


@dataclass
class WikiLink:
    """Représente un wikilink Obsidian [[...]] dans un fichier."""

    raw: str
    target: str
    alias: str | None
    section: str | None
    resolved_path: str | None
    broken: bool
    ambiguous: bool


@dataclass
class MarkdownLink:
    """Représente un lien markdown [text](url) dans un fichier."""

    text: str
    target: str
    is_external: bool
    broken: bool


@dataclass
class Header:
    """Représente un titre H1 ou H2 dans un fichier."""

    level: int
    text: str
    line: int


@dataclass
class FileReport:
    """Rapport d'analyse d'un fichier .md du bundle."""

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
    headers: list[Header]


def _to_json_safe(obj: Any) -> Any:
    """Convertit les types non-JSON-sérialisables issus du parsing YAML.

    Args:
        obj: Valeur arbitraire retournée par yaml.safe_load.

    Returns:
        Valeur JSON-sérialisable équivalente.
    """
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    return obj


def build_vault_index(vault_path: Path) -> dict[str, list[str]]:
    """Indexe tous les .md de la vault entière pour la résolution des wikilinks.

    Args:
        vault_path: Racine de la vault Obsidian.

    Returns:
        Dictionnaire nom_sans_extension → liste de chemins relatifs à vault_path.
    """
    index: dict[str, list[str]] = {}
    for md_file in vault_path.rglob("*.md"):
        name = md_file.stem
        rel = md_file.relative_to(vault_path).as_posix()
        if name not in index:
            index[name] = []
        index[name].append(rel)
    return index


def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Extrait le frontmatter YAML d'un fichier markdown.

    Args:
        content: Contenu complet du fichier.

    Returns:
        Tuple (frontmatter_dict, body) ou (None, content) si absent ou invalide.
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


def get_okf_status(frontmatter: dict[str, Any] | None) -> OkfStatus:
    """Détermine le statut OKF d'un concept selon son frontmatter.

    Args:
        frontmatter: Frontmatter parsé, ou None si absent.

    Returns:
        'conformant' | 'partial' | 'non_conformant'
    """
    if frontmatter is None:
        return "non_conformant"
    if frontmatter.get("type"):
        return "conformant"
    return "partial"


def extract_wikilinks(
    content: str,
    vault_index: dict[str, list[str]],
) -> list[WikiLink]:
    """Extrait et résout les wikilinks [[...]] dans le contenu.

    Args:
        content: Corps du fichier markdown.
        vault_index: Index vault (nom_sans_extension → chemins relatifs).

    Returns:
        Liste de WikiLink avec statut broken/ambiguous.
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


def extract_markdown_links(
    content: str,
    file_path: Path,
    bundle_path: Path,
) -> list[MarkdownLink]:
    """Extrait les liens markdown [text](target) et vérifie les liens internes.

    Les URLs externes (http:// / https://) ne sont pas vérifiées.

    Args:
        content: Corps du fichier markdown.
        file_path: Chemin absolu du fichier courant.
        bundle_path: Racine du bundle (pour résoudre les chemins absolus).

    Returns:
        Liste de MarkdownLink.
    """
    results: list[MarkdownLink] = []
    for m in _MD_LINK_RE.finditer(content):
        text = m.group(1)
        target = m.group(2).strip()
        # Ignorer les ancres pures (#section)
        if target.startswith("#"):
            continue
        is_external = target.startswith(("http://", "https://", "ftp://"))

        if is_external:
            broken = False
        elif target.startswith("/"):
            # Chemin absolu relatif au bundle
            resolved = bundle_path / target.lstrip("/")
            broken = not resolved.exists()
        else:
            # Chemin relatif au fichier courant
            resolved = file_path.parent / target
            broken = not resolved.exists()

        results.append(
            MarkdownLink(
                text=text, target=target, is_external=is_external, broken=broken
            )
        )
    return results


def extract_headers(content: str) -> list[Header]:
    """Extrait les titres H1 et H2 avec leur numéro de ligne dans le body.

    Args:
        content: Corps du fichier (après frontmatter).

    Returns:
        Liste de Header (niveaux 1 et 2 uniquement).
    """
    headers: list[Header] = []
    for i, line in enumerate(content.splitlines(), start=1):
        m = _HEADER_RE.match(line)
        if m:
            headers.append(
                Header(level=len(m.group(1)), text=m.group(2).strip(), line=i)
            )
    return headers


def analyze_file(
    file_path: Path,
    bundle_path: Path,
    vault_index: dict[str, list[str]],
) -> FileReport:
    """Analyse complète d'un fichier .md du bundle.

    Args:
        file_path: Chemin absolu du fichier.
        bundle_path: Racine du bundle.
        vault_index: Index vault pour résolution des wikilinks.

    Returns:
        FileReport avec tous les champs remplis.
    """
    rel_path = file_path.relative_to(bundle_path).as_posix()
    depth = len(file_path.relative_to(bundle_path).parts) - 1
    is_reserved = file_path.name.lower() in RESERVED_NAMES

    content = file_path.read_text(encoding="utf-8")
    lines = len(content.splitlines())
    chars = len(content)

    frontmatter, body = parse_frontmatter(content)
    okf_status = get_okf_status(frontmatter)

    wikilinks = extract_wikilinks(body, vault_index)
    markdown_links = extract_markdown_links(body, file_path, bundle_path)

    split_candidate = lines > SPLIT_THRESHOLD
    headers = extract_headers(body) if split_candidate else []

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
        headers=headers,
    )


def compute_stats(files: list[FileReport], vault_total: int) -> dict[str, Any]:
    """Agrège les statistiques globales du rapport.

    Seuls les fichiers non réservés sont comptés dans by_okf_status.

    Args:
        files: Liste des rapports individuels.
        vault_total: Nombre total de fichiers .md dans la vault entière.

    Returns:
        Dictionnaire de statistiques.
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


def run_audit(bundle_path: Path, vault_path: Path) -> dict[str, Any]:
    """Orchestre l'audit complet d'un bundle OKF.

    Args:
        bundle_path: Racine du bundle à auditer.
        vault_path: Racine de la vault Obsidian (pour l'index wikilinks).

    Returns:
        Rapport d'audit complet sérialisable en JSON.
    """
    print(f"🔎 Indexation de la vault : {vault_path}")
    vault_index = build_vault_index(vault_path)
    vault_total = sum(len(v) for v in vault_index.values())
    print(f"   {vault_total} fichiers .md indexés")

    print(f"📦 Scan du bundle : {bundle_path}")
    md_files = sorted(bundle_path.rglob("*.md"))
    print(f"   {len(md_files)} fichiers trouvés")

    files: list[FileReport] = []
    for md_file in md_files:
        report = analyze_file(md_file, bundle_path, vault_index)
        files.append(report)

    stats = compute_stats(files, vault_total)

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S"
        ),
        "bundle_path": bundle_path.as_posix(),
        "vault_path": vault_path.as_posix(),
        "stats": stats,
        "files": [dataclasses.asdict(f) for f in files],
    }
