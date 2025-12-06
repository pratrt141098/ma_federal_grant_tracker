import pandas as pd

from config import (
    TRUMP_START,
    TX_DEOB_CSV,
    TX_DEOB_CITY_MONTH_CSV,
    ensure_directories,
)


def export_transactions_deob(
    df: pd.DataFrame, m1: pd.DataFrame, datecol: str
) -> pd.DataFrame:
    """
    Export transaction-level de-obligations for Tableau (transactions_deob.csv)
    and a city-month rollup for animated city maps (transactions_deob_city_month.csv).
    """
    ensure_directories()

    # 1) Base de-obligation transactions
    df_neg = df[df["federal_action_obligation"] < 0].copy()
    df_neg["deobligated_amount_usd"] = -df_neg["federal_action_obligation"]

    label_map = m1.set_index("awardid")["label"]
    df_neg["label"] = df_neg["awardid"].map(label_map)

    df_neg[datecol] = pd.to_datetime(df_neg[datecol], errors="coerce")
    df_neg["trump_era_flag"] = (df_neg[datecol] >= TRUMP_START).astype(int)

    out_cols = [
        "awardid",
        datecol,
        "federal_action_obligation",
        "deobligated_amount_usd",
        "label",
        "action_type_code",
        "action_type_description",
        "correction_delete_indicator_code",
        "correction_delete_indicator_description",
        "recipient_name",
        "recipient_city_name",
        "recipient_state_code",
        "primary_place_of_performance_city_name",
        "primary_place_of_performance_state_code",
        "trump_era_flag",
    ]
    out_present = [c for c in out_cols if c in df_neg.columns]

    df_neg[out_present].to_csv(TX_DEOB_CSV, index=False)

    # 2) City–month rollup for animated map
    if "recipient_city_name" in df_neg.columns and "recipient_state_code" in df_neg.columns:
        df_city = df_neg.copy()
        df_city["recipient_city_name"] = df_city["recipient_city_name"].astype(str).str.strip()
        df_city["recipient_state_code"] = df_city["recipient_state_code"].astype(str).str.strip()

        df_city["month"] = df_city[datecol].dt.to_period("M").dt.to_timestamp()

        city_month = (
            df_city.groupby(
                ["month", "recipient_city_name", "recipient_state_code", "trump_era_flag"],
                as_index=False,
            )["deobligated_amount_usd"]
            .sum()
        )

        city_month.to_csv(TX_DEOB_CITY_MONTH_CSV, index=False)

    return df_neg[out_present]
