"""Point d'entrée CLI unifié d'okflint.

Expose deux sous-commandes façon Ruff :
    okflint audit     — inventaire et diagnostic descriptif d'une base
    okflint validate  — gate normatif de conformité (exit 0/1)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from beartype import beartype

from okflint.audit import run_audit
from okflint.validate import ManifestError, run_validate


def _cmd_audit(args: argparse.Namespace) -> int:
    """Exécute la sous-commande audit.

    Args:
        args: Namespace argparse (bundle, vault, apply).

    Returns:
        Code de sortie (toujours 0 : audit est descriptif).
    """
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
        print(f"Rapport : {out}")
    else:
        print("(dry-run — relancer avec --apply pour écrire le rapport JSON)")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Exécute la sous-commande validate.

    Args:
        args: Namespace argparse (manifest, json_output, targets).

    Returns:
        Code de sortie (0 si conforme, 1 si au moins une erreur).
    """
    manifest_path = Path(args.manifest)
    targets = [Path(t) for t in args.targets]
    try:
        errors, code = run_validate(manifest_path, targets)
    except ManifestError as exc:
        print(f"Erreur manifeste : {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        payload = [dataclasses.asdict(e) for e in errors]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for e in errors:
            icon = "❌" if e.severity == "error" else "⚠️"
            print(f"{icon} [{e.code}] {e.file} — {e.message}")
        if not errors:
            print("✅ Tous les fichiers sont conformes OKF.")
        else:
            errs = sum(1 for e in errors if e.severity == "error")
            warns = sum(1 for e in errors if e.severity == "warning")
            print(f"\n{errs} erreur(s), {warns} avertissement(s).")
    return code


@beartype
def build_parser() -> argparse.ArgumentParser:
    """Construit le parser argparse avec les sous-commandes.

    Returns:
        Le parser configuré.
    """
    parser = argparse.ArgumentParser(
        prog="okflint",
        description="Linter de conformité pour bases documentaires OKF.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- audit ----------------------------------------------------------------
    p_audit = subparsers.add_parser(
        "audit", help="Inventaire et diagnostic descriptif d'une base."
    )
    p_audit.add_argument(
        "--bundle",
        required=True,
        help="Racine du bundle à auditer.",
    )
    p_audit.add_argument(
        "--vault",
        required=True,
        help="Racine de la vault (pour l'index de résolution des wikilinks).",
    )
    p_audit.add_argument(
        "--apply",
        action="store_true",
        help="Écrit le rapport JSON dans .okflint/ (rapport daté auto-incrémenté).",
    )
    p_audit.set_defaults(func=_cmd_audit)

    # -- validate -------------------------------------------------------------
    p_validate = subparsers.add_parser(
        "validate", help="Gate de conformité OKF (exit 0 si conforme, 1 sinon)."
    )
    p_validate.add_argument(
        "--manifest",
        default="okf-base.yaml",
        help="Chemin du manifeste OKF (défaut : okf-base.yaml).",
    )
    p_validate.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Sortie JSON (pour CI).",
    )
    p_validate.add_argument(
        "targets",
        nargs="+",
        help="Fichiers ou dossiers à valider.",
    )
    p_validate.set_defaults(func=_cmd_validate)

    return parser


@beartype
def main() -> None:
    """Point d'entrée console_scripts : okflint <command>."""
    parser = build_parser()
    args = parser.parse_args()
    code: int = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
