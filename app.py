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
    # city centroids are optional but needed for the Map tab
    city_centroids_path = DATA_EXPORTS / "city_centroids.csv"
    if city_centroids_path.exists():
        city_coords = pd.read_csv(city_centroids_path)
    else:
        city_coords = pd.DataFrame(
            columns=["recipient_city_name", "recipient_state_code", "latitude", "longitude"]
        )
    return awards, tx, geo, city_coords


awards, tx, geo, city_coords = load_data()

st.set_page_config(
    page_title="MA Grant Cuts – Trump Era",
    layout="wide",
)

st.title("Massachusetts Federal Grant Cuts – Trump Era Dashboard")

# -------------------------------------------------------------------
# Sidebar filters
# -------------------------------------------------------------------
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

# Apply filters to transactions
if trump_only and "trump_era_flag" in tx.columns:
    tx_f = tx[tx["trump_era_flag"] == 1].copy()
else:
    tx_f = tx.copy()

# -------------------------------------------------------------------
# Tabs
# -------------------------------------------------------------------
tab_overview, tab_time, tab_recipients, tab_geo, tab_map = st.tabs(
    ["Overview", "Time Trends", "Recipients & Programs", "Geography & Equity", "Map"]
)

# -------------------------------------------------------------------
# 1. Overview tab
# -------------------------------------------------------------------
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

    # De‑obligated dollars by label
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

    # Distribution of cut sizes (histogram)
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

# -------------------------------------------------------------------
# 2. Time Trends tab
# -------------------------------------------------------------------
with tab_time:
    st.subheader("Time trends of de‑obligations")

    if "action_date" in tx_f.columns:
        tx_f["month"] = tx_f["action_date"].dt.to_period("M").dt.to_timestamp()

        # Overall monthly de‑obligations
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

        # Monthly by label (stacked area)
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

        # Monthly by top CFDA programs (using awards + tx join)
        tx_join = tx_f.merge(
            awards_f[["awardid", "cfda_title"]],
            on="awardid",
            how="left",
        )
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

# -------------------------------------------------------------------
# 3. Recipients & Programs tab
# -------------------------------------------------------------------
with tab_recipients:
    c1, c2 = st.columns(2, gap="large")

    # Top recipients by de‑obligated dollars (transaction-level)
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

    # Top cancelled / rescinded programs (award-level)
    canc_labels = {"CANCELLATION", "RESCISSION"}
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

    min_deob = st.slider(
        "Minimum de‑obligated dollars per award",
        min_value=0,
        max_value=int(awards_f["total_deobligation_neg"].max() or 0),
        value=0,
        step=100000,
    )
    details_cols = [
        "awardid",
        "cfda_title",
        "awarding_agency_name",
        "label",
        "total_obligation_pos",
        "total_deobligation_neg",
    ]
    details = (
        awards_f[awards_f["total_deobligation_neg"] >= min_deob][details_cols]
        .sort_values("total_deobligation_neg", ascending=False)
    )
    st.dataframe(details, height=400)

# -------------------------------------------------------------------
# 4. Geography & Equity tab
# -------------------------------------------------------------------
with tab_geo:
    st.subheader("County‑level equity view")

    # Scatter: % minority vs de‑ob dollars per capita
    geo_scatter = geo.dropna(subset=["pct_minority", "deob_dollars_per_capita"]).copy()
    fig_scatter = px.scatter(
        geo_scatter,
        x="pct_minority",
        y="deob_dollars_per_capita",
        size="population_total",
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

    # Dollars by county
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

    # Cuts per 10k residents by county
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

# -------------------------------------------------------------------
# 5. Map tab (city-level bubbles)
# -------------------------------------------------------------------
with tab_map:
    st.subheader("City‑level map of de‑obligations")

    if city_coords.empty:
        st.info(
            "city_centroids.csv not found or empty. "
            "Run build_city_centroids.py first to enable the map."
        )
    else:
        # Aggregate filtered transactions by city
        tx_city = (
            tx_f.groupby(["recipient_city_name", "recipient_state_code"])["deobligated_amount_usd"]
            .sum()
            .reset_index()
        )

        city_map = tx_city.merge(
            city_coords,
            on=["recipient_city_name", "recipient_state_code"],
            how="inner",
        )

        if city_map.empty:
            st.info("No city coordinates available for current filters.")
        else:
            fig_map = px.scatter_mapbox(
                city_map,
                lat="latitude",
                lon="longitude",
                size="deobligated_amount_usd",
                color="deobligated_amount_usd",
                color_continuous_scale="Reds",
                size_max=30,
                zoom=6,
                hover_name="recipient_city_name",
                hover_data={
                    "recipient_state_code": True,
                    "deobligated_amount_usd": ":,.0f",
                },
                title="De‑obligated dollars by city (bubble size and color)",
            )
            fig_map.update_layout(
                mapbox_style="carto-positron",
                margin=dict(l=10, r=10, t=40, b=40),
            )
            st.plotly_chart(fig_map, key="city_map")
