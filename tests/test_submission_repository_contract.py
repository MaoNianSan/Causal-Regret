"""Read-only submission-companion contract tests.

These tests verify that the repository state matches the frozen canonical
paper results (baseline commit c363d3f6909b8cb2ee11a51796a027d9aa70ddf4)
without running any experiment or modifying any artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "publication" / "CR-EXP-OUTPUT-V1"

CANONICAL = {
    "exp1": ROOT / "exp1_alignment_transfer" / "outputs" / "paper_candidate",
    "exp2": (
        ROOT
        / "exp2_real_delayed_conversion_logs"
        / "outputs"
        / "paper"
        / "exp2-full-20260807T111616+0800"
    ),
    "exp3": ROOT / "exp3_sequential_recommendation_delayed_feedback" / "paper_candidate",
    "exp4": (
        ROOT
        / "exp4_controlled_route_audit"
        / "outputs"
        / "runs"
        / "full_20260817T071019Z_7d7146b7"
    ),
}

MAIN_FIGURES = {
    "exp1": "fig_exp1_alignment_transfer",
    "exp2": "figure_exp2_attribution_sensitivity",
    "exp3": "exp3_main_score_gap_ranking",
    "exp4": "fig_exp4_route_alignment_and_audit_reliability",
}

EXPERIMENT_DIR = {
    "exp1": "exp1_alignment_transfer",
    "exp2": "exp2_real_delayed_conversion_logs",
    "exp3": "exp3_sequential_recommendation_delayed_feedback",
    "exp4": "exp4_controlled_route_audit",
}

LONG_FORM_COLUMNS = [
    "metric_id",
    "estimand_id",
    "condition_id",
    "series_id",
    "point_estimate",
    "interval_lower",
    "interval_upper",
]

MAIN_CSV = {
    "exp1": PUB / "exp1_alignment_transfer" / "figures" / "main" / "data" / "fig_exp1_alignment_transfer.csv",
    "exp2": PUB / "exp2_real_delayed_conversion_logs" / "figures" / "main" / "data" / "figure_exp2_attribution_sensitivity.csv",
    "exp3": PUB / "exp3_sequential_recommendation_delayed_feedback" / "figures" / "main" / "data" / "exp3_main_score_gap_ranking.csv",
    "exp4": PUB / "exp4_controlled_route_audit" / "figures" / "main" / "data" / "fig_exp4_route_alignment_and_audit_reliability.csv",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", sorted(CANONICAL))
def test_canonical_result_root_exists(key: str) -> None:
    assert CANONICAL[key].is_dir(), CANONICAL[key]


def test_exp1_paper_result_flag() -> None:
    manifest = read_json(CANONICAL["exp1"] / "exp1_promotion_manifest.json")
    assert manifest["paper_result"] is True
    assert manifest["run_tier"] == "paper"
    assert manifest["scientific_status"] == "PASS"
    assert manifest["engineering_status"] == "PASS"


def test_exp2_paper_result_flag() -> None:
    manifest = read_json(CANONICAL["exp2"] / "run_manifest.json")
    assert manifest["paper_result"] is True
    assert manifest["paper_promotion_status"] == "PROMOTED"


def test_exp3_paper_result_flag() -> None:
    manifest = read_json(CANONICAL["exp3"] / "manifest.json")
    assert manifest["paper_result"] is True


def test_exp4_paper_result_flag() -> None:
    status = read_json(CANONICAL["exp4"] / "logs" / "exp4_result_status.json")
    assert status["paper_result"] is True
    assert status["paper_promotion"] == "PASS"
    assert status["result_schema"] == "exp4_controlled_route_audit_v3"


@pytest.mark.parametrize("key", sorted(MAIN_CSV))
def test_main_figure_csv_required_columns(key: str) -> None:
    path = MAIN_CSV[key]
    assert path.exists(), path
    frame = pd.read_csv(path)
    missing = [c for c in LONG_FORM_COLUMNS if c not in frame.columns]
    assert not missing, f"{path}: missing {missing}"
    assert len(frame) > 0


@pytest.mark.parametrize("key", sorted(MAIN_FIGURES))
def test_publication_main_figure_all_formats(key: str) -> None:
    fid = MAIN_FIGURES[key]
    base = PUB / EXPERIMENT_DIR[key] / "figures" / "main"
    for ext, suffix in (("pdf", ".pdf"), ("svg", ".svg"), ("png", ".png"), ("data", ".csv"), ("metadata", ".json")):
        path = base / ext / (fid + suffix)
        assert path.exists() and path.stat().st_size > 0, path


def test_exp2_uncertainty_is_not_ci() -> None:
    meta = read_json(
        PUB / "exp2_real_delayed_conversion_logs" / "figures" / "main" / "metadata" / "figure_exp2_attribution_sensitivity.json"
    )
    text = (str(meta.get("uncertainty_definition", "")) + " " + str(meta.get("uncertainty_semantics", ""))).lower()
    assert "resampling sensitivity range" in text
    assert "not a confidence interval" in text


def test_exp3_uncertainty_is_not_ci() -> None:
    meta = read_json(
        PUB / "exp3_sequential_recommendation_delayed_feedback" / "figures" / "main" / "metadata" / "exp3_main_score_gap_ranking.json"
    )
    text = (str(meta.get("uncertainty_definition", "")) + " " + str(meta.get("uncertainty_semantics", ""))).lower()
    assert "resampling sensitivity range" in text
    assert "not a confidence interval" in text


def test_exp4_panel_a_is_dpair_not_legacy() -> None:
    meta = read_json(
        PUB / "exp4_controlled_route_audit" / "figures" / "main" / "metadata" / "fig_exp4_route_alignment_and_audit_reliability.json"
    )
    panel_a = str(meta["panel_definitions"]["a"])
    assert "D_pair" in panel_a
    assert "max" not in panel_a.lower()
    exclusions = meta["presentation_contract"]["panel_a_exclusions"]
    assert any("population_action_gap" in str(e) for e in exclusions)
    assert any("mean_round_max_gap" in str(e) for e in exclusions)


def test_old_exp3_value_not_hardcoded_as_canonical() -> None:
    frame = pd.read_csv(MAIN_CSV["exp3"])
    max_gap = frame.loc[frame["metric_id"] == "maximum_heldout_reference_pair_gap_error"]
    arrival = max_gap[max_gap["condition_id"] == "arrival_carrier"]
    assert len(arrival) == 1
    value = float(arrival.iloc[0]["point_estimate"])
    # canonical value ~ 0.6417907611; old stale value was 0.572
    assert abs(value - 0.6417907611) < 1e-9


def test_legacy_exp4_v2_not_in_current_canonical_registry() -> None:
    docs = (ROOT / "docs" / "PAPER_RESULTS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for text, name in ((docs, "PAPER_RESULTS"), (readme, "README")):
        # the v3 run is the current canonical; the v2 run id must not appear as current
        assert "full_20260817T071019Z_7d7146b7" in text
        # v2 run id is allowed only with legacy/superseded wording
        if "full_20260807T045219Z_7eeb2a31" in text:
            assert any(
                w in text.lower() for w in ("legacy", "superseded", "v2")
            ), f"{name} mentions v2 run without legacy/superseded marking"


@pytest.mark.parametrize("key", sorted(MAIN_FIGURES))
def test_source_and_presentation_lineage_separated(key: str) -> None:
    meta = read_json(
        PUB / EXPERIMENT_DIR[key] / "figures" / "main" / "metadata" / (MAIN_FIGURES[key] + ".json")
    )
    sci = str(meta.get("scientific_source_lineage", ""))
    pres = str(meta.get("presentation_source_lineage", ""))
    assert sci and sci != "NA"
    assert pres
    assert "presentation:" in pres


@pytest.mark.parametrize("key", sorted(MAIN_FIGURES))
def test_publication_validation_passed(key: str) -> None:
    v = read_json(PUB / EXPERIMENT_DIR[key] / "validation" / "presentation_validation.json")
    assert v["passed"] is True
    assert v["spec_id"] == "CR-EXP-OUTPUT-V1"


@pytest.mark.parametrize("key", sorted(MAIN_FIGURES))
def test_publication_manifest_complete(key: str) -> None:
    manifest = read_json(PUB / EXPERIMENT_DIR[key] / "manifests" / "presentation_manifest.json")
    assert manifest["spec_id"] == "CR-EXP-OUTPUT-V1"
    assert MAIN_FIGURES[key] in manifest.get("figure_ids", [])
