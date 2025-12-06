import sys
from pathlib import Path

import pandas as pd

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from config import (
    USASPENDING_CSV,
    AWARDS_MASTER_CSV,
    TX_DEOB_CSV,
    GEO_AGG_CSV,
)
from base_etl import build_base


def test_build_base_runs():
    df, m1, datecol = build_base(str(USASPENDING_CSV))
    assert not df.empty, "df (transactions) should not be empty"
    assert not m1.empty, "m1 (award-level snapshot) should not be empty"
    assert "federal_action_obligation" in df.columns
    assert "label" in m1.columns
    assert datecol in df.columns


def test_exports_exist_and_nonempty():
    # These tests assume you've already run scripts/run_all_exports.py
    for path in [AWARDS_MASTER_CSV, TX_DEOB_CSV, GEO_AGG_CSV]:
        assert path.exists(), f"{path} should exist – run run_all_exports.py first"
        df = pd.read_csv(path)
        assert not df.empty, f"{path.name} should not be empty"


def test_awards_total_consistency():
    """
    Basic check: sum of total_deobligation_neg over awards_master
    should be close to overall negative obligations in the raw df.
    Not exact (because of filters), but nonzero and same order of magnitude.
    """
    df, m1, _ = build_base(str(USASPENDING_CSV))
    total_neg_raw = -df["federal_action_obligation"].clip(upper=0).sum()

    awards = pd.read_csv(AWARDS_MASTER_CSV)
    if "total_deobligation_neg" in awards.columns:
        total_neg_awards = awards["total_deobligation_neg"].sum()
        assert total_neg_awards > 0
        # sanity: within a factor of 2 (adjust if you know exact equality should hold)
        ratio = total_neg_awards / total_neg_raw if total_neg_raw else 0
        assert 0.5 <= ratio <= 1.5, (
            f"total_deobligation_neg in awards_master ({total_neg_awards}) "
            f"differs a lot from raw total ({total_neg_raw})"
        )
