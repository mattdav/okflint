"""Audit d'un bundle OKF Obsidian — inventaire et diagnostic de conformité."""

from __future__ import annotations

import dataclasses
import datetime
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from okf_converter.bin.scanner import (
    MarkdownLink,
    WikiLink,
    blank_code_spans,
    build_file_index,
    extract_markdown_links,
    extract_wikilinks,
    parse_frontmatter,
)

OkfStatus = Literal["conformant", "partial", "non_conformant"]

# Noms réservés OKF v0.1 (ne sont pas des concepts)
RESERVED_NAMES: set[str] = {"index.md", "log.md"}


_HEADER_RE = re.compile(r"^(#{1,2})\s+(.+)$")


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
    split_reason: str | None  # "multiple_h1" | "homogeneous_h2_list"
    split_entity_count: int | None
    headers: list[Header]


# Mots-clés de sections structurelles (ADR, Runbook, Journal, meta-docs)
# Un H2 contenant l'un de ces mots/phrases est une section d'un concept unique
_STRUCTURAL_H2_KEYWORDS: frozenset[str] = frozenset(
    {
        # ADR / décision
        "contexte",
        "options",
        "considérées",
        "décision",
        "conséquences",
        "alternatives",
        "annexes",
        # Runbook / procédure
        "prérequis",
        "dépendances",
        "installation",
        "configuration",
        "utilisation",
        "références",
        "résultats",
        "actions",
        "réalisées",
        "pièges",
        "rencontrés",
        "reste",
        "suite",
        "leçons",
        "bilan",
        "diagnostic",
        "symptômes",
        "liens",
        "troubleshooting",
        "rollback",
        "vérification",
        "historique",
        "maintenance",
        # Architecture / meta-document
        "architecture",
        "navigation",
        "objectifs",
        "inventaire",
        # Statuts de projet (kanban, TODO)
        "en cours",
        "en attente",
        "à venir",
        "résolu",
        "idées",
    }
)

# Pattern de H2 séquentiels (procédures numérotées, étapes)
_SEQUENTIAL_H2_RE = re.compile(
    r"^(?:\d+[\s.\-—]|[Éé]tape\s|Step\s|Partie\s|Part\s|Phase\s)",
    re.IGNORECASE,
)

# Types frontmatter qui indiquent un document non-découpable
_NONSPLIT_TYPES: frozenset[str] = frozenset(
    {
        "journal",
        "journalentry",
        "runbook",
        "procedure",
    }
)

# H1 commençant par une date → journal de session (même sans type frontmatter)
_DATE_H1_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _is_structural_h2(text: str) -> bool:
    """Indique si un titre H2 est une section structurelle (pas une entité listable).

    Args:
        text: Texte du titre H2.

    Returns:
        True si le H2 est une section de document (ADR, runbook, journal).
    """
    # NFC pour neutraliser les variantes d'encodage des accents
    lower = unicodedata.normalize("NFC", text).lower()
    return any(kw in lower for kw in _STRUCTURAL_H2_KEYWORDS)


def _is_nonsplit_type(frontmatter: dict[str, Any] | None) -> bool:
    """Indique si le type frontmatter exclut le fichier du découpage.

    Args:
        frontmatter: Frontmatter parsé, ou None si absent.

    Returns:
        True si le type indique un document séquentiel non-découpable.
    """
    if frontmatter is None:
        return False
    raw = str(frontmatter.get("type", "")).lower().replace("-", "").replace("_", "")
    return raw in _NONSPLIT_TYPES


def _is_sequential_h2(text: str) -> bool:
    """Indique si un titre H2 est un élément de liste séquentielle (étape, partie).

    Args:
        text: Texte du titre H2.

    Returns:
        True si le H2 est une étape numérotée ou nommée séquentiellement.
    """
    normalized = unicodedata.normalize("NFC", text)
    return bool(_SEQUENTIAL_H2_RE.match(normalized))


def _is_session_journal(headers: list[Header]) -> bool:
    """Indique si le fichier est un journal de session (H1 commence par une date).

    Détecte les journaux sans type frontmatter via leur H1 daté (YYYY-MM-DD...).

    Args:
        headers: Liste de headers extraits du fichier.

    Returns:
        True si le fichier est un journal de session.
    """
    h1s = [h for h in headers if h.level == 1]
    return bool(h1s) and all(_DATE_H1_RE.match(h.text) for h in h1s)


def _evaluate_split(
    headers: list[Header],
    frontmatter: dict[str, Any] | None,
) -> tuple[bool, str | None, int | None]:
    """Détermine si un fichier est candidat au découpage selon des critères sémantiques.

    Critères de déclenchement (dans l'ordre) :
    - multiple_h1 : ≥ 2 H1 avec des textes distincts
    - homogeneous_h2_list : ≥ 4 H2 dont < 2 sont structurels et < 50% séquentiels

    Exclusions préalables :
    - Type frontmatter journal/runbook/procedure
    - Journal de session détecté par H1 daté
    - H1 dupliqués (même texte, anomalie de copier-coller)

    Args:
        headers: Liste des headers extraits du fichier.
        frontmatter: Frontmatter parsé, ou None si absent.

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
            # H1 identiques : anomalie de copier-coller, pas un découpage
            return False, None, None
        return True, "multiple_h1", len(h1s)

    if len(h2s) >= 4:
        structural_count = sum(1 for h in h2s if _is_structural_h2(h.text))
        sequential_count = sum(1 for h in h2s if _is_sequential_h2(h.text))
        if structural_count < 2 and sequential_count * 2 < len(h2s):
            return True, "homogeneous_h2_list", len(h2s)

    return False, None, None


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


def extract_headers(content: str) -> list[Header]:
    """Extrait les titres H1 et H2 avec leur numéro de ligne dans le body.

    Doit recevoir un contenu pré-blanqué via blank_code_spans pour ignorer
    les `#` dans les blocs de code.

    Args:
        content: Corps du fichier avec blocs de code masqués.

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
    vault_index = build_file_index([vault_path])
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


def main() -> None:
    """Point d'entrée CLI : okf-audit."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Audit OKF d'une base documentaire.")
    parser.add_argument(
        "--bundle",
        default=str(Path(r"C:\Users\matth\Nextcloud\Obsidian-Vault\Home Lab")),
    )
    parser.add_argument(
        "--vault",
        default=str(Path(r"C:\Users\matth\Nextcloud\Obsidian-Vault")),
    )
    parser.add_argument(
        "--apply", action="store_true", help="Écrit le rapport JSON dans outputs/"
    )
    args = parser.parse_args()
    bundle_path = Path(args.bundle)
    vault_path = Path(args.vault)
    report = run_audit(bundle_path, vault_path)
    stats = report["stats"]
    n_concepts = stats["total_concept_files"]
    print(f"Fichiers : {stats['total_files']} ({n_concepts} concepts)")
    print(f"Statut OKF : {stats['by_okf_status']}")
    wikilinks_broken = stats["broken_wikilinks"]
    print(f"Wikilinks  : {stats['total_wikilinks']} dont {wikilinks_broken} cassés")
    md_broken = stats["broken_markdown_links"]
    print(f"Liens MD   : {stats['total_markdown_links']} dont {md_broken} cassés")
    print(f"Candidats découpe : {stats['split_candidates']}")
    if args.apply:
        from datetime import date

        outputs_dir = Path("outputs")
        outputs_dir.mkdir(exist_ok=True)
        today = date.today().strftime("%Y-%m-%d")
        v = 1
        while (outputs_dir / f"{today}_audit_v{v}.json").exists():
            v += 1
        out = outputs_dir / f"{today}_audit_v{v}.json"
        out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Rapport : {out}")
    else:
        print("(dry-run — relancer avec --apply pour écrire le rapport JSON)")
    sys.exit(0)


if __name__ == "__main__":
    main()
