from __future__ import annotations

import pandas as pd


PNC_HEADERS = {"posted date", "description", "amount", "debit", "credit", "type"}


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
    has_amount_or_split = "amount" in columns or ("debit" in columns and "credit" in columns)
    return "description" in columns and has_amount_or_split and bool(PNC_HEADERS & columns)


def parse(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    lower_map = {c: c.strip().lower() for c in data.columns}
    data = data.rename(columns=lower_map)

    out = pd.DataFrame()
    date_col = "posted date" if "posted date" in data.columns else "date"
    out["date"] = pd.to_datetime(data.get(date_col), errors="coerce")
    out["description"] = data.get("description", "").astype(str)

    if "amount" in data.columns:
        amount = _to_amount(data["amount"])
    else:
        debit = _to_amount(data.get("debit", pd.Series(0, index=data.index, dtype=float)))
        credit = _to_amount(data.get("credit", pd.Series(0, index=data.index, dtype=float)))
        amount = credit - debit

    out["amount"] = amount
    out["bank"] = "PNC"
    return out

