-- Migration 001: indexes identified during the performance investigation.
-- See sql/PERFORMANCE.md for before/after EXPLAIN ANALYZE evidence.
-- Apply after the base schema.sql and any data load.

CREATE INDEX IF NOT EXISTS idx_transactions_transaction_ref
    ON transactions (transaction_ref);

CREATE INDEX IF NOT EXISTS idx_transactions_status_created_at
    ON transactions (status, created_at);

CREATE INDEX IF NOT EXISTS idx_transactions_customer_id_status
    ON transactions (customer_id, status);

ANALYZE transactions;
ANALYZE customers;
