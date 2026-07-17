"""Simple transaction categorization helpers."""

from typing import Any


def categorize_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach a lightweight category to each transaction."""
    categorized: list[dict[str, Any]] = []
    for transaction in transactions:
        row = dict(transaction)
        description = str(row.get("description", "")).lower()

        if any(word in description for word in ("uber", "lyft", "shell", "exxon")):
            row["category"] = "Travel"
        elif any(word in description for word in ("amazon", "walmart", "target")):
            row["category"] = "Supplies"
        elif any(word in description for word in ("payroll", "salary")):
            row["category"] = "Payroll"
        else:
            row["category"] = "Uncategorized"

        categorized.append(row)

    return categorized

