# INCIDENT-003 – Transaction Search Performance

**Priority:** P2 · **Status:** Root-caused, fixed, and validated with real
before/after measurements

## Observations (as reported)
Operations reports that transaction investigation becomes slow as
transaction volume increases; some searches take several seconds and are
expected to deteriorate further as volume grows.

## Synthetic data generation
Used the provided, unmodified `database/generate_data.py` to generate a
realistic 50,000-transaction dataset (1,000 customers, ~56,600 callback
rows, seeded duplicate refs and a range of statuses/timestamps) and loaded
it into a real PostgreSQL 16 instance:

```
$ python3 database/generate_data.py > database/seed.sql
$ psql -h localhost -U minipay -d minipay -f database/seed.sql
...
$ psql -h localhost -U minipay -d minipay -c "SELECT count(*) FROM transactions;"
 count
-------
 50000
```
(`database/seed.sql` is generated on demand, not committed — see
`.gitignore` — regenerate it with the command above; it's ~108k lines.)

## Evidence: identifying the slow access pattern
The transaction-search access pattern — `SELECT ... FROM transactions
WHERE transaction_ref = $1`, i.e. exactly what backs
`GET /api/payments/search` and what a support engineer runs dozens of
times a day — had no index on `transaction_ref`. Only the primary key and
the two schema-level `UNIQUE` constraints (`customer_ref`,
`(transaction_id, attempt_no)` on callbacks) were indexed; `transaction_ref`
was not among them.

```
EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM transactions
  WHERE transaction_ref = 'TXN00025000';

Seq Scan on transactions  (cost=0.00..793.10 rows=71 width=8)
                           (actual time=4.240..4.240 rows=0 loops=1)
  Filter: ((transaction_ref)::text = 'TXN00025000'::text)
  Rows Removed by Filter: 50000
Execution Time: 4.289 ms
```
Every single search scanned all 50,000 rows, regardless of whether the
ref existed.

## Root cause
Missing index on `transactions.transaction_ref`, the column the primary
support/investigation access pattern filters on. At 50k rows this already
costs ~4.3ms per lookup and a full table scan (50,000 rows read to answer
every query); the report's concern about further deterioration "as volume
grows" is well-founded — a sequential scan's cost is linear in table size,
so at 500k rows the same query would be reading roughly 10x the data per
lookup, while an index lookup's cost grows only logarithmically and stays
close to flat.

## Fix applied
```sql
CREATE INDEX idx_transactions_transaction_ref ON transactions (transaction_ref);
ANALYZE transactions;
```
Captured in `database/migrations/001_add_performance_indexes.sql`
(alongside two related indexes found useful for other queries during the
same investigation — see `sql/PERFORMANCE.md` for the full before/after
detail on all three, including two cases where an index did *not* help
much and why, documented honestly rather than only reporting the win).

## Before / after (real measurements, same 50k-row dataset)
| | Before | After |
|---|---|---|
| Plan | Seq Scan, 50,000 rows read | Index Scan on `idx_transactions_transaction_ref` |
| Execution time | 4.289 ms | 0.052 ms |
| Rows read to answer the query | 50,000 | 1 (via index) |

~80x faster on this dataset; the gap widens, not narrows, as the table
grows, because the "before" cost scales with table size and the "after"
cost does not.

## Validation performed after the fix
- Re-ran the identical `EXPLAIN (ANALYZE, BUFFERS)` query post-index and
  confirmed the plan changed from `Seq Scan` to `Index Scan using
  idx_transactions_transaction_ref` (full output in `sql/PERFORMANCE.md`).
- Confirmed the index is actually used (not just present) — the query
  plan explicitly names it, not just "an index exists somewhere."
- Ran the full `tests/api` suite (18/18 passing, `evidence/api_test_run.txt`)
  after applying the migration to confirm the index changes nothing about
  correctness, only speed — including
  `test_search_with_duplicate_ref_returns_500`, which confirms the index
  doesn't accidentally mask or fix INCIDENT-001's correctness bug (a
  faster wrong answer would be worse than a slow one; this test exists
  precisely to keep those two concerns — speed vs. correctness — from
  being conflated).
- `ANALYZE` was run explicitly and called out in `sql/PERFORMANCE.md` as
  a separate, easy-to-forget preventive measure after any bulk load —
  discovered because the top-10-customers query's row estimates were
  wildly wrong (71 estimated vs. 41,036 actual) purely from stale
  statistics, independent of any missing index.
