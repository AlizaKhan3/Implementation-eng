-- Daily success rate as a percentage.
SELECT
    date_trunc('day', created_at)::date AS txn_day,
    count(*) FILTER (WHERE status = 'SUCCESS')                          AS success_count,
    count(*)                                                            AS total_count,
    round(
        100.0 * count(*) FILTER (WHERE status = 'SUCCESS') / NULLIF(count(*), 0),
        2
    ) AS success_rate_pct
FROM transactions
GROUP BY txn_day
ORDER BY txn_day;
