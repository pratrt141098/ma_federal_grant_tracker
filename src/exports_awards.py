import pandas as pd
from config import TRUMP_START, AWARDS_MASTER_CSV, ensure_directories


def export_awards_master(df):
    """
    We build awards_master.csv: one row per awardid, combining:
    - m1 (final_cum_obligation, total_negative_amount, total_obligation_amount, etc.)
    - descriptive columns from df (CFDA, agencies)
    - period flags and Trump-era cut flags
    - total positive obligations and total de-obligations per award
    """

    ensure_directories()

    # HARD CAST to numeric here to avoid any stray string dtype
    df = df.copy()
    df["federal_action_obligation"] = pd.to_numeric(
        df["federal_action_obligation"], errors="coerce"
    ).fillna(0.0)

    # Descriptive columns from the transaction-level df (must match eda_final)
    desc_cols = [
        "recipient_name",
        "cfda_number",
        "cfda_title",
        "awarding_agency_name",
        "funding_agency_name",
    ]
    desc_present = [c for c in desc_cols if c in df.columns]

    # One row per awardid with descriptive info
    base_info = (
        df.groupby("awardid", as_index=False)[desc_present]
        .first()
    )

    # We start from m1 (final snapshots + labels) and add descriptive info
    awards = m1.merge(base_info, on="awardid", how="left")

    # First / last action dates per awardid (using the passed datecol, i.e. "action_date")
    date_aggs = (
        df.groupby("awardid", as_index=False)[datecol]
          .agg(["min", "max"])
    )
    date_aggs = date_aggs.rename(
        columns={"min": "first_action_date", "max": "last_action_date"}
    )

    awards = awards.merge(date_aggs, on="awardid", how="left")

    # Period flags
    awards["pre_trump_flag"] = (awards["first_action_date"] < TRUMP_START).astype(int)
    awards["trump_era_flag"] = (awards["last_action_date"] >= TRUMP_START).astype(int)

    # Awards with any Trump-era negative transaction
    df_trump = df[df[datecol] >= TRUMP_START].copy()

    awards_any_trump_cut = (
        df_trump.loc[df_trump["is_deobligation_tx"]]
        .groupby("awardid")["is_deobligation_tx"]
        .any()
        .astype(int)
        .rename("awards_with_trump_cut")
        .reset_index()
    )

    awards = awards.merge(awards_any_trump_cut, on="awardid", how="left")
    awards["awards_with_trump_cut"] = awards["awards_with_trump_cut"].fillna(0).astype(int)

    # Totals by award using federal_action_obligation (as in eda_final)
    pos_by_award = (
        df["federal_action_obligation"].clip(lower=0)
        .groupby(df["awardid"]).sum()
        .rename("total_obligation_pos")
        .reset_index()
    )

    neg_series = df["federal_action_obligation"].clip(upper=0)
    
    neg_by_award = (
    neg_series.groupby(df["awardid"]).sum()
    .abs()
    .rename("total_deobligation_neg")
    .reset_index()
    )

    awards = awards.merge(pos_by_award, on="awardid", how="left")
    awards = awards.merge(neg_by_award, on="awardid", how="left")

    # De-duplicate just in case
    awards = awards.drop_duplicates(subset=["awardid"])

    out_cols = [
        "awardid",
        "recipient_name",
        "cfda_number",
        "cfda_title",
        "awarding_agency_name",
        "funding_agency_name",
        "final_cum_obligation",
        "total_negative_amount",
        "total_obligation_amount",
        "total_obligation_pos",
        "total_deobligation_neg",
        "total_outlayed_amount_for_overall_award",
        "gross_positive_obligation",
        "label",
        "pct_outlayed_of_pos",
        "first_negative_date",
        "first_action_date",
        "last_action_date",
        "pre_trump_flag",
        "trump_era_flag",
        "awards_with_trump_cut",
    ]
    out_present = [c for c in out_cols if c in awards.columns]

    awards[out_present].to_csv(AWARDS_MASTER_CSV, index=False)

    return awards[out_present]

