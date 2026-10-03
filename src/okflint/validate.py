"""Normative validation of OKF Markdown files — exit 0 if conformant, 1 otherwise."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from beartype import beartype

from okflint.cohesion import analyze_cohesion
from okflint.manifest import (
    HygieneConfig,
    Manifest,
    ManifestError,
    ProfileConfig,
    SplitConfig,
    TypeConfig,
    load_manifest,
)
from okflint.scanner import (
    MarkdownLink,
    WikiLink,
    _is_excluded,
    blank_code_spans,
    build_file_index,
    extract_headers,
    extract_markdown_links,
    extract_wikilinks,
    parse_frontmatter,
)

# ISO date pattern YYYY-MM-DD
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ISO 8601 datetime (date-only strings do not match — SPEC-002 §5 requires a
# time component for `generated.at` / `verified[].at`).
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)

# Actor convention (SPEC-002 §4): `<producer>/<version>`, `human:<id>`, or
# `process:<id>`. Existence of the designated identity is never verified.
_ACTOR_RE = re.compile(r"^(?:human:\S+|process:\S+|[^\s/:]+/[^\s/:]+)$")

# SPEC-002 §5.4's default `status` vocabulary (a SHOULD, not among §11's three
# MUSTs) — overridden by a profile's `status_values` for the concept's type.
_DEFAULT_STATUS_VALUES = frozenset({"draft", "stable", "deprecated"})

# OKF v0.1 default reserved file names, used whenever no manifest overrides
# them via base.reserved_files. Single source of truth: callers with or
# without a loaded manifest must use this instead of re-declaring their own
# reserved-name set.
DEFAULT_RESERVED_FILES: dict[str, str] = {"index": "index.md", "log": "log.md"}

# OKF v0.2's one spec-prescribed concept type (SPEC-002 §7): hardcoded in the
# engine rather than manifest-declared, exactly like the reserved file names
# above are — the vocabulary comes from the spec, not from a producer.
_ATTESTED_COMPUTATION_TYPE = "Attested Computation"

# Re-export for importers (cli.py, audit.py)
__all__ = [
    "DEFAULT_RESERVED_FILES",
    "Diagnostic",
    "ManifestError",
    "dispatch_reserved_file",
    "run_validate",
]


@dataclass
class Diagnostic:
    """OKF validation error or warning."""

    code: str
    tier: str  # "core" | "profile" | "hygiene"
    severity: str  # "error" | "warning"
    file: str
    message: str


# ---------------------------------------------------------------------------
# Stage 1 — OKF core (always active)
# ---------------------------------------------------------------------------


@beartype
def check_core_concept(
    path: str,
    frontmatter: dict[str, Any] | None,
    *,
    okf_version: str = "0.2",
) -> list[Diagnostic]:
    """Check OKF core rules on a concept file.

    Args:
        path: Relative file path (for messages).
        frontmatter: Parsed frontmatter, or None if absent/invalid.
        okf_version: Resolved OKF version driving the base (see
            ``Manifest.resolved_okf_version``). Defaults to ``"0.2"``,
            matching the engine's default when no manifest is loaded
            (SPEC-002 §1). F003/F004/F005 only fire when this is ``"0.2"``:
            a base declaring ``"0.1"`` must be validated exactly as before
            v0.2 support was added.

    Returns:
        List of Diagnostic (F001, F002, and — on v0.2 — F003, F004, F005).
    """
    diags: list[Diagnostic] = []

    # F001: frontmatter absent or unparsable
    if frontmatter is None:
        diags.append(
            Diagnostic(
                code="F001",
                tier="core",
                severity="error",
                file=path,
                message="frontmatter absent or unparsable",
            )
        )
        return diags  # F002-F005 impossible without frontmatter

    # F002: type field absent or empty
    if "type" not in frontmatter or str(frontmatter["type"]).strip() == "":
        diags.append(
            Diagnostic(
                code="F002",
                tier="core",
                severity="error",
                file=path,
                message="`type` field absent or empty",
            )
        )

    if okf_version != "0.2":
        return diags

    # F003: `generated` present without `generated.by` (SPEC-002 §3a)
    if "generated" in frontmatter:
        generated = frontmatter["generated"]
        by = generated.get("by") if isinstance(generated, dict) else None
        if not by or str(by).strip() == "":
            diags.append(
                Diagnostic(
                    code="F003",
                    tier="core",
                    severity="error",
                    file=path,
                    message="`generated` present without `generated.by`",
                )
            )

    # F004: `sources` entries without `resource` (SPEC-002 §3a)
    if "sources" in frontmatter:
        sources = frontmatter["sources"]
        if not isinstance(sources, list) or not all(
            isinstance(entry, dict) for entry in sources
        ):
            diags.append(
                Diagnostic(
                    code="F004",
                    tier="core",
                    severity="error",
                    file=path,
                    message="`sources` must be a list of mappings",
                )
            )
        else:
            for index, entry in enumerate(sources):
                resource = entry.get("resource")
                if not resource or str(resource).strip() == "":
                    diags.append(
                        Diagnostic(
                            code="F004",
                            tier="core",
                            severity="error",
                            file=path,
                            message=f"`sources[{index}]` missing `resource`",
                        )
                    )

    # F005: `Attested Computation` concept without `runtime` (SPEC-002 §3a, §7)
    if str(frontmatter.get("type", "")).strip() == _ATTESTED_COMPUTATION_TYPE:
        runtime = frontmatter.get("runtime")
        if not runtime or str(runtime).strip() == "":
            diags.append(
                Diagnostic(
                    code="F005",
                    tier="core",
                    severity="error",
                    file=path,
                    message=(
                        f"`{_ATTESTED_COMPUTATION_TYPE}` concept without `runtime`"
                    ),
                )
            )

    return diags


@beartype
def check_core_reserved_index(
    path: str,
    content: str,
    is_root_index: bool,
) -> list[Diagnostic]:
    """Check R001 rule on an index.md file.

    Args:
        path: Relative file path.
        content: Raw file content.
        is_root_index: True if the file is at a root's directory level.

    Returns:
        List of Diagnostic (R001).
    """
    diags: list[Diagnostic] = []
    fm, _ = parse_frontmatter(content)

    if fm is None:
        return diags  # no frontmatter → conformant

    # Frontmatter present: only allowed at root AND with only okf_version
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
                    "frontmatter forbidden in index.md "
                    "(only `okf_version` allowed at root)"
                ),
            )
        )

    return diags


@beartype
def check_core_reserved_log(
    path: str,
    content: str,
) -> list[Diagnostic]:
    """Check R002 rule on a log.md file.

    Args:
        path: Relative file path.
        content: Raw file content.

    Returns:
        List of Diagnostic (R002).
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
                    message=f"non-ISO date heading in log.md: `{h.text}`",
                )
            )

    return diags


@beartype
def dispatch_reserved_file(
    path: str,
    file_path: Path,
    content: str,
    *,
    reserved_files: dict[str, str],
    is_root: bool,
) -> list[Diagnostic] | None:
    """Route a file to its reserved-file check, or signal it is a concept file.

    Single source of truth for "is this file reserved, and if so which rule
    applies": both the manifest-driven path (``validate_file``) and the
    manifest-less path (``run_audit``) must go through this instead of each
    deciding independently which names are reserved — that duplication is
    what let F001 fire on reserved files in the manifest-less audit path.

    Args:
        path: Relative file path (for diagnostic messages).
        file_path: Absolute path of the file; its basename is matched
            against ``reserved_files``.
        content: Raw file content.
        reserved_files: Mapping with "index"/"log" keys to their configured
            filename. Pass ``manifest.base.reserved_files`` when a manifest
            is loaded, ``DEFAULT_RESERVED_FILES`` otherwise.
        is_root: True if the file sits directly under the applicable root
            (manifest root, or bundle root when there is no manifest). Only
            affects R001's root exemption for `okf_version`.

    Returns:
        Diagnostics from R001/R002 if the file is reserved (possibly empty
        if conformant), or None if the file is not reserved and the caller
        should fall through to the normal concept-file check.
    """
    reserved_idx = reserved_files.get("index", "index.md")
    reserved_log = reserved_files.get("log", "log.md")

    if file_path.name == reserved_idx:
        return check_core_reserved_index(path, content, is_root)

    if file_path.name == reserved_log:
        return check_core_reserved_log(path, content)

    return None


# ---------------------------------------------------------------------------
# Stage 2 — Profile
# ---------------------------------------------------------------------------


def _resolve_type(
    val_type: str,
    profile: ProfileConfig,
) -> tuple[str | None, str | None]:
    """Resolve a declared type to a canonical profile key.

    Priority: exact match → case-insensitive → aliases (case-insensitive).

    Args:
        val_type: Value of the type field in the frontmatter.
        profile: Profile configuration.

    Returns:
        Tuple (type_key, f106_message) where type_key is None if not found.
    """
    # 1. Exact match
    if val_type in profile.types:
        return val_type, None

    # 2. Case-insensitive match on keys
    for k in profile.types:
        if k.lower() == val_type.lower():
            return k, None

    # 3. Search in aliases (case-insensitive)
    for k, cfg in profile.types.items():
        for alias in cfg.aliases:
            if alias.lower() == val_type.lower():
                msg = f"non-normalised `type` spelling: `{val_type}` → use `{k}`"
                return k, msg

    return None, None


@beartype
def check_profile(
    path: str,
    frontmatter: dict[str, Any],
    profile: ProfileConfig,
) -> list[Diagnostic]:
    """Check profile rules on a concept file.

    Args:
        path: Relative file path.
        frontmatter: Parsed frontmatter (not None).
        profile: Profile configuration.

    Returns:
        List of Diagnostic (F101, F102, F105, F106, S102).
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
                message=f"`type` value not in declared types: `{val_type}`",
            )
        )
        return diags  # no further checks without a resolved type

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

    # F102 — missing required fields (except "type" already checked)
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
                    message=f"missing required field: `{req_field}`",
                )
            )

    # F105 — controlled vocabulary violation (any property declaring `<prop>_values`)
    for prop, allowed in type_cfg.controlled_values.items():
        if prop not in frontmatter:
            continue
        raw_value = frontmatter[prop]
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        if any(v not in allowed for v in values):
            diags.append(
                Diagnostic(
                    code="F105",
                    tier="profile",
                    severity="error",
                    file=path,
                    message=(
                        f"value outside vocabulary: "
                        f"`{prop}={raw_value}` (allowed: {allowed})"
                    ),
                )
            )

    # S102 — incorrectly formatted dates
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
                            f"incorrectly formatted date: `{date_field}={val}` "
                            f"(expected YYYY-MM-DD)"
                        ),
                    )
                )

    return diags


# ---------------------------------------------------------------------------
# Stage 3 — Hygiene
# ---------------------------------------------------------------------------


@beartype
def check_hygiene_unknown_fields(
    path: str,
    frontmatter: dict[str, Any],
    type_cfg: TypeConfig,
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Check for unknown frontmatter fields (F201).

    Args:
        path: Relative file path.
        frontmatter: Parsed frontmatter.
        type_cfg: Configuration of the resolved type.
        level: Control level (off | warn | error).

    Returns:
        List of Diagnostic (F201).
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
            message=f"unknown field in frontmatter: `{f}`",
        )
        for f in sorted(unknown)
    ]


def _verified_entries(raw: Any) -> list[dict[str, Any]]:
    """Normalise `verified` for iteration, without flagging its own shape.

    SPEC-002 §5: `verified` is either a list of `{by, at}` events, or a bare
    mapping (single verifier, no list dash) that MUST be treated as a
    one-element list and MUST NOT be flagged for taking that shorthand form.

    Args:
        raw: Raw value of the `verified` field, or None if absent.

    Returns:
        List of verifier mappings to inspect (empty if absent or malformed).
    """
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    return []


def _check_s207_attested_computation(
    path: str,
    frontmatter: dict[str, Any],
    safe_body: str,
    severity: Literal["warning", "error"],
) -> list[Diagnostic]:
    """Check the `Attested Computation` contract shape (S207).

    Args:
        path: Relative file path.
        frontmatter: Parsed frontmatter of an `Attested Computation` concept.
        safe_body: Markdown body with code spans/fences blanked.
        severity: Severity to attach to each diagnostic (warning | error).

    Returns:
        List of Diagnostic (S207).
    """
    diags: list[Diagnostic] = []

    parameters = frontmatter.get("parameters")
    if parameters is not None:
        valid = isinstance(parameters, list) and all(
            isinstance(p, dict) and {"name", "type", "required"} <= set(p.keys())
            for p in parameters
        )
        if not valid:
            diags.append(
                Diagnostic(
                    code="S207",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=(
                        "`parameters` should be a list of "
                        "`{name, type, required}` entries"
                    ),
                )
            )

    executor = frontmatter.get("executor")
    if isinstance(executor, dict):
        missing = []
        if not executor.get("resource"):
            missing.append("resource")
        receipt = executor.get("receipt")
        if not isinstance(receipt, list) or not receipt:
            missing.append("receipt")
        if missing:
            diags.append(
                Diagnostic(
                    code="S207",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"`executor` should carry {' and '.join(missing)}",
                )
            )

    attester = frontmatter.get("attester")
    if isinstance(attester, dict) and not attester.get("resource"):
        diags.append(
            Diagnostic(
                code="S207",
                tier="hygiene",
                severity=severity,
                file=path,
                message="`attester` should carry `resource`",
            )
        )

    has_field = bool(frontmatter.get("computation"))
    has_block = any(
        h.level == 1 and h.text.strip() == "Computation"
        for h in extract_headers(safe_body)
    )
    if has_field and has_block:
        diags.append(
            Diagnostic(
                code="S207",
                tier="hygiene",
                severity=severity,
                file=path,
                message=(
                    "both a `computation` field and a `# Computation` block are present"
                ),
            )
        )
    elif not has_field and not has_block:
        diags.append(
            Diagnostic(
                code="S207",
                tier="hygiene",
                severity=severity,
                file=path,
                message=(
                    "neither a `computation` field nor a `# Computation` "
                    "block is present"
                ),
            )
        )

    return diags


@beartype
def check_hygiene_okf_v02_shapes(
    path: str,
    frontmatter: dict[str, Any],
    safe_body: str,
    level: Literal["off", "warn", "error"],
    *,
    type_cfg: TypeConfig | None = None,
    date_fields: list[str] | None = None,
    okf_version: str = "0.2",
) -> list[Diagnostic]:
    """Check OKF v0.2 shape hygiene rules (S203-S207, S210).

    Args:
        path: Relative file path.
        frontmatter: Parsed frontmatter (not None).
        safe_body: Markdown body with code spans/fences blanked.
        level: Control level (off | warn | error), from
            `hygiene.okf_v02_shapes`.
        type_cfg: Resolved profile type configuration, if any. Used to
            neutralise S203 when the type declares a `status_values`
            controlled vocabulary (the producer's profile overrides the
            spec's default `status` vocabulary).
        date_fields: `profile.date_fields`, if a profile is declared. Used
            to avoid double-reporting `stale_after` when it is already
            covered by S102.
        okf_version: Resolved OKF version driving the base. Defaults to
            `"0.2"`. S203-S207 only fire when this is `"0.2"`: a base
            declaring `"0.1"` must be validated exactly as before v0.2
            support was added.

    Returns:
        List of Diagnostic (S203, S204, S205, S206, S207, S210).
    """
    if level == "off" or okf_version != "0.2":
        return []

    severity: Literal["warning", "error"] = "warning" if level == "warn" else "error"
    date_fields = date_fields or []
    diags: list[Diagnostic] = []

    # S203 — status outside draft|stable|deprecated
    status = frontmatter.get("status")
    status_overridden = type_cfg is not None and "status" in type_cfg.controlled_values
    if status is not None and not status_overridden:
        if str(status) not in _DEFAULT_STATUS_VALUES:
            diags.append(
                Diagnostic(
                    code="S203",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"`status` outside draft|stable|deprecated: `{status}`",
                )
            )

    # S204 — stale_after not YYYY-MM-DD (S102 already covers it if declared
    # in profile.date_fields — do not double-report)
    if "stale_after" in frontmatter and "stale_after" not in date_fields:
        val = frontmatter["stale_after"]
        if val and not _ISO_DATE_RE.match(str(val)):
            diags.append(
                Diagnostic(
                    code="S204",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=(
                        f"`stale_after` incorrectly formatted: `{val}` "
                        f"(expected YYYY-MM-DD)"
                    ),
                )
            )

    # S205 — generated.at / verified[].at not ISO 8601 datetime
    generated = frontmatter.get("generated")
    if isinstance(generated, dict) and generated.get("at"):
        val = str(generated["at"])
        if not _ISO_DATETIME_RE.match(val):
            diags.append(
                Diagnostic(
                    code="S205",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"`generated.at` not ISO 8601 datetime: `{val}`",
                )
            )
    for entry in _verified_entries(frontmatter.get("verified")):
        if entry.get("at"):
            val = str(entry["at"])
            if not _ISO_DATETIME_RE.match(val):
                diags.append(
                    Diagnostic(
                        code="S205",
                        tier="hygiene",
                        severity=severity,
                        file=path,
                        message=f"`verified[].at` not ISO 8601 datetime: `{val}`",
                    )
                )

    # S206 — generated.by / verified[].by outside the actor convention
    if isinstance(generated, dict) and generated.get("by"):
        val = str(generated["by"])
        if not _ACTOR_RE.match(val):
            diags.append(
                Diagnostic(
                    code="S206",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"`generated.by` outside actor convention: `{val}`",
                )
            )
    for entry in _verified_entries(frontmatter.get("verified")):
        if entry.get("by"):
            val = str(entry["by"])
            if not _ACTOR_RE.match(val):
                diags.append(
                    Diagnostic(
                        code="S206",
                        tier="hygiene",
                        severity=severity,
                        file=path,
                        message=f"`verified[].by` outside actor convention: `{val}`",
                    )
                )

    # S207 — Attested Computation contract shape
    if str(frontmatter.get("type", "")).strip() == _ATTESTED_COMPUTATION_TYPE:
        diags.extend(
            _check_s207_attested_computation(path, frontmatter, safe_body, severity)
        )

    # S210 — generated / verified present but not a structure (e.g. a JSON
    # string typed in Obsidian's Properties panel). An absent field is never
    # flagged: both families are optional.
    if generated is not None and not isinstance(generated, dict):
        diags.append(
            Diagnostic(
                code="S210",
                tier="hygiene",
                severity=severity,
                file=path,
                message=(
                    f"`generated` should be a mapping, got "
                    f"{type(generated).__name__}: `{generated}`"
                ),
            )
        )
    verified = frontmatter.get("verified")
    verified_ok = isinstance(verified, dict) or (
        isinstance(verified, list) and all(isinstance(e, dict) for e in verified)
    )
    if verified is not None and not verified_ok:
        diags.append(
            Diagnostic(
                code="S210",
                tier="hygiene",
                severity=severity,
                file=path,
                message=(
                    f"`verified` should be a mapping or a list of mappings, got "
                    f"{type(verified).__name__}: `{verified}`"
                ),
            )
        )

    return diags


@beartype
def check_hygiene_legacy_forms(
    path: str,
    frontmatter: dict[str, Any],
    safe_body: str,
    level: Literal["off", "warn", "error"],
    *,
    declared_okf_version: str | None = None,
    type_cfg: TypeConfig | None = None,
) -> list[Diagnostic]:
    """Check for residual OKF v0.1 forms in a v0.2 base (S208).

    Args:
        path: Relative file path.
        frontmatter: Parsed frontmatter (not None).
        safe_body: Markdown body with code spans/fences blanked.
        level: Control level (off | warn | error), from
            `hygiene.legacy_forms`.
        declared_okf_version: `manifest.okf_version` (the raw declared
            value, not the resolved one). S208 must stay silent on a base
            with no manifest or no declared version — resolving to "0.2"
            there would flag `timestamp` fields that predate v0.2 support
            entirely, exactly what this rule must avoid.
        type_cfg: Resolved profile type configuration, if any. Neutralises
            the `timestamp` sub-check when the field is declared in the
            type's `required` or `optional` list.

    Returns:
        List of Diagnostic (S208).
    """
    if level == "off" or declared_okf_version != "0.2":
        return []

    severity: Literal["warning", "error"] = "warning" if level == "warn" else "error"
    diags: list[Diagnostic] = []

    timestamp_declared = type_cfg is not None and (
        "timestamp" in type_cfg.required or "timestamp" in type_cfg.optional
    )
    if "timestamp" in frontmatter and not timestamp_declared:
        diags.append(
            Diagnostic(
                code="S208",
                tier="hygiene",
                severity=severity,
                file=path,
                message="legacy v0.1 form `timestamp` used instead of `generated.at`",
            )
        )

    has_citations = any(
        h.level == 1 and h.text.strip() == "Citations"
        for h in extract_headers(safe_body)
    )
    if has_citations:
        diags.append(
            Diagnostic(
                code="S208",
                tier="hygiene",
                severity=severity,
                file=path,
                message="legacy v0.1 `# Citations` list used instead of `sources`",
            )
        )

    return diags


@beartype
def check_hygiene_stale_content(
    path: str,
    frontmatter: dict[str, Any],
    level: Literal["off", "warn", "error"],
    *,
    okf_version: str = "0.2",
    evaluation_date: date | None = None,
) -> list[Diagnostic]:
    """Check whether `stale_after` has been reached or passed (S209).

    Args:
        path: Relative file path.
        frontmatter: Parsed frontmatter (not None).
        level: Control level (off | warn | error), from
            `hygiene.stale_content`.
        okf_version: Resolved OKF version driving the base. Defaults to
            `"0.2"`. S209 only fires when this is `"0.2"`, consistent with
            the rest of the OKF v0.2 shape family.
        evaluation_date: Date to evaluate staleness against. Defaults to
            `date.today()` when omitted; injectable so callers (and tests)
            can obtain reproducible verdicts.

    Returns:
        List of Diagnostic (S209).
    """
    if level == "off" or okf_version != "0.2":
        return []

    stale_after = frontmatter.get("stale_after")
    if not stale_after:
        return []

    val = str(stale_after)
    if not _ISO_DATE_RE.match(val):
        return []

    eval_date = evaluation_date or date.today()
    try:
        stale_date = date.fromisoformat(val)
    except ValueError:
        return []

    if eval_date < stale_date:
        return []

    severity: Literal["warning", "error"] = "warning" if level == "warn" else "error"
    return [
        Diagnostic(
            code="S209",
            tier="hygiene",
            severity=severity,
            file=path,
            message=(
                f"stale: `stale_after={val}` reached as of evaluation date "
                f"`{eval_date.isoformat()}`"
            ),
        )
    ]


@beartype
def check_hygiene_links(
    path: str,
    wikilinks: list[WikiLink],
    md_links: list[MarkdownLink],
    external_refs: set[str],
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Check for broken or ambiguous links (L001, L002, L003).

    Args:
        path: Relative file path.
        wikilinks: List of extracted WikiLinks.
        md_links: List of extracted MarkdownLinks.
        external_refs: Allowed out-of-base file names (lowercased).
        level: Control level (off | warn | error).

    Returns:
        List of Diagnostic (L001, L002, L003).
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
                    message=f"broken wikilink: [[{wl.target}]]",
                )
            )
        if wl.ambiguous:
            diags.append(
                Diagnostic(
                    code="L003",
                    tier="hygiene",
                    severity=severity,
                    file=path,
                    message=f"ambiguous wikilink: [[{wl.target}]]",
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
                    message=f"broken markdown link: {ml.target}",
                )
            )

    return diags


def _net_content_lines(content: str) -> int:
    """Count non-blank body lines after stripping the frontmatter block.

    Args:
        content: Full raw file content, frontmatter included.

    Returns:
        Number of body lines that are not blank/whitespace-only.
    """
    _, body = parse_frontmatter(content)
    return sum(1 for line in body.split("\n") if line.strip())


@beartype
def check_hygiene_structure(
    path: str,
    file_path: Path,
    applicable_root: Path,
    content: str,
    frontmatter: dict[str, Any] | None,
    split_config: SplitConfig,
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Check whether the file is a semantic-cohesion split candidate (S202).

    Gates (all must pass for the check to fire):
    - length: net content lines > split_config.min_lines
    - type: declared `type` not in split_config.exempt_types
    - path: not matched by split_config.exempt_paths
    - cohesion: more than one connected component at split_config.tau

    Args:
        path: Relative file path.
        file_path: Absolute path of the file (for path-exemption matching).
        applicable_root: Manifest root the file belongs to.
        content: Full raw file content, frontmatter included.
        frontmatter: Parsed frontmatter or None.
        split_config: S202 gate configuration (min_lines, exemptions, tau).
        level: Control level (off | warn | error).

    Returns:
        List of Diagnostic (S202).
    """
    if level == "off":
        return []

    if frontmatter is not None:
        file_type = str(frontmatter.get("type", ""))
        if file_type in split_config.exempt_types:
            return []

    if _is_excluded(file_path, applicable_root, split_config.exempt_paths):
        return []

    if _net_content_lines(content) <= split_config.min_lines:
        return []

    result = analyze_cohesion(content, tau=split_config.tau)
    if len(result.components) <= 1:
        return []

    severity = "warning" if level == "warn" else "error"
    n_clusters = len(result.components)
    return [
        Diagnostic(
            code="S202",
            tier="hygiene",
            severity=severity,
            file=path,
            message=f"S202 — split candidate ({n_clusters} cohesion clusters)",
        )
    ]


@beartype
def check_hygiene_reserved(
    roots: list[Path],
    reserved_config: dict[str, str],
    level: Literal["off", "warn", "error"],
) -> list[Diagnostic]:
    """Check for the presence of reserved files in each root (R201).

    Args:
        roots: List of base roots.
        reserved_config: Mapping logical_name → filename.
        level: Control level (off | warn | error).

    Returns:
        List of Diagnostic (R201).
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
                        message=f"reserved file missing in {root}: {filename}",
                    )
                )

    return diags


# ---------------------------------------------------------------------------
# Orchestrators
# ---------------------------------------------------------------------------


@beartype
def validate_file(
    file_path: Path,
    manifest: Manifest,
    base_index: dict[str, list[str]],
) -> list[Diagnostic]:
    """Orchestrate the full validation of a markdown file.

    Args:
        file_path: Absolute path of the file to validate.
        manifest: Loaded and validated OKF manifest.
        base_index: Base file index (name → paths).

    Returns:
        List of Diagnostic (empty if conformant).
    """
    content = file_path.read_text(encoding="utf-8")

    # Determine the applicable root
    applicable_root = manifest.base.roots[0].path
    for root_cfg in manifest.base.roots:
        try:
            file_path.relative_to(root_cfg.path)
            applicable_root = root_cfg.path
            break
        except ValueError:
            continue

    rel = str(file_path.relative_to(applicable_root))

    # Reserved files: specific handling, no concept check
    is_root = any(file_path.parent == r.path for r in manifest.base.roots)
    reserved_diags = dispatch_reserved_file(
        rel,
        file_path,
        content,
        reserved_files=manifest.base.reserved_files,
        is_root=is_root,
    )
    if reserved_diags is not None:
        return reserved_diags

    # Concept file
    fm, body = parse_frontmatter(content)
    diagnostics: list[Diagnostic] = []

    # OKF core
    core_diags = check_core_concept(rel, fm, okf_version=manifest.resolved_okf_version)
    diagnostics.extend(core_diags)

    # If F001 or F002 → skip subsequent stages
    if any(d.code in ("F001", "F002") for d in core_diags):
        return diagnostics

    # fm is necessarily non-None here (F001 did not fire)
    assert fm is not None

    safe_body = blank_code_spans(body)
    wikilinks = extract_wikilinks(safe_body, base_index)
    other_roots = [r.path for r in manifest.base.roots if r.path != applicable_root]
    md_links = extract_markdown_links(
        safe_body, file_path, applicable_root, other_roots
    )

    # Profile
    resolved_type_cfg: TypeConfig | None = None
    if manifest.profile is not None:
        profile_diags = check_profile(rel, fm, manifest.profile)
        diagnostics.extend(profile_diags)
        # Resolve type_cfg for F201 (hygiene unknown fields) and S203
        # (status_values override)
        type_key, _ = _resolve_type(str(fm.get("type", "")), manifest.profile)
        if type_key is not None:
            resolved_type_cfg = manifest.profile.types[type_key]

    # Hygiene
    if manifest.hygiene is not None:
        hygiene: HygieneConfig = manifest.hygiene

        # Links
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
            check_hygiene_structure(
                rel,
                file_path,
                applicable_root,
                content,
                fm,
                hygiene.split,
                hygiene.split_candidates,
            )
        )

        # Unknown fields (only if profile AND resolved type)
        if manifest.profile is not None and resolved_type_cfg is not None:
            diagnostics.extend(
                check_hygiene_unknown_fields(
                    rel, fm, resolved_type_cfg, hygiene.unknown_fields
                )
            )

        # OKF v0.2 shapes (S203-S207)
        diagnostics.extend(
            check_hygiene_okf_v02_shapes(
                rel,
                fm,
                safe_body,
                hygiene.okf_v02_shapes,
                type_cfg=resolved_type_cfg,
                date_fields=(
                    manifest.profile.date_fields if manifest.profile is not None else []
                ),
                okf_version=manifest.resolved_okf_version,
            )
        )

        # Legacy v0.1 forms (S208)
        diagnostics.extend(
            check_hygiene_legacy_forms(
                rel,
                fm,
                safe_body,
                hygiene.legacy_forms,
                declared_okf_version=manifest.okf_version,
                type_cfg=resolved_type_cfg,
            )
        )

        # Stale content (S209)
        diagnostics.extend(
            check_hygiene_stale_content(
                rel,
                fm,
                hygiene.stale_content,
                okf_version=manifest.resolved_okf_version,
            )
        )

    return diagnostics


@beartype
def run_validate(
    manifest_path: Path,
    targets: list[Path],
    *,
    vault_index: dict[str, list[str]] | None = None,
) -> tuple[list[Diagnostic], int]:
    """Orchestrate OKF validation over a list of targets.

    When ``vault_index`` is provided it is used as the wikilink resolution
    index instead of rebuilding one from the manifest roots, allowing the
    caller to pass a vault-wide union index built once for all bundles.

    Args:
        manifest_path: Path to the OKF YAML manifest.
        targets: Files or directories to validate. May be relative (e.g. to
            the process CWD); resolved to absolute internally to match the
            manifest's own resolved roots.
        vault_index: Pre-built file index (stem → list of relative paths).
            When provided, the per-manifest index build is skipped.

    Returns:
        Tuple (list of diagnostics, exit code 0 or 1).

    Raises:
        ManifestError: If the manifest is invalid or unreadable.
    """
    manifest = load_manifest(manifest_path)
    # Resolve here, once, so every downstream comparison (root matching,
    # relative_to in validate_file) is absolute-to-absolute, matching how
    # manifest.base.roots are already resolved.
    targets = [t.resolve() for t in targets]
    _root_paths = [r.path for r in manifest.base.roots]
    _excl_map: dict[Path, list[str]] = {
        r.path: r.exclude_patterns for r in manifest.base.roots if r.exclude_patterns
    }
    _base_index: dict[str, list[str]] = (
        vault_index
        if vault_index is not None
        else build_file_index(
            _root_paths,
            {r.path: r.exclude_patterns for r in manifest.base.roots},
        )
    )

    all_diagnostics: list[Diagnostic] = []

    for target in targets:
        if target.is_dir():
            # Find the manifest root this target belongs to (for exclusion patterns)
            applicable_root: Path | None = None
            for root_path in _root_paths:
                try:
                    target.relative_to(root_path)
                    applicable_root = root_path
                    break
                except ValueError:
                    continue
            patterns = _excl_map.get(applicable_root, []) if applicable_root else []
            if patterns and applicable_root is not None:
                md_files: list[Path] = [
                    f
                    for f in target.rglob("*.md")
                    if not _is_excluded(f, applicable_root, patterns)
                ]
            else:
                md_files = list(target.rglob("*.md"))
        else:
            md_files = [target]

        for md_file in md_files:
            all_diagnostics.extend(validate_file(md_file, manifest, _base_index))

    # Reserved hygiene (global check on roots)
    reserved_level: Literal["off", "warn", "error"] = (
        manifest.hygiene.reserved_files if manifest.hygiene is not None else "off"
    )
    all_diagnostics.extend(
        check_hygiene_reserved(
            _root_paths,
            manifest.base.reserved_files,
            reserved_level,
        )
    )

    code = 0 if not any(d.severity == "error" for d in all_diagnostics) else 1
    return all_diagnostics, code
