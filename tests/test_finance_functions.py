from pathlib import Path
import zipfile
import pandas as pd

def root():
    return Path(__file__).resolve().parents[1]

def read_zip_csv(name, csv_name=None, **kwargs):
    zpath = root()/"data"/"raw"/"archives"/name
    with zipfile.ZipFile(zpath) as z:
        csv_name = csv_name or z.namelist()[0]
        with z.open(csv_name) as fh:
            return pd.read_csv(fh, **kwargs)

def test_public_source_archives_are_embedded():
    raw = root()/"data"/"raw"/"archives"
    expected={"exchange_rate_to_usd.csv.zip","exchange_rate_usd_to.csv.zip","india_col_salary_longitudinal_2010_2024.csv.zip","linkedin_role_market_extract.csv.zip","linkedin_supporting_tables.zip"}
    assert expected.issubset({p.name for p in raw.glob("*.zip")})
    assert not list(root().rglob("fetch_sources.py"))
    assert not list(root().rglob("kagglehub"))
    assert not list(root().rglob("postings.csv"))
    assert not list(root().rglob("*.parquet"))
    assert not list((root()/"data"/"raw").rglob("*.csv"))

def test_fx_source_has_expected_shape():
    df=read_zip_csv("exchange_rate_to_usd.csv.zip")
    assert df.columns[0]=="date"
    assert "indian_rupee_to_usd" in df.columns

def test_india_source_has_expected_columns():
    df=read_zip_csv("india_col_salary_longitudinal_2010_2024.csv.zip")
    assert {"year","city","avg_salary_gross_inr_monthly"}.issubset(df.columns)

def test_linkedin_extract_has_expected_columns():
    df=read_zip_csv("linkedin_role_market_extract.csv.zip")
    assert {"job_id","title","location","min_salary","med_salary","max_salary","currency","pay_period","company_country"}.issubset(df.columns)
