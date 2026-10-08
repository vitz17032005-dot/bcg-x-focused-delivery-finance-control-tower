# Global Delivery Finance Control Tower — Public Data Edition

> External-market finance control tower for delivery cost, labor demand and FX exposure — built from the public datasets supplied from Kaggle.

## Decision question

> Where are labor-market demand, compensation and currency signals creating the strongest finance planning pressure for a technology-delivery organization?

## Compressed public inputs

- `data/raw/archives/exchange_rate_to_usd.csv.zip` — supplied Kaggle/IMF source.
- `data/raw/archives/exchange_rate_usd_to.csv.zip` — supplied Kaggle/IMF source.
- `data/raw/archives/india_col_salary_longitudinal_2010_2024.csv.zip` — supplied Kaggle city salary / cost-of-living panel.
- `data/raw/archives/linkedin_role_market_extract.csv.zip` — exact row-level extract from the supplied Kaggle `postings.csv`, filtered to technology-delivery roles.
- `data/raw/archives/linkedin_supporting_tables.zip` — original smaller LinkedIn CSVs.

The complete LinkedIn `postings.csv` is preserved as a GitHub Release asset rather than tracked in ordinary Git. See `GITHUB_RELEASE_ASSETS.md`.

## Architecture

```text
PUBLIC KAGGLE SOURCES
      ↓
STANDARDISATION + DATA QUALITY
      ↓
Finance-ready analytical tables
  ┌───────┼────────┐
  ↓       ↓        ↓
  FX   Labor pay   Talent demand
  └───────┼────────┘
          ↓
    FP&A CONTROL TOWER
          ↓
    risk / growth / variance
          ↓
    management insight
```

## Important boundary

This is deliberately **not** presented as an internal corporate accounting ledger. Public datasets do not contain genuine project codes, timesheets, budgets or company forecasts. The repository therefore generates analytical views only; it does not invent those missing transactions.

## Run

```bash
pip install -r requirements.txt
python src/run_pipeline.py
pytest
```

No Kaggle credentials, APIs or retrieval scripts are required.