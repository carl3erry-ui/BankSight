from __future__ import annotations

import re

import pandas as pd


CATEGORY_KEYWORDS = {
    "Income": ["payroll", "salary", "deposit", "refund", "interest"],
    "Rent & Utilities": ["rent", "electric", "water", "gas", "utility", "internet", "comcast"],
    "Food & Dining": ["restaurant", "coffee", "cafe", "doordash", "ubereats", "grubhub"],
    "Travel": ["uber", "lyft", "airlines", "hotel", "shell", "exxon", "chevron"],
    "Shopping": ["amazon", "walmart", "target", "costco", "ebay"],
    "Software & Subscriptions": ["microsoft", "google", "aws", "adobe", "slack", "notion"],
    "Transfers": ["zelle", "venmo", "transfer", "ach", "wire"],
    "Fees": ["fee", "charge", "penalty", "overdraft"],
}


MERCHANT_CLEANUP = [
    (r"\d{2}/\d{2}", ""),
    (r"\d{4,}", ""),
    (r"\s+", " "),
]


def _derive_merchant(description: str) -> str:
    merchant = description.upper()
    for pattern, replacement in MERCHANT_CLEANUP:
        merchant = re.sub(pattern, replacement, merchant)
    merchant = merchant.strip(" -#*")
    return merchant[:60] if merchant else "Unknown"


def _derive_category(description: str, amount: float) -> str:
    text = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    if amount > 0:
        return "Income"
    return "Uncategorized"


def categorize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        result = df.copy()
        if "merchant" not in result.columns:
            result["merchant"] = ""
        if "category" not in result.columns:
            result["category"] = ""
        return result

    result = df.copy()
    result["description"] = result["description"].fillna("").astype(str)
    result["amount"] = pd.to_numeric(result["amount"], errors="coerce").fillna(0.0)

    result["merchant"] = result["description"].apply(_derive_merchant)
    result["category"] = result.apply(
        lambda row: _derive_category(str(row["description"]), float(row["amount"])),
        axis=1,
    )
    return result

