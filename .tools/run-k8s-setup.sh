#!/usr/bin/env bash
# SETUP.md §7 — Kubernetes (kind) deploy + evidence capture
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/.tools"
export PATH="$ROOT/.tools:$PATH"
# Prefer Docker Desktop socket if present
if [[ -S "$HOME/.docker/run/docker.sock" ]]; then
  export DOCKER_HOST="unix://$HOME/.docker/run/docker.sock"
fi

EVIDENCE="$ROOT/evidence/kubernetes.md"
LOG="$ROOT/.tools/k8s-setup.log"
mkdir -p "$(dirname "$LOG")"
# Simple redirect (no process substitution — some environments block /dev/fd)
exec >"$LOG" 2>&1

echo "=== Prerequisites ==="
docker info >/dev/null
kind version
kubectl version --client

echo "=== kind create cluster --name minipay ==="
kind delete cluster --name minipay 2>/dev/null || true
kind create cluster --name minipay

echo "=== Build + load API image ==="
docker build -t minipay-api:local -f app/minipay_api/Dockerfile app/minipay_api
kind load docker-image minipay-api:local --name minipay

echo "=== Apply manifests ==="
kubectl apply -f kubernetes/00-namespace.yaml
kubectl apply -f kubernetes/01-configmap.yaml
# Idempotent secret create
if ! kubectl get secret minipay-secrets -n minipay >/dev/null 2>&1; then
  kubectl create secret generic minipay-secrets -n minipay \
    --from-literal=DB_USER=minipay \
    --from-literal=DB_PASSWORD="$(openssl rand -hex 16)" \
    --from-literal=MINIPAY_API_KEY="$(openssl rand -hex 16)"
else
  echo "secret minipay-secrets already exists — keeping it"
fi
kubectl apply -f kubernetes/10-db-pvc.yaml
kubectl apply -f kubernetes/11-db-statefulset.yaml
kubectl apply -f kubernetes/12-db-service.yaml

echo "=== Wait for DB Ready ==="
kubectl wait --for=condition=Ready pod -l app=minipay-db -n minipay --timeout=180s
DB_POD=$(kubectl get pod -n minipay -l app=minipay-db -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n minipay "$DB_POD" -- psql -U minipay -d minipay < database/schema.sql

echo "=== Deploy API ==="
kubectl apply -f kubernetes/20-api-deployment.yaml
kubectl apply -f kubernetes/21-api-service.yaml
kubectl rollout status deployment/minipay-api -n minipay --timeout=180s || true
sleep 5

echo "=== Capture verification ==="
PODS_OUT=$(kubectl get pods -n minipay -o wide)
ENDPOINTS_OUT=$(kubectl get endpoints minipay-api -n minipay)
DEPLOY_OUT=$(kubectl get deploy,sts,svc -n minipay)
CONTEXT=$(kubectl config current-context)
KIND_VER=$(kind version)
KUBECTL_VER=$(kubectl version --client 2>&1)
HOST=$(hostname)
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

kubectl port-forward -n minipay svc/minipay-api 18080:80 >/tmp/minipay-pf.log 2>&1 &
PF_PID=$!
sleep 3
HEALTH_OUT=$(curl -sS -w "\nHTTP %{http_code}\n" http://127.0.0.1:18080/health || true)
kill "$PF_PID" 2>/dev/null || true
wait "$PF_PID" 2>/dev/null || true

cat > "$EVIDENCE" <<EOF
# Kubernetes evidence (kind)

Captured for real on ${HOST} / ${NOW} following \`SETUP.md\` §7. Cluster:
\`kind\` name \`minipay\`. Image: \`minipay-api:local\` built from
\`app/minipay_api/Dockerfile\` and loaded with \`kind load docker-image\`.

## Tooling
\`\`\`
\$ kind version
${KIND_VER}

\$ kubectl version --client
${KUBECTL_VER}
\`\`\`

## Cluster
\`\`\`
\$ kind create cluster --name minipay
# (cluster created; kubeconfig context kind-minipay)
\$ kubectl config current-context
${CONTEXT}
\`\`\`

## Pods
\`\`\`
\$ kubectl get pods -n minipay -o wide
${PODS_OUT}
\`\`\`

## Endpoints
\`\`\`
\$ kubectl get endpoints minipay-api -n minipay
${ENDPOINTS_OUT}
\`\`\`

## Deployments / StatefulSets / Services
\`\`\`
\$ kubectl get deploy,sts,svc -n minipay
${DEPLOY_OUT}
\`\`\`

## Health check (port-forward)
\`\`\`
\$ kubectl port-forward -n minipay svc/minipay-api 18080:80 &
\$ curl http://127.0.0.1:18080/health
${HEALTH_OUT}
\`\`\`

## Notes
- Secret \`minipay-secrets\` created with random \`DB_PASSWORD\` /
  \`MINIPAY_API_KEY\` (values not recorded here).
- Schema loaded into the DB pod with \`psql < database/schema.sql\` after
  the StatefulSet became Ready.
- Manifests applied from \`kubernetes/\` (fixed set; see
  \`investigation/kubernetes-findings.md\` / \`INCIDENT-002-RCA.md\`).
EOF

echo "DONE: wrote $EVIDENCE"
echo "--- pods ---"
echo "$PODS_OUT"
echo "--- endpoints ---"
echo "$ENDPOINTS_OUT"
echo "--- health ---"
echo "$HEALTH_OUT"
