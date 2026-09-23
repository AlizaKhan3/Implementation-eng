# Rancher evidence

Rancher was run locally as a Docker container and used to manage the
`kind` MiniPay cluster (`SETUP.md` §7–8). Screenshots below are redacted
of secrets/bootstrap passwords.

## How it was set up
```bash
docker run -d --name rancher --privileged \
  -p 8443:443 -p 8080:80 \
  rancher/rancher:latest

# Bootstrap password from:
docker logs rancher 2>&1 | grep "Bootstrap Password:"

# UI: https://localhost:8443 — Import Existing cluster, then apply the
# registration manifest Rancher prints against the kind cluster.
```

## Checklist evidence

### 1. Cluster / workload visibility
- Home clusters: ![rancher-home-clusters](rancher-home-clusters.png)
- Workloads overview: ![rancher-1-cluster-workloads](rancher-1-cluster-workloads.png)
- Deployments: ![rancher-1b-deployments](rancher-1b-deployments.png)
- StatefulSets: ![rancher-1b-statefulsets](rancher-1b-statefulsets.png)

### 2. Pod status and logs
- Pods list: ![rancher-2a-pods](rancher-2a-pods.png)
- Pod logs: ![rancher-2-pods-logs](rancher-2-pods-logs.png)

### 3. Configuration / environment inspection
- Env vars on an API pod (Secret values masked by Rancher UI):
  ![rancher-3-env](rancher-3-env.png)

### 4. Scaling / rollout
- Replica scale from Rancher UI:
  ![rancher-4-scale](rancher-4-scale.png)

CLI equivalents used for cross-check:
```bash
kubectl scale deployment minipay-api -n minipay --replicas=3
kubectl rollout restart deployment minipay-api -n minipay
kubectl rollout status deployment minipay-api -n minipay
```

### 5. Basic resource / health visibility
- ![rancher-5-resources](rancher-5-resources.png)
- ![rancher-5b-resources-scrolled](rancher-5b-resources-scrolled.png)

## Related
- Live `kubectl` evidence for the same cluster: `evidence/kubernetes.md`
- Defect analysis of the broken starter manifest:
  `investigation/kubernetes-findings.md`
