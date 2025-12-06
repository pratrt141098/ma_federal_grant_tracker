import pandas as pd
from config import ACS_DP05_CSV, GEO_AGG_CSV, ensure_directories


def load_dp05_county() -> pd.DataFrame:
    """
    Load ACS DP05 and build a county-level demographic lookup with:
    - county_fips (5-digit, derived from GEO_ID/GEOID)
    - county_name (already matching recipient_county_name)
    - population_total
    - pct_minority, pct_black, pct_hispanic, pct_asian
    """

    # DP05 file is actually TAB-delimited even though it has .csv extension
    dp = pd.read_csv(ACS_DP05_CSV, sep="\t", low_memory=False)
    dp.columns = [c.strip() for c in dp.columns]

    # Geography columns
    if "GEO_ID" in dp.columns:
        geo_col = "GEO_ID"
    elif "GEOID" in dp.columns:
        geo_col = "GEOID"
    else:
        raise KeyError(
            f"No GEO_ID/GEOID column found in DP05; got columns: {list(dp.columns[:10])}"
        )

    if "NAME" in dp.columns:
        name_col = "NAME"
    elif "Geographic Area Name" in dp.columns:
        name_col = "Geographic Area Name"
    else:
        raise KeyError("No NAME / Geographic Area Name column found in DP05.")

    out = dp[[geo_col, name_col]].copy()

    # Derive 5-digit county FIPS from GEO_ID like "0500000US25001"
    out["county_fips"] = out[geo_col].astype(str).str[-5:]
    out["county_name"] = out[name_col].astype(str).str.strip()

    # Population total
    pop_col = "DP05_0001E"
    out["population_total"] = pd.to_numeric(dp[pop_col], errors="coerce")

    # Race / ethnicity counts (from your DP05 header)
    black_col = "DP05_0038E"         # One race: Black or African American (count)
    asian_col = "DP05_0047E"         # One race: Asian (count)
    hisp_col = "DP05_0076E"          # Hispanic or Latino (of any race) (count)
    white_not_hisp_col = "DP05_0037E"  # Not Hispanic or Latino, White alone (count)

    out["pct_black"] = (
        pd.to_numeric(dp[black_col], errors="coerce") / out["population_total"] * 100
    )
    out["pct_asian"] = (
        pd.to_numeric(dp[asian_col], errors="coerce") / out["population_total"] * 100
    )
    out["pct_hispanic"] = (
        pd.to_numeric(dp[hisp_col], errors="coerce") / out["population_total"] * 100
    )
    out["pct_minority"] = 100 - (
        pd.to_numeric(dp[white_not_hisp_col], errors="coerce") / out["population_total"] * 100
    )

    return out[[
        "county_fips",
        "county_name",
        "population_total",
        "pct_minority",
        "pct_black",
        "pct_hispanic",
        "pct_asian",
    ]]


def export_geo_aggregation(
    df: pd.DataFrame,
    awards_master: pd.DataFrame,
    county_lookup: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build geo_aggregation.csv at county level by joining:
    - Transaction-level deobligations summed by recipient_county_name
    - DP05 county demographics keyed by county_name (already aligned)
    """

    ensure_directories()

    if county_lookup is None:
        county_lookup = load_dp05_county()

    county_col = "recipient_county_name"
    if county_col not in df.columns:
        raise KeyError(f"df must have '{county_col}' for geo aggregation.")

    df = df.copy()
    df["recipient_county_name"] = df[county_col].astype(str).str.strip()

    # Negative transactions for dollars by county name
    df_neg = df[df["federal_action_obligation"] < 0].copy()
    df_neg["deobligated_amount_usd"] = -df_neg["federal_action_obligation"]

    dollars_by_county = (
        df_neg.groupby("recipient_county_name")["deobligated_amount_usd"]
        .sum()
        .reset_index()
    )

    awards_with_cut_by_county = (
        df_neg.groupby(["recipient_county_name", "awardid"])["deobligated_amount_usd"]
        .sum()
        .reset_index()
        .groupby("recipient_county_name")["awardid"]
        .nunique()
        .reset_index(name="awards_with_any_cut")
    )

    geo = dollars_by_county.merge(
        awards_with_cut_by_county, on="recipient_county_name", how="outer"
    ).fillna({"awards_with_any_cut": 0})

    # Join directly on county_name == recipient_county_name
    county_lookup = county_lookup.copy()
    county_lookup["recipient_county_name"] = county_lookup["county_name"].astype(str).str.strip()

    geo = geo.merge(
        county_lookup,
        on="recipient_county_name",
        how="left",
    )

    geo["deob_dollars_per_capita"] = (
        geo["deobligated_amount_usd"] / geo["population_total"]
    )
    geo["cuts_per_10k_residents"] = (
        geo["awards_with_any_cut"] / geo["population_total"] * 10000
    )

    out_cols = [
        "county_fips",
        "county_name",
        "recipient_county_name",
        "deobligated_amount_usd",
        "awards_with_any_cut",
        "population_total",
        "deob_dollars_per_capita",
        "cuts_per_10k_residents",
        "pct_minority",
        "pct_black",
        "pct_hispanic",
        "pct_asian",
    ]
    out_present = [c for c in out_cols if c in geo.columns]

    geo[out_present].to_csv(GEO_AGG_CSV, index=False)

    return geo[out_present]
