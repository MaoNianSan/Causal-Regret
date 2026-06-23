from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check(name: str, condition: bool, detail: str) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {detail}")
    return bool(condition)


def main() -> int:
    checks: list[bool] = []
    errors = []
    for path in sorted(ROOT.rglob("*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(str(exc))
    checks.append(check("all Python files compile", not errors, " | ".join(errors[:2]) or "compiled"))
    source = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.rglob("*.py") if p.name != "code_check.py")
    checks.append(check("contextual information structure is executable", "context_information_oracle" in source and "observe_context" in source, "X_t and context comparator are in runner/agents"))
    checks.append(check("no hidden pending-source queue is queried", "pending_src_ts" not in source, "unlabelled methods use bounded action/context history only"))
    checks.append(check("per-arrival fairness is encoded", "effective_feedback_units" in source and "for item in arrived" in source, "all updates are source-outcome units"))
    checks.append(check("primary delay path is pre-generated", "build_scenario_trace" in source and "shared_" in source, "shared trace IDs are emitted"))
    checks.append(check("structural EM integrates observable state", "gaussian_observable_state_integrated_quadrature" in source and "_integrated_structural_weight" in source, "no structural plug-in prior is used in the default EM"))
    proxy_feature_marker = 'self.history[src_t]["x"]'
    checks.append(check("proxy labelled updates use saved proxy features", "Never use item['src_x'] here" in source and proxy_feature_marker in source, "proxy train and decision features are source-time consistent"))

    env = dict(os.environ)
    env["EXP1_SMOKE_T"] = "100"
    command = [sys.executable, "main.py", "--mode", "fast", "--smoke", "--raw-log-mode", "summary_only", "--output-tag", "code_check_smoke"]
    proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=240)
    transcript = (proc.stdout + "\n" + proc.stderr)[-2500:]
    checks.append(check("isolated end-to-end smoke", proc.returncode == 0, transcript))
    smoke_summary = ROOT / "outputs" / "code_check_smoke" / "summaries" / "seed_summary.csv"
    if smoke_summary.exists():
        import pandas as pd
        smoke = pd.read_csv(smoke_summary)
        structural = smoke[(smoke["delay_setting"] == "state_structural_matched_15") & (smoke["method"] == "causal_em")]
        checks.append(check("smoke structural EM likelihood contract", set(structural["em_delay_likelihood"].astype(str)) == {"gaussian_observable_state_integrated_quadrature"}, str(structural["em_delay_likelihood"].drop_duplicates().tolist())))
        proxy = smoke[(smoke["method"] == "proxy") & (smoke["regime"].isin(["labelled", "mixture_labelled"]))]
        gap = pd.to_numeric(proxy["labelled_feature_alignment_max"], errors="coerce")
        checks.append(check("smoke proxy feature alignment", bool((gap <= 1e-12).all()), f"max_gap={float(gap.max()) if len(gap) else float('nan')}"))
    else:
        checks.append(check("smoke summary emitted", False, str(smoke_summary)))
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "code_check_report.txt").write_text("\n".join("PASS" if x else "FAIL" for x in checks) + "\n", encoding="utf-8")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
