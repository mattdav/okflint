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

from beartype import beartype

from okflint.audit import run_audit
from okflint.manifest import load_manifest
from okflint.validate import ManifestError, run_validate


def _cmd_audit(args: argparse.Namespace) -> int:
    """Execute the audit sub-command.

    Resolves bundle and vault roots from --manifest, --bundle/--vault, or both.
    Resolution rules (in priority order):
    - --manifest only: multi-root from manifest.base.roots
    - --bundle + --vault: single-root (backward compatible)
    - --manifest + --bundle: manifest roots with --bundle as a sub-filter
    - neither: error

    Args:
        args: argparse Namespace (manifest, bundle, vault, apply).

    Returns:
        Exit code (0 on success, 2 on configuration error).
    """
    has_manifest = args.manifest is not None
    has_bundle = args.bundle is not None
    has_vault = args.vault is not None

    bundle_paths: list[Path]
    vault_paths: list[Path]
    target_filter: Path | None = None

    if has_manifest:
        try:
            manifest = load_manifest(Path(args.manifest))
        except ManifestError as exc:
            print(f"Manifest error: {exc}", file=sys.stderr)
            return 2
        bundle_paths = manifest.base.roots
        vault_paths = manifest.base.roots
        if has_bundle:
            print(
                "Warning: Both --manifest and --bundle provided; "
                "--bundle used as target filter over manifest roots.",
                file=sys.stderr,
            )
            target_filter = Path(args.bundle)
    elif has_bundle and has_vault:
        bundle_paths = [Path(args.bundle)]
        vault_paths = [Path(args.vault)]
    else:
        print(
            "Error: Provide either --manifest or both --bundle and --vault.",
            file=sys.stderr,
        )
        return 2

    report = run_audit(bundle_paths, vault_paths, target_filter=target_filter)
    stats = report["stats"]
    n_concepts = stats["total_concept_files"]
    print(f"Files: {stats['total_files']} ({n_concepts} concepts)")
    print(f"OKF status: {stats['by_okf_status']}")
    wikilinks_broken = stats["broken_wikilinks"]
    print(f"Wikilinks: {stats['total_wikilinks']} of which {wikilinks_broken} broken")
    md_broken = stats["broken_markdown_links"]
    print(f"MD links: {stats['total_markdown_links']} of which {md_broken} broken")
    print(f"Split candidates: {stats['split_candidates']}")

    roots: list[dict[str, object]] = report.get("roots", [])
    if len(roots) > 1:
        print("\nPer-root:")
        for root_info in roots:
            print(f"  {root_info['path']}   {root_info['file_count']} files")

    if args.apply:
        from datetime import date

        outputs_dir = Path(".okflint")
        outputs_dir.mkdir(exist_ok=True)
        today = date.today().strftime("%Y-%m-%d")
        v = 1
        while (outputs_dir / f"{today}_audit_v{v}.json").exists():
            v += 1
        out = outputs_dir / f"{today}_audit_v{v}.json"
        out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Report: {out}")
    else:
        print("(dry-run — re-run with --apply to write the JSON report)")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Execute the validate sub-command.

    When no targets are given, all roots declared in the manifest are validated.
    The wikilink resolution index always spans all manifest roots.

    Args:
        args: argparse Namespace (manifest, json_output, targets).

    Returns:
        Exit code (0 if conformant, 1 if at least one error, 2 on manifest error).
    """
    manifest_path = Path(args.manifest)

    if args.targets:
        targets = [Path(t) for t in args.targets]
    else:
        try:
            manifest = load_manifest(manifest_path)
            targets = manifest.base.roots
        except ManifestError as exc:
            print(f"Manifest error: {exc}", file=sys.stderr)
            return 2

    try:
        errors, code = run_validate(manifest_path, targets)
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
        help="Root of the vault (for the wikilink resolution index).",
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
        default="okf-base.yaml",
        help="Path to the OKF manifest (default: okf-base.yaml).",
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
