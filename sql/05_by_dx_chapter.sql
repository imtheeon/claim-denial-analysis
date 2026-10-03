-- Which diagnosis chapters get denied most, and what does it cost?
-- Rate = denied / adjudicated (pending excluded). Denied $ = billed amount on denied claims.
-- Wilson 95% CI: (p + z2/2n +- z*sqrt(p(1-p)/n + z2/4n2)) / (1 + z2/n), z=1.96.
WITH seg AS (
    SELECT dx_chapter AS dx_chapter,
           count(*) AS claims,
           count(*) FILTER (WHERE is_adjudicated) AS adjudicated,
           count(*) FILTER (WHERE is_denied) AS denied,
           sum(claim_amount_usd) FILTER (WHERE is_denied) AS denied_usd,
           sum(estimated_recovery_usd) FILTER (WHERE is_denied) AS recoverable_usd,
           -- grand total over all segments, computed before any min-volume filter
           sum(sum(claim_amount_usd) FILTER (WHERE is_denied)) OVER () AS total_denied_usd
    FROM 'data/clean/claims.parquet'
    GROUP BY 1
)
SELECT dx_chapter,
       adjudicated, denied,
       round(denied::DOUBLE / adjudicated, 4) AS denial_rate,
       -- Wilson bounds
       round((denied::DOUBLE/adjudicated + 1.9208/adjudicated
              - 1.96*sqrt(denied::DOUBLE/adjudicated*(1-denied::DOUBLE/adjudicated)/adjudicated + 0.9604/adjudicated^2))
             / (1 + 3.8416/adjudicated), 4) AS ci_low,
       round((denied::DOUBLE/adjudicated + 1.9208/adjudicated
              + 1.96*sqrt(denied::DOUBLE/adjudicated*(1-denied::DOUBLE/adjudicated)/adjudicated + 0.9604/adjudicated^2))
             / (1 + 3.8416/adjudicated), 4) AS ci_high,
       round(denied_usd, 0) AS denied_usd,
       round(recoverable_usd, 0) AS recoverable_usd,
       round(denied_usd / total_denied_usd, 4) AS share_of_denied_usd
FROM seg
ORDER BY denied_usd DESC;
