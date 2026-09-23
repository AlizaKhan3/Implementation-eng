# Rancher evidence

## Honesty note on the attempt
The sandbox used to build this submission has no Docker daemon available
(`docker: command not found`, confirmed) and a restricted network egress
allowlist, so **Rancher could not be installed or run in that
environment**. Per the assessment instructions ("if environmental
limitations prevent a full Rancher deployment, document the attempt,
commands/configuration, blockers, and how you would perform the required
operational tasks... a working demonstration earns more credit than
theoretical documentation") — this is documented honestly here, and the
procedure below is written to be run for real on your machine (which has
Docker), with the exact commands and what evidence to capture at each
step. **Do this before submitting** — a few real screenshots here are
worth far more than this document alone.

## Blocker
- Environment: sandboxed container with Docker unavailable and a network
  allowlist that does not include Rancher's install sources or the
  container registries Rancher itself pulls from at runtime.
- What would unblock it: any machine with Docker (which you have) and
  normal internet access — no special hardware or licensing required for
  the community/local-dev path below.

## Recommended approach for your machine (Docker only, no separate K8s install needed for Rancher itself)
Run Rancher server as a container, and give it a cluster to manage by
importing the `kind` cluster created for `investigation/INCIDENT-002-RCA.md`
/ `kubernetes/` (see `SETUP.md` for creating that cluster first).

```bash
# 1. Run Rancher server locally
docker run -d --name rancher --privileged \
  -p 8443:443 -p 8080:80 \
  rancher/rancher:latest

# 2. Get the bootstrap password
docker logs rancher 2>&1 | grep "Bootstrap Password:"

# 3. Open https://localhost:8443 (self-signed cert -- accept the browser warning),
#    set the admin password, and use the "Import Existing" cluster flow,
#    which gives you a kubectl apply command to run against your kind
#    cluster to register it with Rancher.
```

## Evidence to capture (screenshots, secrets/PII redacted)
Work through the required checklist below, saving each screenshot as
`evidence/rancher-<step>.png` and linking it here:

1. **Cluster/workload visibility** — Rancher's cluster dashboard showing
   the imported `kind` cluster, and the `minipay` namespace with its
   Deployments/StatefulSet listed.
2. **Pod status and logs** — the `minipay-api` pods in the workloads view
   (should show Ready 2/2 once `kubernetes/` is applied correctly), and
   the log viewer for one pod (Rancher's UI has a built-in log tail —
   equivalent to `kubectl logs -f`).
3. **Configuration/environment inspection** — the pod detail view's
   "Environment Variables" tab, showing `DB_HOST` etc. resolved from the
   ConfigMap/Secret (Rancher masks Secret values in the UI by default,
   which is itself worth a one-line note in the screenshot caption).
4. **Scaling or rollout/restart** — use Rancher's "Redeploy" or scale the
   replica count from the UI (e.g. 2 → 3), then screenshot the resulting
   pod list; equivalent CLI commands for cross-reference:
   ```bash
   kubectl scale deployment minipay-api -n minipay --replicas=3
   kubectl rollout restart deployment minipay-api -n minipay
   kubectl rollout status deployment minipay-api -n minipay
   ```
5. **Basic resource/health visibility** — the cluster or node-level
   CPU/memory usage graph in Rancher's dashboard.

## If Rancher genuinely cannot be installed on your machine either
Everything in the checklist above has a `kubectl`-only equivalent (shown
inline next to each item), and `investigation/kubernetes-findings.md` /
`INCIDENT-002-RCA.md` already demonstrate the underlying diagnostic
reasoning without Rancher's UI specifically. Capture those `kubectl`
outputs instead, and note in this file that Rancher's UI layer
specifically was substituted with equivalent CLI evidence, and why.
