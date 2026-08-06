from __future__ import annotations

import pandas as pd


def normalize_identifier(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip()
    invalid = values.isna() | values.eq("") | values.str.lower().isin({"nan", "none", "null"})
    return values.mask(invalid)


def normalize_user_identifier(series: pd.Series) -> pd.Series:
    values = normalize_identifier(series)
    invalid = values.isin({"-1", "-1.0"})
    return values.mask(invalid)


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def to_timestamp_utc(series: pd.Series, unit: str) -> pd.Series:
    numeric = to_numeric(series)
    return pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce")


def make_decision_cell_id(campaign_id: pd.Series, date_utc: pd.Series) -> pd.Series:
    campaign = normalize_identifier(campaign_id)
    date_text = pd.to_datetime(date_utc, utc=True, errors="coerce").dt.strftime("%Y-%m-%d")
    return campaign.astype("string") + "|" + date_text.astype("string")
