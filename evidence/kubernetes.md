# Kubernetes evidence

All output below is real, captured on this Mac while MiniPay was
deployed to a local kind cluster (`kind-minipay`) per SETUP.md §7.
Cluster: kind v0.27.0, kubectl client v1.36.1, Darwin arm64.

## Cluster context
```
$ kubectl config current-context
kind-minipay

$ kind version
kind v0.27.0 go1.23.6 darwin/arm64
```

## Pods in namespace minipay
```
$ kubectl get pods -n minipay -o wide
NAME                         READY   STATUS    RESTARTS   AGE    IP           NODE                    NOMINATED NODE   READINESS GATES
minipay-api-794878f9-24cbx   1/1     Running   0          37s    10.244.0.8   minipay-control-plane   <none>           <none>
minipay-api-794878f9-v5hw6   1/1     Running   0          37s    10.244.0.7   minipay-control-plane   <none>           <none>
minipay-db-0                 1/1     Running   0          103s   10.244.0.6   minipay-control-plane   <none>           <none>
```

## API Service endpoints
```
$ kubectl get endpoints minipay-api -n minipay
NAME          ENDPOINTS                         AGE
minipay-api   10.244.0.7:8080,10.244.0.8:8080   37s
```

## Health check via port-forward
```
$ kubectl port-forward -n minipay svc/minipay-api 18080:80 &
$ curl -sS -i http://127.0.0.1:18080/health
HTTP/1.1 200 OK
date: Wed, 23 Sep 2026 07:47:34 GMT
server: uvicorn
content-length: 51
content-type: application/json

{"status":"ok","time":"2026-09-23T07:47:34.341744"}
```
