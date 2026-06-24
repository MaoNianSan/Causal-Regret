"""Generate a non-paper fixture with both campaign and source-time ambiguity."""
from __future__ import annotations

from pathlib import Path
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "inputs" / "pcb_dataset_final.tsv"
DAY = 86400


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a non-paper synthetic Exp2 fixture.")
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()
    output = Path(args.output)
    rng = np.random.default_rng(4242)
    rows: list[dict] = []
    n_campaigns = 20
    # Sufficient decision-cell exposure over a 34-day log.
    for day in range(34):
        for campaign in range(n_campaigns):
            for rep in range(6):
                rows.append({
                    "timestamp": day * DAY + campaign * 600 + rep * 30,
                    "uid": f"background_{day}_{campaign}_{rep}",
                    "campaign": str(campaign),
                    "conversion": 0, "conversion_timestamp": -1, "conversion_id": -1,
                    "attribution": 0, "click": int((day + campaign + rep) % 7 == 0),
                    "cost": round(0.30 + 0.01 * campaign + 0.01 * rep, 4),
                })
    conversion_index = 0
    # Every converted journey has two source days. Half deliberately remain in
    # one campaign, showing that source-time cells prevent campaign-only collapse.
    for day in range(3, 28):
        for rep in range(12):
            left = (day + rep) % n_campaigns
            right = left if (day + rep) % 2 == 0 else (left + 1) % n_campaigns
            uid = f"u_{day}_{rep}"
            cid = f"cv_{conversion_index:04d}"
            t0 = day * DAY + 1800
            t1 = (day + 1) * DAY + 2400
            conversion_ts = t1 + (2 + (day % 5)) * 3600
            first_label = (day + rep) % 2 == 0
            rows.extend([
                {"timestamp": t0, "uid": uid, "campaign": str(left), "conversion": 1, "conversion_timestamp": conversion_ts, "conversion_id": cid, "attribution": int(first_label), "click": int((day + rep) % 3 == 0), "cost": round(0.42 + 0.01 * left, 4)},
                {"timestamp": t1, "uid": uid, "campaign": str(right), "conversion": 1, "conversion_timestamp": conversion_ts, "conversion_id": cid, "attribution": int(not first_label), "click": int((day + rep) % 4 != 0), "cost": round(0.42 + 0.01 * right, 4)},
            ])
            conversion_index += 1
    # UID/conversion-ID integrity stress cases; must be excluded with an audit.
    d = 31 * DAY
    rows += [
        {"timestamp": d + 100, "uid": None, "campaign": "0", "conversion": 1, "conversion_timestamp": d + 8_000, "conversion_id": "cv_missing_uid", "attribution": 1, "click": 1, "cost": 0.4},
        {"timestamp": d + 200, "uid": "cross_left", "campaign": "1", "conversion": 1, "conversion_timestamp": d + 8_000, "conversion_id": "cv_cross_uid", "attribution": 1, "click": 1, "cost": 0.4},
        {"timestamp": d + 300, "uid": "cross_right", "campaign": "1", "conversion": 1, "conversion_timestamp": d + 8_000, "conversion_id": "cv_cross_uid", "attribution": 0, "click": 0, "cost": 0.4},
        {"timestamp": d + 400, "uid": "missing_cid", "campaign": "2", "conversion": 1, "conversion_timestamp": d + 8_000, "conversion_id": None, "attribution": 1, "click": 1, "cost": 0.4},
        {"timestamp": d + 500, "uid": "-1", "campaign": "3", "conversion": 1, "conversion_timestamp": d + 8_000, "conversion_id": "cv_uid_minus_one", "attribution": 1, "click": 1, "cost": 0.4},
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).sort_values(["timestamp", "uid"], kind="stable").to_csv(output, sep="\t", index=False)
    print(f"synthetic fixture: {output} ({len(rows):,} rows; {conversion_index} valid conversion IDs)")


if __name__ == "__main__":
    main()
