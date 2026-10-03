-- Sizing for the three recommendations. Scenario inputs are assumptions, stated in the README:
--   fix_share = share of low-documentation claims (score < 0.7) that a pre-submission hold can
--   bring to >= 0.7 before filing (25% low case, 50% high case).
-- All dollars are BILLED charges, not expected cash. Annualized over the 42 months in the data.
WITH c AS (
    SELECT documentation_completeness < 0.7 AS low_doc, auth_gap, prior_auth_required, is_denied, claim_amount_usd,
           denial_category, estimated_recovery_usd,
           CASE WHEN documentation_completeness < 0.5 THEN 1 WHEN documentation_completeness < 0.7 THEN 2
                WHEN documentation_completeness < 0.9 THEN 3 ELSE 4 END AS doc_band
    FROM 'data/clean/claims.parquet' WHERE is_adjudicated
),
doc AS (  -- denial rate and denied $ in low vs adequate documentation
    SELECT avg(is_denied::INT) FILTER (low_doc)     AS low_rate,
           avg(is_denied::INT) FILTER (NOT low_doc) AS ok_rate,
           sum(claim_amount_usd) FILTER (low_doc AND is_denied) AS low_denied_usd
    FROM c
),
auth AS (  -- extra denials from auth gaps among auth-required claims, measured INSIDE each
           -- documentation band (same bands as 10_doc_auth_matrix) so documentation is not double-counted
    SELECT sum(gap_n * (gap_rate - nogap_rate)) AS excess_denials,
           sum(gap_n * (gap_rate - nogap_rate) * gap_avg_usd) AS excess_denied_usd
    FROM (
        SELECT doc_band,
               count(*) FILTER (auth_gap) AS gap_n,
               avg(is_denied::INT) FILTER (auth_gap) AS gap_rate,
               avg(is_denied::INT) FILTER (NOT auth_gap) AS nogap_rate,
               avg(claim_amount_usd) FILTER (auth_gap) AS gap_avg_usd
        FROM c WHERE prior_auth_required GROUP BY doc_band
    )
    WHERE gap_n > 0
),
rec AS (
    SELECT sum(estimated_recovery_usd) FILTER (denial_category IN ('coding_error', 'bundling')) AS recode_usd,
           sum(claim_amount_usd) FILTER (denial_category IN ('duplicate', 'timely_filing') AND is_denied) AS writeoff_usd
    FROM c
)
SELECT 'docs gate: denied $ avoided (25% fixed), $ per year' AS scenario, round(0.25 * low_denied_usd * (1 - ok_rate / low_rate) / 3.5, 0) AS value FROM doc
UNION ALL SELECT 'docs gate: denied $ avoided (50% fixed), $ per year', round(0.50 * low_denied_usd * (1 - ok_rate / low_rate) / 3.5, 0) FROM doc
UNION ALL SELECT 'docs gate: low-doc denial rate', round(low_rate, 4) FROM doc
UNION ALL SELECT 'docs gate: adequate-doc denial rate', round(ok_rate, 4) FROM doc
UNION ALL SELECT 'auth check: excess denials from auth gaps (claims, per year)', round(excess_denials / 3.5, 0) FROM auth
UNION ALL SELECT 'auth check: excess denied $ from auth gaps, per year', round(excess_denied_usd / 3.5, 0) FROM auth
UNION ALL SELECT 'recode queue: modeled recoverable $ (coding_error + bundling), $ per year', round(recode_usd / 3.5, 0) FROM rec
UNION ALL SELECT 'write-off: duplicate + timely_filing denied $, per year', round(writeoff_usd / 3.5, 0) FROM rec;
