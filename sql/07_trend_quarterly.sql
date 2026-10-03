-- Is the denial rate trending? By year-quarter, adjudicated claims only (pending excluded,
-- so the latest quarter may be understated in volume).
SELECT claim_year || '-' || claim_quarter AS year_quarter,
       count(*) AS adjudicated,
       round(avg(is_denied::INT), 4) AS denial_rate,
       round(sum(claim_amount_usd) FILTER (WHERE is_denied), 0) AS denied_usd
FROM 'data/clean/claims.parquet'
WHERE is_adjudicated
GROUP BY 1
ORDER BY 1;
