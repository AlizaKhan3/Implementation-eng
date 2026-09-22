-- Duplicate transaction references (transaction_ref has no UNIQUE
-- constraint at the DB level -- see investigation/INCIDENT-001-RCA.md,
-- this query is how the duplicates behind that incident were confirmed).
SELECT
    transaction_ref,
    count(*)               AS occurrences,
    array_agg(id ORDER BY id)      AS transaction_ids,
    array_agg(status ORDER BY id)  AS statuses
FROM transactions
GROUP BY transaction_ref
HAVING count(*) > 1
ORDER BY occurrences DESC, transaction_ref;
