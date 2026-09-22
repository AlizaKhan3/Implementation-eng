-- Transaction count and total value by status and day.
SELECT
    date_trunc('day', created_at)::date AS txn_day,
    status,
    count(*)                             AS txn_count,
    sum(amount)                          AS total_value
FROM transactions
GROUP BY txn_day, status
ORDER BY txn_day, status;
