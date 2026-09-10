"""Scope-safe, additive promotion of accepted Exp1 targeted artifacts.

The generic :mod:`promote` gate rebuilds ``outputs/paper_candidate`` from
scratch, copies broad ``outputs/full`` directories, and rewrites every copied
governance flag.  That is the correct behaviour for a *primary* promotion and
the wrong behaviour for a *targeted manuscript extension*, which must be added
to an existing, human-approved primary candidate without replacing, restating,
or silently re-deriving it.

This module is therefore deliberately narrow:

* it never deletes, re-creates, or rebuilds ``outputs/paper_candidate``;
* it copies only an explicit allowlist of accepted targeted artifacts;
* it rewrites only governance cells/fields in the destination copies, so every
  scientific column and every nested scientific payload stays byte-identical;
* it keeps ``analysis_tier = targeted`` and never relabels the ``outputs/full``
  sources as paper results;
* it binds authorization to the exact accepted snapshot (source run id,
  scientific-generation hash, validation hash, targeted validation report hash,
  cancellation invariant hash) instead of "the latest approved memo";
* it fails closed: without a current, scope-specific human authorization it
  stops after the dry run at ``TARGETED_PROMOTION_READY_EXCEPT_AUTHORIZATION``.

Diagnosis and dry run are always safe; the mutating path is only reachable
through :func:`promote`, which refuses to run without that authorization.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from src.artifact_io import (
    atomic_write_json,
    exp1_stage_source_hashes,
    hash_payload,
    sha256_file,
    utc_now,
)


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS = PROJECT_ROOT / "outputs"
STATUS = PROJECT_ROOT / "status"

FULL_ROOT = OUTPUTS / "full"
CANDIDATE_ROOT = OUTPUTS / "paper_candidate"

PROMOTION_SCOPE = "targeted_extension"
PROMOTION_STAGE = "targeted_paper_promotion"
PROMOTION_MANIFEST_RELATIVE = "metadata/exp1_targeted_promotion_manifest.json"
PROMOTION_STATUS_RELATIVE = "status/targeted_paper_promotion_status.json"
CANDIDATE_LEDGER_RELATIVE = "metadata/artifact_manifest.json"

RUN_STATE_RELATIVE = "metadata/run_state.json"
VALIDATION_STATUS_RELATIVE = "status/full_validation_status.json"
TARGETED_STATUS_RELATIVE = "status/full_targeted_status.json"
TARGETED_REPORT_RELATIVE = "targeted/exp1_targeted_validation_report.json"
CANCELLATION_INVARIANTS_RELATIVE = "targeted/exp1_targeted_cancellation_invariants.json"
HORIZON_ROUTE_SUMMARY_RELATIVE = "targeted/exp1_targeted_horizon_route_summary.csv"
UTILIZATION_SUMMARY_RELATIVE = "derived/exp1_regret_stability_utilization_summary.csv"
FIGURE_DATA_RELATIVE = "figures/data/fig_exp1_appendix_targeted_cancellation_data.csv"

BYTE_COPY = "byte_copy"
PAPER_FLAG_ONLY = "paper_flag_only"
METADATA_GOVERNANCE_UPDATE = "metadata_governance_update"
CANDIDATE_LEDGER_REFRESH = "candidate_ledger_refresh"

# ``analysis_tier`` is never written by this module: the accepted targeted tier
# must survive promotion, and the dual-tier utilization containers must keep
# whatever tier they already declare.
CSV_GOVERNANCE_TARGETS = {"paper_result": "True", "run_tier": "paper"}
JSON_GOVERNANCE_TARGETS = {
    "paper_result": True,
    "run_tier": "paper",
    "promotion_scope": PROMOTION_SCOPE,
}

CANCELLATION_GATES = (
    "C1_pure_shared",
    "C2_shared_amplitude_invariance",
    "C3_profile_invariance",
    "C4_delta_margin_ratio",
    "C5_choice_threshold",
    "C6_no_clipping_no_learner",
)

# The publication registry resolves Exp1 to ``outputs/paper_candidate``, and the
# targeted appendix figure reads exactly these two paths from that root.  They
# are declared here so the dry run can report the publication-mode dependency
# without importing the presentation layer.
PUBLICATION_REQUIREMENTS = (
    "targeted/exp1_targeted_cancellation_summary.csv",
    "derived/exp1_regret_stability_utilization_summary.csv",
)

# Every destination this module may write must sit in one of these
# targeted-extension namespaces.  The check exists so that a future allowlist
# edit cannot silently start overwriting a primary scientific artifact.
TARGETED_EXTENSION_DESTINATION_PREFIXES = (
    "targeted/",
    "derived/exp1_regret_stability_utilization",
    "figures/data/fig_exp1_appendix_targeted_cancellation",
    "figures/metadata/fig_exp1_appendix_targeted_cancellation",
    "figures/pdf/fig_exp1_appendix_targeted_cancellation",
    "figures/png/fig_exp1_appendix_targeted_cancellation",
)


def _is_targeted_extension_destination(relative_path: str) -> bool:
    return relative_path.startswith(TARGETED_EXTENSION_DESTINATION_PREFIXES)


# Authorization fields that must be bound, exactly, to the accepted snapshot.
AUTHORIZATION_BINDING_KEYS = (
    "authorized_promotion_scope",
    "authorized_source_run_id",
    "authorized_scientific_generation_hash",
    "authorized_validation_hash",
    "authorized_targeted_validation_report_sha256",
    "authorized_cancellation_invariants_sha256",
)


@dataclass(frozen=True)
class AllowlistEntry:
    """One accepted targeted artifact and its declared destination transform."""

    relative_path: str
    transform: str
    rationale: str


TARGETED_ALLOWLIST: tuple[AllowlistEntry, ...] = (
    AllowlistEntry(
        TARGETED_REPORT_RELATIVE,
        METADATA_GOVERNANCE_UPDATE,
        "Accepted targeted gate record: C1-C6, horizon-route map, theory sweeps.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_cancellation_summary.csv",
        PAPER_FLAG_ONLY,
        "Cancellation summary consumed by the targeted appendix figure.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_cancellation_sweep.csv",
        PAPER_FLAG_ONLY,
        "Row-level cancellation sweep; carries no governance columns.",
    ),
    AllowlistEntry(
        CANCELLATION_INVARIANTS_RELATIVE,
        METADATA_GOVERNANCE_UPDATE,
        "Cancellation invariant payload; the nested evidence block is never rewritten.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_horizon_route_seed_metrics.csv",
        PAPER_FLAG_ONLY,
        "Seed-level horizon-route metrics referenced by the validation report.",
    ),
    AllowlistEntry(
        HORIZON_ROUTE_SUMMARY_RELATIVE,
        PAPER_FLAG_ONLY,
        "Horizon-route summary referenced by the validation report.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_horizon_seed_metrics.csv",
        PAPER_FLAG_ONLY,
        "Pre-existing targeted contract file, refreshed to the accepted snapshot.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_horizon_summary.csv",
        PAPER_FLAG_ONLY,
        "Pre-existing targeted contract file, refreshed to the accepted snapshot.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_mean_delay_seed_metrics.csv",
        PAPER_FLAG_ONLY,
        "Pre-existing targeted contract file, refreshed to the accepted snapshot.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_mean_delay_summary.csv",
        PAPER_FLAG_ONLY,
        "Pre-existing targeted contract file, refreshed to the accepted snapshot.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_theory_exact_shift_sweep.csv",
        PAPER_FLAG_ONLY,
        "Pre-existing targeted contract file, refreshed to the accepted snapshot.",
    ),
    AllowlistEntry(
        "targeted/exp1_targeted_theory_margin_threshold_sweep.csv",
        PAPER_FLAG_ONLY,
        "Pre-existing targeted contract file, refreshed to the accepted snapshot.",
    ),
    AllowlistEntry(
        "targeted/fig_exp1_targeted_validation_data.csv",
        PAPER_FLAG_ONLY,
        "Pre-existing targeted validation figure data, refreshed to the accepted snapshot.",
    ),
    AllowlistEntry(
        UTILIZATION_SUMMARY_RELATIVE,
        PAPER_FLAG_ONLY,
        "Realized stability utilization summary required by the targeted appendix.",
    ),
    AllowlistEntry(
        "derived/exp1_regret_stability_utilization.csv",
        PAPER_FLAG_ONLY,
        "Row-level realized stability utilization behind the summary.",
    ),
    AllowlistEntry(
        FIGURE_DATA_RELATIVE,
        PAPER_FLAG_ONLY,
        "Accepted full-run targeted cancellation figure data.",
    ),
    AllowlistEntry(
        "figures/metadata/fig_exp1_appendix_targeted_cancellation_metadata.json",
        METADATA_GOVERNANCE_UPDATE,
        "Accepted full-run targeted cancellation figure metadata.",
    ),
    AllowlistEntry(
        "figures/pdf/fig_exp1_appendix_targeted_cancellation.pdf",
        BYTE_COPY,
        "Accepted full-run targeted cancellation figure (vector).",
    ),
    AllowlistEntry(
        "figures/png/fig_exp1_appendix_targeted_cancellation.png",
        BYTE_COPY,
        "Accepted full-run targeted cancellation figure (raster).",
    ),
)


ALLOWLIST_PATHS = tuple(entry.relative_path for entry in TARGETED_ALLOWLIST)


def _memo_metadata(path: Path) -> dict[str, str]:
    """Parse ``- key: value`` metadata lines from a change memo."""
    metadata: dict[str, str] = {}
    pattern = re.compile(r"^\s*-\s*([A-Za-z0-9_]+)\s*:\s*(.*?)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            metadata[match.group(1).strip().lower()] = match.group(2).strip().strip('`"\'')
    return metadata


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_authorization_binding(
    full_root: Path | None = None, project_root: Path | None = None
) -> dict[str, str]:
    """Return the exact snapshot binding an authorization memo must declare."""
    full_root = full_root or FULL_ROOT
    project_root = project_root or PROJECT_ROOT
    run_state = _read_json(full_root / RUN_STATE_RELATIVE)
    validation = _read_json(project_root / VALIDATION_STATUS_RELATIVE)
    return {
        "authorized_promotion_scope": PROMOTION_SCOPE,
        "authorized_source_run_id": str(run_state["run_id"]),
        "authorized_scientific_generation_hash": str(
            validation["scientific_generation_source_hash"]
        ),
        "authorized_validation_hash": str(validation["validation_source_hash"]),
        "authorized_targeted_validation_report_sha256": sha256_file(
            full_root / TARGETED_REPORT_RELATIVE
        ),
        "authorized_cancellation_invariants_sha256": sha256_file(
            full_root / CANCELLATION_INVARIANTS_RELATIVE
        ),
    }


def promotion_authorization(
    full_root: Path | None = None, project_root: Path | None = None
) -> dict[str, object]:
    """Evaluate scope-specific authorization for the targeted extension.

    A memo authorizes this promotion only when it is approved, explicitly
    authorizes the *targeted* path, and repeats the exact snapshot binding.
    The approved primary-promotion memos are reported as stale rather than
    reused: they describe an earlier primary snapshot and say nothing about the
    accepted targeted extension.
    """
    full_root = full_root or FULL_ROOT
    project_root = project_root or PROJECT_ROOT
    binding = expected_authorization_binding(full_root, project_root)

    scoped: list[tuple[Path, dict[str, str], list[str]]] = []
    primary_authorizations: list[dict[str, object]] = []
    for path in sorted(project_root.glob("CHANGE_MEMO_EXP1_*.md")):
        metadata = _memo_metadata(path)
        if metadata.get("experiment_id", "exp1_alignment_transfer") != (
            "exp1_alignment_transfer"
        ):
            continue
        memo_scope = metadata.get("authorized_promotion_scope", "").strip()
        approved = metadata.get("approved_status", "").strip().lower() == "approved"
        if memo_scope == PROMOTION_SCOPE:
            mismatches = [
                key
                for key, value in binding.items()
                if metadata.get(key, "") != value
            ]
            scoped.append((path, metadata, mismatches))
        elif approved and metadata.get("paper_promotion_authorized", "").strip().upper() == "YES":
            primary_authorizations.append(
                {
                    "memo_id": metadata.get("memo_id", path.stem),
                    "memo_path": path.name,
                    "authorized_promotion_scope": memo_scope or None,
                    "snapshot_bound": any(
                        metadata.get(key) for key in AUTHORIZATION_BINDING_KEYS[1:]
                    ),
                }
            )

    result: dict[str, object] = {
        "status": "ABSENT",
        "present": False,
        "promotion_scope": PROMOTION_SCOPE,
        "memo_id": None,
        "memo_path": None,
        "expected_binding": binding,
        "legacy_primary_authorizations": primary_authorizations,
        "stale_authorization_reuse": (
            "BLOCKED" if primary_authorizations else "NONE_DETECTED"
        ),
    }

    if not scoped:
        result["reason"] = (
            "STALE_PRIMARY_PROMOTION_MEMO_DOES_NOT_AUTHORIZE_TARGETED_EXTENSION"
            if primary_authorizations
            else "NO_SCOPE_SPECIFIC_TARGETED_AUTHORIZATION_MEMO"
        )
        return result

    path, metadata, mismatches = max(
        scoped, key=lambda item: str(item[1].get("memo_id", item[0].stem))
    )
    result["memo_id"] = metadata.get("memo_id", path.stem)
    result["memo_path"] = path.name
    result["approved_status"] = metadata.get("approved_status")
    result["targeted_paper_promotion_authorized"] = metadata.get(
        "targeted_paper_promotion_authorized"
    )
    approved = metadata.get("approved_status", "").strip().lower() == "approved"
    scoped_authorized = (
        metadata.get("targeted_paper_promotion_authorized", "").strip().upper()
        == "YES"
    )
    if approved and scoped_authorized and not mismatches:
        result["status"] = "PRESENT"
        result["present"] = True
        result["reason"] = "CURRENT_SCOPE_SPECIFIC_TARGETED_AUTHORIZATION"
        return result
    result["authorization_mismatches"] = mismatches
    result["reason"] = (
        "TARGETED_AUTHORIZATION_SNAPSHOT_MISMATCH"
        if mismatches
        else "TARGETED_AUTHORIZATION_NOT_APPROVED_OR_NOT_GRANTED"
    )
    return result


# ---------------------------------------------------------------------------
# Governed copy helpers
# ---------------------------------------------------------------------------
def _csv_field_spans(line: str) -> list[tuple[int, int, bool]]:
    """Return ``(start, end, quoted)`` spans for one CSV record."""
    spans: list[tuple[int, int, bool]] = []
    index = 0
    length = len(line)
    while index <= length:
        start = index
        quoted = index < length and line[index] == '"'
        if quoted:
            index += 1
            while index < length:
                if line[index] == '"':
                    if index + 1 < length and line[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
        else:
            while index < length and line[index] != ",":
                index += 1
        spans.append((start, index, quoted))
        if index >= length:
            break
        index += 1
    return spans


def _render_csv_value(value: str, quoted: bool) -> str:
    if quoted or any(character in value for character in ',"\r\n'):
        return '"' + value.replace('"', '""') + '"'
    return value


def _rewrite_csv_governance_cells(
    text: str, targets: dict[str, str]
) -> tuple[str, list[str]]:
    """Rewrite only the named governance cells, preserving every other byte.

    The generic promotion path round-trips CSV files through pandas, which can
    restyle numeric fields.  Here the file is edited at the character level so
    that every non-governance cell is guaranteed to survive verbatim.
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return text, []
    header_line = lines[0]
    header_body = header_line.rstrip("\r\n")
    header = next(csv.reader(io.StringIO(header_body)))
    indexes = {
        name: position for position, name in enumerate(header) if name in targets
    }
    if not indexes:
        return text, []
    output = [header_line]
    for line in lines[1:]:
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        if not body:
            output.append(line)
            continue
        spans = _csv_field_spans(body)
        replacements = []
        for name, position in indexes.items():
            if position >= len(spans):
                continue
            start, end, quoted = spans[position]
            replacements.append(
                (start, end, _render_csv_value(targets[name], quoted))
            )
        for start, end, value in sorted(replacements, reverse=True):
            body = body[:start] + value + body[end:]
        output.append(body + ending)
    return "".join(output), [header[position] for position in sorted(indexes.values())]


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _apply_csv_governance(
    source: Path, destination: Path, targets: dict[str, str]
) -> dict[str, object]:
    text = _read_text(source)
    rewritten, updated = _rewrite_csv_governance_cells(text, targets)
    _write_text(destination, rewritten)
    return {
        "effective_transform": PAPER_FLAG_ONLY,
        "columns_updated": updated,
        "byte_identical_to_source": rewritten == text,
    }


def _apply_json_governance(
    source: Path, destination: Path, targets: dict[str, object]
) -> dict[str, object]:
    payload = _read_json(source)
    merged = dict(payload)
    merged.update(targets)
    updated = sorted(key for key, value in targets.items() if payload.get(key) != value)
    atomic_write_json(destination, merged)
    return {
        "effective_transform": METADATA_GOVERNANCE_UPDATE,
        "fields_updated": updated,
        "nested_payload_unchanged": True,
        "byte_identical_to_source": False,
    }


def _csv_rows(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(_read_text(path))))


def _verify_csv_payload(source: Path, destination: Path) -> None:
    """Every non-governance cell must be identical, as text."""
    source_rows = _csv_rows(source)
    destination_rows = _csv_rows(destination)
    if len(source_rows) != len(destination_rows):
        raise RuntimeError(
            f"CSV row count changed for {source.name}: "
            f"{len(source_rows)} -> {len(destination_rows)}"
        )
    header = source_rows[0]
    if header != destination_rows[0]:
        raise RuntimeError(f"CSV header changed for {source.name}")
    protected = [
        position
        for position, name in enumerate(header)
        if name not in CSV_GOVERNANCE_TARGETS
    ]
    for index, (source_row, destination_row) in enumerate(
        zip(source_rows[1:], destination_rows[1:]), start=1
    ):
        if len(source_row) != len(destination_row):
            raise RuntimeError(f"CSV field count changed for {source.name}:{index}")
        for position in protected:
            if source_row[position] != destination_row[position]:
                raise RuntimeError(
                    f"non-governance CSV cell changed in {source.name} "
                    f"at record {index}, column {header[position]!r}"
                )


def _verify_json_payload(source: Path, destination: Path) -> None:
    """Everything outside the top-level governance fields must be unchanged."""
    source_payload = dict(_read_json(source))
    destination_payload = dict(_read_json(destination))
    for key in JSON_GOVERNANCE_TARGETS:
        source_payload.pop(key, None)
        destination_payload.pop(key, None)
    if source_payload != destination_payload:
        changed = sorted(
            key
            for key in set(source_payload) | set(destination_payload)
            if source_payload.get(key) != destination_payload.get(key)
        )
        raise RuntimeError(
            f"JSON payload changed beyond governance fields in {source.name}: {changed}"
        )


# ---------------------------------------------------------------------------
# Readiness, plan, dry run
# ---------------------------------------------------------------------------
def primary_candidate_baseline(candidate_root: Path | None = None) -> dict[str, str]:
    """Hash every pre-existing candidate artifact except the targeted extension."""
    candidate_root = candidate_root or CANDIDATE_ROOT
    excluded = set(ALLOWLIST_PATHS) | {PROMOTION_MANIFEST_RELATIVE}
    baseline: dict[str, str] = {}
    if not candidate_root.exists():
        return baseline
    for path in sorted(candidate_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(candidate_root).as_posix()
        if relative in excluded:
            continue
        baseline[relative] = sha256_file(path)
    return baseline


def targeted_source_hashes(full_root: Path | None = None) -> dict[str, str]:
    full_root = full_root or FULL_ROOT
    return {
        entry.relative_path: sha256_file(full_root / entry.relative_path)
        for entry in TARGETED_ALLOWLIST
        if (full_root / entry.relative_path).is_file()
    }


def candidate_ledger_state(candidate_root: Path | None = None) -> dict[str, object]:
    """Report whether the candidate artifact ledger is present and maintainable.

    ``outputs/paper_candidate/metadata/artifact_manifest.json`` indexes the
    candidate artifacts, so a targeted promotion must refresh its own
    destination entries instead of leaving that index stale.
    """
    candidate_root = candidate_root or CANDIDATE_ROOT
    ledger_path = candidate_root / CANDIDATE_LEDGER_RELATIVE
    state: dict[str, object] = {
        "relative_path": CANDIDATE_LEDGER_RELATIVE,
        "path": ledger_path.as_posix(),
    }
    if not ledger_path.is_file():
        state["status"] = "ABSENT"
        return state
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:  # pragma: no cover - defensive
        state["status"] = "MALFORMED"
        state["reason"] = str(error)
        return state
    records = payload.get("artifacts") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        state["status"] = "MALFORMED"
        state["reason"] = "no artifact list"
        return state
    indexed = {str(item.get("path")) for item in records if isinstance(item, dict)}
    state["status"] = "OK"
    state["indexed_records"] = len(indexed)
    state["entries_to_refresh"] = [path for path in ALLOWLIST_PATHS if path in indexed]
    state["entries_to_add"] = [path for path in ALLOWLIST_PATHS if path not in indexed]
    return state


def maintain_candidate_ledger(
    candidate_root: Path | None = None,
    promoted_paths: list[str] | None = None,
) -> dict[str, object]:
    """Refresh only the candidate-ledger entries that belong to the promoted set.

    The candidate ledger is the index behind the frozen-science hygiene test.
    A targeted promotion legitimately changes the bytes of its own
    destinations, so those entries are refreshed here; every other entry must
    stay exactly as recorded, otherwise the promotion fails closed. An absent
    ledger stays absent: this path never invents candidate metadata.
    """
    candidate_root = candidate_root or CANDIDATE_ROOT
    promoted = list(dict.fromkeys(promoted_paths or list(ALLOWLIST_PATHS)))
    ledger_path = candidate_root / CANDIDATE_LEDGER_RELATIVE
    record: dict[str, object] = {
        "relative_path": CANDIDATE_LEDGER_RELATIVE,
        "transformation": CANDIDATE_LEDGER_REFRESH,
        "entries_refreshed": [],
        "entries_added": [],
    }
    state = candidate_ledger_state(candidate_root)
    if state["status"] == "ABSENT":
        record["status"] = "ABSENT"
        return record
    if state["status"] != "OK":
        raise RuntimeError(
            "Candidate ledger is not maintainable: "
            + json.dumps(
                {
                    "relative_path": CANDIDATE_LEDGER_RELATIVE,
                    "reason": state.get("reason"),
                }
            )
        )
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    records = payload["artifacts"]
    index: dict[str, dict[str, object]] = {
        str(item.get("path")): item for item in records if isinstance(item, dict)
    }
    before = {
        path: {"sha256": item.get("sha256"), "size_bytes": item.get("size_bytes")}
        for path, item in index.items()
    }
    ledger_hash_before = sha256_file(ledger_path)
    for relative in promoted:
        destination = candidate_root / relative
        if not destination.is_file():
            raise RuntimeError(f"Promoted destination missing before ledger update: {relative}")
        fresh: dict[str, object] = {
            "path": relative,
            "size_bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        }
        if relative in index:
            index[relative].update(fresh)
            record["entries_refreshed"].append(relative)
        else:
            records.append(fresh)
            index[relative] = fresh
            record["entries_added"].append(relative)
    after = {
        path: {"sha256": item.get("sha256"), "size_bytes": item.get("size_bytes")}
        for path, item in index.items()
    }
    unchanged = set(promoted)
    changed = sorted(
        path for path in before if path not in unchanged and before[path] != after.get(path)
    )
    if changed:
        raise RuntimeError(f"Non-promoted candidate ledger entries changed: {changed}")
    atomic_write_json(ledger_path, payload)
    reloaded = json.loads(ledger_path.read_text(encoding="utf-8"))
    reloaded_index = {
        str(item.get("path")): item
        for item in reloaded.get("artifacts", [])
        if isinstance(item, dict)
    }
    for relative in promoted:
        entry = reloaded_index.get(relative)
        if entry is None or entry.get("sha256") != sha256_file(candidate_root / relative):
            raise RuntimeError(f"Candidate ledger verification failed for {relative}")
    record.update(
        {
            "status": "REFRESHED",
            "sha256_before": ledger_hash_before,
            "sha256_after": sha256_file(ledger_path),
            "records_total": len(reloaded_index),
            "non_promoted_entries_unchanged": True,
        }
    )
    return record


def technical_readiness(
    full_root: Path | None = None,
    candidate_root: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, object]:
    """Evaluate every targeted-promotion gate without mutating any artifact."""
    full_root = full_root or FULL_ROOT
    candidate_root = candidate_root or CANDIDATE_ROOT
    project_root = project_root or PROJECT_ROOT

    validation_path = project_root / VALIDATION_STATUS_RELATIVE
    validation = _read_json(validation_path) if validation_path.exists() else {}
    targeted_status_path = project_root / TARGETED_STATUS_RELATIVE
    targeted_status = _read_json(targeted_status_path) if targeted_status_path.exists() else {}
    report_path = full_root / TARGETED_REPORT_RELATIVE
    report = _read_json(report_path) if report_path.exists() else {}
    invariants_path = full_root / CANCELLATION_INVARIANTS_RELATIVE
    invariants = _read_json(invariants_path) if invariants_path.exists() else {}
    cancellation = report.get("cancellation_sweep", {}) if report else {}
    gates = cancellation.get("gates", {}) if isinstance(cancellation, dict) else {}
    route_map = report.get("horizon_route_map", {}) if report else {}

    missing = [
        entry.relative_path
        for entry in TARGETED_ALLOWLIST
        if not (full_root / entry.relative_path).is_file()
    ]
    fallback_markers = [str(path) for path in full_root.rglob("*.fallback.json")]
    current_hashes = exp1_stage_source_hashes(project_root)

    baseline = primary_candidate_baseline(candidate_root)
    ledger_state = candidate_ledger_state(candidate_root)
    destinations = [candidate_root / entry.relative_path for entry in TARGETED_ALLOWLIST]
    candidate_root_resolved = candidate_root.resolve()

    checks = {
        "full_source_exists": full_root.is_dir(),
        "paper_candidate_exists": candidate_root.is_dir(),
        "full_validation_status_present": validation_path.exists(),
        "full_validation_engineering_pass": validation.get("engineering_status") == "PASS",
        "full_validation_scientific_pass": validation.get("scientific_status") == "PASS",
        "full_targeted_status_present": targeted_status_path.exists(),
        "full_targeted_status_pass": targeted_status.get("status") == "PASS",
        "targeted_validation_report_present": report_path.is_file(),
        "targeted_validation_status_pass": report.get("status") == "PASS",
        "targeted_analysis_tier_targeted": report.get("analysis_tier") == "targeted",
        "targeted_source_not_paper_result": report.get("paper_result") is False,
        "cancellation_gates_pass": all(gates.get(gate) is True for gate in CANCELLATION_GATES),
        "cancellation_grid_complete": bool(cancellation.get("n_cells"))
        and cancellation.get("grid_cells_per_seed", 0) * len(cancellation.get("seeds", []))
        == cancellation.get("n_cells"),
        "cancellation_invariants_present": invariants_path.is_file(),
        "cancellation_invariants_gates_present": all(
            gate in invariants.get("cancellation_sweep", {}) for gate in CANCELLATION_GATES
        ),
        "horizon_route_artifacts_present": (full_root / HORIZON_ROUTE_SUMMARY_RELATIVE).is_file()
        and (full_root / "targeted/exp1_targeted_horizon_route_seed_metrics.csv").is_file(),
        "horizon_route_stability_inequality_pass": route_map.get(
            "stability_inequality_pass"
        )
        is True,
        "stability_utilization_defined_rows": (route_map.get("utilization_defined_rows") or 0) > 0,
        "stability_utilization_summary_present": (
            full_root / UTILIZATION_SUMMARY_RELATIVE
        ).is_file(),
        "allowlist_files_present_in_full": not missing,
        "allowlist_has_no_duplicates": len(set(ALLOWLIST_PATHS)) == len(ALLOWLIST_PATHS),
        "allowlist_covers_publication_requirements": set(PUBLICATION_REQUIREMENTS)
        <= set(ALLOWLIST_PATHS),
        "scientific_generation_source_hash_unchanged": current_hashes[
            "scientific_generation_source_hash"
        ]
        == validation.get("scientific_generation_source_hash"),
        "validation_source_hash_unchanged": current_hashes["validation_source_hash"]
        == validation.get("validation_source_hash"),
        "no_parquet_fallback_markers": not fallback_markers,
        "primary_candidate_baseline_created": bool(baseline),
        "candidate_ledger_maintainable": ledger_state["status"] in {"OK", "ABSENT"},
        "destination_paths_deterministic": all(
            path.as_posix() == (candidate_root / entry.relative_path).as_posix()
            for path, entry in zip(destinations, TARGETED_ALLOWLIST)
        ),
        "destinations_stay_inside_candidate_root": all(
            candidate_root_resolved in path.resolve().parents for path in destinations
        ),
        "no_non_targeted_destination_would_be_overwritten": all(
            _is_targeted_extension_destination(entry.relative_path)
            for entry in TARGETED_ALLOWLIST
        ),
        "full_source_remains_nonpromoted": validation.get("paper_result") is False
        and targeted_status.get("paper_result") is False,
    }

    notes = {
        "reporting_source_hash_recorded": current_hashes["reporting_source_hash"],
        "reporting_source_hash_recorded_in_validation_status": validation.get(
            "reporting_source_hash"
        ),
        "reporting_source_hash_drift": current_hashes["reporting_source_hash"]
        != validation.get("reporting_source_hash"),
        "reporting_drift_is_non_blocking": True,
        "scientific_acceptance": "PASS" if report.get("status") == "PASS" else "UNKNOWN",
        "protected_primary_artifacts_hashed": len(baseline),
        "candidate_ledger_state": ledger_state["status"],
        "validation_status_generated_at": validation.get("generated_at"),
        "targeted_report_generated_at": report.get("generated_at"),
        "full_run_id": _read_json(full_root / RUN_STATE_RELATIVE).get("run_id")
        if (full_root / RUN_STATE_RELATIVE).is_file()
        else None,
    }

    passed = all(checks.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "notes": notes,
        "failed_checks": [name for name, value in checks.items() if not value],
        "missing_allowlist_files": missing,
        "fallback_markers": fallback_markers,
        "source_hashes": current_hashes,
        "primary_candidate_baseline": baseline,
        "candidate_ledger": ledger_state,
        "report": report,
    }


def _simulate_transform(entry: AllowlistEntry, source: Path) -> dict[str, object]:
    """Predict the destination transform without writing anything."""
    if entry.transform == BYTE_COPY:
        return {
            "declared_transform": BYTE_COPY,
            "effective_transform": BYTE_COPY,
            "byte_identical_to_source": True,
        }
    text = _read_text(source)
    if entry.transform == PAPER_FLAG_ONLY:
        rewritten, updated = _rewrite_csv_governance_cells(text, CSV_GOVERNANCE_TARGETS)
        return {
            "declared_transform": PAPER_FLAG_ONLY,
            "effective_transform": PAPER_FLAG_ONLY,
            "columns_updated": updated,
            "byte_identical_to_source": rewritten == text,
        }
    payload = _read_json(source)
    updated = sorted(
        key for key, value in JSON_GOVERNANCE_TARGETS.items() if payload.get(key) != value
    )
    return {
        "declared_transform": METADATA_GOVERNANCE_UPDATE,
        "effective_transform": METADATA_GOVERNANCE_UPDATE,
        "fields_updated": updated,
        "nested_payload_unchanged": True,
        "byte_identical_to_source": False,
    }


def promotion_plan(
    full_root: Path | None = None, candidate_root: Path | None = None
) -> dict[str, object]:
    full_root = full_root or FULL_ROOT
    candidate_root = candidate_root or CANDIDATE_ROOT
    files_to_copy: list[dict[str, object]] = []
    files_to_transform: list[dict[str, object]] = []
    byte_identical: list[str] = []
    source_hashes: dict[str, str] = {}
    records: list[dict[str, object]] = []

    for entry in TARGETED_ALLOWLIST:
        source = full_root / entry.relative_path
        destination = candidate_root / entry.relative_path
        if not source.is_file():
            records.append(
                {
                    "relative_path": entry.relative_path,
                    "declared_transform": entry.transform,
                    "present_in_source": False,
                }
            )
            continue
        source_hashes[entry.relative_path] = sha256_file(source)
        record: dict[str, object] = {
            "relative_path": entry.relative_path,
            "rationale": entry.rationale,
            "present_in_source": True,
            "destination_exists_now": destination.is_file(),
            "source_sha256": source_hashes[entry.relative_path],
            "source_size_bytes": source.stat().st_size,
        }
        record.update(_simulate_transform(entry, source))
        records.append(record)
        if entry.transform == BYTE_COPY:
            files_to_copy.append(record)
            byte_identical.append(entry.relative_path)
        else:
            files_to_transform.append(record)
            if record.get("byte_identical_to_source"):
                byte_identical.append(entry.relative_path)

    publication_requirements = []
    for relative in PUBLICATION_REQUIREMENTS:
        publication_requirements.append(
            {
                "relative_path": relative,
                "present_in_full": (full_root / relative).is_file(),
                "present_in_paper_candidate_now": (candidate_root / relative).is_file(),
                "in_allowlist": relative in ALLOWLIST_PATHS,
            }
        )

    return {
        "promotion_scope": PROMOTION_SCOPE,
        "files_to_copy": [record["relative_path"] for record in files_to_copy],
        "files_to_transform": [record["relative_path"] for record in files_to_transform],
        "files_to_leave_byte_identical": byte_identical,
        "source_hashes": source_hashes,
        "artifact_records": records,
        "publication_renderer_requirements_after_promotion": publication_requirements,
    }


def dry_run(
    full_root: Path | None = None,
    candidate_root: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, object]:
    """Report exactly what a targeted promotion would do; mutate nothing."""
    full_root = full_root or FULL_ROOT
    candidate_root = candidate_root or CANDIDATE_ROOT
    project_root = project_root or PROJECT_ROOT
    readiness = technical_readiness(full_root, candidate_root, project_root)
    authorization = promotion_authorization(full_root, project_root)
    plan = promotion_plan(full_root, candidate_root)
    ledger_state = candidate_ledger_state(candidate_root)
    ready_except_authorization = (
        readiness["status"] == "PASS" and not authorization["present"]
    )
    return {
        "stage": PROMOTION_STAGE,
        "promotion_scope": PROMOTION_SCOPE,
        "technical_readiness": readiness["status"],
        "scientific_acceptance": readiness["notes"]["scientific_acceptance"],
        "source_files_complete": readiness["checks"]["allowlist_files_present_in_full"],
        "source_hashes": plan["source_hashes"],
        "primary_candidate_preservation_baseline": {
            "protected_artifacts": len(readiness["primary_candidate_baseline"]),
            "excluded_destinations": list(ALLOWLIST_PATHS)
            + [PROMOTION_MANIFEST_RELATIVE],
        },
        "authorization_status": authorization["status"],
        "candidate_ledger_maintenance": ledger_state,
        "authorization": authorization,
        "files_to_copy": plan["files_to_copy"],
        "files_to_transform": plan["files_to_transform"],
        "files_to_leave_byte_identical": plan["files_to_leave_byte_identical"],
        "publication_renderer_requirements_after_promotion": plan[
            "publication_renderer_requirements_after_promotion"
        ],
        "artifact_records": plan["artifact_records"],
        "checks": readiness["checks"],
        "failed_checks": readiness["failed_checks"],
        "notes": readiness["notes"],
        "targeted_promotion_ready_except_authorization": ready_except_authorization,
        "actual_promotion_executed": False,
        "mutations_performed": [],
    }


def promote(
    full_root: Path | None = None,
    candidate_root: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, object]:
    """Copy the allowlisted targeted artifacts into the existing candidate.

    Fails closed: no technical gate failure and no missing scope-specific
    authorization can be bypassed, and the source tree and primary candidate
    are re-verified after the copy.
    """
    full_root = full_root or FULL_ROOT
    candidate_root = candidate_root or CANDIDATE_ROOT
    project_root = project_root or PROJECT_ROOT

    if candidate_root.resolve() == full_root.resolve():
        raise RuntimeError("Refusing to promote onto the source tree")
    readiness = technical_readiness(full_root, candidate_root, project_root)
    if readiness["status"] != "PASS":
        raise RuntimeError(
            f"Targeted promotion technical gates failed: {readiness['failed_checks']}"
        )
    authorization = promotion_authorization(full_root, project_root)
    if not authorization["present"]:
        raise RuntimeError(
            "Targeted promotion requires a current, scope-specific authorization: "
            + json.dumps(
                {
                    "status": authorization["status"],
                    "reason": authorization["reason"],
                    "memo_id": authorization["memo_id"],
                }
            )
        )

    binding = expected_authorization_binding(full_root, project_root)
    source_hashes_before = targeted_source_hashes(full_root)
    baseline_before = primary_candidate_baseline(candidate_root)
    promoted_at = utc_now()
    artifacts: list[dict[str, object]] = []

    for entry in TARGETED_ALLOWLIST:
        source = full_root / entry.relative_path
        destination = candidate_root / entry.relative_path
        existed_before = destination.is_file()
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_hash = sha256_file(source)
        if source_hash != source_hashes_before.get(entry.relative_path):
            raise RuntimeError(f"Source changed while planning: {entry.relative_path}")
        if entry.transform == BYTE_COPY:
            shutil.copyfile(source, destination)
            applied: dict[str, object] = {
                "effective_transform": BYTE_COPY,
                "columns_updated": [],
                "fields_updated": [],
            }
            if sha256_file(destination) != source_hash:
                raise RuntimeError(f"Byte copy diverged: {entry.relative_path}")
        elif entry.transform == PAPER_FLAG_ONLY:
            applied = _apply_csv_governance(source, destination, CSV_GOVERNANCE_TARGETS)
            _verify_csv_payload(source, destination)
        else:
            applied = _apply_json_governance(source, destination, JSON_GOVERNANCE_TARGETS)
            _verify_json_payload(source, destination)
        artifacts.append(
            {
                "relative_path": entry.relative_path,
                "source_path": (full_root / entry.relative_path).as_posix(),
                "source_sha256": source_hash,
                "destination_path": (candidate_root / entry.relative_path).as_posix(),
                "destination_sha256": sha256_file(destination),
                "destination_size_bytes": destination.stat().st_size,
                "declared_transform": entry.transform,
                "destination_existed_before": existed_before,
                "operation": "updated" if existed_before else "added",
                **applied,
            }
        )

    ledger_record = maintain_candidate_ledger(
        candidate_root, [entry.relative_path for entry in TARGETED_ALLOWLIST]
    )

    manifest = {
        "experiment_id": "exp1_alignment_transfer",
        "promotion_scope": PROMOTION_SCOPE,
        "analysis_tier": "targeted",
        "paper_result": True,
        "scientific_acceptance": "PASS",
        "source_root": "outputs/full",
        "destination_root": "outputs/paper_candidate",
        "source_run_id": binding["authorized_source_run_id"],
        "scientific_generation_source_hash": binding[
            "authorized_scientific_generation_hash"
        ],
        "validation_config_hash": binding["authorized_validation_hash"],
        "targeted_validation_report_sha256": binding[
            "authorized_targeted_validation_report_sha256"
        ],
        "cancellation_invariants_sha256": binding[
            "authorized_cancellation_invariants_sha256"
        ],
        "authorization_memo_id": authorization["memo_id"],
        "promoted_at": promoted_at,
        "primary_candidate_baseline_hash": hash_payload(baseline_before),
        "primary_candidate_protected_artifacts": len(baseline_before),
        "candidate_ledger": ledger_record,
        "artifacts": artifacts,
    }
    atomic_write_json(candidate_root / PROMOTION_MANIFEST_RELATIVE, manifest)
    atomic_write_json(
        project_root / PROMOTION_STATUS_RELATIVE,
        {
            "stage": PROMOTION_STAGE,
            "status": "PASS",
            "analysis_tier": "targeted",
            "paper_result": True,
            "promotion_scope": PROMOTION_SCOPE,
            "manifest": "outputs/paper_candidate/" + PROMOTION_MANIFEST_RELATIVE,
            "generated_at": utc_now(),
        },
    )

    source_hashes_after = targeted_source_hashes(full_root)
    baseline_after = primary_candidate_baseline(candidate_root)
    full_source_hash_preservation = source_hashes_after == source_hashes_before
    changed_primary = sorted(
        key
        for key in set(baseline_before) | set(baseline_after)
        if key != CANDIDATE_LEDGER_RELATIVE
        and baseline_before.get(key) != baseline_after.get(key)
    )
    ledger_maintained = ledger_record["status"] in {"REFRESHED", "ABSENT"}
    primary_paper_candidate_hash_preservation = not changed_primary and ledger_maintained
    if not full_source_hash_preservation:
        raise RuntimeError("Full-source hash preservation failed")
    if changed_primary:
        raise RuntimeError(
            f"Primary paper-candidate preservation failed: {changed_primary}"
        )
    if not ledger_maintained:
        raise RuntimeError("Candidate ledger was not maintained by the targeted promotion")
    if ledger_record["status"] == "ABSENT" and CANDIDATE_LEDGER_RELATIVE in baseline_after:
        raise RuntimeError("Candidate ledger appeared during the targeted promotion")
    if not (candidate_root / PROMOTION_MANIFEST_RELATIVE).is_file():
        raise RuntimeError("Targeted promotion manifest was not written")

    return {
        "stage": PROMOTION_STAGE,
        "status": "PASS",
        "promotion_scope": PROMOTION_SCOPE,
        "authorization_memo_id": authorization["memo_id"],
        "manifest_path": (candidate_root / PROMOTION_MANIFEST_RELATIVE).as_posix(),
        "status_path": (project_root / PROMOTION_STATUS_RELATIVE).as_posix(),
        "artifacts_promoted": len(artifacts),
        "full_source_hash_preservation": "PASS"
        if full_source_hash_preservation
        else "FAIL",
        "primary_paper_candidate_hash_preservation": (
            "PASS" if primary_paper_candidate_hash_preservation else "FAIL"
        ),
        "primary_candidate_protected_artifacts": len(baseline_before),
        "candidate_ledger": ledger_record,
        "promoted_at": promoted_at,
        "artifacts": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scope-safe additive promotion of Exp1 targeted artifacts."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args()
    project_root = args.project_root or PROJECT_ROOT
    full_root = project_root / "outputs" / "full"
    candidate_root = project_root / "outputs" / "paper_candidate"

    if args.dry_run:
        result = dry_run(full_root, candidate_root, project_root)
        print(json.dumps(result, indent=2, default=str))
        print("TECHNICAL_READINESS=" + str(result["technical_readiness"]))
        print("PROMOTION_AUTHORIZATION=" + str(result["authorization_status"]))
        if result["targeted_promotion_ready_except_authorization"]:
            print("TARGETED_PROMOTION_READY_EXCEPT_AUTHORIZATION")
        print("ACTUAL_PROMOTION_EXECUTED=FALSE")
        return

    result = promote(full_root, candidate_root, project_root)
    print("TARGETED_PAPER_PROMOTION_COMPLETE")
    print("promotion_scope=targeted_extension")
    print("analysis_tier=targeted")
    print("paper_result=true")
    print("manifest=" + str(result["manifest_path"]))


if __name__ == "__main__":
    main()
