-- Simpson's paradox check: is a segment's denial rate just its procedure / documentation / auth mix?
-- Indirect standardization: expected = avg over the segment's claims of the overall denial rate of
-- each claim's stratum. ratio = observed / expected (>1 = worse than its mix predicts).
WITH c AS (
    SELECT payer_type, provider_specialty, cpt_code, is_denied::INT AS d,
           CASE WHEN documentation_completeness < 0.5 THEN 1
                WHEN documentation_completeness < 0.7 THEN 2
                WHEN documentation_completeness < 0.9 THEN 3 ELSE 4 END AS doc_band,
           auth_gap
    FROM 'data/clean/claims.parquet' WHERE is_adjudicated
),
e AS (
    -- stratum-level overall rates attached to every claim via window avg (no join needed)
    SELECT *,
           avg(d) OVER (PARTITION BY cpt_code) AS exp_cpt,
           avg(d) OVER (PARTITION BY doc_band, auth_gap) AS exp_doc_auth
    FROM c
),
u AS (
    SELECT 'payer (CPT mix)' AS dimension, payer_type AS segment, d, exp_cpt AS exp FROM e
    UNION ALL SELECT 'specialty (CPT mix)', provider_specialty, d, exp_cpt FROM e
    UNION ALL SELECT 'payer (doc band + auth gap mix)', payer_type, d, exp_doc_auth FROM e
)
SELECT dimension, segment, count(*) AS adjudicated,
       round(avg(d), 4) AS observed_rate,
       round(avg(exp), 4) AS expected_rate,
       round(avg(d) / avg(exp), 3) AS ratio
FROM u
GROUP BY 1, 2
ORDER BY dimension, ratio DESC, segment;
