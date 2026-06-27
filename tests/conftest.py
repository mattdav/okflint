"""Shared fixtures for the okflint test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml


def _base_manifest_dict(root: Path) -> dict:
    return {
        "okf_version": "0.1",
        "base": {
            "name": "test-base",
            "roots": [{"path": root.as_posix()}],
            "reserved_files": {"index": "index.md", "log": "log.md"},
            "status_field": "statut",
        },
    }


@pytest.fixture
def make_md() -> Callable[[Path, str], Path]:
    """Create a .md file at the given path with the given content."""

    def _make(path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    return _make


@pytest.fixture
def minimal_manifest(tmp_path: Path) -> tuple[Path, Path]:
    """Minimal manifest (base only) + root directory."""
    root = tmp_path / "root"
    root.mkdir()
    manifest_path = tmp_path / "manifest.yaml"
    data = _base_manifest_dict(root)
    manifest_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return manifest_path, root


@pytest.fixture
def profile_manifest(tmp_path: Path) -> tuple[Path, Path]:
    """Manifest with profile: Decision + JournalEntry."""
    root = tmp_path / "root"
    root.mkdir()
    manifest_path = tmp_path / "manifest.yaml"
    data = _base_manifest_dict(root)
    data["profile"] = {
        "date_fields": ["created", "updated"],
        "types": {
            "Decision": {
                "required": ["type", "statut", "created"],
                "optional": ["updated", "tags"],
                "status_values": ["Accepté", "Proposé", "Déprécié"],
                "aliases": ["adr", "ADR"],
            },
            "JournalEntry": {
                "required": ["type", "created"],
                "optional": ["updated", "tags"],
                "status_values": False,
                "aliases": [],
            },
        },
    }
    manifest_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return manifest_path, root


@pytest.fixture
def hygiene_manifest(tmp_path: Path) -> tuple[Path, Path]:
    """Manifest with profile + full hygiene set to warn."""
    root = tmp_path / "root"
    root.mkdir()
    manifest_path = tmp_path / "manifest.yaml"
    data = _base_manifest_dict(root)
    data["profile"] = {
        "date_fields": ["created", "updated"],
        "types": {
            "Decision": {
                "required": ["type", "statut", "created"],
                "optional": ["updated", "tags"],
                "status_values": ["Accepté", "Proposé", "Déprécié"],
                "aliases": ["adr", "ADR"],
            },
            "JournalEntry": {
                "required": ["type", "created"],
                "optional": ["updated", "tags"],
                "status_values": False,
                "aliases": [],
            },
        },
    }
    data["hygiene"] = {
        "broken_links": "warn",
        "split_candidates": "warn",
        "reserved_files": "warn",
        "unknown_fields": "warn",
    }
    manifest_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return manifest_path, root
