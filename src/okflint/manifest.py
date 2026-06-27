"""Chargement et validation du manifeste OKF YAML."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from beartype import beartype
import yaml


class ManifestError(Exception):
    """Manifeste OKF invalide ou illisible."""


@dataclass
class TypeConfig:
    """Configuration d'un type de concept déclaré dans le profil."""

    required: list[str]
    optional: list[str]
    status_values: list[str] | Literal[False] | None
    aliases: list[str]


@dataclass
class ProfileConfig:
    """Configuration du profil de la base documentaire."""

    types: dict[str, TypeConfig]
    date_fields: list[str]


@dataclass
class HygieneConfig:
    """Configuration des contrôles d'hygiène (opt-in)."""

    broken_links: Literal["off", "warn", "error"]
    split_candidates: Literal["off", "warn", "error"]
    reserved_files: Literal["off", "warn", "error"]
    unknown_fields: Literal["off", "warn", "error"]


@dataclass
class BaseConfig:
    """Configuration de la base documentaire."""

    name: str
    roots: list[Path]
    reserved_files: dict[str, str]
    status_field: str | None
    external_refs: set[str]


@dataclass
class Manifest:
    """Manifeste OKF chargé et validé."""

    okf_version: str | None
    base: BaseConfig
    profile: ProfileConfig | None
    hygiene: HygieneConfig | None


# Valeurs d'hygiène valides
_HYGIENE_VALUES: frozenset[str] = frozenset({"off", "warn", "error"})

# Version OKF connue
_KNOWN_OKF_VERSION = "0.1"

# Valeurs par défaut de HygieneConfig quand la clé est absente
_DEFAULT_HYGIENE = HygieneConfig(
    broken_links="warn",
    split_candidates="off",
    reserved_files="off",
    unknown_fields="off",
)


def _coerce_level(value: Any, key: str) -> Literal["off", "warn", "error"]:
    """Normalise une valeur YAML vers un niveau d'hygiène.

    YAML 1.1 (PyYAML) interprète off/no/false comme bool False,
    et on/yes/true comme bool True. On absorbe ces deux cas pour ne
    pas piéger l'utilisateur sur cette subtilité.

    Args:
        value: Valeur brute issue de yaml.safe_load.
        key: Clé hygiene (pour le message d'erreur).

    Returns:
        Niveau normalisé parmi off | warn | error.

    Raises:
        ManifestError: Si la valeur n'est pas normalisable.
    """
    if value is False:
        return "off"
    if value is True:
        return "warn"
    if value in _HYGIENE_VALUES:
        return cast(Literal["off", "warn", "error"], value)
    raise ManifestError(
        f"hygiene.{key} doit être off | warn | error (reçu : {value!r})."
    )


def _parse_type_config(name: str, raw: Any) -> TypeConfig:
    """Parse la configuration d'un type depuis le YAML brut.

    Args:
        name: Nom canonique du type (pour les messages d'erreur).
        raw: Valeur brute depuis le YAML.

    Returns:
        TypeConfig validé.

    Raises:
        ManifestError: Si la configuration est invalide.
    """
    if not isinstance(raw, dict):
        raise ManifestError(f"profile.types.{name} doit être un mapping.")

    required = raw.get("required", [])
    if not isinstance(required, list) or not all(isinstance(s, str) for s in required):
        raise ManifestError(
            f"profile.types.{name}.required doit être une liste de strings."
        )

    optional = raw.get("optional", [])
    if not isinstance(optional, list) or not all(isinstance(s, str) for s in optional):
        raise ManifestError(
            f"profile.types.{name}.optional doit être une liste de strings."
        )

    # Vérification intersection required ∩ optional = ∅
    overlap = set(required) & set(optional)
    if overlap:
        raise ManifestError(
            f"profile.types.{name} : champs à la fois dans required et optional : "
            f"{sorted(overlap)}"
        )

    # status_values : liste, False (bool), None/absent — rien d'autre
    # CRITIQUE : distinguer is False de is None
    if "status_values" not in raw:
        status_values: list[str] | Literal[False] | None = None
    else:
        sv_raw = raw["status_values"]
        if sv_raw is False:
            # YAML `false` → Python False (bool)
            status_values = False
        elif sv_raw is None:
            status_values = None
        elif isinstance(sv_raw, list):
            if not all(isinstance(s, str) for s in sv_raw):
                raise ManifestError(
                    f"profile.types.{name}.status_values"
                    " doit être une liste de strings."
                )
            status_values = sv_raw
        else:
            raise ManifestError(
                f"profile.types.{name}.status_values"
                f" doit être une liste, false ou null (reçu : {sv_raw!r})."
            )

    aliases = raw.get("aliases", [])
    if not isinstance(aliases, list) or not all(isinstance(s, str) for s in aliases):
        raise ManifestError(
            f"profile.types.{name}.aliases doit être une liste de strings."
        )

    return TypeConfig(
        required=list(required),
        optional=list(optional),
        status_values=status_values,
        aliases=list(aliases),
    )


def _parse_profile(raw: Any, status_field: str | None) -> ProfileConfig:
    """Parse la configuration du profil depuis le YAML brut.

    Args:
        raw: Valeur brute du bloc profile depuis le YAML.
        status_field: Champ de statut déclaré dans base (peut être None).

    Returns:
        ProfileConfig validé.

    Raises:
        ManifestError: Si la configuration est invalide.
    """
    if not isinstance(raw, dict):
        raise ManifestError("profile doit être un mapping.")

    raw_types = raw.get("types", {})
    if not isinstance(raw_types, dict):
        raise ManifestError("profile.types doit être un mapping.")

    types: dict[str, TypeConfig] = {}
    # Vrai si au moins un type nécessite status_field déclaré
    needs_status_field = False

    for type_name, type_raw in raw_types.items():
        cfg = _parse_type_config(str(type_name), type_raw)
        types[str(type_name)] = cfg
        # status_field requis si au moins un type a status_values liste ou False
        if isinstance(cfg.status_values, list) or cfg.status_values is False:
            needs_status_field = True

    if needs_status_field and status_field is None:
        raise ManifestError(
            "base.status_field doit être déclaré quand au moins un type "
            "utilise status_values (liste ou false)."
        )

    date_fields_raw = raw.get("date_fields", [])
    if not isinstance(date_fields_raw, list) or not all(
        isinstance(s, str) for s in date_fields_raw
    ):
        raise ManifestError("profile.date_fields doit être une liste de strings.")

    return ProfileConfig(
        types=types,
        date_fields=list(date_fields_raw),
    )


def _parse_hygiene(raw: Any) -> HygieneConfig:
    """Parse la configuration d'hygiène depuis le YAML brut.

    Args:
        raw: Valeur brute du bloc hygiene depuis le YAML.

    Returns:
        HygieneConfig validé.

    Raises:
        ManifestError: Si une valeur n'est pas dans {off, warn, error}.
    """
    if not isinstance(raw, dict):
        raise ManifestError("hygiene doit être un mapping.")

    def _get_level(key: str, default: str = "off") -> Literal["off", "warn", "error"]:
        return _coerce_level(raw.get(key, default), key)

    return HygieneConfig(
        broken_links=_get_level("broken_links", "warn"),
        split_candidates=_get_level("split_candidates", "off"),
        reserved_files=_get_level("reserved_files", "off"),
        unknown_fields=_get_level("unknown_fields", "off"),
    )


@beartype
def load_manifest(path: Path) -> Manifest:
    """Charge et valide un manifeste OKF YAML.

    Args:
        path: Chemin vers le fichier YAML.

    Returns:
        Manifest typé et validé.

    Raises:
        ManifestError: Si le fichier est illisible, invalide, ou viole les contraintes.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"Impossible de lire {path} : {exc}") from exc

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"YAML invalide dans {path} : {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"{path} n'est pas un mapping YAML au niveau racine.")

    # Clé base obligatoire
    if "base" not in data:
        raise ManifestError(f"Clé 'base' absente dans {path}.")

    raw_base = data["base"]
    if not isinstance(raw_base, dict):
        raise ManifestError("base doit être un mapping.")

    # base.roots
    raw_roots = raw_base.get("roots")
    if not raw_roots or not isinstance(raw_roots, list):
        raise ManifestError("base.roots doit être une liste non vide.")
    roots: list[Path] = []
    for entry in raw_roots:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ManifestError(
                "Chaque entrée de base.roots doit avoir une clé 'path' de type string."
            )
        if not isinstance(entry["path"], str):
            raise ManifestError("base.roots[].path doit être un string.")
        roots.append(Path(entry["path"]))

    # base.reserved_files
    raw_reserved = raw_base.get("reserved_files")
    if not isinstance(raw_reserved, dict):
        raise ManifestError("base.reserved_files doit être un mapping.")
    if "index" not in raw_reserved or "log" not in raw_reserved:
        raise ManifestError(
            "base.reserved_files doit contenir les clés 'index' et 'log'."
        )
    reserved_files: dict[str, str] = {str(k): str(v) for k, v in raw_reserved.items()}

    # base.status_field (optionnel)
    status_field_raw = raw_base.get("status_field")
    status_field: str | None = (
        str(status_field_raw) if status_field_raw is not None else None
    )

    # base.external_refs (depuis link_resolution)
    link_res = raw_base.get("link_resolution", {})
    external_refs_raw = (
        link_res.get("external_refs", []) if isinstance(link_res, dict) else []
    )
    external_refs: set[str] = {
        s.lower() for s in external_refs_raw if isinstance(s, str)
    }

    # base.name
    name = str(raw_base.get("name", ""))

    base_config = BaseConfig(
        name=name,
        roots=roots,
        reserved_files=reserved_files,
        status_field=status_field,
        external_refs=external_refs,
    )

    # okf_version (optionnel, warning si inconnu)
    okf_version: str | None = None
    if "okf_version" in data:
        okf_version = str(data["okf_version"])
        if okf_version != _KNOWN_OKF_VERSION:
            print(
                f"Warning : version okf_version={okf_version!r} inconnue "
                f"(attendu : {_KNOWN_OKF_VERSION!r}).",
                file=sys.stderr,
            )

    # profile (optionnel)
    profile: ProfileConfig | None = None
    if "profile" in data:
        profile = _parse_profile(data["profile"], status_field)

    # hygiene (optionnel)
    hygiene: HygieneConfig | None = None
    if "hygiene" in data:
        hygiene = _parse_hygiene(data["hygiene"])

    return Manifest(
        okf_version=okf_version,
        base=base_config,
        profile=profile,
        hygiene=hygiene,
    )
