-- Reconciliation: successful transaction count/value versus callback-success
-- count/value. A transaction is only considered callback-confirmed if it
-- has at least one callback row with callback_status = 'SUCCESS'.
WITH txn_success AS (
    SELECT id, amount
    FROM transactions
    WHERE status = 'SUCCESS'
),
callback_success AS (
    SELECT DISTINCT transaction_id
    FROM callbacks
    WHERE callback_status = 'SUCCESS'
)
SELECT
    (SELECT count(*) FROM txn_success)                                   AS txn_success_count,
    (SELECT sum(amount) FROM txn_success)                                AS txn_success_value,
    (SELECT count(*) FROM callback_success)                              AS callback_success_count,
    (SELECT count(*) FROM txn_success ts
       WHERE NOT EXISTS (SELECT 1 FROM callback_success cs WHERE cs.transaction_id = ts.id)
    ) AS success_txn_missing_callback,
    (SELECT count(*) FROM callback_success cs
       WHERE NOT EXISTS (SELECT 1 FROM txn_success ts WHERE ts.id = cs.transaction_id)
    ) AS callback_success_without_txn_success;
