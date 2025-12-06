from pathlib import Path
import pandas as pd

# Root of the repo (adjust if needed)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = PROJECT_ROOT / "data_raw"
DATA_INTERMEDIATE = PROJECT_ROOT / "data_intermediate"
DATA_EXPORTS = PROJECT_ROOT / "data_exports"

# Input files
USASPENDING_CSV = DATA_RAW / "Assistance_PrimeTransactions_2025-10-09_H19M31S57_1.zip"
ACS_DP05_CSV = DATA_RAW / "ACSDP5Y2023.DP05-Data.csv"


# Output files
AWARDS_MASTER_CSV = DATA_EXPORTS / "awards_master.csv"
TX_DEOB_CSV = DATA_EXPORTS / "transactions_deob.csv"
GEO_AGG_CSV = DATA_EXPORTS / "geo_aggregation.csv"
TX_DEOB_CITY_MONTH_CSV = DATA_EXPORTS / "transactions_deob_city_month.csv"

# Analysis constants
TRUMP_START = pd.Timestamp("2025-01-20")  # your current Trump-era start

def ensure_directories():
    DATA_INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    DATA_EXPORTS.mkdir(parents=True, exist_ok=True)
