-- Which controllable drivers move the denial rate? Auth gap, documentation band, modifier.
-- Wilson 95% CI, z=1.96. Pending excluded.
WITH base AS (
    -- one row per claim per driver, tagged with its level
    SELECT 'auth_gap (auth-required claims only)' AS driver,
           CASE WHEN auth_gap THEN 'gap' ELSE 'no gap' END AS level, is_denied, claim_amount_usd
    FROM 'data/clean/claims.parquet' WHERE is_adjudicated AND prior_auth_required
    UNION ALL
    SELECT 'documentation_completeness',
           CASE WHEN documentation_completeness < 0.5 THEN '1: <0.5'
                WHEN documentation_completeness < 0.7 THEN '2: 0.5-0.7'
                WHEN documentation_completeness < 0.9 THEN '3: 0.7-0.9'
                ELSE '4: >=0.9' END, is_denied, claim_amount_usd
    FROM 'data/clean/claims.parquet' WHERE is_adjudicated
    UNION ALL
    SELECT 'modifier', CASE WHEN modifier IS NULL THEN 'absent' ELSE 'present' END, is_denied, claim_amount_usd
    FROM 'data/clean/claims.parquet' WHERE is_adjudicated
),
agg AS (
    SELECT driver, level, count(*) AS n, sum(is_denied::INT) AS denied, avg(is_denied::INT) AS p,
           sum(claim_amount_usd) FILTER (is_denied) AS denied_usd
    FROM base GROUP BY 1, 2
)
SELECT driver, level, n AS adjudicated, denied, round(p, 4) AS denial_rate,
       round((p + 1.9208/n - 1.96*sqrt(p*(1-p)/n + 0.9604/n^2)) / (1 + 3.8416/n), 4) AS ci_low,
       round((p + 1.9208/n + 1.96*sqrt(p*(1-p)/n + 0.9604/n^2)) / (1 + 3.8416/n), 4) AS ci_high,
       round(coalesce(denied_usd, 0), 0) AS denied_usd
FROM agg
ORDER BY driver, level;
