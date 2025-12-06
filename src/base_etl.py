import pandas as pd
import numpy as np
from config import USASPENDING_CSV

def load_raw_transactions(path: str | None = None) -> pd.DataFrame:
    csv_path = path if path is not None else USASPENDING_CSV
    df = pd.read_csv(csv_path, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    return df

def build_awardid(df: pd.DataFrame) -> pd.DataFrame:
    # Use the same logic as eda_final: assistance_award_unique_key / award_id_fain / award_id_uri
    award_candidates = [
        "assistance_award_unique_key",
        "award_id_fain",
        "award_id_uri",
        "award_id",  # already created in your notebook, but include as fallback
    ]
    present_award_cols = [c for c in award_candidates if c in df.columns]

    if present_award_cols:
        awardid = df[present_award_cols[0]].astype(str)
        for c in present_award_cols[1:]:
            awardid = awardid.where(
                awardid.notna() & (awardid.str.len() > 0),
                df[c].astype(str),
            )
        df["awardid"] = awardid.fillna("").astype(str).str.strip()
    else:
        # Fallback to transaction-level key if for some reason the award-level ones are not present
        tx_candidates = [
            "assistance_transaction_unique_key",
        ]
        tx_present = [c for c in tx_candidates if c in df.columns]
        if not tx_present:
            raise KeyError("No award or transaction identifier columns to build awardid.")
        df["awardid"] = df[tx_present[0]].astype(str).str.strip()

    df = df[df["awardid"].str.len() > 0].copy()
    return df

def convert_dates_and_amounts(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    # In eda_final you use action_date
    datecol = "action_date" if "action_date" in df.columns else None
    if datecol is None:
        raise KeyError("Expected 'action_date' column (as in eda_final).")

    df[datecol] = pd.to_datetime(df[datecol], errors="coerce")

    if "federal_action_obligation" not in df.columns:
        raise KeyError("Missing 'federal_action_obligation' column (eda_final).")
    df["federal_action_obligation"] = (
        pd.to_numeric(df["federal_action_obligation"], errors="coerce").fillna(0.0)
    )

    # In eda_final you standardised to total_outlayed_amount_for_overall_award
    outlay_col_raw = "total_outlayed_amount_for_overall_award"
    if outlay_col_raw not in df.columns:
        # safe default
        df[outlay_col_raw] = 0.0
    else:
        df[outlay_col_raw] = pd.to_numeric(
            df[outlay_col_raw], errors="coerce"
        ).fillna(0.0)

    return df, datecol

def build_snapshots(df: pd.DataFrame, datecol: str) -> pd.DataFrame:
    df = df.sort_values(["awardid", datecol]).copy()

    # Same as eda_final: cumulative_obligation, is_deobligation_tx, neg_date
    df["cumulative_obligation"] = (
        df.groupby("awardid")["federal_action_obligation"].cumsum()
    )
    df["is_deobligation_tx"] = df["federal_action_obligation"] < 0

    df["neg_date"] = df[datecol].where(df["is_deobligation_tx"])
    firstnegbyaward = df.groupby("awardid")["neg_date"].min()

    grossposbyaward = (
        df.loc[df["federal_action_obligation"] > 0]
        .groupby("awardid")["federal_action_obligation"]
        .sum()
    )

    finalsnap = (
        df.groupby("awardid")
        .agg(
            final_cum_obligation=("cumulative_obligation", "last"),
            any_negative=("is_deobligation_tx", "any"),
            total_negative_amount=("federal_action_obligation", lambda s: (s[s < 0]).sum()),
            total_obligation_amount=("federal_action_obligation", "sum"),
        )
        .reset_index()
    )

    finalsnap = finalsnap.merge(
        firstnegbyaward.rename("first_negative_date").reset_index(),
        on="awardid",
        how="left",
    )

    outlay_col = "total_outlayed_amount_for_overall_award"
    finaloutlay = (
        df.groupby("awardid")[outlay_col].last().rename(outlay_col).reset_index()
    )
    finalsnap = finalsnap.merge(finaloutlay, on="awardid", how="left")
    finalsnap[outlay_col] = finalsnap[outlay_col].fillna(0.0)

    finalsnap = finalsnap.merge(
        grossposbyaward.rename("gross_positive_obligation").reset_index(),
        on="awardid",
        how="left",
    ).fillna({"gross_positive_obligation": 0.0})

    return df, finalsnap

def classify_awards(finalsnap: pd.DataFrame) -> pd.DataFrame:
    outlay_col = "total_outlayed_amount_for_overall_award"

    def classify_and_explain(row: pd.Series) -> pd.Series:
        finalcum = row["final_cum_obligation"]
        outlays = row[outlay_col]
        anyneg = row["any_negative"]
        grosspos = row["gross_positive_obligation"]
        totalneg = row["total_negative_amount"]

        pctoutlayed = outlays / grosspos if grosspos > 0 else 0.0

        if finalcum <= 0:
            if outlays > 0:
                label = "RESCISSION"
                rationale = "Funds were disbursed and later clawed back, reducing the award to zero or below."
            else:
                label = "CANCELLATION"
                rationale = "No funds were disbursed; the award's cumulative obligation dropped to zero."
        else:
            if anyneg and outlays > 0:
                label = "PARTIAL_RES_CUM_POS"
                rationale = "Funds were disbursed and some portion was clawed back, but the award remains positive."
            elif anyneg and outlays == 0:
                label = "ADMIN_OR_PREPAY_ADJ"
                rationale = "No funds were disbursed; negative transactions occurred but the award remains positive."
            else:
                label = "NO_DEOBLIGATION"
                rationale = "No negative transactions observed for this award."

        explanation = (
            f"{label} | final_cum={finalcum:.2f}, "
            f"outlays={outlays:.2f} ({pctoutlayed:.1%} of positives), "
            f"total_neg={abs(totalneg):.2f}, "
            f"first_neg={row['first_negative_date']}, "
            f"{rationale}"
        )

        return pd.Series(
            {
                "label": label,
                "explanation": explanation,
                "pct_outlayed_of_pos": pctoutlayed,
            }
        )

    meta = finalsnap.apply(classify_and_explain, axis=1)
    m1 = finalsnap.copy()
    m1[["label", "explanation", "pct_outlayed_of_pos"]] = meta

    return m1

def build_base(path: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    df = load_raw_transactions(path)
    df = build_awardid(df)
    df, datecol = convert_dates_and_amounts(df)
    df, finalsnap = build_snapshots(df, datecol)
    m1 = classify_awards(finalsnap)
    return df, m1, datecol
