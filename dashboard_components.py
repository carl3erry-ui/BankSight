from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import streamlit as st


def render_overview_tab(df: pd.DataFrame, client_name: str) -> None:
    st.subheader(f"Overview - {client_name}")

    safe_df = df.copy()
    safe_df["date"] = pd.to_datetime(safe_df["date"], errors="coerce")
    safe_df["amount"] = pd.to_numeric(safe_df["amount"], errors="coerce").fillna(0.0)
    safe_df = safe_df.dropna(subset=["date"]).sort_values("date")

    total_transactions = len(safe_df)
    total_inflow = safe_df.loc[safe_df["amount"] > 0, "amount"].sum()
    total_outflow = abs(safe_df.loc[safe_df["amount"] < 0, "amount"].sum())
    net_cash_flow = total_inflow - total_outflow

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Transactions", f"{total_transactions:,}")
    c2.metric("Inflow", f"${total_inflow:,.2f}")
    c3.metric("Outflow", f"${total_outflow:,.2f}")
    c4.metric("Net Cash Flow", f"${net_cash_flow:,.2f}")

    if safe_df.empty:
        st.info("No valid dated transactions available for overview charts.")
        return

    running = safe_df.copy()
    running["running_balance"] = running["amount"].cumsum()
    balance_chart = px.line(
        running,
        x="date",
        y="running_balance",
        title="Balance Trend",
        labels={"date": "Date", "running_balance": "Running Balance"},
    )

    cashflow = safe_df.copy()
    cashflow["month"] = cashflow["date"].dt.to_period("M").astype(str)
    monthly = cashflow.groupby("month", as_index=False)["amount"].sum().sort_values("month")
    cashflow_chart = px.bar(
        monthly,
        x="month",
        y="amount",
        title="Monthly Net Cash Flow",
        labels={"month": "Month", "amount": "Net Amount"},
    )

    category_df = (
        safe_df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    )
    category_pie = px.pie(category_df, values="amount", names="category", title="Category Mix")

    left, right = st.columns(2)
    left.plotly_chart(balance_chart, use_container_width=True)
    right.plotly_chart(cashflow_chart, use_container_width=True)

    left2, right2 = st.columns(2)
    bank_breakdown = (
        safe_df.groupby("bank", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    )
    if not bank_breakdown.empty:
        fig = px.bar(
            bank_breakdown,
            x="bank",
            y="amount",
            title="Net Amount by Bank",
            labels={"bank": "Bank", "amount": "Net Amount"},
        )
        left2.plotly_chart(fig, use_container_width=True)
    if not category_df.empty:
        right2.plotly_chart(category_pie, use_container_width=True)


def render_cash_flow_tab(df: pd.DataFrame) -> None:
    st.subheader("Cash Flow")
    cash_df = df.copy()
    cash_df["month"] = cash_df["date"].dt.to_period("M").astype(str)

    monthly = cash_df.groupby("month", as_index=False)["amount"].sum().sort_values("month")
    if monthly.empty:
        st.info("No monthly cash flow available.")
        return

    fig = px.line(
        monthly,
        x="month",
        y="amount",
        markers=True,
        title="Monthly Net Cash Flow",
        labels={"month": "Month", "amount": "Net Amount"},
    )
    st.plotly_chart(fig, use_container_width=True)

    inflow_outflow = cash_df.assign(
        inflow=cash_df["amount"].where(cash_df["amount"] > 0, 0),
        outflow=(-cash_df["amount"].where(cash_df["amount"] < 0, 0)),
    )
    breakdown = inflow_outflow.groupby("month", as_index=False)[["inflow", "outflow"]].sum().sort_values("month")
    st.dataframe(breakdown, use_container_width=True)


def render_categories_tab(df: pd.DataFrame) -> None:
    st.subheader("Categories")
    cat_df = (
        df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    )
    if cat_df.empty:
        st.info("No category data available.")
        return

    fig = px.pie(cat_df, values="amount", names="category", title="Category Distribution")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(cat_df, use_container_width=True)


def render_merchants_tab(df: pd.DataFrame) -> None:
    st.subheader("Merchants")
    merchant_df = (
        df.groupby("merchant", as_index=False)["amount"].sum().sort_values("amount", ascending=True)
    )
    if merchant_df.empty:
        st.info("No merchant data available.")
        return

    top_merchants = merchant_df.tail(20)
    fig = px.bar(
        top_merchants,
        x="amount",
        y="merchant",
        orientation="h",
        title="Top Merchants by Net Amount",
        labels={"merchant": "Merchant", "amount": "Net Amount"},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(merchant_df.sort_values("amount", ascending=False), use_container_width=True)


def render_transactions_tab(df: pd.DataFrame) -> None:
    st.subheader("Transactions")

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")

    min_date = working["date"].dropna().min()
    max_date = working["date"].dropna().max()

    selected_dates = None
    if pd.notna(min_date) and pd.notna(max_date):
        selected_dates = st.date_input("Date Range", value=(min_date.date(), max_date.date()))

    search_text = st.text_input("Search Description or Merchant", value="").strip().lower()

    category_options = sorted(working["category"].dropna().unique().tolist())
    selected_categories = st.multiselect(
        "Categories",
        options=category_options,
        default=category_options,
    )

    bank_options = sorted(working["bank"].dropna().unique().tolist())
    selected_banks = st.multiselect("Banks", options=bank_options, default=bank_options)

    filtered = working.copy()
    if selected_dates is not None and len(selected_dates) == 2:
        start_date, end_date = pd.to_datetime(selected_dates[0]), pd.to_datetime(selected_dates[1])
        filtered = filtered[(filtered["date"] >= start_date) & (filtered["date"] <= end_date)]

    if selected_categories:
        filtered = filtered[filtered["category"].isin(selected_categories)]

    if selected_banks:
        filtered = filtered[filtered["bank"].isin(selected_banks)]

    if search_text:
        search_blob = (
            filtered["description"].fillna("").astype(str).str.lower()
            + " "
            + filtered["merchant"].fillna("").astype(str).str.lower()
        )
        filtered = filtered[search_blob.str.contains(search_text, na=False)]

    filtered = filtered.sort_values("date", ascending=False)
    st.caption(f"Showing {len(filtered):,} transactions")
    st.dataframe(filtered, use_container_width=True)


def build_excel_export(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")

        summary = pd.DataFrame(
            {
                "metric": ["transactions", "inflow", "outflow", "net_cash_flow"],
                "value": [
                    len(df),
                    df.loc[df["amount"] > 0, "amount"].sum(),
                    abs(df.loc[df["amount"] < 0, "amount"].sum()),
                    df["amount"].sum(),
                ],
            }
        )
        summary.to_excel(writer, index=False, sheet_name="Summary")

        by_category = df.groupby("category", as_index=False)["amount"].sum()
        by_category.to_excel(writer, index=False, sheet_name="By Category")

        by_merchant = df.groupby("merchant", as_index=False)["amount"].sum()
        by_merchant.to_excel(writer, index=False, sheet_name="By Merchant")

    output.seek(0)
    return output.getvalue()


def build_html_report(df: pd.DataFrame, client_name: str, client_email: str, generated_at: str) -> str:
    metrics_html = f"""
    <ul>
      <li>Total Transactions: {len(df):,}</li>
      <li>Total Inflow: ${df.loc[df['amount'] > 0, 'amount'].sum():,.2f}</li>
      <li>Total Outflow: ${abs(df.loc[df['amount'] < 0, 'amount'].sum()):,.2f}</li>
      <li>Net Cash Flow: ${df['amount'].sum():,.2f}</li>
    </ul>
    """

    by_category = (
        df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    )
    by_merchant = (
        df.groupby("merchant", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    )

    transactions_html = df.sort_values("date", ascending=False).to_html(index=False)
    category_html = by_category.to_html(index=False)
    merchant_html = by_merchant.head(50).to_html(index=False)

    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>BankSight Report - {client_name}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
    h1, h2 {{ color: #0f172a; }}
    .meta {{ margin-bottom: 18px; color: #374151; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; font-size: 12px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 6px; text-align: left; }}
    th {{ background: #f9fafb; }}
  </style>
</head>
<body>
  <h1>BankSight Financial Report</h1>
  <div class=\"meta\">Client: {client_name}<br/>Email: {client_email}<br/>Generated: {generated_at}</div>
  <h2>Overview</h2>
  {metrics_html}
  <h2>Category Summary</h2>
  {category_html}
  <h2>Merchant Summary (Top 50)</h2>
  {merchant_html}
  <h2>Transactions</h2>
  {transactions_html}
</body>
</html>
"""

