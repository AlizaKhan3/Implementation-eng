# Kubernetes findings: `starter/kubernetes/broken-api.yaml`

Original file preserved unmodified at `kubernetes/broken-api.original.yaml`
for reference. Findings below, then the fix applied in `kubernetes/`.

## Defects identified

1. **Service selector doesn't match the Deployment's pod labels.**
   The Deployment's pod template sets `app: minipay-api`. The Service
   selects `app: minipay-backend`. These never match, so the Service has
   **zero endpoints** — every request to it would hang or fail with
   "connection refused" / no route, even though the pods themselves are
   healthy. This is the single defect that would actually take the
   service down end-to-end; the others degrade it more subtly.
   - Confirms as: `kubectl get endpoints minipay-api -n minipay` → empty
     `ENDPOINTS` column once the pods are running.

2. **Service `targetPort` (8081) doesn't match the container's
   `containerPort` (8080).** Even after fixing the selector, traffic sent
   to the Service on `targetPort: 8081` has nothing listening on 8081
   inside the pod (the app listens on 8080), so it would still fail.

3. **`readinessProbe` checks port 8081, not 8080.** The app never listens
   on 8081, so the readiness probe would never succeed, and the pod would
   never be marked Ready — it would stay out of rotation permanently
   (kubectl would show `0/1 Ready` indefinitely), independent of defects
   1–2. This is likely why the deployment "never comes up" if someone
   only fixes the Service.

4. **`image: YOUR_IMAGE_HERE` is a placeholder**, not a real image
   reference. As written this manifest cannot schedule a working pod at
   all (`ErrImagePull`/`InvalidImageName`).

5. **No CPU/memory `requests`/`limits`.** Required by the assessment
   brief and by any real cluster's scheduling and noisy-neighbour
   protection; a runaway pod could starve the node.

6. **Only `DB_HOST` is provided as an env var.** The application also
   needs `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and
   `MINIPAY_API_KEY` (see `app/minipay_api/db.py` / `auth.py`). As written
   the pod would start (probes aside) but every DB-backed request would
   fail because `DB_USER`/`DB_PASSWORD` would fall back to the
   code-level dev defaults, not the real database's credentials.

7. **No `Namespace` object is defined anywhere.** The manifest assumes
   `minipay` already exists (`kubectl apply -f broken-api.yaml` fails
   outright on a cluster where it doesn't: `namespaces "minipay" not
   found`).

8. **Secrets aren't used at all** — `DB_HOST` is a plain env var and
   there's no separation between non-secret config (host, port, feature
   flags) and secret config (password, API key). Everything is inlined
   in the Deployment, which also means any change to the DB host requires
   editing and re-rolling the Deployment rather than a ConfigMap.

9. **No liveness-vs-readiness distinction problem, but worth noting:**
   the liveness probe correctly targets 8080/`/health`, and `/health`
   itself checks DB connectivity (`db.healthcheck()`). That means a
   temporary DB blip would fail liveness and cause Kubernetes to restart
   the API pod even though the API process itself is fine — a
   self-inflicted restart loop during a DB incident. Not "broken" per se,
   but flagged here because it's the kind of thing that shows up as a
   confusing symptom during an incident (pods restarting for a reason
   unrelated to the code deployed). The fix keeps liveness intentionally
   lighter than readiness — see `kubernetes/20-api-deployment.yaml`.

## Fix applied

See `kubernetes/` for the corrected, expanded manifest set:
- `00-namespace.yaml`
- `01-configmap.yaml` (non-secret config: `DB_HOST`, `DB_PORT`, `DB_NAME`)
- `02-secret.example.yaml` (**template only** — see comment header; the
  real Secret is created imperatively, never committed)
- `10-db-pvc.yaml`, `11-db-statefulset.yaml`, `12-db-service.yaml`
- `20-api-deployment.yaml` (selector/ports/probes fixed, requests/limits
  added, env sourced from the ConfigMap + Secret, liveness probe changed
  to a lightweight `/livez` endpoint that does **not** check the DB —
  see item 9 above and `app/minipay_api/main.py`)
- `21-api-service.yaml`

Verification commands used after deploying (see `evidence/kubernetes.md`
for actual captured output):
```
kubectl get endpoints minipay-api -n minipay
kubectl get pods -n minipay -o wide
kubectl describe pod <api-pod> -n minipay   # check probe status
kubectl logs <api-pod> -n minipay
```
