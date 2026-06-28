"""OKF vault manifest loading and validation."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from beartype import beartype

_KNOWN_VAULT_VERSION = "0.1"

__all__ = ["BundleEntry", "VaultConfig", "VaultError", "load_vault"]


class VaultError(Exception):
    """Invalid or unreadable okf-vault.json."""


@dataclass
class BundleEntry:
    """A bundle entry resolved from the vault manifest."""

    path: Path
    manifest_path: Path


@dataclass
class VaultConfig:
    """Loaded and validated vault configuration."""

    okf_vault_version: str | None
    name: str
    bundles: list[BundleEntry]


@beartype
def load_vault(path: Path) -> VaultConfig:
    """Load and validate an okf-vault.json file.

    Resolution rules:
    - ``path`` is absolute or resolved relative to the vault JSON file's parent.
    - ``manifest`` is resolved relative to the bundle ``path`` (not the vault file).
    - If ``manifest`` is absent in an entry, ``okf-base.yaml`` is used as default.

    Args:
        path: Path to the okf-vault.json file.

    Returns:
        Validated VaultConfig.

    Raises:
        VaultError: If the file is unreadable, invalid JSON, or violates constraints.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VaultError(f"Cannot read {path}: {exc}") from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise VaultError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise VaultError(f"{path} is not a JSON object at root level.")

    vault_dir = path.parent

    # okf_vault_version (optional — warn if absent or unknown, never block)
    okf_vault_version: str | None = None
    if "okf_vault_version" in data:
        okf_vault_version = str(data["okf_vault_version"])
        if okf_vault_version != _KNOWN_VAULT_VERSION:
            print(
                f"Warning: unknown okf_vault_version={okf_vault_version!r} "
                f"(expected: {_KNOWN_VAULT_VERSION!r}).",
                file=sys.stderr,
            )
    else:
        print(
            "Warning: okf_vault_version absent in vault manifest "
            f"(expected: {_KNOWN_VAULT_VERSION!r}).",
            file=sys.stderr,
        )

    name = str(data.get("name", ""))

    raw_bundles = data.get("bundles")
    if not raw_bundles or not isinstance(raw_bundles, list):
        raise VaultError("bundles must be a non-empty list.")

    bundles: list[BundleEntry] = []
    for i, entry in enumerate(raw_bundles):
        if not isinstance(entry, dict) or "path" not in entry:
            raise VaultError(
                f"bundles[{i}] must be a mapping with at least a 'path' key."
            )

        raw_path = entry["path"]
        if not isinstance(raw_path, str):
            raise VaultError(f"bundles[{i}].path must be a string.")

        bundle_path = Path(raw_path)
        if not bundle_path.is_absolute():
            bundle_path = (vault_dir / bundle_path).resolve()

        if not bundle_path.exists():
            raise VaultError(f"bundles[{i}].path does not exist: {bundle_path}")

        raw_manifest = entry.get("manifest", "okf-base.yaml")
        if not isinstance(raw_manifest, str):
            raise VaultError(f"bundles[{i}].manifest must be a string.")

        manifest_path = bundle_path / raw_manifest
        if not manifest_path.exists():
            raise VaultError(f"bundles[{i}].manifest does not exist: {manifest_path}")

        bundles.append(BundleEntry(path=bundle_path, manifest_path=manifest_path))

    return VaultConfig(
        okf_vault_version=okf_vault_version,
        name=name,
        bundles=bundles,
    )
