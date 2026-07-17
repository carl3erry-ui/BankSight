from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from categorizer import categorize_transactions
from dashboard_components import (
    build_excel_export,
    build_html_report,
    render_categories_tab,
    render_cash_flow_tab,
    render_merchants_tab,
    render_overview_tab,
    render_transactions_tab,
)
from parsers import parse_statement_file


st.set_page_config(page_title="BankSight", layout="wide")


REQUIRED_COLUMNS = ["date", "description", "amount", "bank", "source_file", "merchant", "category"]


def _init_state() -> None:
    if "client_name" not in st.session_state:
        st.session_state.client_name = ""
    if "client_email" not in st.session_state:
        st.session_state.client_email = ""
    if "client_ready" not in st.session_state:
        st.session_state.client_ready = False
    if "transactions_df" not in st.session_state:
        st.session_state.transactions_df = pd.DataFrame(columns=REQUIRED_COLUMNS)


def _start_new_client() -> None:
    st.session_state.client_name = ""
    st.session_state.client_email = ""
    st.session_state.client_ready = False
    st.session_state.transactions_df = pd.DataFrame(columns=REQUIRED_COLUMNS)


def _client_intake_screen() -> None:
    st.title("BankSight")
    st.subheader("Client Setup")
    st.caption("Enter client details to start analyzing one or more bank statements.")

    with st.form("client_form", clear_on_submit=False):
        client_name = st.text_input("Client Name", value=st.session_state.client_name)
        client_email = st.text_input("Client Email", value=st.session_state.client_email)
        submitted = st.form_submit_button("Continue")

    if submitted:
        if not client_name.strip() or not client_email.strip():
            st.error("Client Name and Client Email are required.")
            return
        st.session_state.client_name = client_name.strip()
        st.session_state.client_email = client_email.strip()
        st.session_state.client_ready = True
        st.rerun()


def _parse_uploaded_files(uploaded_files: list[st.runtime.uploaded_file_manager.UploadedFile]) -> pd.DataFrame:
    parsed_frames: list[pd.DataFrame] = []
    errors: list[str] = []

    for uploaded in uploaded_files:
        try:
            parsed_df = parse_statement_file(uploaded)
            if parsed_df.empty:
                continue
            parsed_df["source_file"] = uploaded.name
            parsed_frames.append(parsed_df)
        except Exception as exc:
            errors.append(f"{uploaded.name}: {exc}")

    if errors:
        st.warning("Some files could not be parsed:\n- " + "\n- ".join(errors))

    if not parsed_frames:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    merged = pd.concat(parsed_frames, ignore_index=True)
    merged = categorize_transactions(merged)

    for col in REQUIRED_COLUMNS:
        if col not in merged.columns:
            merged[col] = "" if col not in {"amount", "date"} else (0.0 if col == "amount" else pd.NaT)

    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged["amount"] = pd.to_numeric(merged["amount"], errors="coerce").fillna(0.0)
    merged = merged.sort_values("date", ascending=False)

    return merged[REQUIRED_COLUMNS].reset_index(drop=True)


def _dashboard_screen() -> None:
    with st.sidebar:
        st.header("Client")
        st.write(st.session_state.client_name)
        st.write(st.session_state.client_email)
        st.divider()
        if st.button("Start New Client", use_container_width=True):
            _start_new_client()
            st.rerun()

    st.title(f"BankSight Dashboard - {st.session_state.client_name}")
    st.caption("Upload one or more statement CSV files from Chase, Wells Fargo, PNC, or generic format.")

    uploaded_files = st.file_uploader(
        "Upload bank statement CSVs",
        type=["csv"],
        accept_multiple_files=True,
        help="You can upload multiple files at once.",
    )

    if uploaded_files:
        st.session_state.transactions_df = _parse_uploaded_files(uploaded_files)

    df = st.session_state.transactions_df
    if df.empty:
        st.info("Upload statement files to build the dashboard.")
        return

    tab_overview, tab_cash_flow, tab_categories, tab_merchants, tab_transactions, tab_export = st.tabs(
        ["Overview", "Cash Flow", "Categories", "Merchants", "Transactions", "Export"]
    )

    with tab_overview:
        render_overview_tab(df, st.session_state.client_name)

    with tab_cash_flow:
        render_cash_flow_tab(df)

    with tab_categories:
        render_categories_tab(df)

    with tab_merchants:
        render_merchants_tab(df)

    with tab_transactions:
        render_transactions_tab(df)

    with tab_export:
        st.subheader("Export")
        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        excel_bytes = build_excel_export(df)
        html_report = build_html_report(
            df=df,
            client_name=st.session_state.client_name,
            client_email=st.session_state.client_email,
            generated_at=generated_at,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Download Excel",
                data=excel_bytes,
                file_name=f"{st.session_state.client_name.replace(' ', '_').lower()}_banksight_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                "Download HTML Report",
                data=html_report.encode("utf-8"),
                file_name=f"{st.session_state.client_name.replace(' ', '_').lower()}_banksight_report.html",
                mime="text/html",
                use_container_width=True,
            )


def main() -> None:
    _init_state()

    if not st.session_state.client_ready:
        _client_intake_screen()
        return

    _dashboard_screen()


if __name__ == "__main__":
    main()

