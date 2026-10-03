-- Headline KPIs: volume, denial rate, denied $, appealable and recoverable $.
-- Denied $ = billed amount on denied claims; recoverable = sum(estimated_recovery_usd) on denied.
SELECT count(*) AS total_claims,
       count(*) FILTER (WHERE is_adjudicated) AS adjudicated,
       count(*) FILTER (WHERE is_denied) AS denied,
       round(count(*) FILTER (WHERE is_denied)::DOUBLE / count(*) FILTER (WHERE is_adjudicated), 4) AS denial_rate,
       round(sum(claim_amount_usd) FILTER (WHERE is_denied), 0) AS denied_usd,
       round(median(claim_amount_usd) FILTER (WHERE is_denied), 0) AS median_denied_claim_usd,
       count(*) FILTER (WHERE is_denied AND appealable) AS appealable_denied,
       round(sum(claim_amount_usd) FILTER (WHERE is_denied AND appealable), 0) AS appealable_denied_usd,
       round(sum(estimated_recovery_usd) FILTER (WHERE is_denied), 0) AS recoverable_usd
FROM 'data/clean/claims.parquet';
