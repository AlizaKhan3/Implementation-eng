-- Top 10 customers by successful transaction value.
SELECT
    c.customer_ref,
    c.name,
    sum(t.amount) AS successful_value,
    count(*)      AS successful_count
FROM transactions t
JOIN customers c ON c.id = t.customer_id
WHERE t.status = 'SUCCESS'
GROUP BY c.id, c.customer_ref, c.name
ORDER BY successful_value DESC
LIMIT 10;
