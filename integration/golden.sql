-- Reopened unique images for a policy: include evidence IDs via current_reviews.
SELECT policy_id, release_id, count(DISTINCT image_id) AS reopened_images, array_agg(DISTINCT id ORDER BY id) AS evidence_ids FROM avtriage.current_reviews WHERE decision = 'omission' GROUP BY policy_id, release_id;
-- Audit estimate and finite-population interval are precomputed by avtriage.audit.
SELECT design_id, release_id, policy_id, population, sampled, completed, status, estimate, lower_bound, upper_bound FROM avtriage.audit_results ORDER BY design_id;
-- Evidence for exclusions.
SELECT policy_id, release_id, image_id, evidence_id FROM avtriage.policy_exclusions ORDER BY policy_id, release_id, image_id, evidence_id;
