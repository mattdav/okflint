"""Validation normative de fichiers Markdown OKF — exit 0 si conforme, exit 1 sinon."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from beartype import beartype

from okflint.manifest import (
    HygieneConfig,
    Manifest,
    ManifestError,
    ProfileConfig,
    TypeConfig,
    load_manifest,
)
from okflint.scanner import (
    Header,
    MarkdownLink,
    WikiLink,
    blank_code_spans,
    build_file_index,
    evaluate_split,
    extract_headers,
    extract_markdown_links,
    extract_wikilinks,
    parse_frontmatter,
)

# Pattern ISO date YYYY-MM-DD
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Re-export pour les importeurs (cli.py)
__all__ = ["Diagnostic", "ManifestError", "run_validate"]


@dataclass
class Diagnostic:
    """Erreur ou avertissement de validation OKF."""

    code: str
    tier: str  # "core" | "profile" | "hygiene"
    severity: str  # "error" | "warning"
    file: str
    message: str


# ---------------------------------------------------------------------------
# Étage 1 — Cœur OKF (toujours actif)
# ---------------------------------------------------------------------------


@beartype
def check_core_concept(
    path: str,
    frontmatter: dict[str, Any] | None,
) -> list[Diagnostic]:
    """Vérifie les règles cœur OKF sur un fichier concept.

    Args:
        path: Chemin relatif du fichier (pour les messages).
        frontmatter: Frontmatter parsé, ou None si absent/invalide.

    Returns:
        Liste de Diagnostic (F001, F002).
    """
    diags: list[Diagnostic] = []

    # F001 : frontmatter absent ou non parsable
    if frontmatter is None:
        diags.append(
            Diagnostic(
                code="F001",
                tier="core",
                severity="error",
                file=path,
                message="frontmatter absent ou non parsable",
            )
        )
        return diags  # F002 impossible sans frontmatter

    # F002 : champ type absent ou vide
    if "type" not in frontmatter or str(frontmatter["type"]).strip() == "":
        diags.append(
            Diagnostic(
                code="F002",
                tier="core",
                severity="error",
                file=path,
                message="champ `type` absent ou vide",
            )
        )

    return diags


@beartype
def check_core_reserved_index(
    path: str,
    content: str,
    is_root_index: bool,
) -> list[Diagnostic]:
    """Vérifie la règle R001 sur un fichier index.md.

    Args:
        path: Chemin relatif du fichier.
        content: Contenu brut du fichier.
        is_root_index: True si le fichier est à la racine d'un root.

    Returns:
        Liste de Diagnostic (R001).
    """
    diags: list[Diagnostic] = []
    fm, _ = parse_frontmatter(content)

    if fm is None:
        return diags  # pas de frontmatter → conforme

    # Frontmatter présent : autorisé seulement si root ET uniquement okf_version
    allowed_keys = {"okf_version"}
    has_extra_keys = bool(set(fm.keys()) - allowed_keys)

    if not is_root_index or has_extra_keys:
        diags.append(
            Diagnostic(
                code="R001",
                tier="core",
                severity="error",
                file=path,
                message=(
                    "frontmatter interdit dans index.md "
                    "(seul `okf_version` autorisé à la racine)"
                ),
            )
        )

    return diags


@beartype
def check_core_reserved_log(
    path: str,
    content: str,
) -> list[Diagnostic]:
    """Vérifie la règle R002 sur un fichier log.md.

    Args:
        path: Chemin relatif du fichier.
        content: Contenu brut du fichier.

    Returns:
        Liste de Diagnostic (R002).
    """
    diags: list[Diagnostic] = []
    _, body = parse_frontmatter(content)
    safe_body = blank_code_spans(body)
    headers = extract_headers(safe_body)

    for h in headers:
        if h.level == 2 and not re.match(r"^\d{4}-\d{2}-\d{2}$", h.text):
            diags.append(
                Diagnostic(
                    code="R002",
                    tier="core",
                    severity="error",
                    file=path,
                    message=f"heading de date non ISO dans log.md : `{h.text}`",
                )
            )

    return diags


# ---------------------------------------------------------------------------
# Étage 2 — Profil
# ---------------------------------------------------------------------------


def _resolve_type(
    val_type: str,
    profile: ProfileConfig,
) -> tuple[str | None, str | None]:
    """Résout le type déclaré vers une clé canonique du profil.

    Priorité : exact match → case-insensitive → aliases (case-insensitive).

    Args:
        val_type: Valeur du champ type dans le frontmatter.
        profile: Configuration du profil.

    Returns:
        Tuple (type_key, f106_message) où type_key est None si non trouvé.
    """
    # 1. Correspondance exacte
    if val_type in profile.types:
        return val_type, None

    # 2. Correspondance case-insensitive sur les clés
    for k in profile.types:
        if k.lower() == val_type.lower():
            return k, None

    # 3. Recherche dans les aliases (case-insensitive)
    for k, cfg in profile.types.items():
        for alias in cfg.aliases:
            if alias.lower() == val_type.lower():
                msg = (
                    f"graphie de `type` non normalisée : `{val_type}` → utiliser `{k}`"
                )
                return k, msg

    return None, None


@beartype
def check_profile(
    path: str,
    frontmatter: dict[str, Any],
    profile: ProfileConfig,
    status_field: str | None,
) -> list[Diagnostic]:
    """Vérifie les règles de profil sur un fichier concept.

    Args:
        path: Chemin relatif du fichier.
        frontmatter: Frontmatter parsé (non None).
        profile: Configuration du profil.
        status_field: Nom du champ de statut déclaré dans base (peut être None).

    Returns:
        Liste de Diagnostic (F101-F106, S101, S102).
    """
    diags: list[Diagnostic] = []
    val_type = str(frontmatter.get("type", ""))

    type_key, f106_msg = _resolve_type(val_type, profile)

    if type_key is None:
        diags.append(
            Diagnostic(
                code="F101",
                tier="profile",
                severity="error",
                file=path,
                message=f"valeur `type` hors des types déclarés : `{val_type}`",
            )
        )
        return diags  # pas de checks suivants sans type résolu

    if f106_msg is not None:
        diags.append(
            Diagnostic(
                code="F106",
                tier="profile",
                severity="error",
                file=path,
                message=f106_msg,
            )
        )

    type_cfg: TypeConfig = profile.types[type_key]

    # F102 — champs requis manquants (sauf "type" déjà vérifié)
    for req_field in type_cfg.required:
        if req_field == "type":
            continue
        if req_field not in frontmatter:
            diags.append(
                Diagnostic(
                    code="F102",
                    tier="profile",
                    severity="error",
                    file=path,
                    message=f"champ requis manquant : `{req_field}`",
                )
            )

    # F103/F104/F105 — statut
    # CRITIQUE : distinguer is False de is None
    sv = type_cfg.status_values
    sf = status_field or "statut"  # nom du champ de statut

    if sv is False:
        # statut interdit pour ce type
        if sf in frontmatter:
            diags.append(
                Diagnostic(
                    code="F103",
                    tier="profile",
                    severity="error",
                    file=path,
                    message=(
                        f"champ de statut `{sf}` présent mais interdit "
                        f"pour le type `{type_key}`"
                    ),
                )
            )
    elif isinstance(sv, list):
        # statut obligatoire et à valeur contrainte
        if sf not in frontmatter:
            diags.append(
                Diagnostic(
                    code="F104",
                    tier="profile",
                    severity="error",
                    file=path,
                    message=f"champ de statut `{sf}` requis pour le type `{type_key}`",
                )
            )
        elif frontmatter[sf] not in sv:
            diags.append(
                Diagnostic(
                    code="F105",
                    tier="profile",
                    severity="error",
                    file=path,
                    message=(
                        f"valeur de statut hors vocabulaire : "
                        f"`{sf}={frontmatter[sf]}` (valeurs : {sv})"
                    ),
                )
            )
    # sv is None → optionnel, aucune vérification

    # S101 — champ de statut mal nommé
    if status_field is not None:
        # Vérifier "status" (anglais) si status_field != "status"
        if status_field != "status" and "status" in frontmatter:
            diags.append(
                Diagnostic(
                    code="S101",
                    tier="profile",
                    severity="error",
                    file=path,
                    message=(
                        f"champ de statut mal nommé : `status`"
                        f" → utiliser `{status_field}`"
                    ),
                )
            )
        # Vérifier "statut" (français) si status_field != "statut"
        if status_field != "statut" and "statut" in frontmatter:
            diags.append(
                Diagnostic(
                    code="S101",
                    tier="profile",
                    severity="error",
                    file=path,
                    message=(
                        f"champ de statut mal nommé : `statut`"
                        f" → utiliser `{status_field}`"
                    ),
                )
            )

    # S102 — dates mal formatées
    for date_field in profile.date_fields:
        if date_field in frontmatter and frontmatter[date_field]:
            val = str(frontmatter[date_field])
            if not _ISO_DATE_RE.match(val):
                diags.append(
                    Diagnostic(
                        code="S102",
                        tier="profile",
                        severity="error",
                        file=path,
                        message=(
                            f"date mal formatée : `{date_field}={val}` "
                            f"(attendu YYYY-MM-DD)"
                        ),
                    )
                )

    return diags


# ---------------------------------------------------------------------------
# Étage 3 — Hygiène
# ---------------------------------------------------------------------------


@beartype
def check_hygiene_unknown_fields(
    path: str,
    frontmatter: dict[str, Any],
    type_cfg: TypeConfig,
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Vérifie les champs frontmatter inconnus (F201).

    Args:
        path: Chemin relatif du fichier.
        frontmatter: Frontmatter parsé.
        type_cfg: Configuration du type résolu.
        level: Niveau de contrôle (off | warn | error).

    Returns:
        Liste de Diagnostic (F201).
    """
    if level == "off":
        return []

    severity = "warning" if level == "warn" else "error"
    known_fields = set(type_cfg.required) | set(type_cfg.optional) | {"type"}
    unknown = set(frontmatter.keys()) - known_fields

    return [
        Diagnostic(
            code="F201",
            tier="hygiene",
            severity=severity,
            file=path,
            message=f"champ inconnu dans le frontmatter : `{f}`",
        )
        for f in sorted(unknown)
    ]


@beartype
def check_hygiene_links(
    path: str,
    wikilinks: list[WikiLink],
    md_links: list[MarkdownLink],
    external_refs: set[str],
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Vérifie les liens cassés ou ambigus (L001, L002, L003).

    Args:
        path: Chemin relatif du fichier.
        wikilinks: Liste de WikiLink extraits.
        md_links: Liste de MarkdownLink extraits.
        external_refs: Noms de fichiers hors-base autorisés (lowercased).
        level: Niveau de contrôle (off | warn | error).

    Returns:
        Liste de Diagnostic (L001, L002, L003).
    """
    if level == "off":
        return []

    severity = "warning" if level == "warn" else "error"
    diags: list[Diagnostic] = []

    for wl in wikilinks:
        if wl.broken and wl.target.lower() not in external_refs:
            diags.append(
                Diagnostic(
                    code="L001",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"wikilink cassé : [[{wl.target}]]",
                )
            )
        if wl.ambiguous:
            diags.append(
                Diagnostic(
                    code="L003",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"wikilink ambigu : [[{wl.target}]]",
                )
            )

    for ml in md_links:
        if ml.broken and not ml.is_external:
            diags.append(
                Diagnostic(
                    code="L002",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"lien markdown cassé : {ml.target}",
                )
            )

    return diags


@beartype
def check_hygiene_structure(
    path: str,
    headers: list[Header],
    frontmatter: dict[str, Any] | None,
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Vérifie si le fichier est candidat au découpage (S201).

    Args:
        path: Chemin relatif du fichier.
        headers: Liste des headers extraits.
        frontmatter: Frontmatter parsé ou None.
        level: Niveau de contrôle (off | warn | error).

    Returns:
        Liste de Diagnostic (S201).
    """
    if level == "off":
        return []

    severity = "warning" if level == "warn" else "error"
    split, reason, count = evaluate_split(headers, frontmatter)

    if split:
        return [
            Diagnostic(
                code="S201",
                tier="hygiene",
                severity=severity,
                file=path,
                message=f"candidat au découpage ({reason}, {count} sections)",
            )
        ]

    return []


@beartype
def check_hygiene_reserved(
    roots: list[Path],
    reserved_config: dict[str, str],
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Vérifie la présence des fichiers réservés dans chaque root (R201).

    Args:
        roots: Liste des racines de la base.
        reserved_config: Mapping nom_logique → nom_fichier.
        level: Niveau de contrôle (off | warn | error).

    Returns:
        Liste de Diagnostic (R201).
    """
    if level == "off":
        return []

    severity = "warning" if level == "warn" else "error"
    diags: list[Diagnostic] = []

    for root in roots:
        for filename in reserved_config.values():
            if not (root / filename).exists():
                diags.append(
                    Diagnostic(
                        code="R201",
                        tier="hygiene",
                        severity=severity,
                        file=filename,
                        message=f"fichier réservé absent dans {root} : {filename}",
                    )
                )

    return diags


# ---------------------------------------------------------------------------
# Orchestrateurs
# ---------------------------------------------------------------------------


@beartype
def validate_file(
    file_path: Path,
    manifest: Manifest,
    base_index: dict[str, list[str]],
) -> list[Diagnostic]:
    """Orchestre la validation complète d'un fichier markdown.

    Args:
        file_path: Chemin absolu du fichier à valider.
        manifest: Manifeste OKF chargé et validé.
        base_index: Index des fichiers de la base (nom → chemins).

    Returns:
        Liste de Diagnostic (vide si conforme).
    """
    content = file_path.read_text(encoding="utf-8")

    # Détermination de la root applicable
    applicable_root = manifest.base.roots[0]
    for root in manifest.base.roots:
        try:
            file_path.relative_to(root)
            applicable_root = root
            break
        except ValueError:
            continue

    rel = str(file_path.relative_to(applicable_root))

    reserved_idx = manifest.base.reserved_files.get("index", "index.md")
    reserved_log = manifest.base.reserved_files.get("log", "log.md")

    # Fichiers réservés : traitements spécifiques, pas de check concept
    if file_path.name == reserved_idx:
        is_root = any(file_path.parent == r for r in manifest.base.roots)
        return check_core_reserved_index(rel, content, is_root)

    if file_path.name == reserved_log:
        return check_core_reserved_log(rel, content)

    # Fichier concept
    fm, body = parse_frontmatter(content)
    diagnostics: list[Diagnostic] = []

    # Cœur OKF
    core_diags = check_core_concept(rel, fm)
    diagnostics.extend(core_diags)

    # Si F001 ou F002 → skip les étages suivants
    if any(d.code in ("F001", "F002") for d in core_diags):
        return diagnostics

    # fm est forcément non-None ici (F001 n'a pas déclenché)
    assert fm is not None

    safe_body = blank_code_spans(body)
    wikilinks = extract_wikilinks(safe_body, base_index)
    md_links = extract_markdown_links(safe_body, file_path, applicable_root)
    headers = extract_headers(safe_body)

    # Profil
    resolved_type_cfg: TypeConfig | None = None
    if manifest.profile is not None:
        profile_diags = check_profile(
            rel, fm, manifest.profile, manifest.base.status_field
        )
        diagnostics.extend(profile_diags)
        # Résoudre le type_cfg pour F201 (hygiene unknown fields)
        type_key, _ = _resolve_type(str(fm.get("type", "")), manifest.profile)
        if type_key is not None:
            resolved_type_cfg = manifest.profile.types[type_key]

    # Hygiène
    if manifest.hygiene is not None:
        hygiene: HygieneConfig = manifest.hygiene

        # Liens
        diagnostics.extend(
            check_hygiene_links(
                rel,
                wikilinks,
                md_links,
                manifest.base.external_refs,
                hygiene.broken_links,
            )
        )

        # Structure
        diagnostics.extend(
            check_hygiene_structure(rel, headers, fm, hygiene.split_candidates)
        )

        # Champs inconnus (seulement si profil ET type résolu)
        if manifest.profile is not None and resolved_type_cfg is not None:
            diagnostics.extend(
                check_hygiene_unknown_fields(
                    rel, fm, resolved_type_cfg, hygiene.unknown_fields
                )
            )

    return diagnostics


@beartype
def run_validate(
    manifest_path: Path,
    targets: list[Path],
) -> tuple[list[Diagnostic], int]:
    """Orchestre la validation OKF d'une liste de cibles.

    Args:
        manifest_path: Chemin vers le manifeste OKF YAML.
        targets: Fichiers ou dossiers à valider.

    Returns:
        Tuple (liste de diagnostics, code de sortie 0 ou 1).

    Raises:
        ManifestError: Si le manifeste est invalide ou illisible.
    """
    manifest = load_manifest(manifest_path)
    base_index = build_file_index(manifest.base.roots)

    all_diagnostics: list[Diagnostic] = []

    for target in targets:
        if target.is_dir():
            md_files: list[Path] = list(target.rglob("*.md"))
        else:
            md_files = [target]

        for md_file in md_files:
            all_diagnostics.extend(validate_file(md_file, manifest, base_index))

    # Hygiène réservée (contrôle global sur les roots)
    reserved_level: Literal["off", "warn", "error"] = (
        manifest.hygiene.reserved_files if manifest.hygiene is not None else "off"
    )
    all_diagnostics.extend(
        check_hygiene_reserved(
            manifest.base.roots,
            manifest.base.reserved_files,
            reserved_level,
        )
    )

    code = 0 if not any(d.severity == "error" for d in all_diagnostics) else 1
    return all_diagnostics, code
