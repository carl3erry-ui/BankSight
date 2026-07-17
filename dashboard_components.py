"""Reusable Streamlit dashboard components."""

from collections import Counter
from typing import Any

import streamlit as st


def render_summary(transactions: list[dict[str, Any]]) -> None:
    """Render a compact summary for categorized transactions."""
    st.subheader("Summary")
    st.metric("Transactions", len(transactions))

    category_counts = Counter(
        str(transaction.get("category", "Uncategorized")) for transaction in transactions
    )
    if category_counts:
        st.bar_chart(category_counts)

    st.subheader("Transactions")
    st.dataframe(transactions, use_container_width=True)

