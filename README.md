#Massachusetts Federal Grant Cuts – Dashboard
##nto CANCELLATION, RESCISSION, PARTIAL_RES_CUMPOS, ADMIN_OR_PREPAY_ADJ, and NODEOBLIGATION using transaction histories and outlay data.​

Aggregates award‑ and county‑level metrics for equity analysis and builds an interactive Streamlit dashboard for exploration.​

Data pipeline
The ma_grant_cuts package (see __init__.py and submodules) prepares all inputs to the dashboard.​

Core steps:

Ingest USAspending data

Load Assistance Prime Transactions for MA.

Build cumulative obligation and outlay series per award.

Classify awards

Use compute_confidence_for_award to infer the dominant pattern (cancellation vs rescission vs administrative) from: number and timing of negative transactions, final obligation balance, and outlay history.​

Attach label and confidence columns at the award level.​

Export dashboard datasets

awards_master.csv: one row per award with

IDs: award_id, award_id_fain, award_id_uri, assistance_award_unique_key

Totals: total_obligation_pos, total_deobligation_neg, total_outlayed_amount_for_overall_award

Dates: first_action_date, last_action_date, first_negative_date

Classification: label, confidence, trump_era_flag (≥ 2025‑01‑20).​

transactions_deob.csv: negative transactions only, with dates, agency, award IDs, program (CFDA), and deobligated_amount_usd.​

geo_aggregation.csv: county‑level totals (e.g., deobligated_amount_usd, deob_dollars_per_capita, cuts_per_10k_residents, %_minority).​

Optional city_centroids.csv: city‑level lat/long for mapping.​

Dashboard features (Streamlit app)
The main app is app.py, implemented with Streamlit and Plotly Express.​

Global filters
Available in the left sidebar:​

Award classification (label), multi‑select over available inferred classes.

Awarding agency (awarding_agency_name).

“Trump‑era only” toggle: restricts to awards/transactions on or after 2025‑01‑20 using trump_era_flag.​

These filters apply consistently across all tabs and charts.​

Tabs and views
Overview​

KPI cards:

Total de‑obligated dollars (total_deobligation_neg)

Number of awards with any cuts

De‑obligation rate = total de‑obligations ÷ total positive obligations (amount basis).

Bar chart: total de‑obligated dollars by classification (label).

Histogram: distribution of de‑obligated dollars per award (cut size distribution).

Time trends​

Line chart: total de‑obligations by month (month, deobligated_amount_usd).

Stacked area: monthly de‑obligations by classification.

Multi‑series line: monthly de‑obligations for top CFDA programs (by total de‑obligated dollars).

Recipients​

Bar chart: top recipients by de‑obligated dollars (recipient_name).

Bar chart: top programs by cancelled/rescinded dollars (filter label to CANCELLATION and RESCISSION).

Award‑level table with slider for minimum cut size, showing IDs, program, agency, label, and obligation/de‑obligation amounts.

Geography & equity​

Scatter: de‑obligated dollars per capita vs percent minority by county, optionally sized by population.

Bar: counties by total de‑obligated dollars.

Bar: counties by cuts per 10,000 residents.

Programs & agencies​

Treemap: Awarding agency → CFDA program → label, weighted by total de‑obligated dollars.

Grouped bar: pre‑ vs Trump‑era cuts for the top CFDA programs, using trump_era_flag to split “Pre‑Trump only” vs “Trump era”.

Communities & narratives (placeholder / narrative‑oriented tab)​

Intended for storylines connecting data back to communities and media reporting (e.g., Healey / school meals case studies).

Map​

If city_centroids.csv is present: geospatial plotting of de‑obligations using city‑level coordinates.

Otherwise, the app falls back gracefully without city‑level mapping.

Local setup and usage
1. Clone the repo
bash
git clone https://github.com/pratrt141098/ma_federal_grant_tracker.git
cd ma_federal_grant_tracker
2. Create environment and install dependencies
Create and activate a virtual environment, then install packages (example using pip):

bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
If requirements.txt is missing, ensure at least: streamlit, pandas, numpy, plotly, and pyarrow (if using Parquet).​

3. Generate dashboard data (ETL)
Run the ETL to produce the exports expected by app.py:​

bash
python -m ma_grant_cuts.base_etl          # or project-specific driver script
python -m ma_grant_cuts.exports_awards    # writes data_exports/awards_master.csv
python -m ma_grant_cuts.exports_transactions  # writes data_exports/transactions_deob.csv
python -m ma_grant_cuts.exports_geo       # writes data_exports/geo_aggregation.csv
By default, outputs are written under a data_exports/ directory at the project root, as referenced in app.py.​

Expected files for the dashboard:

text
data_exports/
  awards_master.csv
  transactions_deob.csv
  geo_aggregation.csv
  city_centroids.csv        # optional, for map tab
4. Run the dashboard
From the repo root:

bash
streamlit run app.py
The app will open in your browser (default at http://localhost:8501) with all tabs and filters enabled.​

Interpreting classifications
The award‑level label is inferred and not an official USAspending field, but is constructed to approximate federal modification codes and practical impacts:​

CANCELLATION – award halted before funds were effectively used (final obligation near zero, outlays low or zero).

RESCISSION – funds were paid out and later clawed back; outlays positive, followed by large negative transactions.

PARTIAL_RES_CUMPOS – partial funding reductions where the award remains active with a non‑zero final balance.

ADMIN_OR_PREPAY_ADJ – small or accounting‑type adjustments with limited substantive program impact.

NODEOBLIGATION – awards without any negative obligation transactions.

Each label is accompanied by a numeric confidence score (0–1) and a breakdown across competing hypotheses for transparency.​

Files of interest
app.py – Streamlit dashboard entry point and all front‑end logic.​

ma_grant_cuts/__init__.py – package description and high‑level ETL exports.​

eda_final.ipynb – exploratory analysis, diagnostic plots, and narrative findings used to validate the logic; includes charts on de‑obligations by classification and detailed award examples.​

data_exports/ – CSV exports feeding the dashboard (not tracked here if generated locally).


If you plan to extend this work (e.g., to additional states or time periods), replicate the ETL pattern in ma_grant_cuts and ensure new exports preserve the column structure expected in app.py filters and charts.​
