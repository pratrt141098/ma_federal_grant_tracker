"""
MA grant cuts dashboard prep package.

Modules:
- config: paths, constants (TRUMP_START), directory helpers.
- base_etl: load raw USAspending, build df + m1 snapshots and labels.
- exports_awards: write awards_master.csv (1 row per award).
- exports_transactions: write transactions_deob.csv (negative transactions).
- exports_geo: write geo_aggregation.csv (county-level metrics).
"""