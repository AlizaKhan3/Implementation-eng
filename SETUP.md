# Setup / reproduction guide

## Prerequisites
- Docker (+ Docker Compose)
- Python 3.12 (for running tests/CLI outside containers)
- For the Kubernetes section: `kubectl` and `kind`
- For the Rancher section: nothing extra beyond Docker (see `evidence/rancher.md`)

## 1. Local stack (API + UI + DB) via Docker Compose
```bash
git clone <this-repo-url>
cd minipay
docker compose up --build
```
- API + embedded UI: http://localhost:8080 (UI at `/`, API under `/api/...`)
- Postgres: localhost:5432 (user/db/password: `minipay` — local dev only,
  never used outside this compose file)
- Health check: `curl http://localhost:8080/health`

Default local dev API key (set in `docker-compose.yml`, not a secret in
any real sense): `dev-local-key`, sent as header `X-API-Key`.

## 2. Load the schema and (optionally) synthetic data
The schema auto-loads on first `docker compose up` via
`database/schema.sql` mounted into Postgres's init directory. To also load
a ~50k-row synthetic dataset (needed for `sql/`, `INCIDENT-003`, and
realistic Python CLI output):
```bash
python3 database/generate_data.py > database/seed.sql
docker compose exec -T db psql -U minipay -d minipay < database/seed.sql
docker compose exec -T db psql -U minipay -d minipay -f - < database/migrations/001_add_performance_indexes.sql
```

## 3. Run the SQL investigation queries
```bash
for f in sql/0*.sql; do
  echo "== $f =="
  docker compose exec -T db psql -U minipay -d minipay -f - < "$f"
done
```
Or connect directly: `psql -h localhost -U minipay -d minipay` (password `minipay`).

## 4. Run the Python support tool
```bash
cd python
pip install -r requirements.txt
export DB_HOST=localhost DB_PORT=5432 DB_NAME=minipay DB_USER=minipay DB_PASSWORD=minipay
export MINIPAY_API_URL=http://localhost:8080 MINIPAY_API_KEY=dev-local-key
python3 support_tool.py --transaction TXN00004999 --json   # a known seeded duplicate
python3 support_tool.py --stuck-report
python3 support_tool.py --healthcheck
python3 -m pytest tests/ -v   # unit tests, no DB required
```

## 5. Run the API test suite
```bash
cd tests/api
pip install -r ../../app/minipay_api/requirements.txt -r requirements.txt
export MINIPAY_API_URL=http://localhost:8080 MINIPAY_API_KEY=dev-local-key
export DB_HOST=localhost DB_PORT=5432 DB_NAME=minipay DB_USER=minipay DB_PASSWORD=minipay
pytest -v
```

## 6. Run the UI test suite
```bash
cd tests/ui
pip install -r requirements.txt
playwright install chromium
export MINIPAY_UI_URL=http://localhost:8080 MINIPAY_API_KEY=dev-local-key
pytest -v --browser chromium
```
See `tests/ui/NOTES.md` — this could not be executed end-to-end in the
development sandbox (Playwright's browser-binary CDN was outside that
sandbox's network allowlist); run it for real here and save the output.

## 7. Kubernetes (kind)
```bash
# Install kind + kubectl if you don't have them:
#   https://kind.sigs.k8s.io/docs/user/quick-start/#installation
#   https://kubernetes.io/docs/tasks/tools/#kubectl

kind create cluster --name minipay

# Build the API image and load it into the kind cluster (kind can't pull
# from your local Docker daemon directly -- this step bridges that gap)
docker build -t minipay-api:local -f app/minipay_api/Dockerfile app/minipay_api
kind load docker-image minipay-api:local --name minipay

kubectl apply -f kubernetes/00-namespace.yaml
kubectl apply -f kubernetes/01-configmap.yaml
kubectl create secret generic minipay-secrets -n minipay \
  --from-literal=DB_USER=minipay \
  --from-literal=DB_PASSWORD="$(openssl rand -hex 16)" \
  --from-literal=MINIPAY_API_KEY="$(openssl rand -hex 16)"
kubectl apply -f kubernetes/10-db-pvc.yaml
kubectl apply -f kubernetes/11-db-statefulset.yaml
kubectl apply -f kubernetes/12-db-service.yaml
# wait for the DB pod to be Ready before loading the schema:
kubectl wait --for=condition=Ready pod -l app=minipay-db -n minipay --timeout=120s
kubectl exec -n minipay $(kubectl get pod -n minipay -l app=minipay-db -o jsonpath='{.items[0].metadata.name}') \
  -- psql -U minipay -d minipay < database/schema.sql

kubectl apply -f kubernetes/20-api-deployment.yaml
kubectl apply -f kubernetes/21-api-service.yaml

# Verify:
kubectl get pods -n minipay -o wide
kubectl get endpoints minipay-api -n minipay
kubectl port-forward -n minipay svc/minipay-api 8080:80
curl http://localhost:8080/health
```
See `investigation/kubernetes-findings.md` and
`investigation/INCIDENT-002-RCA.md` for what was wrong with the starter
manifest and why each fix above was made. **Capture real command output
here and drop it into a new `evidence/kubernetes.md`** — this repo was
built in an environment without Docker/kind, so that evidence is not yet
captured (see the honesty note in `INCIDENT-002-RCA.md`).

## 8. Rancher
See `evidence/rancher.md` for the exact procedure and evidence checklist
(also not completed in the build sandbox, for the same reason as #7).

## Git / branching
Single-branch (`main`), linear incremental commits, tagged
`submission-v1.0` at the final commit. See `README.md` for the full
rationale.

## Cleanup
```bash
docker compose down -v
kind delete cluster --name minipay
docker rm -f rancher
```
