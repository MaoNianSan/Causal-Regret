from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from synthetic import create_synthetic_fixture

from ..raw_data import PreparedRawData, prepare_raw_log, write_json
from .context import RunContext


@dataclass(frozen=True)
class InputSpec:
    path: Path
    kind: str


def resolve_input(context: RunContext, input_path: str | Path | None) -> InputSpec:
    if input_path is None:
        configured_input = context.project_root / str(context.config["input"]["raw_file"])
        if context.mode == "fast" and bool(context.config.get("fast", {}).get("synthetic_fixture", False)):
            resolved_input = create_synthetic_fixture(
                context.paths.audit / "synthetic_contract_fixture.tsv",
                seed=int(context.config["resampling"]["seed"]),
            )
            input_kind = "synthetic_contract_fixture"
        else:
            resolved_input = configured_input
            input_kind = "external_criteo_log"
    else:
        resolved_input = Path(input_path)
        input_kind = "explicit_input_override"
    if context.mode == "full" and input_kind == "synthetic_contract_fixture":
        raise RuntimeError("Full mode cannot use a synthetic fixture.")
    print(f"      Input: {resolved_input}")
    print(f"      Input kind: {input_kind}")
    print("      Status: PASS")
    return InputSpec(path=resolved_input, kind=input_kind)


def scan_input(context: RunContext, input_spec: InputSpec) -> PreparedRawData:
    prepared = prepare_raw_log(
        input_spec.path,
        context.config,
        mode=context.mode,
        progress=context.config["runtime"].get("progress_mode", "normal") != "quiet",
        apply_fast_hash_sample=(
            context.mode == "fast" and input_spec.kind != "synthetic_contract_fixture"
        ),
    )
    write_json(prepared.audit, context.paths.audit / "raw_input_audit.json")
    write_json(prepared.input_manifest, context.paths.audit / "input_manifest.json")
    print(f"      Candidate rows: {len(prepared.candidates):,}")
    print(f"      Impression cells before support filter: {len(prepared.impression_counts):,}")
    print("      Status: PASS")
    return prepared
