-- Which denial categories cost most, and how recoverable are they?
-- Denied claims only; share = category denied $ / total denied $.
WITH d AS (
    SELECT * FROM 'data/clean/claims.parquet' WHERE is_denied
),
action AS (
    -- most common recovery_action per category (ties broken alphabetically)
    SELECT denial_category, recovery_action
    FROM d
    GROUP BY denial_category, recovery_action
    QUALIFY row_number() OVER (PARTITION BY denial_category ORDER BY count(*) DESC, recovery_action) = 1
)
SELECT d.denial_category,
       count(*) AS denied,
       round(sum(claim_amount_usd), 0) AS denied_usd,
       round(sum(claim_amount_usd) / sum(sum(claim_amount_usd)) OVER (), 4) AS share_of_denied_usd,
       round(avg(appealable::INT), 4) AS appealable_pct,
       round(avg(appeal_success_probability), 4) AS avg_appeal_success_prob,
       round(sum(estimated_recovery_usd), 0) AS recoverable_usd,
       any_value(a.recovery_action) AS top_recovery_action,
       round(avg((documentation_completeness < 0.7)::INT), 4) AS low_doc_share  -- share of these denials with documentation < 0.7
FROM d JOIN action a USING (denial_category)
GROUP BY d.denial_category
ORDER BY denied_usd DESC;
