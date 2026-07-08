"""OKF manifest loading and validation."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from beartype import beartype


class ManifestError(Exception):
    """Invalid or unreadable OKF manifest."""


@dataclass
class TypeConfig:
    """Configuration of a concept type declared in the profile."""

    required: list[str]
    optional: list[str]
    controlled_values: dict[str, list[str]]
    aliases: list[str]


@dataclass
class ProfileConfig:
    """Profile configuration of the documentary base."""

    types: dict[str, TypeConfig]
    date_fields: list[str]


@dataclass
class SplitConfig:
    """Gate configuration for the S202 semantic cohesion check."""

    min_lines: int
    exempt_types: frozenset[str]
    exempt_paths: list[str]
    # Cosine similarity threshold for cohesion clustering. 0.15 default locked
    # via the STEP 1 tau-sweep calibration (0.13-0.22 range on representative
    # memos); manifest-overridable per base.
    tau: float = 0.15


@dataclass
class HygieneConfig:
    """Configuration of hygiene checks (opt-in)."""

    broken_links: Literal["off", "warn", "error"]
    split_candidates: Literal["off", "warn", "error"]
    reserved_files: Literal["off", "warn", "error"]
    unknown_fields: Literal["off", "warn", "error"]
    split: SplitConfig


@dataclass
class RootConfig:
    """Configuration of a single root in the documentary base."""

    path: Path
    exclude_patterns: list[str]


@dataclass
class BaseConfig:
    """Documentary base configuration."""

    name: str
    roots: list[RootConfig]
    reserved_files: dict[str, str]
    external_refs: set[str]


@dataclass
class Manifest:
    """Loaded and validated OKF manifest."""

    okf_version: str | None
    base: BaseConfig
    profile: ProfileConfig | None
    hygiene: HygieneConfig | None


# Valid hygiene values
_HYGIENE_VALUES: frozenset[str] = frozenset({"off", "warn", "error"})

# Known OKF version
_KNOWN_OKF_VERSION = "0.1"

# Default SplitConfig: no length gate, no exemptions
_DEFAULT_SPLIT_CONFIG = SplitConfig(
    min_lines=0,
    exempt_types=frozenset(),
    exempt_paths=[],
)

# Default HygieneConfig values when the key is absent
_DEFAULT_HYGIENE = HygieneConfig(
    broken_links="warn",
    split_candidates="off",
    reserved_files="off",
    unknown_fields="off",
    split=_DEFAULT_SPLIT_CONFIG,
)


def _coerce_level(value: Any, key: str) -> Literal["off", "warn", "error"]:
    """Normalise a YAML value to a hygiene level.

    YAML 1.1 (PyYAML) interprets off/no/false as Python bool False,
    and on/yes/true as Python bool True. Both cases are absorbed here
    to avoid trapping the user on this subtlety.

    Args:
        value: Raw value returned by yaml.safe_load.
        key: Hygiene key (for the error message).

    Returns:
        Normalised level among off | warn | error.

    Raises:
        ManifestError: If the value cannot be normalised.
    """
    if value is False:
        return "off"
    if value is True:
        return "warn"
    if value in _HYGIENE_VALUES:
        return cast(Literal["off", "warn", "error"], value)
    raise ManifestError(
        f"hygiene.{key} must be off | warn | error (received: {value!r})."
    )


def _parse_type_config(name: str, raw: Any) -> TypeConfig:
    """Parse the configuration of a type from raw YAML.

    Args:
        name: Canonical name of the type (for error messages).
        raw: Raw value from the YAML.

    Returns:
        Validated TypeConfig.

    Raises:
        ManifestError: If the configuration is invalid.
    """
    if not isinstance(raw, dict):
        raise ManifestError(f"profile.types.{name} must be a mapping.")

    required = raw.get("required", [])
    if not isinstance(required, list) or not all(isinstance(s, str) for s in required):
        raise ManifestError(f"profile.types.{name}.required must be a list of strings.")

    optional = raw.get("optional", [])
    if not isinstance(optional, list) or not all(isinstance(s, str) for s in optional):
        raise ManifestError(f"profile.types.{name}.optional must be a list of strings.")

    # Check required ∩ optional = ∅
    overlap = set(required) & set(optional)
    if overlap:
        raise ManifestError(
            f"profile.types.{name}: fields present in both required and optional: "
            f"{sorted(overlap)}"
        )

    known_props = set(required) | set(optional)

    # Any key ending in `_values` declares a controlled vocabulary for the
    # property named by its prefix (e.g. `priority_values` → property `priority`).
    controlled_values: dict[str, list[str]] = {}
    for key, raw_values in raw.items():
        if not key.endswith("_values"):
            continue
        prop = key[: -len("_values")]
        if prop not in known_props:
            raise ManifestError(
                f"profile.types.{name}: _values declared for an undeclared "
                f"property: {prop}"
            )
        if not isinstance(raw_values, list) or not all(
            isinstance(s, str) for s in raw_values
        ):
            raise ManifestError(
                f"profile.types.{name}.{key} must be a list of strings."
            )
        controlled_values[prop] = list(raw_values)

    aliases = raw.get("aliases", [])
    if not isinstance(aliases, list) or not all(isinstance(s, str) for s in aliases):
        raise ManifestError(f"profile.types.{name}.aliases must be a list of strings.")

    return TypeConfig(
        required=list(required),
        optional=list(optional),
        controlled_values=controlled_values,
        aliases=list(aliases),
    )


def _parse_profile(raw: Any) -> ProfileConfig:
    """Parse the profile configuration from raw YAML.

    Args:
        raw: Raw value of the profile block from the YAML.

    Returns:
        Validated ProfileConfig.

    Raises:
        ManifestError: If the configuration is invalid.
    """
    if not isinstance(raw, dict):
        raise ManifestError("profile must be a mapping.")

    raw_types = raw.get("types", {})
    if not isinstance(raw_types, dict):
        raise ManifestError("profile.types must be a mapping.")

    types: dict[str, TypeConfig] = {
        str(type_name): _parse_type_config(str(type_name), type_raw)
        for type_name, type_raw in raw_types.items()
    }

    date_fields_raw = raw.get("date_fields", [])
    if not isinstance(date_fields_raw, list) or not all(
        isinstance(s, str) for s in date_fields_raw
    ):
        raise ManifestError("profile.date_fields must be a list of strings.")

    return ProfileConfig(
        types=types,
        date_fields=list(date_fields_raw),
    )


def _parse_split_config(raw: Any) -> SplitConfig:
    """Parse the hygiene.split sub-block (S202 gate configuration) from raw YAML.

    Args:
        raw: Raw value of the hygiene.split block, or None if absent.

    Returns:
        Validated SplitConfig (defaults to no length gate, no exemptions,
        tau=0.15).

    Raises:
        ManifestError: If the block or one of its fields is malformed, or if
            tau lies outside the open interval (0, 1).
    """
    if raw is None:
        return SplitConfig(min_lines=0, exempt_types=frozenset(), exempt_paths=[])
    if not isinstance(raw, dict):
        raise ManifestError("hygiene.split must be a mapping.")

    min_lines = raw.get("min_lines", 0)
    if not isinstance(min_lines, int) or isinstance(min_lines, bool) or min_lines < 0:
        raise ManifestError("hygiene.split.min_lines must be a non-negative integer.")

    exempt_types_raw = raw.get("exempt_types", [])
    if not isinstance(exempt_types_raw, list) or not all(
        isinstance(s, str) for s in exempt_types_raw
    ):
        raise ManifestError("hygiene.split.exempt_types must be a list of strings.")

    exempt_paths_raw = raw.get("exempt_paths", [])
    if not isinstance(exempt_paths_raw, list) or not all(
        isinstance(s, str) for s in exempt_paths_raw
    ):
        raise ManifestError("hygiene.split.exempt_paths must be a list of strings.")

    tau_raw = raw.get("tau", 0.15)
    if (
        not isinstance(tau_raw, (int, float))
        or isinstance(tau_raw, bool)
        or not (0 < tau_raw < 1)
    ):
        raise ManifestError(
            "hygiene.split.tau must be a number in the open interval (0, 1)."
        )

    return SplitConfig(
        min_lines=min_lines,
        exempt_types=frozenset(exempt_types_raw),
        exempt_paths=list(exempt_paths_raw),
        tau=float(tau_raw),
    )


def _parse_hygiene(raw: Any) -> HygieneConfig:
    """Parse the hygiene configuration from raw YAML.

    Args:
        raw: Raw value of the hygiene block from the YAML.

    Returns:
        Validated HygieneConfig.

    Raises:
        ManifestError: If a value is not in {off, warn, error}.
    """
    if not isinstance(raw, dict):
        raise ManifestError("hygiene must be a mapping.")

    def _get_level(key: str, default: str = "off") -> Literal["off", "warn", "error"]:
        return _coerce_level(raw.get(key, default), key)

    return HygieneConfig(
        broken_links=_get_level("broken_links", "warn"),
        split_candidates=_get_level("split_candidates", "off"),
        reserved_files=_get_level("reserved_files", "off"),
        unknown_fields=_get_level("unknown_fields", "off"),
        split=_parse_split_config(raw.get("split")),
    )


@beartype
def load_manifest(path: Path) -> Manifest:
    """Load and validate an OKF YAML manifest.

    Args:
        path: Path to the YAML file.

    Returns:
        Typed and validated Manifest.

    Raises:
        ManifestError: If the file is unreadable, invalid, or violates constraints.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"Cannot read {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"{path} is not a YAML mapping at root level.")

    # Mandatory base key
    if "base" not in data:
        raise ManifestError(f"Key 'base' absent in {path}.")

    raw_base = data["base"]
    if not isinstance(raw_base, dict):
        raise ManifestError("base must be a mapping.")

    # base.roots
    raw_roots = raw_base.get("roots")
    if not raw_roots or not isinstance(raw_roots, list):
        raise ManifestError("base.roots must be a non-empty list.")
    roots: list[RootConfig] = []
    for entry in raw_roots:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ManifestError(
                "Each entry in base.roots must have a 'path' key of type string."
            )
        if not isinstance(entry["path"], str):
            raise ManifestError("base.roots[].path must be a string.")
        raw_root = Path(entry["path"])
        # Resolve relative roots against the manifest file's directory so that
        # roots like "." or "docs/" work regardless of the process CWD.
        resolved_root = (
            raw_root if raw_root.is_absolute() else (path.parent / raw_root).resolve()
        )
        raw_patterns = entry.get("exclude_patterns", [])
        if not isinstance(raw_patterns, list) or not all(
            isinstance(s, str) for s in raw_patterns
        ):
            raise ManifestError(
                "base.roots[].exclude_patterns must be a list of strings."
            )
        roots.append(
            RootConfig(path=resolved_root, exclude_patterns=list(raw_patterns))
        )

    # base.reserved_files
    raw_reserved = raw_base.get("reserved_files")
    if not isinstance(raw_reserved, dict):
        raise ManifestError("base.reserved_files must be a mapping.")
    if "index" not in raw_reserved or "log" not in raw_reserved:
        raise ManifestError("base.reserved_files must contain keys 'index' and 'log'.")
    reserved_files: dict[str, str] = {str(k): str(v) for k, v in raw_reserved.items()}

    # base.external_refs (from link_resolution)
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
        external_refs=external_refs,
    )

    # okf_version (optional, warning if unknown)
    okf_version: str | None = None
    if "okf_version" in data:
        okf_version = str(data["okf_version"])
        if okf_version != _KNOWN_OKF_VERSION:
            print(
                f"Warning: unknown okf_version={okf_version!r} "
                f"(expected: {_KNOWN_OKF_VERSION!r}).",
                file=sys.stderr,
            )

    # profile (optional)
    profile: ProfileConfig | None = None
    if "profile" in data:
        profile = _parse_profile(data["profile"])

    # hygiene (optional)
    hygiene: HygieneConfig | None = None
    if "hygiene" in data:
        hygiene = _parse_hygiene(data["hygiene"])

    return Manifest(
        okf_version=okf_version,
        base=base_config,
        profile=profile,
        hygiene=hygiene,
    )
