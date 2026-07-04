"""Unified CLI entry point for okflint.

Exposes two sub-commands Ruff-style:
    okflint audit     — inventory and descriptive diagnostic of a base
    okflint validate  — normative compliance gate (exit 0/1)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from beartype import beartype

from okflint.audit import run_audit
from okflint.manifest import Manifest, RootConfig, load_manifest
from okflint.scanner import build_file_index
from okflint.validate import Diagnostic, ManifestError, run_validate
from okflint.vault import VaultConfig, VaultError, load_vault

# ---------------------------------------------------------------------------
# Shared printing helpers
# ---------------------------------------------------------------------------


def _print_audit_stats(
    stats: dict[str, Any],
    title: str | None = None,
    diagnostics_summary: dict[str, Any] | None = None,
) -> None:
    """Print the standard audit stats block, optionally preceded by a title.

    Args:
        stats: Stats dict as returned by ``compute_stats``.
        title: If set, prints ``=== title ===`` before the stats.
        diagnostics_summary: If set and non-empty, prints a synthetic
            errors/warnings line (full detail is carried by the JSON report).
    """
    if title is not None:
        print(f"\n=== {title} ===")
    n_concepts = stats["total_concept_files"]
    print(f"Files: {stats['total_files']} ({n_concepts} concepts)")
    print(f"OKF status: {stats['by_okf_status']}")
    wikilinks_broken = stats["broken_wikilinks"]
    print(f"Wikilinks: {stats['total_wikilinks']} of which {wikilinks_broken} broken")
    md_broken = stats["broken_markdown_links"]
    print(f"MD links: {stats['total_markdown_links']} of which {md_broken} broken")
    print(f"Split candidates: {stats['split_candidates']}")
    if diagnostics_summary:
        by_severity = diagnostics_summary["by_severity"]
        by_tier = diagnostics_summary["by_tier"]
        tiers = "/".join(f"{k}={v}" for k, v in by_tier.items())
        print(
            f"Diagnostics: {by_severity['error']} errors, "
            f"{by_severity['warning']} warnings ({tiers})"
        )


def _aggregate_audit_stats(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate stats from multiple per-bundle audit reports.

    Args:
        reports: List of individual bundle audit reports.

    Returns:
        Combined stats dict compatible with ``_print_audit_stats``.
    """
    by_status: dict[str, int] = {"conformant": 0, "partial": 0, "non_conformant": 0}
    for r in reports:
        for k, v in r["stats"]["by_okf_status"].items():
            by_status[str(k)] = by_status.get(str(k), 0) + int(v)

    return {
        "total_files": sum(int(r["stats"]["total_files"]) for r in reports),
        "total_concept_files": sum(
            int(r["stats"]["total_concept_files"]) for r in reports
        ),
        "by_okf_status": by_status,
        "total_wikilinks": sum(int(r["stats"]["total_wikilinks"]) for r in reports),
        "broken_wikilinks": sum(int(r["stats"]["broken_wikilinks"]) for r in reports),
        "total_markdown_links": sum(
            int(r["stats"]["total_markdown_links"]) for r in reports
        ),
        "broken_markdown_links": sum(
            int(r["stats"]["broken_markdown_links"]) for r in reports
        ),
        "split_candidates": sum(int(r["stats"]["split_candidates"]) for r in reports),
    }


def _write_audit_report(report: dict[str, Any], suffix: str = "audit") -> None:
    """Write a dated audit JSON report to .okflint/ and print its path.

    Args:
        report: Audit report dict.
        suffix: Filename infix (``audit`` or ``vault_audit``).
    """
    from datetime import date

    outputs_dir = Path(".okflint")
    outputs_dir.mkdir(exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    v = 1
    while (outputs_dir / f"{today}_{suffix}_v{v}.json").exists():
        v += 1
    out = outputs_dir / f"{today}_{suffix}_v{v}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {out}")


# ---------------------------------------------------------------------------
# Full-vault sub-command implementations
# ---------------------------------------------------------------------------


def _cmd_audit_full_vault(
    vault_cfg: VaultConfig,
    vault_index: dict[str, list[str]],
    args: argparse.Namespace,
) -> int:
    """Audit every bundle in the vault with the shared union index.

    Args:
        vault_cfg: Loaded vault configuration.
        vault_index: Pre-built union file index for all vault bundles.
        args: CLI namespace (apply).

    Returns:
        Exit code (0 on success).
    """
    all_reports: list[dict[str, Any]] = []

    for bundle_entry in vault_cfg.bundles:
        bundle_name = bundle_entry.path.name
        try:
            manifest = load_manifest(bundle_entry.manifest_path)
        except ManifestError as exc:
            print(
                f"Warning: skipping bundle '{bundle_name}': {exc}",
                file=sys.stderr,
            )
            continue

        report = run_audit(
            manifest.base.roots, [], vault_index=vault_index, manifest=manifest
        )
        all_reports.append(report)
        _print_audit_stats(
            report["stats"],
            title=bundle_name,
            diagnostics_summary=report.get("diagnostics_summary"),
        )

    if all_reports:
        _print_audit_stats(_aggregate_audit_stats(all_reports), title="Total vault")

    if args.apply and all_reports:
        combined: dict[str, Any] = {"reports": all_reports}
        _write_audit_report(combined, suffix="vault_audit")
    elif not args.apply:
        print("(dry-run — re-run with --apply to write the JSON report)")

    return 0


def _cmd_validate_full_vault(
    vault_cfg: VaultConfig,
    vault_index: dict[str, list[str]],
    args: argparse.Namespace,
) -> int:
    """Validate every bundle in the vault with the shared union index.

    Args:
        vault_cfg: Loaded vault configuration.
        vault_index: Pre-built union file index for all vault bundles.
        args: CLI namespace (json_output).

    Returns:
        Aggregated exit code (max of all bundle exit codes).
    """
    all_errors: list[Diagnostic] = []
    max_code = 0

    for bundle_entry in vault_cfg.bundles:
        bundle_name = bundle_entry.path.name
        try:
            manifest = load_manifest(bundle_entry.manifest_path)
        except ManifestError as exc:
            print(
                f"Warning: skipping bundle '{bundle_name}': {exc}",
                file=sys.stderr,
            )
            max_code = max(max_code, 2)
            continue

        try:
            errors, code = run_validate(
                bundle_entry.manifest_path,
                [r.path for r in manifest.base.roots],
                vault_index=vault_index,
            )
        except ManifestError as exc:
            print(
                f"Warning: manifest error in bundle '{bundle_name}': {exc}",
                file=sys.stderr,
            )
            max_code = max(max_code, 2)
            continue

        max_code = max(max_code, code)

        if not args.json_output:
            for e in errors:
                icon = "❌" if e.severity == "error" else "⚠️"
                print(f"{icon} [{e.code}] [{bundle_name}] {e.file} — {e.message}")
        else:
            all_errors.extend(errors)

    if args.json_output:
        payload = [dataclasses.asdict(e) for e in all_errors]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif max_code == 0:
        print("✅ All files are OKF-conformant.")

    return max_code


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def _cmd_audit(args: argparse.Namespace) -> int:
    """Execute the audit sub-command.

    When ``--vault`` points to a ``.json`` file the vault manifest is loaded
    and the union index is built from all declared bundles.  Resolution
    priority (most to least specific):

    +----------------+----------+-------------+----------------------------------+
    | ``--manifest`` | ``--bundle`` | ``--vault`` (json) | Behaviour          |
    +----------------+----------+-------------+----------------------------------+
    | ✗              | ✗        | ✓           | Full vault (each bundle)         |
    | ✗              | ✓        | ✓           | ``--bundle`` only, union index   |
    | ✓              | ✗        | ✓           | Manifest roots, union index      |
    | ✓              | ✓        | ✓           | Manifest roots + bundle filter   |
    | ✓              | ✗        | ✗           | Manifest multi-root (current)    |
    | ✗              | ✓        | ✗ (folder)  | Single-root (current)            |
    +----------------+----------+-------------+----------------------------------+

    Args:
        args: argparse Namespace (manifest, bundle, vault, apply).

    Returns:
        Exit code (0 on success, 2 on configuration error).
    """
    has_manifest = args.manifest is not None
    has_bundle = args.bundle is not None
    has_vault = args.vault is not None
    vault_path = Path(args.vault) if has_vault else None
    vault_is_json = vault_path is not None and vault_path.suffix.lower() == ".json"

    if vault_is_json:
        assert vault_path is not None  # narrowing for mypy
        try:
            vault_cfg = load_vault(vault_path)
        except VaultError as exc:
            print(f"Vault error: {exc}", file=sys.stderr)
            return 2

        all_vault_paths = [b.path for b in vault_cfg.bundles]
        print(f"🔎 Indexing vault: {len(vault_cfg.bundles)} bundles")
        vault_excl: dict[Path, list[str]] = {}
        for _be in vault_cfg.bundles:
            try:
                _m = load_manifest(_be.manifest_path)
                for _r in _m.base.roots:
                    if _r.exclude_patterns:
                        vault_excl[_r.path] = _r.exclude_patterns
            except ManifestError:
                pass
        vault_index = build_file_index(all_vault_paths, vault_excl or None)
        vault_total = sum(len(v) for v in vault_index.values())
        print(f"   {vault_total} .md files indexed")

        if not has_bundle and not has_manifest:
            return _cmd_audit_full_vault(vault_cfg, vault_index, args)

        target_filter: Path | None = None
        manifest_obj: Manifest | None = None

        if has_manifest:
            try:
                manifest_obj = load_manifest(Path(args.manifest))
            except ManifestError as exc:
                print(f"Manifest error: {exc}", file=sys.stderr)
                return 2
            bundle_paths = manifest_obj.base.roots
            if has_bundle:
                print(
                    "Warning: Both --manifest and --bundle provided; "
                    "--bundle used as target filter over manifest roots.",
                    file=sys.stderr,
                )
                target_filter = Path(args.bundle)
        else:
            bundle_paths = [RootConfig(path=Path(args.bundle), exclude_patterns=[])]

        report = run_audit(
            bundle_paths,
            [],
            target_filter=target_filter,
            vault_index=vault_index,
            manifest=manifest_obj,
        )
        _print_audit_stats(
            report["stats"], diagnostics_summary=report.get("diagnostics_summary")
        )
        roots: list[dict[str, object]] = report.get("roots", [])
        if len(roots) > 1:
            print("\nPer-root:")
            for root_info in roots:
                print(f"  {root_info['path']}   {root_info['file_count']} files")
        if args.apply:
            _write_audit_report(report)
        else:
            print("(dry-run — re-run with --apply to write the JSON report)")
        return 0

    # ── Original behaviour (vault is a folder or absent) ──────────────────────
    vault_paths_orig: list[Path]
    target_filter_orig: Path | None = None
    manifest_obj_orig: Manifest | None = None

    if has_manifest:
        try:
            manifest_obj_orig = load_manifest(Path(args.manifest))
        except ManifestError as exc:
            print(f"Manifest error: {exc}", file=sys.stderr)
            return 2
        bundle_paths_orig = manifest_obj_orig.base.roots
        vault_paths_orig = [r.path for r in manifest_obj_orig.base.roots]
        if has_bundle:
            print(
                "Warning: Both --manifest and --bundle provided; "
                "--bundle used as target filter over manifest roots.",
                file=sys.stderr,
            )
            target_filter_orig = Path(args.bundle)
    elif has_bundle and has_vault:
        bundle_paths_orig = [RootConfig(path=Path(args.bundle), exclude_patterns=[])]
        vault_paths_orig = [Path(args.vault)]
    else:
        print(
            "Error: Provide either --manifest or both --bundle and --vault.",
            file=sys.stderr,
        )
        return 2

    report_orig = run_audit(
        bundle_paths_orig,
        vault_paths_orig,
        target_filter=target_filter_orig,
        manifest=manifest_obj_orig,
    )
    _print_audit_stats(
        report_orig["stats"],
        diagnostics_summary=report_orig.get("diagnostics_summary"),
    )

    roots_orig: list[dict[str, object]] = report_orig.get("roots", [])
    if len(roots_orig) > 1:
        print("\nPer-root:")
        for root_info in roots_orig:
            print(f"  {root_info['path']}   {root_info['file_count']} files")

    if args.apply:
        _write_audit_report(report_orig)
    else:
        print("(dry-run — re-run with --apply to write the JSON report)")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Execute the validate sub-command.

    When ``--vault`` points to a ``.json`` file:
    - With explicit ``--manifest``: validate using that manifest and the vault
      union index.
    - Without ``--manifest`` and without targets: validate every bundle with
      its own manifest using the vault union index; exit code is the max of
      all bundle codes.
    - Without ``--manifest`` but with explicit targets: error (ambiguous).

    When ``--vault`` is absent or is a folder, behaviour is unchanged.

    Args:
        args: argparse Namespace (manifest, vault, json_output, targets).

    Returns:
        Exit code (0 if conformant, 1 if at least one error, 2 on manifest error).
    """
    has_vault = args.vault is not None
    vault_path = Path(args.vault) if has_vault else None
    vault_is_json = vault_path is not None and vault_path.suffix.lower() == ".json"
    explicit_manifest = args.manifest is not None

    if vault_is_json:
        assert vault_path is not None  # narrowing for mypy
        try:
            vault_cfg = load_vault(vault_path)
        except VaultError as exc:
            print(f"Vault error: {exc}", file=sys.stderr)
            return 2

        all_vault_paths = [b.path for b in vault_cfg.bundles]
        vault_excl_v: dict[Path, list[str]] = {}
        for _be in vault_cfg.bundles:
            try:
                _m = load_manifest(_be.manifest_path)
                for _r in _m.base.roots:
                    if _r.exclude_patterns:
                        vault_excl_v[_r.path] = _r.exclude_patterns
            except ManifestError:
                pass
        vault_index = build_file_index(all_vault_paths, vault_excl_v or None)

        if not explicit_manifest:
            if args.targets:
                print(
                    "Error: --vault without --manifest combined with explicit "
                    "targets is ambiguous.",
                    file=sys.stderr,
                )
                return 2
            return _cmd_validate_full_vault(vault_cfg, vault_index, args)

        # Explicit manifest + vault JSON → validate with union index
        manifest_path = Path(args.manifest)
        if args.targets:
            targets: list[Path] = [Path(t) for t in args.targets]
        else:
            try:
                manifest_for_roots = load_manifest(manifest_path)
                targets = [r.path for r in manifest_for_roots.base.roots]
            except ManifestError as exc:
                print(f"Manifest error: {exc}", file=sys.stderr)
                return 2

        try:
            errors, code = run_validate(manifest_path, targets, vault_index=vault_index)
        except ManifestError as exc:
            print(f"Manifest error: {exc}", file=sys.stderr)
            return 2

        if args.json_output:
            payload = [dataclasses.asdict(e) for e in errors]
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for e in errors:
                icon = "❌" if e.severity == "error" else "⚠️"
                print(f"{icon} [{e.code}] {e.file} — {e.message}")
            if not errors:
                print("✅ All files are OKF-conformant.")
            else:
                errs = sum(1 for e in errors if e.severity == "error")
                warns = sum(1 for e in errors if e.severity == "warning")
                print(f"\n{errs} error(s), {warns} warning(s).")
        return code

    # ── Original behaviour ────────────────────────────────────────────────────
    manifest_path_orig = Path(args.manifest or "okf-base.yaml")

    if args.targets:
        targets_orig: list[Path] = [Path(t) for t in args.targets]
    else:
        try:
            manifest_obj = load_manifest(manifest_path_orig)
            targets_orig = [r.path for r in manifest_obj.base.roots]
        except ManifestError as exc:
            print(f"Manifest error: {exc}", file=sys.stderr)
            return 2

    try:
        errors_orig, code_orig = run_validate(manifest_path_orig, targets_orig)
    except ManifestError as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        payload_orig = [dataclasses.asdict(e) for e in errors_orig]
        print(json.dumps(payload_orig, indent=2, ensure_ascii=False))
    else:
        for e in errors_orig:
            icon = "❌" if e.severity == "error" else "⚠️"
            print(f"{icon} [{e.code}] {e.file} — {e.message}")
        if not errors_orig:
            print("✅ All files are OKF-conformant.")
        else:
            errs_orig = sum(1 for e in errors_orig if e.severity == "error")
            warns_orig = sum(1 for e in errors_orig if e.severity == "warning")
            print(f"\n{errs_orig} error(s), {warns_orig} warning(s).")
    return code_orig


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


@beartype
def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with sub-commands.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="okflint",
        description="Compliance linter for OKF documentary bases.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- audit ----------------------------------------------------------------
    p_audit = subparsers.add_parser(
        "audit", help="Inventory and descriptive diagnostic of a base."
    )
    p_audit.add_argument(
        "--manifest",
        default=None,
        help="Path to the OKF manifest (use base.roots for multi-root scanning).",
    )
    p_audit.add_argument(
        "--bundle",
        default=None,
        help="Root of the bundle to audit (or sub-filter when --manifest is used).",
    )
    p_audit.add_argument(
        "--vault",
        default=None,
        help=(
            "Path to an okf-vault.json file (vault-wide mode) "
            "or root of the vault folder (wikilink resolution index)."
        ),
    )
    p_audit.add_argument(
        "--apply",
        action="store_true",
        help="Write the JSON report to .okflint/ (dated, auto-incremented).",
    )
    p_audit.set_defaults(func=_cmd_audit)

    # -- validate -------------------------------------------------------------
    p_validate = subparsers.add_parser(
        "validate", help="OKF compliance gate (exit 0 if conformant, 1 otherwise)."
    )
    p_validate.add_argument(
        "--manifest",
        default=None,
        help="Path to the OKF manifest (default: okf-base.yaml).",
    )
    p_validate.add_argument(
        "--vault",
        default=None,
        help=(
            "Path to an okf-vault.json file.  Without --manifest, validates "
            "every bundle with its own manifest using a vault-wide union index."
        ),
    )
    p_validate.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="JSON output (for CI).",
    )
    p_validate.add_argument(
        "targets",
        nargs="*",
        help="Files or directories to validate (default: all manifest roots).",
    )
    p_validate.set_defaults(func=_cmd_validate)

    return parser


@beartype
def main() -> None:
    """Console scripts entry point: okflint <command>."""
    parser = build_parser()
    args = parser.parse_args()
    code: int = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
