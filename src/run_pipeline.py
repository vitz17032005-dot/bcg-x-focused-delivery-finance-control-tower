from pathlib import Path
import json
import numpy as np
import pandas as pd
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
CFG = json.loads((ROOT / "config" / "source_config.json").read_text(encoding="utf-8"))

def read_csv_from_zip(zip_path: Path, csv_name: str, **kwargs):
    with zipfile.ZipFile(zip_path) as z:
        if csv_name not in z.namelist():
            raise FileNotFoundError(f"{csv_name} not found in {zip_path}")
        with z.open(csv_name) as fh:
            return pd.read_csv(fh, **kwargs)

def load_fx():
    p = RAW / "archives" / "exchange_rate_to_usd.csv.zip"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}")
    df = read_csv_from_zip(p, "exchange_rate_to_usd.csv")
    df = df.rename(columns={df.columns[0]: "date"})
    out = df.melt(id_vars=["date"], var_name="currency", value_name="rate_to_usd")
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["rate_to_usd"] = pd.to_numeric(out["rate_to_usd"], errors="coerce")
    out = out.dropna(subset=["date", "currency", "rate_to_usd"]).sort_values(["currency","date"])
    out["currency"] = out["currency"].astype(str).str.strip()
    out["month"] = out["date"].dt.to_period("M").dt.to_timestamp()
    return out

def load_india_salary():
    p = RAW / "archives" / "india_col_salary_longitudinal_2010_2024.csv.zip"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}")
    df = read_csv_from_zip(p, "india_col_salary_longitudinal_2010_2024.csv")
    df = df.rename(columns={
        "avg_salary_gross_inr_monthly": "avg_salary_inr_monthly",
        "median_salary_gross_inr_monthly": "median_salary_inr_monthly",
    })
    required = {"year","city","avg_salary_inr_monthly"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"India salary source missing columns: {sorted(missing)}")
    for c in ["year","avg_salary_inr_monthly","median_salary_inr_monthly"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["year","city","avg_salary_inr_monthly"])

def load_linkedin_extract():
    p = RAW / "archives" / "linkedin_role_market_extract.csv.zip"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}")
    return read_csv_from_zip(p, "linkedin_role_market_extract.csv", low_memory=False)

def build_fx(fx):
    monthly = fx.groupby(["currency","month"], as_index=False).agg(
        avg_rate_to_usd=("rate_to_usd","mean"),
        daily_std=("rate_to_usd","std"),
        observations=("rate_to_usd","count"),
    )
    fx = fx.sort_values(["currency","date"]).copy()
    fx["ret_1d"] = fx.groupby("currency")["rate_to_usd"].pct_change()
    vol = fx.set_index("date").groupby("currency")["ret_1d"].rolling(30, min_periods=10).std().reset_index(name="volatility_30d")
    vol["month"] = vol["date"].dt.to_period("M").dt.to_timestamp()
    month_vol = vol.groupby(["currency","month"], as_index=False)["volatility_30d"].last()
    latest = fx.sort_values("date").groupby("currency", as_index=False).tail(1)[["currency","date","rate_to_usd"]].rename(columns={"date":"latest_date","rate_to_usd":"latest_rate_to_usd"})
    return monthly.merge(month_vol,on=["currency","month"],how="left").merge(latest,on="currency",how="left")

def build_india(sal, fx):
    inr = fx[fx["currency"].str.lower().str.startswith("indian_rupee_to_usd")].copy()
    if inr.empty:
        raise ValueError("Expected Indian rupee FX series")
    inr["year"] = inr["date"].dt.year
    annual = inr.groupby("year",as_index=False)["rate_to_usd"].mean().rename(columns={"rate_to_usd":"avg_inr_per_usd"})
    out = sal.merge(annual,on="year",how="left")
    out["avg_salary_usd_monthly"] = out["avg_salary_inr_monthly"] / out["avg_inr_per_usd"]
    if "median_salary_inr_monthly" in out:
        out["median_salary_usd_monthly"] = out["median_salary_inr_monthly"] / out["avg_inr_per_usd"]
    return out

def build_jobs(jobs, fx):
    jobs = jobs.copy()
    jobs["listed_date"] = pd.to_datetime(jobs["listed_time"], errors="coerce", unit="ms")
    lo = pd.to_numeric(jobs.get("min_salary"), errors="coerce")
    med = pd.to_numeric(jobs.get("med_salary"), errors="coerce")
    hi = pd.to_numeric(jobs.get("max_salary"), errors="coerce")
    jobs["salary_local_annual"] = med.fillna((lo+hi)/2)
    multiplier = jobs["pay_period"].fillna("").astype(str).str.upper().map({"YEARLY":1,"MONTHLY":12,"HOURLY":2080}).fillna(1)
    jobs["salary_local_annual"] *= multiplier
    latest = fx.sort_values("date").groupby("currency",as_index=False).tail(1)
    lookup = dict(zip(latest["currency"].astype(str).str.upper(),latest["rate_to_usd"].astype(float)))
    aliases = {"USD":"US_DOLLAR_TO_USD","EUR":"EURO_TO_USD","GBP":"UK_POUND_TO_USD","INR":"INDIAN_RUPEE_TO_USD","CAD":"CANADIAN_DOLLAR_TO_USD","PLN":"POLISH_ZLOTY_TO_USD","MXN":"MEXICAN_PESO_TO_USD","CRC":"COSTA_RICAN_COLON_TO_USD"}
    jobs["currency_key"] = jobs["currency"].fillna("").astype(str).str.upper().map(aliases).fillna(jobs["currency"].fillna("").astype(str).str.upper())
    jobs["fx_rate_to_usd"] = jobs["currency_key"].map(lookup)
    r = jobs["fx_rate_to_usd"]
    jobs["salary_usd_annual"] = np.where(r.isna(),np.nan,np.where(r>1,jobs["salary_local_annual"]/r,jobs["salary_local_annual"]*r))
    jobs["month"] = jobs["listed_date"].dt.to_period("M").dt.to_timestamp()
    return jobs.dropna(subset=["listed_date"])

def build_control_tower(fx_kpi, india, jobs):
    latest_fx = fx_kpi.sort_values(["currency","month"]).groupby("currency",as_index=False).tail(1)
    india_year = india.groupby("year",as_index=False).agg(avg_salary_usd_monthly=("avg_salary_usd_monthly","mean"),cities=("city","nunique"))
    india_year["salary_growth_yoy"] = india_year["avg_salary_usd_monthly"].pct_change()
    demand = jobs.groupby(["company_country"],dropna=False).agg(job_postings=("job_id","nunique"),median_usd_salary=("salary_usd_annual","median"),salary_observations=("salary_usd_annual","count")).reset_index().rename(columns={"company_country":"employer_country"}).sort_values("job_postings",ascending=False)
    fx_panel = latest_fx[["currency","month","avg_rate_to_usd","volatility_30d"]].copy()
    fx_panel["risk"] = np.select([fx_panel["volatility_30d"]>=CFG["risk_thresholds"]["fx_volatility_30d_red"],fx_panel["volatility_30d"]>=CFG["risk_thresholds"]["fx_volatility_30d_amber"]],["RED","AMBER"],default="GREEN")
    return fx_panel,india_year,demand

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    fx = load_fx()
    sal = load_india_salary()
    jobs = build_jobs(load_linkedin_extract(),fx)
    fx_kpi = build_fx(fx)
    india = build_india(sal,fx)
    fx_panel,india_year,demand = build_control_tower(fx_kpi,india,jobs)
    fx.to_csv(OUT/"fact_fx_daily.csv",index=False)
    fx_kpi.to_csv(OUT/"fx_monthly_kpis.csv",index=False)
    india.to_csv(OUT/"india_salary_benchmark.csv",index=False)
    india_year.to_csv(OUT/"india_salary_yearly_kpis.csv",index=False)
    jobs.to_csv(OUT/"fact_linkedin_role_market.csv",index=False)
    demand.to_csv(OUT/"talent_demand_snapshot.csv",index=False)
    fx_panel.to_csv(OUT/"control_tower_fx_risk.csv",index=False)
    meta={"synthetic_operational_data":False,"linkedin_extract_rows":int(len(jobs)),"note":"Only public-source records and derived analytics are used."}
    (OUT/"build_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print("Source-driven finance control tower built.")

if __name__=="__main__":
    run()
