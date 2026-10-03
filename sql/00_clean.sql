-- Build the clean claims table: one row per claim, raw claims joined to denial labels.
-- Run by clean.py. Rows are only dropped if invalid (duplicate id, non-positive amount,
-- date outside the documented range); DATA_QUALITY.md logs how many hit each rule.
CREATE OR REPLACE TABLE claims AS
WITH joined AS (
    SELECT c.* EXCLUDE (dataset_version, synthetic_flag, generation_date),  -- constant columns
           l.denial_code_description, l.appealable, l.appeal_success_probability,
           l.recovery_action, l.estimated_recovery_usd,
           row_number() OVER (PARTITION BY c.claim_id ORDER BY c.claim_submission_date) AS copy_no
    FROM raw_claims c
    LEFT JOIN raw_labels l USING (claim_id)
)
SELECT * EXCLUDE (copy_no),
       outcome = 'denied'   AS is_denied,
       outcome <> 'pending' AS is_adjudicated,          -- pending claims have no result yet
       date_trunc('month', claim_submission_date)::DATE AS claim_month,
       CASE left(primary_icd10_dx, 1)                   -- ICD-10 chapter from the first letter
           WHEN 'A' THEN 'Infectious' WHEN 'B' THEN 'Infectious'
           WHEN 'C' THEN 'Neoplasms'
           WHEN 'E' THEN 'Endocrine/metabolic'
           WHEN 'F' THEN 'Mental/behavioral'
           WHEN 'G' THEN 'Nervous system'
           WHEN 'I' THEN 'Circulatory'
           WHEN 'J' THEN 'Respiratory'
           WHEN 'K' THEN 'Digestive'
           WHEN 'M' THEN 'Musculoskeletal'
           WHEN 'O' THEN 'Pregnancy'
           WHEN 'S' THEN 'Injury' WHEN 'T' THEN 'Injury'
           WHEN 'Z' THEN 'Health status/encounters'
           ELSE 'Other' END AS dx_chapter,
       prior_auth_required AND coalesce(prior_auth_obtained, false) = false AS auth_gap
FROM joined
WHERE copy_no = 1
  AND claim_amount_usd > 0
  AND claim_submission_date BETWEEN DATE '2021-01-01' AND DATE '2024-06-30';
