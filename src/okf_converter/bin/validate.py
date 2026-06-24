"""Validation normative de fichiers Markdown OKF — exit 0 si conforme, exit 1 sinon."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from okf_converter.bin.scanner import (
    MarkdownLink,
    WikiLink,
    blank_code_spans,
    build_file_index,
    extract_markdown_links,
    extract_wikilinks,
    parse_frontmatter,
)

# Pattern ISO date YYYY-MM-DD
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class ValidationError:
    """Erreur ou avertissement de validation OKF."""

    file: str
    family: str  # "frontmatter" | "links" | "reserved"
    severity: str  # "error" | "warning"
    message: str


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Charge et valide la structure minimale d'un manifeste OKF YAML.

    Args:
        manifest_path: Chemin vers le fichier YAML du manifeste.

    Returns:
        Dictionnaire du manifeste chargé.

    Raises:
        SystemExit: Si le fichier est illisible ou si les clés obligatoires sont
            absentes.
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"Erreur lecture manifeste {manifest_path} : {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(
            f"Manifeste invalide : {manifest_path} n'est pas un mapping YAML."
        )

    for key in ("base", "types"):
        if key not in data:
            raise SystemExit(
                f"Manifeste invalide : clé '{key}' absente dans {manifest_path}."
            )

    # isinstance(data, dict) garanti par les vérifications ci-dessus
    result: dict[str, Any] = data
    return result


def validate_frontmatter(
    path: str,
    frontmatter: dict[str, Any] | None,
    types_config: dict[str, Any],
) -> list[ValidationError]:
    """Valide le frontmatter d'un fichier selon la configuration des types OKF.

    Args:
        path: Chemin relatif du fichier (pour les messages d'erreur).
        frontmatter: Frontmatter parsé, ou None si absent.
        types_config: Configuration des types depuis le manifeste.

    Returns:
        Liste de ValidationError (vide si conforme).
    """
    errors: list[ValidationError] = []

    def err(message: str) -> ValidationError:
        return ValidationError(
            file=path, family="frontmatter", severity="error", message=message
        )

    def warn(message: str) -> ValidationError:
        return ValidationError(
            file=path, family="frontmatter", severity="warning", message=message
        )

    # Règle 1 : frontmatter absent
    if frontmatter is None:
        errors.append(err("frontmatter absent"))
        return errors

    # Règle 2 : champ `type` manquant
    if "type" not in frontmatter:
        errors.append(err("champ `type` obligatoire absent"))
        return errors

    val_type = str(frontmatter["type"])

    # Règle 3 : type inconnu (comparaison case-insensitive sur les clés)
    type_key: str | None = None
    for k in types_config:
        if k.lower() == val_type.lower():
            type_key = k
            break

    if type_key is None:
        errors.append(err(f"type inconnu : {val_type}"))
        return errors

    # Règle 4 : récupération de la config du type
    type_cfg: dict[str, Any] = types_config[type_key]

    # Règle 5 : champs requis (sauf `type`)
    required: list[str] = list(type_cfg.get("required", []))
    for field in required:
        if field == "type":
            continue
        if field not in frontmatter:
            errors.append(err(f"champ requis absent : {field}"))

    # Règle 6 : validation du champ `statut`
    statut_values = type_cfg.get("statut_values")

    if statut_values is False:
        # statut interdit pour ce type
        if "statut" in frontmatter:
            errors.append(err(f"champ `statut` interdit pour le type {type_key}"))
    elif isinstance(statut_values, list):
        # statut obligatoire et à valeur contrainte
        if "statut" not in frontmatter:
            errors.append(err(f"champ `statut` requis pour le type {type_key}"))
        else:
            val_statut = frontmatter["statut"]
            if val_statut not in statut_values:
                errors.append(
                    err(
                        f"valeur `statut` invalide : {val_statut}"
                        f" (valeurs : {statut_values})"
                    )
                )
    # statut_values is None ou absent → optionnel, pas de vérification

    # Règle 7 : champ `status` (anglais) présent
    if "status" in frontmatter:
        errors.append(warn("champ `status` (anglais) trouvé — renommer en `statut`"))

    # Règle 8 : format dates
    for field in ("created", "updated"):
        if field in frontmatter and frontmatter[field]:
            val = str(frontmatter[field])
            if not _ISO_DATE_RE.match(val):
                errors.append(warn(f"date mal formatée : {field}={val}"))

    return errors


def validate_links(
    path: str,
    wikilinks: list[WikiLink],
    md_links: list[MarkdownLink],
    base_index: dict[str, list[str]],
    external_refs: set[str],
) -> list[ValidationError]:
    """Valide les liens wikilink et markdown d'un fichier.

    Args:
        path: Chemin relatif du fichier (pour les messages d'erreur).
        wikilinks: Liste de WikiLink extraits du fichier.
        md_links: Liste de MarkdownLink extraits du fichier.
        base_index: Index des fichiers de la base (nom → chemins).
        external_refs: Ensemble des noms de fichiers externes autorisés (en minuscules).

    Returns:
        Liste de ValidationError (vide si conforme).
    """
    errors: list[ValidationError] = []

    for wl in wikilinks:
        if wl.broken and wl.target.lower() not in external_refs:
            errors.append(
                ValidationError(
                    file=path,
                    family="links",
                    severity="error",
                    message=f"wikilink cassé : [[{wl.target}]]",
                )
            )
        if wl.ambiguous:
            errors.append(
                ValidationError(
                    file=path,
                    family="links",
                    severity="warning",
                    message=f"wikilink ambigu : [[{wl.target}]]",
                )
            )

    for ml in md_links:
        if ml.broken and not ml.is_external:
            errors.append(
                ValidationError(
                    file=path,
                    family="links",
                    severity="error",
                    message=f"lien markdown cassé : {ml.target}",
                )
            )

    return errors


def validate_file(
    file_path: Path,
    root: Path,
    base_index: dict[str, list[str]],
    types_config: dict[str, Any],
    external_refs: set[str],
) -> list[ValidationError]:
    """Orchestre la validation complète d'un fichier markdown.

    Args:
        file_path: Chemin absolu du fichier à valider.
        root: Racine de la base (pour les chemins relatifs et la résolution des liens).
        base_index: Index des fichiers de la base.
        types_config: Configuration des types depuis le manifeste.
        external_refs: Ensemble des références externes autorisées (en minuscules).

    Returns:
        Liste de ValidationError (vide si conforme).
    """
    content = file_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    safe_body = blank_code_spans(body)
    wikilinks = extract_wikilinks(safe_body, base_index)
    md_links = extract_markdown_links(safe_body, file_path, root)
    rel = str(file_path.relative_to(root))

    return validate_frontmatter(rel, fm, types_config) + validate_links(
        rel, wikilinks, md_links, base_index, external_refs
    )


def check_reserved_files(
    roots: list[Path],
    reserved_config: dict[str, str],
) -> list[ValidationError]:
    """Vérifie la présence des fichiers réservés dans chaque root.

    Args:
        roots: Liste des racines de la base.
        reserved_config: Mapping nom_logique → nom_fichier depuis le manifeste.

    Returns:
        Liste de ValidationError (warnings pour les fichiers absents).
    """
    errors: list[ValidationError] = []
    for root in roots:
        for filename in reserved_config.values():
            if not (root / filename).exists():
                errors.append(
                    ValidationError(
                        file=filename,
                        family="reserved",
                        severity="warning",
                        message=f"fichier réservé absent : {filename}",
                    )
                )
    return errors


def run_validate(
    manifest_path: Path,
    targets: list[Path],
) -> tuple[list[ValidationError], int]:
    """Orchestre la validation OKF d'une liste de cibles.

    Args:
        manifest_path: Chemin vers le manifeste OKF YAML.
        targets: Fichiers ou dossiers à valider.

    Returns:
        Tuple (liste d'erreurs, code de sortie 0 ou 1).
    """
    manifest = load_manifest(manifest_path)
    roots = [Path(r["path"]) for r in manifest["base"]["roots"]]
    base_index = build_file_index(roots)
    external_refs = {
        s.lower()
        for s in manifest["base"].get("link_resolution", {}).get("external_refs", [])
    }
    types_config: dict[str, Any] = manifest["types"]
    reserved_config: dict[str, str] = manifest["base"].get("reserved_files", {})

    # Collecte des fichiers réservés à exclure de la validation frontmatter/liens
    reserved_names = set(reserved_config.values())

    all_errors: list[ValidationError] = []

    for target in targets:
        if target.is_dir():
            md_files = list(target.rglob("*.md"))
        else:
            md_files = [target]

        for md_file in md_files:
            if md_file.name in reserved_names:
                continue
            # Détermination de la root applicable
            applicable_root = roots[0]
            for root in roots:
                try:
                    md_file.relative_to(root)
                    applicable_root = root
                    break
                except ValueError:
                    continue
            all_errors.extend(
                validate_file(
                    md_file, applicable_root, base_index, types_config, external_refs
                )
            )

    all_errors.extend(check_reserved_files(roots, reserved_config))

    code = 0 if not any(e.severity == "error" for e in all_errors) else 1
    return all_errors, code


def main() -> None:
    """Point d'entrée CLI : okf-validate."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Validation OKF de documents.")
    parser.add_argument("--manifest", default="okf-base.yaml")
    parser.add_argument("--json", dest="json_output", action="store_true")
    parser.add_argument("targets", nargs="+", help="Fichiers ou dossiers à valider")
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    targets = [Path(t) for t in args.targets]
    errors, code = run_validate(manifest_path, targets)
    if args.json_output:
        payload = [dataclasses.asdict(e) for e in errors]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for e in errors:
            icon = "❌" if e.severity == "error" else "⚠️"
            print(f"{icon} [{e.family}] {e.file} — {e.message}")
        if not errors:
            print("✅ Tous les fichiers sont conformes OKF.")
        else:
            errs = sum(1 for e in errors if e.severity == "error")
            warns = sum(1 for e in errors if e.severity == "warning")
            print(f"\n{errs} erreur(s), {warns} avertissement(s).")
    sys.exit(code)


if __name__ == "__main__":
    main()
