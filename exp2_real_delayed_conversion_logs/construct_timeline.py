from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.common import (
    SECONDS_PER_DAY,
    add_time_columns,
    ensure_output_dirs,
    get_col,
    load_config,
    make_output_manifest,
    normalise_conversion_identifier,
    normalise_identifier,
    normalise_uid_identifier,
    sentinel_minus_one_mask,
    out_dir,
    read_chunks,
    save_run_metadata,
    write_csv,
)


def _safe_numeric(
    frame: pd.DataFrame, column: str, default: float = np.nan
) -> pd.Series:
    if column not in frame:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _uid_integrity_filter(
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Keep conversion journeys having exactly one nonmissing UID.

    The Criteo public file is read in chunks and identifiers can be absent or
    malformed after round-trips.  Bootstrap clusters are undefined for a
    conversion journey with a missing/cross-user identifier, so this filter is
    intentionally applied before action-cell assignment and repeated later.
    """
    raw_rows = int(len(candidates))
    frame = candidates.copy()
    frame["conversion_id"] = normalise_conversion_identifier(frame["conversion_id"])
    uid_sentinel = (
        pd.to_numeric(frame.get("uid_sentinel_minus_one", 0), errors="coerce")
        .fillna(0)
        .astype(int)
        .eq(1)
        if "uid_sentinel_minus_one" in frame.columns
        else sentinel_minus_one_mask(frame["uid"])
    )
    frame["uid_sentinel_minus_one"] = uid_sentinel.astype(int)
    frame["uid"] = normalise_uid_identifier(frame["uid"])
    invalid_conversion_rows = int(frame["conversion_id"].isna().sum())
    frame = frame[frame["conversion_id"].notna()].copy()
    if frame.empty:
        raise RuntimeError(
            "No candidate rows with a valid conversion_id remain after identifier normalisation."
        )

    grouped = frame.groupby("conversion_id", sort=False)
    audit = (
        pd.concat(
            [
                grouped.size().rename("n_candidate_rows"),
                frame["uid"]
                .isna()
                .groupby(frame["conversion_id"], sort=False)
                .sum()
                .rename("n_missing_uid_rows"),
                frame["uid_sentinel_minus_one"]
                .groupby(frame["conversion_id"], sort=False)
                .sum()
                .rename("n_uid_sentinel_minus_one_rows"),
                frame.loc[frame["uid"].notna()]
                .groupby("conversion_id", sort=False)["uid"]
                .nunique()
                .rename("n_distinct_nonmissing_uid"),
            ],
            axis=1,
        )
        .fillna(
            {
                "n_missing_uid_rows": 0,
                "n_uid_sentinel_minus_one_rows": 0,
                "n_distinct_nonmissing_uid": 0,
            }
        )
        .reset_index()
    )
    audit["n_missing_uid_rows"] = audit["n_missing_uid_rows"].astype(int)
    audit["n_uid_sentinel_minus_one_rows"] = audit[
        "n_uid_sentinel_minus_one_rows"
    ].astype(int)
    audit["n_distinct_nonmissing_uid"] = audit["n_distinct_nonmissing_uid"].astype(int)
    audit["uid_integrity_status"] = np.select(
        [audit["n_missing_uid_rows"].gt(0), audit["n_distinct_nonmissing_uid"].ne(1)],
        ["missing_uid", "cross_uid"],
        default="valid_one_uid",
    )
    valid_ids = set(
        audit.loc[
            audit["uid_integrity_status"].eq("valid_one_uid"), "conversion_id"
        ].astype(str)
    )
    retained = frame[frame["conversion_id"].astype(str).isin(valid_ids)].copy()
    if retained.empty:
        raise RuntimeError("No candidate rows remain after UID integrity filtering.")
    retained["conversion_id"] = retained["conversion_id"].astype(str)
    retained["uid"] = retained["uid"].astype(str)

    summary = pd.DataFrame(
        [
            {"metric": "candidate_rows_before_identifier_filter", "value": raw_rows},
            {
                "metric": "candidate_rows_missing_conversion_id",
                "value": invalid_conversion_rows,
            },
            {
                "metric": "candidate_rows_after_conversion_id_filter",
                "value": int(len(frame)),
            },
            {
                "metric": "conversion_ids_total_with_valid_conversion_id",
                "value": int(len(audit)),
            },
            {
                "metric": "conversion_ids_valid_one_uid",
                "value": int(audit["uid_integrity_status"].eq("valid_one_uid").sum()),
            },
            {
                "metric": "conversion_ids_missing_uid",
                "value": int(audit["uid_integrity_status"].eq("missing_uid").sum()),
            },
            {
                "metric": "conversion_ids_uid_sentinel_minus_one",
                "value": int(audit["n_uid_sentinel_minus_one_rows"].gt(0).sum()),
            },
            {
                "metric": "candidate_rows_uid_sentinel_minus_one",
                "value": int(audit["n_uid_sentinel_minus_one_rows"].sum()),
            },
            {
                "metric": "conversion_ids_cross_uid",
                "value": int(audit["uid_integrity_status"].eq("cross_uid").sum()),
            },
            {
                "metric": "candidate_rows_retained_after_uid_integrity_filter",
                "value": int(len(retained)),
            },
            {
                "metric": "conversion_id_retention_rate",
                "value": float(
                    audit["uid_integrity_status"].eq("valid_one_uid").mean()
                ),
            },
        ]
    )
    return retained, audit, summary


def _build_action_cells(
    impressions: pd.DataFrame, candidates: pd.DataFrame, cfg: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build eligible campaign × source-day decision cells.

    The campaign is not a sufficient action unit in this data when every
    timeline has a single campaign.  A cell is a transparent coarsening of the
    source event: (mapped campaign, source calendar day).  It is used only for
    logged credit displacement diagnostics.
    """
    min_impressions = int(cfg["action"]["min_impressions_per_decision_cell"])
    imp = impressions.copy()
    imp["source_day_index"] = pd.to_numeric(
        imp["source_day_index"], errors="coerce"
    ).astype("Int64")
    imp["campaign"] = normalise_identifier(imp["campaign"])
    imp = imp.dropna(subset=["campaign", "source_day_index"]).copy()
    imp["source_day_index"] = imp["source_day_index"].astype(int)
    imp["cost"] = (
        pd.to_numeric(imp.get("cost", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    )
    cell_summary = imp.groupby(["campaign", "source_day_index"], as_index=False).agg(
        n_impressions=("campaign", "size"),
        total_cost=("cost", "sum"),
        mean_cost=("cost", "mean"),
    )
    candidate_counts = (
        candidates.groupby(["candidate_campaign", "source_day_index"], as_index=False)[
            "conversion_id"
        ]
        .nunique()
        .rename(
            columns={
                "candidate_campaign": "campaign",
                "conversion_id": "n_candidate_conversions",
            }
        )
    )
    cell_summary = cell_summary.merge(
        candidate_counts, on=["campaign", "source_day_index"], how="left"
    )
    cell_summary["n_candidate_conversions"] = (
        cell_summary["n_candidate_conversions"].fillna(0).astype(int)
    )
    cell_summary["eligible_decision_cell"] = (
        cell_summary["n_impressions"].ge(min_impressions).astype(int)
    )
    eligible = cell_summary[cell_summary["eligible_decision_cell"].eq(1)].copy()
    minimum = int(cfg["action"]["minimum_eligible_decision_cells"])
    if len(eligible) < minimum:
        raise RuntimeError(
            f"Only {len(eligible)} eligible campaign-source-day cells satisfy min_impressions_per_decision_cell={min_impressions}; need at least {minimum}."
        )
    eligible = eligible.sort_values(
        ["source_day_index", "campaign"], kind="stable"
    ).reset_index(drop=True)
    eligible["action_id"] = np.arange(len(eligible), dtype=np.int64)
    eligible["decision_cell_key"] = (
        eligible["campaign"].astype(str)
        + "__d"
        + eligible["source_day_index"].astype(str)
    )
    mapping = eligible[
        [
            "action_id",
            "decision_cell_key",
            "campaign",
            "source_day_index",
            "n_impressions",
            "total_cost",
            "mean_cost",
            "n_candidate_conversions",
        ]
    ].copy()

    imp = imp.merge(
        mapping[["campaign", "source_day_index", "action_id", "decision_cell_key"]],
        on=["campaign", "source_day_index"],
        how="inner",
        validate="many_to_one",
    )
    cand = candidates.copy()
    cand["candidate_campaign"] = normalise_identifier(cand["candidate_campaign"])
    cand["source_day_index"] = pd.to_numeric(
        cand["source_day_index"], errors="coerce"
    ).astype("Int64")
    cand = cand.dropna(subset=["candidate_campaign", "source_day_index"]).copy()
    cand["source_day_index"] = cand["source_day_index"].astype(int)
    cand = cand.merge(
        mapping[["campaign", "source_day_index", "action_id", "decision_cell_key"]],
        left_on=["candidate_campaign", "source_day_index"],
        right_on=["campaign", "source_day_index"],
        how="inner",
        validate="many_to_one",
    ).drop(columns=["campaign"])
    return imp, cand, mapping, cell_summary


def _arrival_anchor_by_day(impressions: pd.DataFrame) -> pd.DataFrame:
    """Construct a labelled arrival-bin anchor; it is not an observed policy."""
    counts = (
        impressions.groupby(
            ["source_day_index", "campaign", "action_id"], as_index=False
        )
        .size()
        .rename(columns={"size": "n_impressions"})
    )
    counts = counts.sort_values(
        ["source_day_index", "n_impressions", "campaign", "action_id"],
        ascending=[True, False, True, True],
        kind="stable",
    )
    active = counts.drop_duplicates("source_day_index", keep="first").copy()
    active = active.rename(
        columns={
            "source_day_index": "arrival_day_index",
            "campaign": "arrival_anchor_campaign",
            "action_id": "arrival_time_action_id",
        }
    )
    return active[
        [
            "arrival_day_index",
            "arrival_anchor_campaign",
            "arrival_time_action_id",
            "n_impressions",
        ]
    ]


def _conversion_table(
    candidates: pd.DataFrame, active: pd.DataFrame, attribution_col: str, click_col: str
) -> pd.DataFrame:
    rows: list[dict] = []
    active_map = active.set_index("arrival_day_index")[
        "arrival_time_action_id"
    ].to_dict()
    for conversion_id, group in candidates.groupby("conversion_id", sort=False):
        group = group.sort_values(["candidate_timestamp", "row_id"], kind="stable")
        uid_values = group["uid"].dropna().astype(str).unique()
        if len(uid_values) != 1:
            raise RuntimeError(
                f"UID integrity contract violated after filtering for conversion_id={conversion_id!r}."
            )
        conversion_timestamp = float(
            pd.to_numeric(group["conversion_timestamp"], errors="coerce").iloc[0]
        )
        arrival_day_index = int(np.floor(conversion_timestamp / SECONDS_PER_DAY))
        attributed = group[_safe_numeric(group, attribution_col).eq(1)]
        labelled = attributed.iloc[0] if len(attributed) == 1 else None
        actions = group["action_id"].nunique()
        rows.append(
            {
                "conversion_id": str(conversion_id),
                "uid": uid_values[0],
                "conversion_timestamp": conversion_timestamp,
                "arrival_day_index": arrival_day_index,
                "arrival_time_action_id": active_map.get(arrival_day_index, np.nan),
                "n_candidate_source_rows": int(len(group)),
                "n_candidate_decision_cells": int(actions),
                "n_candidate_campaigns": int(group["candidate_campaign"].nunique()),
                "n_clicked_candidate_rows": int(
                    _safe_numeric(group, click_col).eq(1).sum()
                ),
                "n_attributed_candidate_rows": int(len(attributed)),
                "unique_labelled_conversion_candidates_flag": int(labelled is not None),
                "labelled_source_action_id": (
                    int(labelled["action_id"]) if labelled is not None else np.nan
                ),
                "labelled_source_campaign": (
                    str(labelled["candidate_campaign"])
                    if labelled is not None
                    else pd.NA
                ),
                "labelled_source_day_index": (
                    int(labelled["source_day_index"])
                    if labelled is not None
                    else np.nan
                ),
                "first_candidate_timestamp": float(
                    pd.to_numeric(group["candidate_timestamp"], errors="coerce").min()
                ),
                "last_candidate_timestamp": float(
                    pd.to_numeric(group["candidate_timestamp"], errors="coerce").max()
                ),
                "delay_from_first_candidate_days": float(
                    (
                        conversion_timestamp
                        - pd.to_numeric(
                            group["candidate_timestamp"], errors="coerce"
                        ).min()
                    )
                    / SECONDS_PER_DAY
                ),
                "delay_from_last_candidate_days": float(
                    (
                        conversion_timestamp
                        - pd.to_numeric(
                            group["candidate_timestamp"], errors="coerce"
                        ).max()
                    )
                    / SECONDS_PER_DAY
                ),
                "uid_integrity_status": "valid_one_uid",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construct source-time decision-cell timelines for Experiment 2."
    )
    parser.add_argument("--config", default="config_exp2.yaml")
    parser.add_argument("--fast-nrows", type=int, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    ensure_output_dirs(cfg)
    precheck = out_dir(cfg, "precheck")
    processed = out_dir(cfg, "processed")
    campaign_summary_path = precheck / "exp2_campaign_summary.csv"
    window_path = precheck / "exp2_analysis_window.json"
    if not campaign_summary_path.exists() or not window_path.exists():
        raise FileNotFoundError("Run run_precheck.py before construct_timeline.py.")
    analysis_window = json.loads(window_path.read_text(encoding="utf-8"))
    start, end = float(analysis_window["analysis_window_start_timestamp"]), float(
        analysis_window["analysis_window_end_timestamp"]
    )

    ts, uid, campaign = (
        get_col(cfg, "timestamp"),
        get_col(cfg, "uid"),
        get_col(cfg, "campaign"),
    )
    conversion, conversion_ts, conversion_id = (
        get_col(cfg, "conversion"),
        get_col(cfg, "conversion_timestamp"),
        get_col(cfg, "conversion_id"),
    )
    attribution, click, cost = (
        get_col(cfg, "attribution"),
        get_col(cfg, "click"),
        get_col(cfg, "cost"),
    )

    campaign_frame = pd.read_csv(campaign_summary_path, dtype={"campaign": "string"})
    campaign_frame["campaign"] = normalise_identifier(campaign_frame["campaign"])
    n_campaigns = int(cfg["action"]["candidate_campaign_count_requested"])
    campaigns = (
        campaign_frame.sort_values(
            ["n_impressions", "campaign"], ascending=[False, True], kind="stable"
        )
        .head(n_campaigns)["campaign"]
        .dropna()
        .astype(str)
        .tolist()
    )
    if len(campaigns) < int(cfg["action"]["candidate_campaign_count_minimum"]):
        raise RuntimeError("Too few mapped campaigns after precheck filtering.")
    campaign_set = set(campaigns)
    write_csv(
        pd.DataFrame(
            {"campaign": campaigns, "campaign_rank": range(1, len(campaigns) + 1)}
        ),
        processed / "exp2_campaign_mapping.csv",
    )

    raw_impressions = processed / "exp2_impression_timeline_raw.csv"
    raw_candidates = processed / "exp2_candidate_sources_raw.csv"
    for path in (
        raw_impressions,
        raw_candidates,
        processed / "exp2_impression_timeline.csv",
        processed / "exp2_candidate_sources.csv",
    ):
        if path.exists():
            path.unlink()
    row_offset = 0
    rows_seen = 0
    candidate_rows_missing_conversion_id = 0
    candidate_rows_after_analysis_end = 0
    for chunk_index, chunk in enumerate(
        read_chunks(cfg, usecols=None, nrows=args.fast_nrows), start=1
    ):
        chunk = add_time_columns(chunk, cfg)
        chunk = chunk[
            _safe_numeric(chunk, ts).between(start, end, inclusive="both")
        ].copy()
        if chunk.empty:
            continue
        chunk.insert(
            0, "row_id", np.arange(row_offset, row_offset + len(chunk), dtype=np.int64)
        )
        row_offset += len(chunk)
        rows_seen += len(chunk)
        chunk["uid_sentinel_minus_one"] = sentinel_minus_one_mask(chunk[uid]).astype(
            int
        )
        chunk[uid] = normalise_uid_identifier(chunk[uid])
        chunk[conversion_id] = normalise_conversion_identifier(chunk[conversion_id])
        chunk["campaign_str"] = normalise_identifier(chunk[campaign])
        chunk["is_mapped_campaign"] = (
            chunk["campaign_str"].astype("string").isin(campaign_set).astype(int)
        )
        keep = [
            "row_id",
            uid,
            "uid_sentinel_minus_one",
            ts,
            "day_index",
            campaign,
            "campaign_str",
            "is_mapped_campaign",
            conversion,
            conversion_ts,
            conversion_id,
            attribution,
            click,
            cost,
        ]
        keep = [col for col in keep if col in chunk.columns]
        mapped = chunk.loc[chunk["is_mapped_campaign"].eq(1), keep].copy()
        if not mapped.empty:
            mapped = mapped.rename(
                columns={
                    uid: "uid",
                    ts: "timestamp",
                    campaign: "campaign",
                    conversion_id: "conversion_id",
                    conversion_ts: "conversion_timestamp",
                }
            )
            mapped["source_day_index"] = pd.to_numeric(
                mapped["day_index"], errors="coerce"
            )
            mapped["cost"] = _safe_numeric(mapped, cost).fillna(0.0).clip(lower=0.0)
            mapped["uid"] = normalise_uid_identifier(mapped["uid"])
            mapped["conversion_id"] = normalise_conversion_identifier(
                mapped["conversion_id"]
            )
            mapped.to_csv(
                raw_impressions,
                mode="a",
                index=False,
                header=not raw_impressions.exists(),
            )

        timestamps = _safe_numeric(chunk, ts)
        conv_times = _safe_numeric(chunk, conversion_ts)
        conversion_with_valid_timing = (
            _safe_numeric(chunk, conversion).eq(1)
            & conv_times.gt(timestamps)
            & np.isfinite(timestamps)
            & np.isfinite(conv_times)
        )
        # A conversion observed after the configured analysis end cannot be treated as
        # part of the fixed observed log. Exclude it rather than silently importing
        # future feedback into a source-time diagnostic.
        conversion_observed_within_analysis = (
            conversion_with_valid_timing & conv_times.le(end)
        )
        candidate_rows_after_analysis_end += int(
            (conversion_with_valid_timing & ~conversion_observed_within_analysis).sum()
        )
        valid_conversion_id = chunk[conversion_id].notna()
        candidate_rows_missing_conversion_id += int(
            (conversion_observed_within_analysis & ~valid_conversion_id).sum()
        )
        candidate = chunk.loc[
            conversion_observed_within_analysis
            & valid_conversion_id
            & chunk["is_mapped_campaign"].eq(1),
            keep,
        ].copy()
        if not candidate.empty:
            candidate = candidate.rename(
                columns={
                    uid: "uid",
                    ts: "candidate_timestamp",
                    campaign: "candidate_campaign",
                    conversion_id: "conversion_id",
                    conversion_ts: "conversion_timestamp",
                }
            )
            candidate["source_day_index"] = pd.to_numeric(
                candidate["day_index"], errors="coerce"
            )
            candidate["uid"] = normalise_uid_identifier(candidate["uid"])
            candidate["conversion_id"] = normalise_conversion_identifier(
                candidate["conversion_id"]
            )
            candidate["delay_to_conversion_days"] = (
                _safe_numeric(candidate, "conversion_timestamp")
                - _safe_numeric(candidate, "candidate_timestamp")
            ) / SECONDS_PER_DAY
            candidate["cost"] = (
                _safe_numeric(candidate, cost).fillna(0.0).clip(lower=0.0)
            )
            candidate.to_csv(
                raw_candidates,
                mode="a",
                index=False,
                header=not raw_candidates.exists(),
            )
        print(
            f"[construct] processed chunk {chunk_index}, retained rows={rows_seen:,}",
            flush=True,
        )

    if not raw_impressions.exists() or not raw_candidates.exists():
        raise RuntimeError(
            "No mapped impressions or conversion candidates were written."
        )
    impressions_raw = pd.read_csv(
        raw_impressions,
        dtype={"uid": "string", "conversion_id": "string", "campaign": "string"},
    )
    candidates_raw = pd.read_csv(
        raw_candidates,
        dtype={
            "uid": "string",
            "conversion_id": "string",
            "candidate_campaign": "string",
        },
    )
    candidates_uid, uid_audit, uid_summary = _uid_integrity_filter(candidates_raw)
    uid_summary = pd.concat(
        [
            uid_summary,
            pd.DataFrame(
                [
                    {
                        "metric": "candidate_rows_missing_conversion_id_before_persistence",
                        "value": candidate_rows_missing_conversion_id,
                    },
                    {
                        "metric": "candidate_rows_conversion_after_analysis_end_excluded",
                        "value": candidate_rows_after_analysis_end,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    write_csv(uid_audit, processed / "exp2_conversion_uid_integrity.csv")
    write_csv(uid_summary, processed / "exp2_conversion_uid_integrity_summary.csv")

    impressions, candidates, action_map, action_cell_audit = _build_action_cells(
        impressions_raw, candidates_uid, cfg
    )
    write_csv(action_map, processed / "exp2_action_cell_mapping.csv")
    write_csv(action_cell_audit, processed / "exp2_action_cell_eligibility_audit.csv")
    write_csv(impressions, processed / "exp2_impression_timeline.csv")
    write_csv(candidates, processed / "exp2_candidate_sources.csv")
    action_exposure = action_map[
        [
            "action_id",
            "decision_cell_key",
            "campaign",
            "source_day_index",
            "n_impressions",
            "total_cost",
            "mean_cost",
        ]
    ].copy()
    write_csv(action_exposure, processed / "exp2_action_exposure_cost.csv")

    active = _arrival_anchor_by_day(impressions)
    write_csv(active, processed / "exp2_arrival_bin_anchor.csv")
    conversions = _conversion_table(candidates, active, attribution, click)
    n_cells = int(len(action_map))
    conversions["main_cohort_eligible"] = (
        conversions["n_candidate_decision_cells"].gt(0)
        & conversions["arrival_time_action_id"].notna()
        & pd.to_numeric(conversions["arrival_time_action_id"], errors="coerce").between(
            0, n_cells - 1
        )
        & conversions["uid"].notna()
        & conversions["uid_integrity_status"].eq("valid_one_uid")
    ).astype(int)
    conversions["source_linked_audit_eligible"] = (
        conversions["main_cohort_eligible"].eq(1)
        & conversions["unique_labelled_conversion_candidates_flag"].eq(1)
        & pd.to_numeric(
            conversions["labelled_source_action_id"], errors="coerce"
        ).between(0, n_cells - 1)
    ).astype(int)
    write_csv(conversions, processed / "exp2_conversion_arrivals.csv")
    write_csv(
        conversions[conversions["main_cohort_eligible"].eq(1)].copy(),
        processed / "exp2_all_conversion_candidates.csv",
    )
    write_csv(
        conversions[conversions["source_linked_audit_eligible"].eq(1)].copy(),
        processed / "exp2_unique_labelled_conversion_candidates.csv",
    )

    save_run_metadata(
        cfg,
        "construct_timeline_success",
        {
            "n_retained_rows": int(rows_seen),
            "n_candidate_rows": int(len(candidates)),
            "n_conversion_ids": int(conversions["conversion_id"].nunique()),
            "n_eligible_decision_cells": int(len(action_map)),
            "action_unit": str(cfg["action"]["action_unit"]),
            "n_uid_valid_one_uid_conversion_ids": int(
                uid_audit["uid_integrity_status"].eq("valid_one_uid").sum()
            ),
            "n_uid_missing_or_cross_uid_conversion_ids": int(
                (~uid_audit["uid_integrity_status"].eq("valid_one_uid")).sum()
            ),
            "n_uid_sentinel_minus_one_candidate_rows": int(
                uid_audit["n_uid_sentinel_minus_one_rows"].sum()
            ),
        },
    )
    make_output_manifest(cfg)
    print("[construct] done", flush=True)


if __name__ == "__main__":
    main()
