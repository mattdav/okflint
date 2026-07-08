"""Normative validation of OKF Markdown files — exit 0 if conformant, 1 otherwise."""

from __future__ import annotations

import re
from dataclasses import dataclass
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

# Re-export for importers (cli.py)
__all__ = ["Diagnostic", "ManifestError", "run_validate"]


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
) -> list[Diagnostic]:
    """Check OKF core rules on a concept file.

    Args:
        path: Relative file path (for messages).
        frontmatter: Parsed frontmatter, or None if absent/invalid.

    Returns:
        List of Diagnostic (F001, F002).
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
        return diags  # F002 impossible without frontmatter

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

    reserved_idx = manifest.base.reserved_files.get("index", "index.md")
    reserved_log = manifest.base.reserved_files.get("log", "log.md")

    # Reserved files: specific handling, no concept check
    if file_path.name == reserved_idx:
        is_root = any(file_path.parent == r.path for r in manifest.base.roots)
        return check_core_reserved_index(rel, content, is_root)

    if file_path.name == reserved_log:
        return check_core_reserved_log(rel, content)

    # Concept file
    fm, body = parse_frontmatter(content)
    diagnostics: list[Diagnostic] = []

    # OKF core
    core_diags = check_core_concept(rel, fm)
    diagnostics.extend(core_diags)

    # If F001 or F002 → skip subsequent stages
    if any(d.code in ("F001", "F002") for d in core_diags):
        return diagnostics

    # fm is necessarily non-None here (F001 did not fire)
    assert fm is not None

    safe_body = blank_code_spans(body)
    wikilinks = extract_wikilinks(safe_body, base_index)
    md_links = extract_markdown_links(safe_body, file_path, applicable_root)

    # Profile
    resolved_type_cfg: TypeConfig | None = None
    if manifest.profile is not None:
        profile_diags = check_profile(rel, fm, manifest.profile)
        diagnostics.extend(profile_diags)
        # Resolve type_cfg for F201 (hygiene unknown fields)
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
        targets: Files or directories to validate.
        vault_index: Pre-built file index (stem → list of relative paths).
            When provided, the per-manifest index build is skipped.

    Returns:
        Tuple (list of diagnostics, exit code 0 or 1).

    Raises:
        ManifestError: If the manifest is invalid or unreadable.
    """
    manifest = load_manifest(manifest_path)
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
