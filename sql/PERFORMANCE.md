# Performance investigation

Dataset: seeded `database/generate_data.py` output loaded into PostgreSQL 16
(1,000 customers / 50,000 transactions / ~56,600 callbacks). All numbers
below are real `EXPLAIN (ANALYZE, BUFFERS)` output captured against that
dataset, not estimates.

## Deliberately inefficient query: transaction lookup by reference

This is the query behind `GET /api/payments/search?ref=...` (see
`investigation/INCIDENT-001-RCA.md` for the correctness bug in that same
endpoint — this document is only about its performance).

```sql
SELECT id FROM transactions WHERE transaction_ref = 'TXN00025000';
```

`transaction_ref` had no index (the base schema only indexes the primary
keys and the two UNIQUE constraints). Every lookup by reference — which is
the primary access pattern a support engineer or the UI search box uses —
did a full sequential scan of the table.

**Before (no index):**

```
Seq Scan on transactions  (cost=0.00..793.10 rows=71 width=8)
                           (actual time=4.240..4.240 rows=0 loops=1)
  Filter: ((transaction_ref)::text = 'TXN00025000'::text)
  Rows Removed by Filter: 50000
Execution Time: 4.289 ms
```

**Change applied:**

```sql
CREATE INDEX idx_transactions_transaction_ref ON transactions (transaction_ref);
ANALYZE transactions;
```

**After:**

```
Index Scan using idx_transactions_transaction_ref on transactions
  (cost=0.29..8.31 rows=1 width=8) (actual time=0.025..0.025 rows=0 loops=1)
  Index Cond: ((transaction_ref)::text = 'TXN00025000'::text)
Execution Time: 0.052 ms
```

~4.3ms → ~0.05ms (roughly 80x) on this 50k-row dataset, and the query plan
changes from a full scan to an index scan, so the gap only widens as the
table grows — at 50k rows the table already fits comfortably in shared
buffers, which is why the absolute numbers are small; the row-scan-count
difference (50,000 vs. effectively 0) is the meaningful signal.

Note: this index does **not** fix INCIDENT-001 (the duplicate-reference
crash) — it only makes the lookup fast regardless of how many rows match.
The RCA covers the correctness fix separately, and recommends this same
column be made unique once historical duplicates are cleaned up, which
would fold this index into that constraint's backing index for free.

## Other queries checked (kept as sequential scans, on purpose)

Two more candidates were profiled before/after adding
`idx_transactions_status_created_at` and `idx_transactions_customer_id_status`:

- **Stuck-PROCESSING query** (`sql/03_stuck_processing.sql`): filters
  `status = 'PROCESSING'`, which matches ~5% of rows (2,439 / 50,000). The
  planner switched from a Seq Scan to a Bitmap Heap Scan after the index
  and `ANALYZE`, but total execution time only moved from ~12.7ms to
  ~9.8ms. At this selectivity and table size a scan is already close to
  optimal — the index becomes worth keeping mainly as the table grows past
  a few hundred thousand rows, not for an immediate win today.
- **Top-10 customers join** (`sql/02_top10_customers.sql`): before adding
  indexes, `EXPLAIN` row estimates were badly off (71 estimated vs 41,036
  actual) because the table had never been `ANALYZE`d after the bulk load.
  Running `ANALYZE` alone (independent of any index) corrected the planner's
  statistics and materially changed the chosen join strategy. **Lesson
  documented here on purpose:** after any bulk load, `ANALYZE` is at least
  as important as indexing, and is easy to forget in CI/seed scripts.

## How to reproduce

```bash
export PGPASSWORD=minipay
psql -h localhost -U minipay -d minipay \
  -c "EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM transactions WHERE transaction_ref = 'TXN00025000';"
```
