"""Primitives partagées de scan de fichiers Markdown OKF."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_WIKILINK_RE = re.compile(r"\[\[([^\[\]#|]+?)(?:#([^\[\]|]*?))?(?:\|([^\[\]]*?))?\]\]")
_MD_LINK_RE = re.compile(r"\[([^\[\]]*)\]\(([^()]+)\)")
_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


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


def blank_code_spans(content: str) -> str:
    """Neutralise les blocs de code fencés et les spans inline.

    Permet l'extraction de liens sans faux positifs dans les zones de code.
    Remplace le contenu des zones de code par des espaces en préservant les
    positions de caractères (numéros de ligne inchangés). Une fence non fermée
    en fin de fichier est traitée comme ouverte jusqu'à l'EOF.

    Args:
        content: Corps brut du fichier markdown (après frontmatter).

    Returns:
        Contenu avec blocs de code masqués par des espaces.
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


def build_file_index(roots: list[Path]) -> dict[str, list[str]]:
    """Indexe tous les .md d'une liste de racines pour la résolution des wikilinks.

    Args:
        roots: Liste de racines à indexer.

    Returns:
        Dictionnaire nom_sans_extension → liste de chemins relatifs à la première root.
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
