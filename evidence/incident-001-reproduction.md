## Reproduction: INCIDENT-001

### 1. A transaction_ref with no duplicates searches fine
$ curl -s -o /dev/null -w "%{http_code}
" "http://localhost:8080/api/payments/search?ref=TXN00030001" -H "X-API-Key: dev-local-key"
200

### 2. Insert a second row with a duplicate transaction_ref (simulating historical dirty data from before an idempotency safeguard existed)
$ psql -h localhost -U minipay -d minipay -c "INSERT INTO transactions (transaction_ref, customer_id, amount, status, created_at) VALUES ('TXN00030001', 2, 10.00, 'FAILED', now());"
INSERT 0 1

### 3. The same search now returns HTTP 500
$ curl -s -w "
HTTP %{http_code}
" "http://localhost:8080/api/payments/search?ref=TXN00030001" -H "X-API-Key: dev-local-key"
Internal Server Error
HTTP 500

### 4. Server-side traceback (application log)
    (row,) = rows  # <-- intentional defect: fails when duplicates exist
    ^^^^^^
ValueError: too many values to unpack (expected 1)
