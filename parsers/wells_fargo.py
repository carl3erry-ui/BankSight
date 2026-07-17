from __future__ import annotations

import pandas as pd


WELLS_HEADERS = {"date", "amount", "description", "memo", "check number"}


def _to_amount(series: pd.Series) -> pd.Series:
    normalized = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(r"\(([^\)]+)\)", r"-\1", regex=True)
        .str.replace(r"[^0-9\.-]", "", regex=True)
        .replace("", "0")
    )
    return pd.to_numeric(normalized, errors="coerce").fillna(0.0)


def can_parse(df: pd.DataFrame) -> bool:
    columns = {c.strip().lower() for c in df.columns}
    return "description" in columns and "amount" in columns and bool(WELLS_HEADERS & columns)


def parse(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    lower_map = {c: c.strip().lower() for c in data.columns}
    data = data.rename(columns=lower_map)

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(data.get("date"), errors="coerce")
    out["description"] = data.get("description", "").astype(str)
    out["amount"] = _to_amount(data.get("amount", pd.Series(0, index=data.index, dtype=float)))
    out["bank"] = "Wells Fargo"
    return out

