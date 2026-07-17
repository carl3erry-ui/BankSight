from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


THEME = {
    "bg": "#0f1419",
    "card": "#1a2332",
    "border": "#2a3544",
    "text": "#e7e9ea",
    "muted": "#8b98a5",
    "green": "#2ecc71",
    "red": "#e74c3c",
    "blue": "#3498db",
    "accent": "#f39c12",
    "hover": "#243044",
}


MAJOR_COLORS = {
    "Sales / POS Deposits": "#2ecc71",
    "Payroll": "#e74c3c",
    "Supplies / COGS": "#e67e22",
    "Utilities": "#1abc9c",
    "Rent / Lease": "#3498db",
    "Software Subscriptions": "#00bcd4",
    "Transfers": "#607d8b",
    "Owner Draws / Personal": "#8d6e63",
    "Operating Expense": "#95a5a6",
    "General Income": "#27ae60",
    "Payment Processor Fees": "#c0392b",
    "Bank Fees": "#9b59b6",
    "Taxes": "#9b59b6",
    "Debt & Interest": "#795548",
    "Refunds": "#16a085",
    "Uncategorized": "#7f8c8d",
}


_THEME_INJECTED_KEY = "banksight_theme_injected"


def _inject_theme() -> None:
    if st.session_state.get(_THEME_INJECTED_KEY):
        return

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: {THEME['bg']};
            color: {THEME['text']};
        }}
        [data-testid="stHeader"] {{
            background: rgba(15, 20, 25, 0.75);
            backdrop-filter: blur(8px);
        }}
        [data-testid="stSidebar"] {{
            background: #121922;
        }}
        h1, h2, h3, h4, h5, h6, p, label, span, li, .stMarkdown {{
            color: {THEME['text']} !important;
        }}
        .bs-card {{
            background: {THEME['card']};
            border: 1px solid {THEME['border']};
            border-radius: 12px;
            padding: 14px 16px;
            min-height: 112px;
        }}
        .bs-label {{
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: .06em;
            color: {THEME['muted']};
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .bs-value {{
            font-size: 1.35rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        .bs-sub {{
            margin-top: 6px;
            font-size: 0.76rem;
            color: {THEME['muted']};
        }}
        .bs-hero {{
            background: linear-gradient(135deg, #1a2332 0%, #0f1419 100%);
            border: 1px solid {THEME['border']};
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 12px;
        }}
        .bs-hero-title {{
            font-size: 1.2rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }}
        .bs-hero-sub {{
            font-size: 0.76rem;
            color: {THEME['muted']};
            margin-top: 3px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state[_THEME_INJECTED_KEY] = True


def _chart_layout(title: str) -> dict:
    return {
        "title": {"text": f"<b>{title}</b>", "x": 0.5, "font": {"size": 14, "color": THEME["text"]}},
        "paper_bgcolor": THEME["bg"],
        "plot_bgcolor": THEME["card"],
        "font": {"color": THEME["text"], "size": 11},
        "margin": {"l": 16, "r": 16, "t": 56, "b": 36},
    }


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working["amount"] = pd.to_numeric(working["amount"], errors="coerce").fillna(0.0)
    working["description"] = working["description"].fillna("").astype(str)
    working["merchant"] = working["merchant"].fillna("Unknown").astype(str)
    working["category"] = working["category"].fillna("Uncategorized").astype(str)
    working["bank"] = working["bank"].fillna("Unknown").astype(str)
    if "source_file" not in working.columns:
        working["source_file"] = ""
    working["month"] = working["date"].dt.to_period("M").astype(str)
    return working.dropna(subset=["date"])


def _kpi_card(label: str, value: str, help_text: str, color: str) -> str:
    return (
        "<div class='bs-card'>"
        f"<div class='bs-label'>{label}</div>"
        f"<div class='bs-value' style='color:{color}'>{value}</div>"
        f"<div class='bs-sub'>{help_text}</div>"
        "</div>"
    )


def _selected_months_widget(df: pd.DataFrame, key: str) -> tuple[pd.DataFrame, list[str]]:
    months = sorted(df["month"].dropna().unique().tolist())
    labels = {m: pd.Period(m, freq="M").strftime("%b %Y") for m in months}
    default = st.session_state.get(key, months)
    chosen = st.multiselect(
        "Select Month(s)",
        options=months,
        default=[m for m in default if m in months],
        format_func=lambda m: labels.get(m, m),
        key=f"{key}_widget",
    )
    st.session_state[key] = chosen if chosen else months
    selected = st.session_state[key]
    return df[df["month"].isin(selected)].copy(), selected


def _group_outflows(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["amount"] < 0].copy()
    out["abs_amount"] = out["amount"].abs()
    return out


def render_overview_tab(df: pd.DataFrame, client_name: str) -> None:
    _inject_theme()
    st.markdown(
        f"""
        <div class="bs-hero">
          <div class="bs-hero-title">{client_name} • Use of Funds Dashboard</div>
          <div class="bs-hero-sub">Multi-period view with sources, uses, and vendor concentration</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    safe_df = _prepare(df).sort_values("date")
    if safe_df.empty:
        st.info("No valid dated transactions available for overview charts.")
        return

    filtered, selected_months = _selected_months_widget(safe_df, "banksight_month_selection")

    if filtered.empty:
        st.warning("No transactions in the selected months.")
        return

    income = filtered.loc[filtered["amount"] > 0, "amount"].sum()
    expenses = abs(filtered.loc[filtered["amount"] < 0, "amount"].sum())
    net = income - expenses
    daily_out = filtered.loc[filtered["amount"] < 0].groupby(filtered["date"].dt.date)["amount"].sum()
    avg_daily_spend = abs(daily_out.mean()) if not daily_out.empty else 0.0
    largest_outflow_row = filtered.loc[filtered["amount"].idxmin()]

    sel_text = "All periods" if len(selected_months) == safe_df["month"].nunique() else ", ".join(selected_months)
    st.caption(f"Showing: {sel_text}")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.markdown(_kpi_card("Total Income", _money(income), "Inflows across selected months", THEME["green"]), unsafe_allow_html=True)
    k2.markdown(_kpi_card("Total Expenses", _money(expenses), "Outflows (use of funds)", THEME["red"]), unsafe_allow_html=True)
    k3.markdown(_kpi_card("Net Cash Flow", _money(net), "Income minus expenses", THEME["blue"]), unsafe_allow_html=True)
    k4.markdown(_kpi_card("Avg Daily Spend", _money(avg_daily_spend), "Average daily outflow", THEME["accent"]), unsafe_allow_html=True)
    k5.markdown(
        _kpi_card(
            "Largest Outflow",
            _money(abs(float(largest_outflow_row["amount"]))),
            str(largest_outflow_row["merchant"])[:24],
            THEME["text"],
        ),
        unsafe_allow_html=True,
    )

    running = filtered.copy()
    running["balance"] = running["amount"].cumsum()
    balance_fig = px.line(running, x="date", y="balance", color_discrete_sequence=[THEME["accent"]])
    balance_fig.update_layout(**_chart_layout("Balance Over Time"))
    balance_fig.update_xaxes(gridcolor=THEME["border"])
    balance_fig.update_yaxes(gridcolor=THEME["border"], tickprefix="$")

    weekly = filtered.copy()
    weekly["week"] = weekly["date"].dt.to_period("W").astype(str)
    weekly_flow = weekly.groupby("week", as_index=False)["amount"].sum().tail(16)
    weekly_fig = px.bar(
        weekly_flow,
        x="week",
        y="amount",
        color="amount",
        color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
    )
    weekly_fig.update_layout(**_chart_layout("Weekly Net Cash Flow"), coloraxis_showscale=False)
    weekly_fig.update_xaxes(gridcolor=THEME["border"])
    weekly_fig.update_yaxes(gridcolor=THEME["border"], tickprefix="$")

    monthly = filtered.copy()
    monthly_flow = monthly.groupby("month", as_index=False)["amount"].sum().tail(12)
    monthly_fig = go.Figure()
    monthly_fig.add_trace(
        go.Bar(x=monthly_flow["month"], y=monthly_flow["amount"], marker_color=THEME["blue"], name="Net")
    )
    monthly_fig.update_layout(**_chart_layout("Monthly Net Cash Flow"))
    monthly_fig.update_xaxes(gridcolor=THEME["border"])
    monthly_fig.update_yaxes(gridcolor=THEME["border"], tickprefix="$")

    category_expense = _group_outflows(filtered)
    by_category = (
        category_expense.groupby("category", as_index=False)["abs_amount"].sum().sort_values("abs_amount", ascending=False)
    )
    category_fig = px.pie(
        by_category.head(10),
        values="abs_amount",
        names="category",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Dark24,
    )
    category_fig.update_layout(**_chart_layout("Expense Category Breakdown"))

    col_a, col_b = st.columns(2)
    col_a.plotly_chart(balance_fig, use_container_width=True)
    col_b.plotly_chart(weekly_fig, use_container_width=True)

    col_c, col_d = st.columns(2)
    col_c.plotly_chart(monthly_fig, use_container_width=True)
    col_d.plotly_chart(category_fig, use_container_width=True)

    st.markdown("### Sources to Uses")
    inflows = filtered[filtered["amount"] > 0].groupby("category", as_index=False)["amount"].sum()
    outflows = _group_outflows(filtered).groupby("category", as_index=False)["abs_amount"].sum()
    outflows = outflows.sort_values("abs_amount", ascending=False).head(10)

    if not inflows.empty and not outflows.empty:
        src_labels = inflows["category"].tolist()
        tgt_labels = outflows["category"].tolist()
        labels = src_labels + ["Operating Cash"] + tgt_labels
        cash_idx = len(src_labels)

        s, t, v, c = [], [], [], []
        for i, row in inflows.iterrows():
            s.append(i)
            t.append(cash_idx)
            v.append(float(row["amount"]))
            c.append("rgba(46, 204, 113, 0.40)")

        for i, row in outflows.iterrows():
            s.append(cash_idx)
            t.append(cash_idx + 1 + i)
            v.append(float(row["abs_amount"]))
            c.append("rgba(231, 76, 60, 0.35)")

        sankey = go.Figure(
            go.Sankey(
                node={
                    "label": labels,
                    "pad": 14,
                    "thickness": 16,
                    "color": [THEME["green"]] * len(src_labels) + [THEME["accent"]] + [THEME["red"]] * len(tgt_labels),
                },
                link={"source": s, "target": t, "value": v, "color": c},
            )
        )
        sankey.update_layout(**_chart_layout("Sources → Uses of Funds (Sankey)"), height=430)
        st.plotly_chart(sankey, use_container_width=True)

    st.markdown("### Use of Funds Breakdown")
    outflow_detail = _group_outflows(filtered)
    treemap_data = outflow_detail.groupby(["category", "merchant"], as_index=False)["abs_amount"].sum()
    if not treemap_data.empty:
        treemap = px.treemap(
            treemap_data,
            path=["category", "merchant"],
            values="abs_amount",
            color="category",
            color_discrete_map=MAJOR_COLORS,
        )
        treemap.update_layout(**_chart_layout("Use of Funds Treemap"), height=520)
        st.plotly_chart(treemap, use_container_width=True)

        drill_col1, drill_col2 = st.columns([1, 1])
        major = drill_col1.selectbox(
            "Drilldown Category",
            options=sorted(outflow_detail["category"].unique().tolist()),
            key="overview_drill_category",
        )
        sub_df = outflow_detail[outflow_detail["category"] == major].copy().sort_values("abs_amount", ascending=False)
        merchant_options = ["All"] + sorted(sub_df["merchant"].unique().tolist())
        merchant = drill_col2.selectbox("Merchant", options=merchant_options, key="overview_drill_merchant")
        if merchant != "All":
            sub_df = sub_df[sub_df["merchant"] == merchant]

        display = sub_df[["date", "merchant", "description", "category", "amount", "bank", "source_file"]].copy()
        display = display.sort_values("date", ascending=False)
        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            },
        )

    bottom_l, bottom_r = st.columns(2)

    inflow_mix = filtered[filtered["amount"] > 0].groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    if not inflow_mix.empty:
        pie = px.pie(inflow_mix, values="amount", names="category", hole=0.52, color_discrete_sequence=px.colors.qualitative.Bold)
        pie.update_layout(**_chart_layout("Inflow Composition"))
        bottom_l.plotly_chart(pie, use_container_width=True)

    vendors = _group_outflows(filtered).groupby("merchant", as_index=False)["abs_amount"].sum().sort_values("abs_amount", ascending=False).head(15)
    if not vendors.empty:
        top = px.bar(vendors.sort_values("abs_amount", ascending=True), x="abs_amount", y="merchant", orientation="h", color="abs_amount", color_continuous_scale="Reds")
        top.update_layout(**_chart_layout("Top Payees / Vendors"), coloraxis_showscale=False)
        top.update_xaxes(gridcolor=THEME["border"], tickprefix="$")
        top.update_yaxes(gridcolor=THEME["border"])
        bottom_r.plotly_chart(top, use_container_width=True)


def render_cash_flow_tab(df: pd.DataFrame) -> None:
    _inject_theme()
    st.subheader("Cash Flow")
    cash_df = _prepare(df)
    if cash_df.empty:
        st.info("No monthly cash flow available.")
        return

    cash_df["month"] = cash_df["date"].dt.to_period("M").astype(str)
    cash_df["week"] = cash_df["date"].dt.to_period("W").astype(str)

    monthly = cash_df.groupby("month", as_index=False)["amount"].sum().sort_values("month")
    weekly = cash_df.groupby("week", as_index=False)["amount"].sum().sort_values("week").tail(20)

    filtered, _ = _selected_months_widget(cash_df, "banksight_month_selection_cashflow")
    filtered["month"] = filtered["date"].dt.to_period("M").astype(str)
    filtered["week"] = filtered["date"].dt.to_period("W").astype(str)

    monthly = filtered.groupby("month", as_index=False)["amount"].sum().sort_values("month")
    weekly = filtered.groupby("week", as_index=False)["amount"].sum().sort_values("week").tail(20)

    fig = px.line(
        monthly,
        x="month",
        y="amount",
        markers=True,
        labels={"month": "Month", "amount": "Net Amount"},
        color_discrete_sequence=[THEME["accent"]],
    )
    fig.update_layout(**_chart_layout("Monthly Net Cash Flow"))
    fig.update_xaxes(gridcolor=THEME["border"])
    fig.update_yaxes(gridcolor=THEME["border"], tickprefix="$")
    st.plotly_chart(fig, use_container_width=True)

    weekly_fig = px.bar(
        weekly,
        x="week",
        y="amount",
        color="amount",
        color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
    )
    weekly_fig.update_layout(**_chart_layout("Weekly Net Cash Flow"), coloraxis_showscale=False)
    weekly_fig.update_xaxes(gridcolor=THEME["border"])
    weekly_fig.update_yaxes(gridcolor=THEME["border"], tickprefix="$")
    st.plotly_chart(weekly_fig, use_container_width=True)

    inflow_outflow = filtered.assign(
        inflow=filtered["amount"].where(filtered["amount"] > 0, 0),
        outflow=(-filtered["amount"].where(filtered["amount"] < 0, 0)),
    )
    breakdown = inflow_outflow.groupby("month", as_index=False)[["inflow", "outflow"]].sum().sort_values("month")
    st.dataframe(
        breakdown,
        use_container_width=True,
        column_config={
            "inflow": st.column_config.NumberColumn("Inflow", format="$%.2f"),
            "outflow": st.column_config.NumberColumn("Outflow", format="$%.2f"),
        },
    )


def render_categories_tab(df: pd.DataFrame) -> None:
    _inject_theme()
    st.subheader("Categories")
    safe_df = _prepare(df)
    safe_df, _ = _selected_months_widget(safe_df, "banksight_month_selection_categories")
    cat_df = (
        safe_df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    )
    if cat_df.empty:
        st.info("No category data available.")
        return

    cat_df["absolute"] = cat_df["amount"].abs()
    fig = px.pie(
        cat_df.sort_values("absolute", ascending=False),
        values="absolute",
        names="category",
        title="Category Distribution",
        hole=0.35,
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig.update_layout(**_chart_layout("Category Distribution"))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        cat_df.drop(columns=["absolute"]),
        use_container_width=True,
        column_config={"amount": st.column_config.NumberColumn("Net Amount", format="$%.2f")},
    )


def render_merchants_tab(df: pd.DataFrame) -> None:
    _inject_theme()
    st.subheader("Merchants")
    safe_df = _prepare(df)
    safe_df, _ = _selected_months_widget(safe_df, "banksight_month_selection_merchants")
    merchant_df = (
        safe_df.groupby("merchant", as_index=False)["amount"].sum().sort_values("amount", ascending=True)
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
    fig.update_layout(**_chart_layout("Top Merchants by Net Amount"))
    fig.update_xaxes(gridcolor=THEME["border"], tickprefix="$")
    fig.update_yaxes(gridcolor=THEME["border"])
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        merchant_df.sort_values("amount", ascending=False),
        use_container_width=True,
        column_config={"amount": st.column_config.NumberColumn("Net Amount", format="$%.2f")},
    )


def render_transactions_tab(df: pd.DataFrame) -> None:
    _inject_theme()
    st.subheader("Transactions")

    working = _prepare(df)
    if working.empty:
        st.info("No transactions available.")
        return

    min_date = working["date"].dropna().min()
    max_date = working["date"].dropna().max()

    f1, f2, f3 = st.columns([2, 2, 1])
    selected_dates = f1.date_input("Date Range", value=(min_date.date(), max_date.date()))
    search_text = f2.text_input("Search", value="", placeholder="Description, merchant, category, bank, source file").strip().lower()
    min_amount = float(working["amount"].min())
    max_amount = float(working["amount"].max())
    amount_filter = f3.slider("Min Abs $", min_value=0, max_value=max(int(abs(min_amount)), int(abs(max_amount))), value=0)

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
            + " "
            + filtered["category"].fillna("").astype(str).str.lower()
            + " "
            + filtered["bank"].fillna("").astype(str).str.lower()
            + " "
            + filtered["source_file"].fillna("").astype(str).str.lower()
        )
        filtered = filtered[search_blob.str.contains(search_text, na=False)]

    if amount_filter > 0:
        filtered = filtered[filtered["amount"].abs() >= amount_filter]

    filtered = filtered.sort_values("date", ascending=False)
    st.caption(f"Showing {len(filtered):,} transactions")
    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "description": st.column_config.TextColumn("Description", width="large"),
            "merchant": st.column_config.TextColumn("Merchant", width="medium"),
            "category": st.column_config.TextColumn("Category", width="medium"),
            "bank": st.column_config.TextColumn("Bank", width="small"),
        },
    )


def build_excel_export(df: pd.DataFrame) -> bytes:
    _inject_theme()
    safe_df = _prepare(df).sort_values("date", ascending=False)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        safe_df.to_excel(writer, index=False, sheet_name="Transactions")

        summary = pd.DataFrame(
            {
                "metric": ["transactions", "inflow", "outflow", "net_cash_flow"],
                "value": [
                    len(safe_df),
                    safe_df.loc[safe_df["amount"] > 0, "amount"].sum(),
                    abs(safe_df.loc[safe_df["amount"] < 0, "amount"].sum()),
                    safe_df["amount"].sum(),
                ],
            }
        )
        summary.to_excel(writer, index=False, sheet_name="Summary")

        by_category = safe_df.groupby("category", as_index=False)["amount"].sum()
        by_category.to_excel(writer, index=False, sheet_name="By Category")

        by_merchant = safe_df.groupby("merchant", as_index=False)["amount"].sum()
        by_merchant.to_excel(writer, index=False, sheet_name="By Merchant")

    output.seek(0)
    return output.getvalue()


def build_html_report(df: pd.DataFrame, client_name: str, client_email: str, generated_at: str) -> str:
    safe_df = _prepare(df).sort_values("date", ascending=False)

    income = safe_df.loc[safe_df["amount"] > 0, "amount"].sum()
    expenses = abs(safe_df.loc[safe_df["amount"] < 0, "amount"].sum())
    net = safe_df["amount"].sum()

    by_category = safe_df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    by_merchant = safe_df.groupby("merchant", as_index=False)["amount"].sum().sort_values("amount", ascending=False)

    trend = safe_df.groupby("month", as_index=False)["amount"].sum().sort_values("month")
    trend_fig = go.Figure()
    trend_fig.add_trace(go.Bar(x=trend["month"], y=trend["amount"], marker_color=THEME["blue"], name="Net"))
    trend_fig.update_layout(
        title="Monthly Net Cash Flow",
        paper_bgcolor=THEME["bg"],
        plot_bgcolor=THEME["card"],
        font={"color": THEME["text"]},
        margin={"l": 16, "r": 16, "t": 48, "b": 30},
    )

    expenses_only = _group_outflows(safe_df).groupby("category", as_index=False)["abs_amount"].sum()
    expense_fig = px.pie(expenses_only, values="abs_amount", names="category", hole=0.55, color_discrete_sequence=px.colors.qualitative.Dark24)
    expense_fig.update_layout(
        title="Expense Mix",
        paper_bgcolor=THEME["bg"],
        plot_bgcolor=THEME["card"],
        font={"color": THEME["text"]},
        margin={"l": 16, "r": 16, "t": 48, "b": 30},
    )

    trend_html = pio.to_html(trend_fig, include_plotlyjs="inline", full_html=False, config={"displayModeBar": False})
    expense_html = pio.to_html(expense_fig, include_plotlyjs=False, full_html=False, config={"displayModeBar": False})

    transactions_html = safe_df.to_html(index=False, classes="table")
    category_html = by_category.to_html(index=False, classes="table")
    merchant_html = by_merchant.head(50).to_html(index=False, classes="table")

    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>BankSight Report - {client_name}</title>
  <style>
        body {{ font-family: "Segoe UI", Tahoma, sans-serif; margin: 0; background: #0f1419; color: #e7e9ea; }}
        .wrap {{ max-width: 1160px; margin: 0 auto; padding: 24px; }}
        .hero {{ background: linear-gradient(115deg, #1a2332 0%, #0f1419 100%); color: white; border-radius: 16px; padding: 20px 24px; border:1px solid #2a3544; }}
        .hero h1 {{ margin: 0; font-size: 30px; }}
        .meta {{ margin-top: 8px; font-size: 13px; color: #8b98a5; }}
        .cards {{ display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 12px; margin: 16px 0 22px; }}
        .card {{ background: #1a2332; border: 1px solid #2a3544; border-radius: 12px; padding: 12px; }}
        .card .k {{ color: #8b98a5; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }}
        .card .v {{ margin-top: 8px; color: #e7e9ea; font-size: 26px; font-weight: 800; }}
        h2 {{ margin: 22px 0 10px; }}
        .table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; font-size: 12px; background: #1a2332; }}
        .table th, .table td {{ border: 1px solid #2a3544; padding: 7px; text-align: left; }}
        .table th {{ background: #141d2a; }}
        .chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin: 18px 0; }}
        @media (max-width: 900px) {{ .cards, .chart-grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
    <div class=\"wrap\">
        <div class=\"hero\">
            <h1>BankSight Report: {client_name}</h1>
            <div class=\"meta\">{client_email} | Generated {generated_at}</div>
        </div>
        <div class=\"cards\">
            <div class=\"card\"><div class=\"k\">Transactions</div><div class=\"v\">{len(safe_df):,}</div></div>
            <div class=\"card\"><div class=\"k\">Income</div><div class=\"v\">${income:,.2f}</div></div>
            <div class=\"card\"><div class=\"k\">Expenses</div><div class=\"v\">${expenses:,.2f}</div></div>
            <div class=\"card\"><div class=\"k\">Net Cash Flow</div><div class=\"v\">${net:,.2f}</div></div>
        </div>
        <div class="chart-grid">
            <div>{trend_html}</div>
            <div>{expense_html}</div>
        </div>
        <h2>Category Summary</h2>
        {category_html}
        <h2>Merchant Summary (Top 50)</h2>
        {merchant_html}
        <h2>Transactions</h2>
        {transactions_html}
    </div>
</body>
</html>
"""

