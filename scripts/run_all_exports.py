from pathlib import Path
import sys

# Ensure src is on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from config import ensure_directories
from base_etl import build_base
from exports_awards import export_awards_master
from exports_transactions import export_transactions_deob
from exports_geo import export_geo_aggregation
import pandas as pd

def main():
    ensure_directories()

    print("Building base data (df, m1)...")
    df, m1, date_col = build_base()

    print("Exporting awards_master...")
    awards_master = export_awards_master(df, m1, date_col)

    print("Exporting transactions_deob...")
    tx_deob = export_transactions_deob(df, m1, date_col)


    print("Exporting geo_aggregation...")
    geo = export_geo_aggregation(df, awards_master, county_lookup=None)
    print(f"geo_aggregation rows: {len(geo)}")
    print("Done.")
    print(f"awards_master rows: {len(awards_master)}")
    print(f"transactions_deob rows: {len(tx_deob)}")
    print(f"geo_aggregation rows: {len(geo)}")

if __name__ == "__main__":
    main()
