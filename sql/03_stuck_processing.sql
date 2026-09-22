-- Transactions that have remained in PROCESSING for more than 15 minutes.
-- "Now" is parameterised as the latest created_at in the dataset so this
-- query is reproducible against a static seeded dataset; in production
-- replace :as_of with now().
SELECT
    id,
    transaction_ref,
    customer_id,
    amount,
    created_at,
    (SELECT max(created_at) FROM transactions) - created_at AS age
FROM transactions
WHERE status = 'PROCESSING'
  AND created_at < (SELECT max(created_at) FROM transactions) - INTERVAL '15 minutes'
ORDER BY created_at ASC;
