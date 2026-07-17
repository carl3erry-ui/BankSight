"""Streamlit entry point for BankSight."""

import streamlit as st

from categorizer import categorize_transactions
from dashboard_components import render_summary
from parsers.generic import parse_generic_statement


def main() -> None:
    st.set_page_config(page_title="BankSight", layout="wide")
    st.title("BankSight")
    st.caption("CSV transaction review for bookkeepers managing multiple clients.")

    uploaded_file = st.file_uploader("Upload a CSV bank statement", type=["csv"])

    if not uploaded_file:
        st.info("Upload a CSV file to start reviewing transactions.")
        return

    transactions = parse_generic_statement(uploaded_file)
    categorized = categorize_transactions(transactions)
    render_summary(categorized)


if __name__ == "__main__":
    main()

