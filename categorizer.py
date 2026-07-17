from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd


TRASH_TOKENS = {
    "DEBIT CARD PURCHASE",
    "POS PURCHASE",
    "PURCHASE AUTHORIZED ON",
    "DBT PURCHASE",
    "CHECKCARD",
    "WITHDRAWAL",
    "ONLINE TRANSFER",
    "ACH CREDIT",
    "ACH DEBIT",
    "PPD ID",
    "TRACE",
    "REF",
    "WEB ID",
    "SQ",
    "TST",
}


MERCHANT_REPLACEMENTS = [
    (r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " "),
    (r"\b\d{4,}\b", " "),
    (r"[#*]+", " "),
    (r"\s+", " "),
]


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _derive_merchant(description: str) -> str:
    merchant = description.upper().strip()
    for pattern, replacement in MERCHANT_REPLACEMENTS:
        merchant = re.sub(pattern, replacement, merchant)

    tokens = [token for token in merchant.split(" ") if token and token not in TRASH_TOKENS]
    merchant = " ".join(tokens).strip(" -:.,")

    merchant = merchant.replace("DOORDASH", "DOORDASH")
    merchant = merchant.replace("UBER *", "UBER ")
    merchant = merchant.replace("SPOTIFYUSA", "SPOTIFY")
    merchant = re.sub(r"\s+", " ", merchant).strip()

    return merchant[:64].title() if merchant else "Unknown"


def _derive_category(description: str, merchant: str, amount: float) -> str:
    text = f"{description} {merchant}".lower()

    sales_pos = [
        "toast", "stripe", "square", "sq *", "squarespace payments", "doordash", "uber eats",
        "grubhub", "postmates", "shopify payments", "clover", "sumup", "pos deposit", "merchant deposit",
    ]
    payroll = ["payroll", "gusto", "adp", "paychex", "intuit payroll", "salary", "wages"]
    rent_lease = ["rent", "lease", "landlord", "property mgmt", "property management", "wework"]
    utilities = ["utility", "electric", "water", "sewer", "gas bill", "internet", "comcast", "att", "verizon"]
    supplies_cogs = [
        "restaurant depot", "sysco", "us foods", "costco business", "staples", "office depot", "uline", "amazon business",
        "inventory", "supplies", "wholesale", "cogs", "ingredient", "packaging",
    ]
    software = [
        "quickbooks", "xero", "shopify", "stripe fee", "slack", "notion", "microsoft", "google workspace", "aws", "adobe",
        "zoom", "dropbox", "hubspot", "canva", "github", "figma",
    ]
    transfers = ["transfer", "zelle", "venmo", "wire", "ach", "cash app", "paypal", "internal transfer"]
    owner_draws = ["owner draw", "owner's draw", "owners draw", "personal", "atm withdrawal", "cash withdrawal", "draw"]

    if _contains_any(text, sales_pos):
        return "Sales / POS Deposits" if amount > 0 else "Payment Processor Fees"
    if _contains_any(text, payroll):
        return "Payroll"
    if _contains_any(text, rent_lease):
        return "Rent / Lease"
    if _contains_any(text, utilities):
        return "Utilities"
    if _contains_any(text, supplies_cogs):
        return "Supplies / COGS"
    if _contains_any(text, software):
        return "Software Subscriptions"
    if _contains_any(text, transfers):
        return "Transfers"
    if _contains_any(text, owner_draws):
        return "Owner Draws / Personal"

    if _contains_any(text, ["refund", "reversal", "chargeback"]):
        return "Refunds"
    if _contains_any(text, ["tax", "irs", "franchise tax", "sales tax"]):
        return "Taxes"
    if _contains_any(text, ["interest", "loan", "credit card payment", "line of credit"]):
        return "Debt & Interest"
    if _contains_any(text, ["fee", "overdraft", "nsf", "service charge", "monthly maintenance"]):
        return "Bank Fees"

    if amount > 0:
        return "General Income"
    if amount < 0:
        return "Operating Expense"
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
        lambda row: _derive_category(str(row["description"]), str(row["merchant"]), float(row["amount"])),
        axis=1,
    )
    return result

