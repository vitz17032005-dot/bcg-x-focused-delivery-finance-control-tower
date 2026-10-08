-- Public-data finance views.
SELECT currency, month, avg_rate_to_usd, volatility_30d
FROM fx_monthly_kpis
ORDER BY month, currency;

SELECT employer_country, job_postings, median_usd_salary, salary_observations
FROM talent_demand_snapshot
ORDER BY job_postings DESC;
