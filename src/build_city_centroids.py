from pathlib import Path
import time

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_EXPORTS = PROJECT_ROOT / "data_exports"

TX_DEOB_CSV = DATA_EXPORTS / "transactions_deob.csv"
CITY_CENTROIDS_CSV = DATA_EXPORTS / "city_centroids.csv"


def build_city_centroids():
    """
    Build city_centroids.csv with one row per (recipient_city_name, recipient_state_code)
    found in transactions_deob.csv, using OpenStreetMap/Nominatim for geocoding.

    Output columns:
      - recipient_city_name
      - recipient_state_code
      - latitude
      - longitude
    """
    tx = pd.read_csv(TX_DEOB_CSV)
    tx["recipient_city_name"] = tx["recipient_city_name"].astype(str).str.strip()
    tx["recipient_state_code"] = tx["recipient_state_code"].astype(str).str.strip()

    cities = (
        tx.dropna(subset=["recipient_city_name", "recipient_state_code"])
        .loc[tx["recipient_city_name"] != ""]
        .drop_duplicates(subset=["recipient_city_name", "recipient_state_code"])[
            ["recipient_city_name", "recipient_state_code"]
        ]
        .reset_index(drop=True)
    )

    print(f"Unique city/state combos to geocode: {len(cities)}")

    geolocator = Nominatim(user_agent="ma_grant_cuts_dashboard")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, max_retries=2)

    lats = []
    lons = []

    for _, row in cities.iterrows():
        city = row["recipient_city_name"]
        state = row["recipient_state_code"]
        query = f"{city}, {state}, USA"
        try:
            loc = geocode(query)
        except Exception as e:
            print(f"Error geocoding {query}: {e}")
            loc = None

        if loc is None:
            print(f"Could not geocode {query}")
            lats.append(None)
            lons.append(None)
        else:
            lats.append(loc.latitude)
            lons.append(loc.longitude)
        # small extra delay to be gentle on the API
        time.sleep(0.1)

    cities["latitude"] = lats
    cities["longitude"] = lons

    # Drop any that failed to geocode
    cities = cities.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)

    CITY_CENTROIDS_CSV.parent.mkdir(parents=True, exist_ok=True)
    cities.to_csv(CITY_CENTROIDS_CSV, index=False)
    print(f"Saved {len(cities)} city centroids to {CITY_CENTROIDS_CSV}")


if __name__ == "__main__":
    build_city_centroids()
