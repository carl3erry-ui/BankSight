from __future__ import annotations

import io
import re

import pandas as pd

from . import chase, pnc, wells_fargo


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    copy = df.copy()
    copy.columns = [str(c).strip() for c in copy.columns]
    return copy


def _read_csv(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.read()
    uploaded_file.seek(0)

    decoded = raw.decode("utf-8-sig", errors="replace")
    return pd.read_csv(io.StringIO(decoded), sep=None, engine="python", skipinitialspace=True)


def _to_amount(series: pd.Series) -> pd.Series:
    # Normalize common statement formats like "$1,234.56" and "(54.22)".
    normalized = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace(r"\(([^\)]+)\)", r"-\1", regex=True)
        .str.replace(r"[^0-9\.-]", "", regex=True)
        .replace("", "0")
    )
    return pd.to_numeric(normalized, errors="coerce").fillna(0.0)


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    lowered = {normalize(c): c for c in columns}
    for candidate in candidates:
        normalized_candidate = normalize(candidate)
        if normalized_candidate in lowered:
            return lowered[normalized_candidate]
    for col in columns:
        col_l = normalize(col)
        if any(normalize(candidate) in col_l for candidate in candidates):
            return col
    return None


def _infer_column_by_values(df: pd.DataFrame, prefer_date: bool = False) -> str | None:
    if df.empty:
        return None

    sample_size = min(len(df), 25)
    best_column = None
    best_score = 0.0

    for column in df.columns:
        series = df[column].dropna().astype(str).head(sample_size)
        if series.empty:
            continue

        if prefer_date:
            parsed = pd.to_datetime(series, errors="coerce")
            score = parsed.notna().mean()
        else:
            numeric_like = series.str.replace(r"[^0-9\.-]", "", regex=True).str.len() > 0
            score = 1.0 - numeric_like.mean()

        if score > best_score:
            best_score = float(score)
            best_column = column

    if best_score >= 0.5:
        return best_column
    return None


def _parse_generic(df: pd.DataFrame) -> pd.DataFrame:
    data = _normalize_columns(df)
    lower_map = {c: c.lower() for c in data.columns}
    data = data.rename(columns=lower_map)

    date_col_candidates = ["date", "transaction date", "posting date", "posted date", "transaction_date"]
    desc_col_candidates = ["description", "details", "memo", "transaction description", "name"]

    date_col = _find_column(data.columns.tolist(), date_col_candidates)
    desc_col = _find_column(data.columns.tolist(), desc_col_candidates)

    if date_col is None:
        date_col = _infer_column_by_values(data, prefer_date=True)
    if desc_col is None:
        desc_col = _infer_column_by_values(data, prefer_date=False)

    if date_col is None or desc_col is None:
        raise ValueError("CSV is missing required date/description columns.")

    amount_col = _find_column(data.columns.tolist(), ["amount"])
    debit_col = _find_column(data.columns.tolist(), ["debit", "withdrawal", "payment"])
    credit_col = _find_column(data.columns.tolist(), ["credit", "deposit"])

    if amount_col is not None:
        amount = _to_amount(data[amount_col])
    elif debit_col is not None or credit_col is not None:
        debit = _to_amount(data[debit_col]) if debit_col is not None else pd.Series(0, index=data.index, dtype=float)
        credit = _to_amount(data[credit_col]) if credit_col is not None else pd.Series(0, index=data.index, dtype=float)
        amount = credit - debit
    else:
        raise ValueError("CSV is missing amount or debit/credit columns.")

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(data[date_col], errors="coerce")
    out["description"] = data[desc_col].astype(str)
    out["amount"] = amount
    out["bank"] = "Generic"
    return out


def parse_statement_file(uploaded_file) -> pd.DataFrame:
    raw_df = _read_csv(uploaded_file)
    normalized = _normalize_columns(raw_df)

    if chase.can_parse(normalized):
        return chase.parse(normalized)
    if wells_fargo.can_parse(normalized):
        return wells_fargo.parse(normalized)
    if pnc.can_parse(normalized):
        return pnc.parse(normalized)

    return _parse_generic(normalized)

