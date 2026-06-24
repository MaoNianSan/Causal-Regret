from __future__ import annotations

import argparse
import json
from collections import defaultdict
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
    normalise_uid_identifier,
    out_dir,
    read_chunks,
    save_config_snapshot,
    save_run_metadata,
    write_csv,
)


def _new_conversion_stat() -> dict:
    return {
        "n_candidate_rows": 0,
        "n_attributed_rows": 0,
        "n_clicked_rows": 0,
        "min_timestamp": np.inf,
        "max_timestamp": -np.inf,
        "conversion_timestamp": np.nan,
        "campaigns": set(),
        "uid": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Precheck Criteo delayed-conversion dataset for Experiment 2."
    )
    parser.add_argument("--config", default="config_exp2.yaml")
    parser.add_argument(
        "--fast-nrows", type=int, default=None, help="Optional row cap for debugging."
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_output_dirs(cfg)
    save_config_snapshot(cfg)

    ts = get_col(cfg, "timestamp")
    uid = get_col(cfg, "uid")
    campaign = get_col(cfg, "campaign")
    conversion = get_col(cfg, "conversion")
    conv_ts = get_col(cfg, "conversion_timestamp")
    conv_id = get_col(cfg, "conversion_id")
    attribution = get_col(cfg, "attribution")
    click = get_col(cfg, "click")

    required = [ts, uid, campaign, conversion, conv_ts, conv_id, attribution, click]

    n_rows = 0
    campaigns = set()
    uids = set() if bool(cfg["data"].get("exact_uid_count", True)) else None
    n_conversion_rows = 0
    n_attributed_rows = 0
    n_clicked_rows = 0
    min_ts = np.inf
    max_ts = -np.inf
    sample_written = False

    campaign_stats = defaultdict(
        lambda: {
            "n_impressions": 0,
            "n_conversion_rows": 0,
            "n_attributed_rows": 0,
            "n_clicked_rows": 0,
        }
    )
    conversion_stats = defaultdict(_new_conversion_stat)
    delays = []

    for chunk_id, chunk in enumerate(
        read_chunks(cfg, usecols=None, nrows=args.fast_nrows)
    ):
        missing = [c for c in required if c not in chunk.columns]
        if missing:
            raise ValueError(f"Missing required columns in raw data: {missing}")

        if not sample_written:
            write_csv(chunk.head(100), out_dir(cfg, "precheck") / "exp2_sample_100.csv")
            sample_written = True

        chunk = add_time_columns(chunk, cfg)
        n_rows += len(chunk)
        campaigns.update(chunk[campaign].dropna().astype(str).unique().tolist())

        n_conversion_rows += int((chunk[conversion] == 1).sum())
        n_attributed_rows += int((chunk[attribution] == 1).sum())
        n_clicked_rows += int((chunk[click] == 1).sum())
        min_ts = min(min_ts, float(chunk[ts].min()))
        max_ts = max(max_ts, float(chunk[ts].max()))

        agg = chunk.groupby(campaign, dropna=False).agg(
            n_impressions=(campaign, "size"),
            n_conversion_rows=(conversion, lambda x: int((x == 1).sum())),
            n_attributed_rows=(attribution, lambda x: int((x == 1).sum())),
            n_clicked_rows=(click, lambda x: int((x == 1).sum())),
        )
        for camp, row in agg.iterrows():
            d = campaign_stats[str(camp)]
            for k in d:
                d[k] += int(row[k])

        chunk[uid] = normalise_uid_identifier(chunk[uid])
        chunk[conv_id] = normalise_conversion_identifier(chunk[conv_id])
        if uids is not None:
            uids.update(chunk[uid].dropna().astype(str).unique().tolist())
        valid_conversion_id = chunk[conv_id].notna()
        valid = (
            (chunk[conversion] == 1)
            & (chunk[conv_ts] > chunk[ts])
            & valid_conversion_id
        )
        if valid.any():
            vc = chunk.loc[
                valid, [uid, ts, conv_ts, conv_id, campaign, attribution, click]
            ].copy()
            vc["delay_seconds"] = vc[conv_ts] - vc[ts]
            delays.extend(vc["delay_seconds"].dropna().astype(float).tolist())
            for cid, g in vc.groupby(conv_id, dropna=False):
                st = conversion_stats[str(cid)]
                st["n_candidate_rows"] += len(g)
                st["n_attributed_rows"] += int((g[attribution] == 1).sum())
                st["n_clicked_rows"] += int((g[click] == 1).sum())
                st["min_timestamp"] = min(st["min_timestamp"], float(g[ts].min()))
                st["max_timestamp"] = max(st["max_timestamp"], float(g[ts].max()))
                cts_values = g[conv_ts].dropna().astype(float)
                if len(cts_values):
                    st["conversion_timestamp"] = float(cts_values.max())
                valid_uids = g[uid].dropna().astype(str).unique()
                if st["uid"] is None and len(valid_uids) == 1:
                    st["uid"] = str(valid_uids[0])
                st["campaigns"].update(
                    g[campaign].dropna().astype(str).unique().tolist()
                )

        print(f"[precheck] processed chunk {chunk_id + 1}, cumulative rows={n_rows:,}")

    time_span_days = (
        (max_ts - min_ts) / SECONDS_PER_DAY
        if np.isfinite(min_ts) and np.isfinite(max_ts)
        else np.nan
    )
    configured_window_days = float(
        cfg["data"].get(
            "observation_window_days",
            time_span_days if np.isfinite(time_span_days) else 0,
        )
    )
    analysis_start_ts = (
        max(min_ts, max_ts - configured_window_days * SECONDS_PER_DAY)
        if np.isfinite(max_ts)
        else np.nan
    )
    analysis_window = {
        "configured_observation_window_days": configured_window_days,
        "analysis_window_start_timestamp": float(analysis_start_ts),
        "analysis_window_end_timestamp": float(max_ts),
        "selection_rule": "last configured observation_window_days ending at the maximum observed impression timestamp",
    }
    (out_dir(cfg, "precheck") / "exp2_analysis_window.json").write_text(
        json.dumps(analysis_window, indent=2), encoding="utf-8"
    )
    dataset_summary = pd.DataFrame(
        [
            {"metric": "n_rows", "value": n_rows},
            {
                "metric": "n_users_exact",
                "value": len(uids) if uids is not None else np.nan,
            },
            {"metric": "n_campaigns", "value": len(campaigns)},
            {"metric": "n_conversion_rows", "value": n_conversion_rows},
            {"metric": "n_attributed_rows", "value": n_attributed_rows},
            {"metric": "n_clicked_rows", "value": n_clicked_rows},
            {
                "metric": "row_conversion_rate",
                "value": n_conversion_rows / n_rows if n_rows else np.nan,
            },
            {
                "metric": "row_attribution_rate",
                "value": n_attributed_rows / n_rows if n_rows else np.nan,
            },
            {
                "metric": "row_click_rate",
                "value": n_clicked_rows / n_rows if n_rows else np.nan,
            },
            {"metric": "min_timestamp", "value": min_ts},
            {"metric": "max_timestamp", "value": max_ts},
            {"metric": "time_span_days", "value": time_span_days},
            {
                "metric": "configured_observation_window_days",
                "value": configured_window_days,
            },
            {"metric": "analysis_window_start_timestamp", "value": analysis_start_ts},
            {"metric": "analysis_window_end_timestamp", "value": max_ts},
        ]
    )
    write_csv(dataset_summary, out_dir(cfg, "precheck") / "exp2_dataset_summary.csv")

    campaign_summary = pd.DataFrame(
        [{"campaign": k, **v} for k, v in campaign_stats.items()]
    )
    min_conv = int(cfg["action"].get("min_conversion_rows_per_campaign", 0))
    eligible_campaign_summary = campaign_summary[
        campaign_summary["n_conversion_rows"] >= min_conv
    ].copy()
    minimum_actions = int(cfg["action"].get("candidate_campaign_count_minimum", 1))
    if len(eligible_campaign_summary) < minimum_actions:
        raise RuntimeError(
            f"Only {len(eligible_campaign_summary)} campaigns satisfy min_conversion_rows_per_campaign={min_conv}; need at least {minimum_actions}."
        )
    campaign_summary = eligible_campaign_summary
    campaign_summary["conversion_rate"] = campaign_summary[
        "n_conversion_rows"
    ] / campaign_summary["n_impressions"].replace(0, np.nan)
    campaign_summary["click_rate"] = campaign_summary[
        "n_clicked_rows"
    ] / campaign_summary["n_impressions"].replace(0, np.nan)
    campaign_summary["impression_coverage_pct"] = (
        100 * campaign_summary["n_impressions"] / max(n_rows, 1)
    )
    campaign_summary["conversion_coverage_pct"] = (
        100 * campaign_summary["n_conversion_rows"] / max(n_conversion_rows, 1)
    )
    campaign_summary["attribution_coverage_pct"] = (
        100 * campaign_summary["n_attributed_rows"] / max(n_attributed_rows, 1)
    )
    campaign_summary = campaign_summary.sort_values("n_impressions", ascending=False)
    write_csv(campaign_summary, out_dir(cfg, "precheck") / "exp2_campaign_summary.csv")

    topk_rows = []
    for k in cfg["action"].get("sensitivity_top_k", [10, 20, 50]):
        top = campaign_summary.head(int(k))
        topk_rows.append(
            {
                "n_campaigns": int(k),
                "impression_coverage_pct": float(
                    100 * top["n_impressions"].sum() / max(n_rows, 1)
                ),
                "conversion_coverage_pct": float(
                    100 * top["n_conversion_rows"].sum() / max(n_conversion_rows, 1)
                ),
                "attribution_coverage_pct": float(
                    100 * top["n_attributed_rows"].sum() / max(n_attributed_rows, 1)
                ),
                "min_conversion_rows": (
                    int(top["n_conversion_rows"].min()) if len(top) else 0
                ),
                "min_attributed_rows": (
                    int(top["n_attributed_rows"].min()) if len(top) else 0
                ),
            }
        )
    write_csv(
        pd.DataFrame(topk_rows),
        out_dir(cfg, "precheck") / "exp2_top_campaign_coverage_summary.csv",
    )

    delays = np.asarray(delays, dtype=float)
    delay_summary = pd.DataFrame(
        [
            {
                "count": int(len(delays)),
                "mean_seconds": float(np.mean(delays)) if len(delays) else np.nan,
                "median_seconds": float(np.median(delays)) if len(delays) else np.nan,
                "p25_seconds": (
                    float(np.quantile(delays, 0.25)) if len(delays) else np.nan
                ),
                "p75_seconds": (
                    float(np.quantile(delays, 0.75)) if len(delays) else np.nan
                ),
                "p90_seconds": (
                    float(np.quantile(delays, 0.90)) if len(delays) else np.nan
                ),
                "p95_seconds": (
                    float(np.quantile(delays, 0.95)) if len(delays) else np.nan
                ),
                "p99_seconds": (
                    float(np.quantile(delays, 0.99)) if len(delays) else np.nan
                ),
                "max_seconds": float(np.max(delays)) if len(delays) else np.nan,
            }
        ]
    )
    for c in list(delay_summary.columns):
        if c.endswith("seconds"):
            delay_summary[c.replace("seconds", "days")] = (
                delay_summary[c] / SECONDS_PER_DAY
            )
    write_csv(delay_summary, out_dir(cfg, "precheck") / "exp2_delay_summary.csv")

    if len(delays):
        labels = ["<=1h", "1-6h", "6-24h", "1-7d", "7-30d"]
        bins = [
            -np.inf,
            3600,
            6 * 3600,
            SECONDS_PER_DAY,
            7 * SECONDS_PER_DAY,
            30 * SECONDS_PER_DAY + 1,
        ]
        bucket = pd.cut(delays, bins=bins, labels=labels, right=True)
        delay_bucket = pd.DataFrame({"delay_seconds": delays, "delay_bucket": bucket})
        delay_bucket_summary = (
            delay_bucket.groupby("delay_bucket", observed=False)
            .agg(
                n_conversion_rows=("delay_seconds", "size"),
                mean_delay_seconds=("delay_seconds", "mean"),
                median_delay_seconds=("delay_seconds", "median"),
            )
            .reset_index()
        )
        delay_bucket_summary["share_pct"] = (
            100 * delay_bucket_summary["n_conversion_rows"] / len(delays)
        )
        delay_bucket_summary["mean_delay_days"] = (
            delay_bucket_summary["mean_delay_seconds"] / SECONDS_PER_DAY
        )
        delay_bucket_summary["median_delay_days"] = (
            delay_bucket_summary["median_delay_seconds"] / SECONDS_PER_DAY
        )
    else:
        delay_bucket_summary = pd.DataFrame()
    write_csv(
        delay_bucket_summary, out_dir(cfg, "precheck") / "exp2_delay_bucket_summary.csv"
    )

    conversion_summary = pd.DataFrame(
        [
            {
                "conversion_id": cid,
                "uid": st["uid"],
                "n_candidate_rows": st["n_candidate_rows"],
                "n_attributed_rows": st["n_attributed_rows"],
                "n_clicked_rows": st["n_clicked_rows"],
                "n_campaigns": len(st["campaigns"]),
                "min_timestamp": st["min_timestamp"],
                "max_timestamp": st["max_timestamp"],
                "conversion_timestamp": st["conversion_timestamp"],
            }
            for cid, st in conversion_stats.items()
        ]
    )
    if not conversion_summary.empty:
        conversion_summary["source_window_length_seconds"] = (
            conversion_summary["max_timestamp"] - conversion_summary["min_timestamp"]
        )
        conversion_summary["source_window_length_days"] = (
            conversion_summary["source_window_length_seconds"] / SECONDS_PER_DAY
        )
    write_csv(
        conversion_summary, out_dir(cfg, "precheck") / "exp2_conversion_id_summary.csv"
    )

    if not conversion_summary.empty:
        n_cids = len(conversion_summary)
        check = pd.DataFrame(
            [
                {"metric": "n_conversion_ids", "value": n_cids},
                {
                    "metric": "share_unique_attributed_row",
                    "value": float(
                        (conversion_summary["n_attributed_rows"] == 1).mean()
                    ),
                },
                {
                    "metric": "share_no_attributed_row",
                    "value": float(
                        (conversion_summary["n_attributed_rows"] == 0).mean()
                    ),
                },
                {
                    "metric": "share_multiple_attributed_rows",
                    "value": float(
                        (conversion_summary["n_attributed_rows"] > 1).mean()
                    ),
                },
                {
                    "metric": "mean_candidate_rows_per_conversion",
                    "value": float(conversion_summary["n_candidate_rows"].mean()),
                },
                {
                    "metric": "median_candidate_rows_per_conversion",
                    "value": float(conversion_summary["n_candidate_rows"].median()),
                },
                {
                    "metric": "p90_candidate_rows",
                    "value": float(
                        conversion_summary["n_candidate_rows"].quantile(0.90)
                    ),
                },
                {
                    "metric": "p99_candidate_rows",
                    "value": float(
                        conversion_summary["n_candidate_rows"].quantile(0.99)
                    ),
                },
            ]
        )
    else:
        check = pd.DataFrame()
    write_csv(check, out_dir(cfg, "precheck") / "exp2_conversion_id_check.csv")

    report = out_dir(cfg, "precheck") / "exp2_precheck_preview_report.md"
    report.write_text(
        "# Experiment 2: Real Delayed Conversion Logs — Precheck Preview\n\n"
        f"Rows processed: {n_rows:,}\n\n"
        f"Campaigns: {len(campaigns):,}\n\n"
        f"Conversion rows: {n_conversion_rows:,}\n\n"
        f"Attributed rows: {n_attributed_rows:,}\n\n"
        f"Clicked rows: {n_clicked_rows:,}\n\n"
        f"Time span: {time_span_days:.2f} days\n\n"
        "See `outputs/precheck/` for CSV files.\n",
        encoding="utf-8",
    )

    save_run_metadata(
        cfg,
        status="precheck_success",
        extra={
            "n_rows_processed": n_rows,
            "analysis_window": analysis_window,
            "eligible_action_count": len(campaign_summary),
        },
    )
    make_output_manifest(cfg)
    print("[precheck] done")


if __name__ == "__main__":
    main()
