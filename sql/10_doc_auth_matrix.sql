-- Part A (scope = all claims): how much of the denial problem sits in low-documentation claims
--   (documentation_completeness < 0.7)?
-- Part B (scope = prior-auth-required claims only): does an auth gap still raise denials once
--   documentation is held constant? Gap claims are mostly low-documentation, which inflates the raw
--   auth-gap effect (confounding / Simpson's paradox check), so compare gap vs no gap INSIDE each
--   documentation band. Pending claims excluded throughout.
WITH c AS (
    SELECT *,
           CASE WHEN documentation_completeness < 0.5 THEN '1: <0.5'
                WHEN documentation_completeness < 0.7 THEN '2: 0.5-0.7'
                WHEN documentation_completeness < 0.9 THEN '3: 0.7-0.9'
                ELSE '4: >=0.9' END AS doc_band
    FROM 'data/clean/claims.parquet' WHERE is_adjudicated
)
SELECT 'A: all claims' AS part,
       CASE WHEN documentation_completeness < 0.7 THEN 'low doc (<0.7)' ELSE 'adequate doc (>=0.7)' END AS doc_group,
       NULL AS auth_status,
       count(*) AS adjudicated,
       round(count(*) / sum(count(*)) OVER (), 4) AS share_of_claims,
       round(avg(is_denied::INT), 4) AS denial_rate,
       round(sum(claim_amount_usd) FILTER (is_denied), 0) AS denied_usd,
       round(sum(claim_amount_usd) FILTER (is_denied) / sum(sum(claim_amount_usd) FILTER (is_denied)) OVER (), 4) AS share_of_denied_usd
FROM c GROUP BY 1, 2
UNION ALL
SELECT 'B: auth-required claims', doc_band,
       CASE WHEN auth_gap THEN 'gap' ELSE 'no gap' END,
       count(*),
       round(count(*) / sum(count(*)) OVER (PARTITION BY auth_gap), 4),  -- share of gap / no-gap claims in this band
       round(avg(is_denied::INT), 4),
       round(sum(claim_amount_usd) FILTER (is_denied), 0),
       NULL
FROM c WHERE prior_auth_required GROUP BY 1, 2, auth_gap
ORDER BY part, doc_group, auth_status;
