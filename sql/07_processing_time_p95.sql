-- Average and p95 processing time (created_at -> completed_at) for
-- completed (SUCCESS or FAILED) transactions.
SELECT
    status,
    round(avg(EXTRACT(EPOCH FROM (completed_at - created_at))), 2)               AS avg_seconds,
    round(
        (percentile_cont(0.95) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (completed_at - created_at))
        ))::numeric, 2
    ) AS p95_seconds,
    count(*) AS sample_size
FROM transactions
WHERE completed_at IS NOT NULL
GROUP BY status
ORDER BY status;
