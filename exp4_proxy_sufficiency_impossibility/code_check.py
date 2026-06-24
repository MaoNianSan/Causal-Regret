"""Static project validation for the Exp4 contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import config


def run(run_dir: Path | None) -> bool:
    root = Path(__file__).resolve().parent
    required = [
        "main.py",
        "reproduce_all.py",
        "run_experiment4.py",
        "engine.py",
        "simulator.py",
        "policies.py",
        "aggregate_results.py",
        "plot_results.py",
        "make_tables.py",
        "self_check.py",
        "write_audit_report.py",
        "write_output_manifest.py",
        "README.md",
    ]
    source = "\n".join(
        (root / filename).read_text(encoding="utf-8")
        for filename in required
        if (root / filename).exists()
    )
    reproduce = (root / "reproduce_all.py").read_text(encoding="utf-8")
    legacy_paths = [
        "src/runner.py",
        "simulator_adapter.py",
        "proxy_models.py",
        "make_tables_exp4.py",
        "write_experiment_audit.py",
        "reproduce_fast.py",
        "reproduce_full.py",
        "__init__.py",
    ]
    forbidden_legacy_ids = [
        "measurement_proxy",
        "latent_oracle_diagnostic",
        "partial_label_ucb",
        "fig_exp4_primary_evidence",
        "fig_app_exp4_online_trajectory",
        "two_sided_bootstrap_p",
    ]
    checks = [
        ("standalone entry point", (root / "main.py").exists()),
        (
            "canonical reproduce-all entry point",
            "from main import main" in reproduce and "main()" in reproduce,
        ),
        ("no external common package dependency", "common." not in source),
        (
            "all required scripts present",
            all((root / filename).exists() for filename in required),
        ),
        (
            "redundant reproduction wrappers and package stub are removed",
            not any((root / filename).exists() for filename in legacy_paths),
        ),
        (
            "no obsolete method, figure, or pseudo-p-value identifiers remain",
            not any(token in source for token in forbidden_legacy_ids),
        ),
        (
            "method registry separates deployable, reference, and diagnostic roles",
            config.METHOD_REGISTRY["proxy_oracle_diagnostic"]["diagnostic_only"]
            and not config.METHOD_REGISTRY["proxy_oracle_diagnostic"]["deployable"]
            and config.METHOD_REGISTRY["source_labelled_reference"]["reference_role"]
            == "source_labelled_reference",
        ),
        (
            "observable history metadata matches arrival-feedback implementation",
            config.METHOD_REGISTRY["observable_history_surrogate"][
                "uses_arrival_feedback"
            ]
            is True,
        ),
        (
            "fast/full worker caps are 16/32",
            config.auto_workers("fast") <= 16 and config.auto_workers("full") <= 32,
        ),
        (
            "full paired inference reports confidence intervals only",
            "formal_full_paired_percentile_bootstrap_ci"
            in (root / "aggregate_results.py").read_text(encoding="utf-8")
            and "two_sided_bootstrap_p"
            not in (root / "aggregate_results.py").read_text(encoding="utf-8"),
        ),
        (
            "q by sigma phase map and source-reference normalization are implemented",
            "recoverability_phase_map" in source
            and "source_labelled_normalized_recovery" in source,
        ),
        (
            "warmup parameter is used in the primary metric",
            "regrets[config.WARMUP_T:]"
            in (root / "engine.py").read_text(encoding="utf-8"),
        ),
        (
            "q=1 action-trace audit covers source sweep and every phase-grid sigma",
            "action_trace_sha256" in (root / "engine.py").read_text(encoding="utf-8")
            and "phase-grid q=1 action trace"
            in (root / "self_check.py").read_text(encoding="utf-8"),
        ),
        (
            "phase summary is canonical and duplicate source-labelled summary is not emitted",
            "source_labelled_recovery_summary.csv"
            not in (root / "aggregate_results.py").read_text(encoding="utf-8"),
        ),
    ]
    print("\n".join(f"[{'PASS' if ok else 'FAIL'}] {name}" for name, ok in checks))
    if run_dir is not None:
        import pandas as pd

        pd.DataFrame(
            [
                {
                    "check_name": name,
                    "status": "PASSED" if ok else "FAILED",
                    "details": "static code check",
                }
                for name, ok in checks
            ]
        ).to_csv(run_dir / "checks" / "exp4_code_check_report.csv", index=False)
    return all(ok for _, ok in checks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()
    if not run(args.run_dir):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
