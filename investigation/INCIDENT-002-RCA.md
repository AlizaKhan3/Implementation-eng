# INCIDENT-002 – Application Unavailable After Deployment

**Priority:** P1 · **Status:** Root-caused, fixed in manifests, and
validated on a live kind cluster (`evidence/kubernetes.md`)

## Observations (as reported)
A new release was deployed to Kubernetes. Pods appear to start, but users
cannot successfully access the application.

## Reproduction / evidence
Static analysis of `starter/kubernetes/broken-api.yaml` (preserved at
`kubernetes/broken-api.original.yaml`) against the application it's meant
to deploy (`app/minipay_api/`). Full defect-by-defect breakdown with
reasoning is in `investigation/kubernetes-findings.md` — this RCA
summarizes it as an incident, that doc is the supporting evidence.

Diagnostic sequence observed against the broken contract (and what each
shows), then confirmed after the fix on kind:

```
$ kubectl get pods -n minipay
# With the broken starter: READY 0/1 — readinessProbe never succeeds
# (checks port 8081; app listens on 8080).

$ kubectl get endpoints minipay-api -n minipay
# With the broken starter: ENDPOINTS empty — Service selector
# (app: minipay-backend) never matches Deployment labels (app: minipay-api).

$ kubectl describe pod <pod> -n minipay
# Events: "Readiness probe failed: dial tcp :8081: connect: connection refused"
```

After applying the fixed manifests (`SETUP.md` §7), live evidence shows
Ready pods, populated endpoints, and a healthy `/health` via port-forward
— see `evidence/kubernetes.md`.
## Hypotheses considered
| Hypothesis | Status | Why |
|---|---|---|
| Bad application code in the image | Rejected | `app/minipay_api` passes its own test suite (18/18, `evidence/api_test_run.txt`) run directly against it outside Kubernetes — the code is not the problem. |
| Database unreachable from the API pod | Considered, secondary at most | `DB_HOST` is set, but only `DB_HOST` — `DB_USER`/`DB_PASSWORD`/`MINIPAY_API_KEY` are entirely absent from the starter manifest, so even a reachable DB would fail auth. This alone wouldn't explain "pods appear to start" though, since a DB failure would surface via `/health` returning 503, not total unreachability. |
| Service/selector/port misconfiguration | **Confirmed as primary cause** | Three independent defects (selector mismatch, Service targetPort mismatch, readinessProbe port mismatch) each individually prevent traffic from ever reaching a running container — see below. |

## Root cause(s)
Three compounding defects in `starter/kubernetes/broken-api.yaml`, any one
of which alone would cause this exact symptom ("pods start, app
unreachable"):

1. **Service selector (`app: minipay-backend`) doesn't match the
   Deployment's pod label (`app: minipay-api`).** The Service has zero
   endpoints regardless of pod health.
2. **`readinessProbe` targets port 8081; the app listens on 8080.** Pods
   never become Ready, so even a correctly-selected Service would still
   route to nothing (Kubernetes excludes non-Ready pods from Service
   endpoints).
3. **Service `targetPort` is 8081, not 8080.** Even bypassing 1 and 2,
   traffic forwarded by the Service would hit a closed port inside the
   pod.

Contributing (not sole causes, but would surface as follow-on incidents
even after 1–3 are fixed): missing `DB_USER`/`DB_PASSWORD`/
`MINIPAY_API_KEY` env vars, a placeholder `image: YOUR_IMAGE_HERE`, and a
liveness probe that depends on the database (see finding #9 in
`kubernetes-findings.md` — would cause *new* pods to restart-loop during
any future DB blip, a second P1 hiding behind this one).

## Correction applied
Full corrected manifest set in `kubernetes/`:
`00-namespace.yaml`, `01-configmap.yaml`, `02-secret.example.yaml`,
`10-db-pvc.yaml`, `11-db-statefulset.yaml`, `12-db-service.yaml`,
`20-api-deployment.yaml`, `21-api-service.yaml`. Every change is annotated
inline in the YAML with a comment tying it back to the finding number in
`kubernetes-findings.md`. Also fixed at the application level: added a
DB-independent `GET /livez` endpoint (`app/minipay_api/main.py`) so
liveness no longer depends on database health, addressing the
contributing cause above at its source rather than only in the manifest.

## Validation performed after the fix
- YAML syntax validated (`python3 -c "import yaml; ..."` against every
  file in `kubernetes/` — all parse cleanly).
- The corrected Deployment/Service's selector, ports and probe targets
  were cross-checked line-by-line against `app/minipay_api/main.py`
  (`containerPort: 8080`, `/health` for readiness, `/livez` for
  liveness) and `01-configmap.yaml`/`02-secret.example.yaml` (env var
  names match exactly what `app/minipay_api/db.py` and `auth.py` read).
- **Live kind cluster:** `minipay-api` 2/2 Ready, `minipay-db-0` Ready,
  Service endpoints populated, `curl /health` → 200 — captured in
  `evidence/kubernetes.md`. Rancher UI evidence for the same cluster is
  in `evidence/rancher.md`.

## Preventive controls for the future
- **CI-side manifest linting** before merge: `kubectl apply --dry-run=server`
  against a disposable cluster (or `kubeconform`/`kubeval` offline) would
  have caught the placeholder image and basic schema issues immediately,
  without needing a human to notice a selector typo by eye.
- **A same-labels convention enforced by a template/Kustomize base**
  rather than hand-written Service + Deployment pairs: generating both
  from one `commonLabels` block makes a selector/label mismatch
  structurally impossible instead of relying on careful proofreading.
- **A post-deploy smoke-test job** (`kubectl run --rm curl-test --
  curl -f http://minipay-api/health`) as a required CI/CD gate before a
  rollout is considered successful — would have caught defects 1–3
  automatically instead of waiting for a user report.
- **Separate the liveness and readiness semantics explicitly in template
  review**: a checklist item ("does liveness depend on anything other
  than the process itself?") would have caught the DB-coupled liveness
  probe before it became defect #9.
