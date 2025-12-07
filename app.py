# app.py

import numpy as np
import pandas as pd
from pathlib import Path

import streamlit as st
import plotly.express as px

# -------------------------------------------------------------------
# Paths and data loading
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_EXPORTS = PROJECT_ROOT / "data_exports"

TRUMP_START = pd.Timestamp("2025-01-20")


@st.cache_data
def load_data():
    awards = pd.read_csv(
        DATA_EXPORTS / "awards_master.csv",
        parse_dates=["first_action_date", "last_action_date", "first_negative_date"],
    )

    tx = pd.read_csv(
        DATA_EXPORTS / "transactions_deob.csv",
        parse_dates=["action_date"],
    )

    geo = pd.read_csv(DATA_EXPORTS / "geo_aggregation.csv")
    return awards, tx, geo


awards, tx, geo= load_data()

st.set_page_config(
    page_title="MA Grant Cuts – Trump Era",
    layout="wide",
)

st.title("Massachusetts Federal Grant Cuts – Trump Era Dashboard")


# Sidebar filters

st.sidebar.header("Global filters")

available_labels = sorted(awards["label"].dropna().unique())
label_filter = st.sidebar.multiselect(
    "Award classification (label)",
    available_labels,
    default=available_labels,
)

available_agencies = sorted(awards["awarding_agency_name"].dropna().unique())
agency_filter = st.sidebar.multiselect(
    "Awarding agency",
    available_agencies,
    default=[],
)

trump_only = st.sidebar.checkbox(
    "Trump-era only (transactions on or after 2025‑01‑20)",
    value=True,
)

# Apply filters to awards
awards_f = awards[awards["label"].isin(label_filter)].copy()
if agency_filter:
    awards_f = awards_f[awards_f["awarding_agency_name"].isin(agency_filter)]

# Overview respects Trump-era toggle
if trump_only and "trump_era_flag" in awards.columns:
    awards_f = awards_f[awards_f["trump_era_flag"] == 1].copy()

# Apply filters to transactions
if trump_only and "trump_era_flag" in tx.columns:
    tx_f = tx[tx["trump_era_flag"] == 1].copy()
else:
    tx_f = tx.copy()

# Tabs (tab name changed to "City Impacts")


(
    tab_overview,
    tab_time,
    tab_recipients,
    tab_geo,
    tab_programs,
    tab_cities
) = st.tabs(
    [
        "Overview",
        "Time Trends",
        "Recipients & Programs",
        "Geography & Equity",
        "Programs & Agencies",
        "City Impacts"
    ]
)

# 1. Overview tab


with tab_overview:
    c1, c2, c3 = st.columns(3, gap="large")
    total_deob = float(awards_f["total_deobligation_neg"].sum())
    total_pos = float(awards_f["total_obligation_pos"].sum())
    n_awards_cut = int((awards_f["total_deobligation_neg"] > 0).sum())
    deob_rate = (total_deob / total_pos * 100) if total_pos > 0 else np.nan

    c1.metric("Total de‑obligated dollars", f"${total_deob:,.0f}")
    c2.metric("Awards with cuts", f"{n_awards_cut:,}")
    c3.metric(
        "De‑obligation rate (amount basis)",
        f"{deob_rate:0.2f}%" if not np.isnan(deob_rate) else "NA",
    )

    by_label = (
        awards_f.groupby("label")["total_deobligation_neg"]
            .sum()
            .reset_index()
            .sort_values("total_deobligation_neg", ascending=False)
    )

    fig_label = px.bar(
        by_label,
        x="total_deobligation_neg",
        y="label",
        orientation="h",
        labels={
            "total_deobligation_neg": "De‑obligated dollars (USD)",
            "label": "Classification",
        },
        title="De‑obligated dollars by classification",
    )
    fig_label.update_layout(
        margin=dict(l=10, r=10, t=40, b=40),
        yaxis=dict(categoryorder="total ascending"),
    )
    st.plotly_chart(fig_label, key="overview_label")

    cuts = awards_f["total_deobligation_neg"]
    cuts = cuts[cuts > 0]
    if not cuts.empty:
        fig_hist = px.histogram(
            cuts,
            nbins=40,
            labels={"value": "De‑obligated dollars per award (USD)"},
            title="Distribution of cut sizes across awards",
        )
        fig_hist.update_layout(margin=dict(l=10, r=10, t=40, b=40))
        st.plotly_chart(fig_hist, key="overview_hist")


# 2. Time Trends tab


with tab_time:
    st.subheader("Time trends of de‑obligations")

    if "action_date" in tx_f.columns:
        tx_f["month"] = tx_f["action_date"].dt.to_period("M").dt.to_timestamp()

        by_month = (
            tx_f.groupby("month")["deobligated_amount_usd"]
                .sum()
                .reset_index()
                .sort_values("month")
        )

        fig_month = px.line(
            by_month,
            x="month",
            y="deobligated_amount_usd",
            markers=True,
            labels={
                "month": "Month",
                "deobligated_amount_usd": "De‑obligated dollars (USD)",
            },
            title="Total de‑obligations by month",
        )
        fig_month.update_layout(margin=dict(l=10, r=10, t=40, b=40))
        st.plotly_chart(fig_month, key="time_month")

        by_month_label = (
            tx_f.groupby(["month", "label"])["deobligated_amount_usd"]
                .sum()
                .reset_index()
                .sort_values("month")
        )

        fig_area = px.area(
            by_month_label,
            x="month",
            y="deobligated_amount_usd",
            color="label",
            labels={
                "month": "Month",
                "deobligated_amount_usd": "De‑obligated dollars (USD)",
                "label": "Classification",
            },
            title="Monthly de‑obligations by classification",
        )
        fig_area.update_layout(margin=dict(l=10, r=10, t=40, b=40))
        st.plotly_chart(fig_area, key="time_area")

        tx_join = tx_f.merge(
            awards_f[[c for c in ["awardid", "cfda_title"] if c in awards_f.columns]],
            on="awardid",
            how="left",
        )

        if "cfda_title" in tx_join.columns:
            by_prog_month = (
                tx_join.groupby(["month", "cfda_title"])["deobligated_amount_usd"]
                    .sum()
                    .reset_index()
            )

            top_cfda = (
                by_prog_month.groupby("cfda_title")["deobligated_amount_usd"]
                    .sum()
                    .nlargest(8)
                    .index
            )

            by_prog_month = by_prog_month[by_prog_month["cfda_title"].isin(top_cfda)]

            fig_prog_month = px.line(
                by_prog_month,
                x="month",
                y="deobligated_amount_usd",
                color="cfda_title",
                labels={
                    "month": "Month",
                    "deobligated_amount_usd": "De‑obligated dollars (USD)",
                    "cfda_title": "Program (CFDA)",
                },
                title="Monthly de‑obligations for top programs",
            )
            fig_prog_month.update_layout(margin=dict(l=10, r=10, t=40, b=40))
            st.plotly_chart(fig_prog_month, key="time_prog")


# 3. Recipients & Programs tab

with tab_recipients:
    c1, c2 = st.columns(2, gap="large")

    tx_rec = (
        tx_f.groupby("recipient_name")["deobligated_amount_usd"]
            .sum()
            .reset_index()
            .sort_values("deobligated_amount_usd", ascending=False)
            .head(20)
    )

    fig_rec = px.bar(
        tx_rec,
        x="deobligated_amount_usd",
        y="recipient_name",
        orientation="h",
        labels={
            "deobligated_amount_usd": "De‑obligated dollars (USD)",
            "recipient_name": "Recipient",
        },
        title="Top recipients by de‑obligated dollars",
    )
    fig_rec.update_layout(
        margin=dict(l=10, r=10, t=40, b=40),
        yaxis=dict(categoryorder="total ascending"),
    )
    c1.plotly_chart(fig_rec, key="recipients_top")

    canc_labels = {"CANCELLATION", "RESCISSION"}
    if "cfda_title" in awards_f.columns:
        top_prog = (
            awards_f[awards_f["label"].isin(canc_labels)]
                .groupby("cfda_title")["total_deobligation_neg"]
                .sum()
                .reset_index()
                .sort_values("total_deobligation_neg", ascending=False)
                .head(20)
        )

        fig_prog = px.bar(
            top_prog,
            x="total_deobligation_neg",
            y="cfda_title",
            orientation="h",
            labels={
                "total_deobligation_neg": "Cancelled/rescinded dollars (USD)",
                "cfda_title": "Program (CFDA)",
            },
            title="Top cancelled / rescinded programs",
        )
        fig_prog.update_layout(
            margin=dict(l=10, r=10, t=40, b=40),
            yaxis=dict(categoryorder="total ascending"),
        )
        c2.plotly_chart(fig_prog, key="recipients_prog")

    st.subheader("Award‑level table")
    max_deob = int(awards_f["total_deobligation_neg"].max() or 0)
    min_deob = st.slider(
        "Minimum de‑obligated dollars per award",
        min_value=0,
        max_value=max_deob,
        value=0,
        step=max(100000, max_deob // 50 if max_deob > 0 else 100000),
    )

    details_cols = [
        "awardid",
        "cfda_title",
        "awarding_agency_name",
        "label",
        "total_obligation_pos",
        "total_deobligation_neg",
    ]
    details_cols = [c for c in details_cols if c in awards_f.columns]
    details = (
        awards_f[awards_f["total_deobligation_neg"] >= min_deob][details_cols]
            .sort_values("total_deobligation_neg", ascending=False)
    )
    st.dataframe(details, height=400)


# 4. Geography & Equity tab

with tab_geo:
    st.subheader("County‑level equity view")

    if {"pct_minority", "deob_dollars_per_capita"}.issubset(geo.columns):
        geo_scatter = geo.dropna(subset=["pct_minority", "deob_dollars_per_capita"]).copy()
        fig_scatter = px.scatter(
            geo_scatter,
            x="pct_minority",
            y="deob_dollars_per_capita",
            size="population_total" if "population_total" in geo.columns else None,
            hover_name="county_name",
            labels={
                "pct_minority": "% minority (ACS DP05)",
                "deob_dollars_per_capita": "De‑obligated dollars per capita",
            },
            title="De‑obligations per capita vs % minority by county",
        )
        fig_scatter.update_layout(margin=dict(l=10, r=10, t=40, b=40))
        st.plotly_chart(fig_scatter, key="geo_scatter")

    c1, c2 = st.columns(2, gap="large")

    if {"county_name", "deobligated_amount_usd"}.issubset(geo.columns):
        top_geo = (
            geo.groupby("county_name")["deobligated_amount_usd"]
                .sum()
                .reset_index()
                .sort_values("deobligated_amount_usd", ascending=False)
        )
        fig_geo_bar = px.bar(
            top_geo,
            x="deobligated_amount_usd",
            y="county_name",
            orientation="h",
            labels={
                "deobligated_amount_usd": "De‑obligated dollars (USD)",
                "county_name": "County",
            },
            title="De‑obligated dollars by county",
        )
        fig_geo_bar.update_layout(
            margin=dict(l=10, r=10, t=40, b=40),
            yaxis=dict(categoryorder="total ascending"),
        )
        c1.plotly_chart(fig_geo_bar, key="geo_bar")

    if {"county_name", "cuts_per_10k_residents"}.issubset(geo.columns):
        rate_geo = (
            geo.groupby("county_name")["cuts_per_10k_residents"]
                .mean()
                .reset_index()
                .sort_values("cuts_per_10k_residents", ascending=False)
        )
        fig_geo_rate = px.bar(
            rate_geo,
            x="cuts_per_10k_residents",
            y="county_name",
            orientation="h",
            labels={
                "cuts_per_10k_residents": "Cuts per 10,000 residents",
                "county_name": "County",
            },
            title="Cuts per 10,000 residents by county",
        )
        fig_geo_rate.update_layout(
            margin=dict(l=10, r=10, t=40, b=40),
            yaxis=dict(categoryorder="total ascending"),
        )
        c2.plotly_chart(fig_geo_rate, key="geo_rate")

# 5. Programs & Agencies tab

with tab_programs:
    st.subheader("Programs and agencies")

    if {"awarding_agency_name", "cfda_title", "label", "total_deobligation_neg"}.issubset(
        awards_f.columns
    ):
        treemap_df = awards_f.copy()
        fig_treemap = px.treemap(
            treemap_df,
            path=["awarding_agency_name", "cfda_title", "label"],
            values="total_deobligation_neg",
            color="label",
            title="Hierarchy of cuts: agency → program → classification",
        )
        fig_treemap.update_layout(margin=dict(l=10, r=10, t=40, b=40))
        st.plotly_chart(fig_treemap, key="prog_treemap")

    if {"cfda_title", "total_deobligation_neg", "trump_era_flag"}.issubset(awards.columns):
        prog_full = awards.copy()
        prog_full["era"] = np.where(
            prog_full["trump_era_flag"] == 1, "Trump era", "Pre‑Trump only"
        )
        prog_agg = (
            prog_full.groupby(["cfda_title", "era"])["total_deobligation_neg"]
                .sum()
                .reset_index()
        )
        top_prog_names = (
            prog_agg.groupby("cfda_title")["total_deobligation_neg"]
                .sum()
                .nlargest(10)
                .index
        )
        prog_agg = prog_agg[prog_agg["cfda_title"].isin(top_prog_names)]

        fig_prog_era = px.bar(
            prog_agg,
            x="total_deobligation_neg",
            y="cfda_title",
            color="era",
            barmode="group",
            orientation="h",
            labels={
                "total_deobligation_neg": "De‑obligated dollars (USD)",
                "cfda_title": "Program (CFDA)",
                "era": "Period",
            },
            title="Pre‑ vs Trump‑era cuts for top programs",
        )
        fig_prog_era.update_layout(
            margin=dict(l=10, r=10, t=40, b=40),
            yaxis=dict(categoryorder="total ascending"),
        )
        st.plotly_chart(fig_prog_era, key="prog_pre_trump")

    # Program size vs Trump-era cuts, colored by absolute dollars (not share)
    if {"cfda_title", "total_obligation_pos", "total_deobligation_neg", "trump_era_flag"}.issubset(
        awards.columns
    ):
        prog_trump = awards[awards["trump_era_flag"] == 1].copy()
        prog_size = (
            prog_trump.groupby("cfda_title")[
                ["total_obligation_pos", "total_deobligation_neg"]
            ]
                .sum()
                .reset_index()
        )

        fig_prog_scatter = px.scatter(
            prog_size,
            x="total_obligation_pos",
            y="total_deobligation_neg",
            color="total_deobligation_neg",
            size="total_deobligation_neg",
            hover_name="cfda_title",
            labels={
                "total_obligation_pos": "Trump‑era obligations (USD)",
                "total_deobligation_neg": "Trump‑era de‑obligated dollars (USD)",
            },
            title="Program size vs Trump‑era cuts (dollar impact)",
            color_continuous_scale="Plasma",
        )
        fig_prog_scatter.update_layout(
            margin=dict(l=10, r=10, t=40, b=40),
        )
        st.plotly_chart(fig_prog_scatter, key="prog_intensity")


# 6. City Impacts tab (first and last visuals use top 10 cities)

with tab_cities:
    st.subheader("City impacts")

    if "action_date" in tx.columns and "recipient_city_name" in tx.columns:
        tx_full = tx.copy()
        tx_full["month"] = tx_full["action_date"].dt.to_period("M").dt.to_timestamp()

        # Top 10 affected cities by total de-obligations
        city_totals_all = (
            tx_full.groupby("recipient_city_name")["deobligated_amount_usd"]
                .sum()
                .reset_index()
                .sort_values("deobligated_amount_usd", ascending=False)
        )
        top10_cities = city_totals_all["recipient_city_name"].dropna().head(10).tolist()

        # Small multiples for top 10
        sm_df = tx_full[tx_full["recipient_city_name"].isin(top10_cities)].copy()
        fig_cities_ts = px.line(
            sm_df,
            x="month",
            y="deobligated_amount_usd",
            color="recipient_city_name",
            facet_col="recipient_city_name",
            facet_col_wrap=5,
            labels={
                "month": "Month",
                "deobligated_amount_usd": "De‑obligated dollars (USD)",
                "recipient_city_name": "City",
            },
            title="Monthly de‑obligations for top 10 Massachusetts cities",
        )
        fig_cities_ts.update_layout(
            margin=dict(l=10, r=10, t=40, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_cities_ts, key="cities_small_multiples")

        # Timeline heatmap for same top 10
        city_month = (
            tx_full.groupby(["month", "recipient_city_name"])[
                "deobligated_amount_usd"
            ]
                .sum()
                .reset_index()
        )
        city_month_top = city_month[city_month["recipient_city_name"].isin(top10_cities)]

        fig_heat = px.density_heatmap(
            city_month_top,
            x="month",
            y="recipient_city_name",
            z="deobligated_amount_usd",
            color_continuous_scale="Reds",
            labels={
                "month": "Month",
                "recipient_city_name": "City",
                "deobligated_amount_usd": "De‑obligated dollars (USD)",
            },
            title="Timeline of de‑obligations across top 10 cities",
        )
        fig_heat.update_layout(margin=dict(l=10, r=10, t=40, b=40))
        st.plotly_chart(fig_heat, key="cities_heatmap")

