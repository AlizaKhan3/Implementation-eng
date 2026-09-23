# Linux evidence

All output below is real, captured on the Linux host used to build and
validate this submission (Ubuntu 24.04.4 LTS, kernel 6.18) while the
MiniPay API and PostgreSQL were running. Reproduce any of it with
`./healthcheck.sh` (in this directory) plus the individual commands
below.

## OS / kernel identification
```
$ uname -a
Linux vm 6.18.44-fc-v37 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux

$ cat /etc/os-release
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
ID=ubuntu
ID_LIKE=debian
```

## CPU / memory / disk utilization
```
$ nproc
1

$ free -h
               total        used        free      shared  buff/cache   available
Mem:           3.9Gi       355Mi       3.3Gi        26Mi       533Mi       3.6Gi
Swap:             0B          0B          0B

$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda        252G  8.4G   11G  45% /
```

## Listening ports and relevant processes
```
$ netstat -tlnp
Proto Recv-Q Send-Q Local Address     Foreign Address   State    PID/Program name
tcp        0      0 127.0.0.1:5432    0.0.0.0:*         LISTEN   215/postgres
tcp        0      0 0.0.0.0:8080      0.0.0.0:*         LISTEN   233/python3
```
(5432 = PostgreSQL, 8080 = the MiniPay API via uvicorn — matches
`docker-compose.yml`'s port mapping.)

## DNS / network connectivity checks
```
$ getent hosts github.com
140.82.113.3    github.com

$ curl -s -o /dev/null -w "HTTP %{http_code}, %{time_total}s\n" https://github.com
HTTP 200, 0.097s
```

## Application/container logs
API access + error log (uvicorn, `app/minipay_api/main.py`'s own request
logging middleware), captured live during the INCIDENT-001 reproduction:
```
2026-09-23 06:17:5x INFO minipay.api POST /api/customers -> 201 (13.3ms)
...
  File "/home/claude/minipay/app/minipay_api/main.py", line 165, in search_payment
    (row,) = rows  # <-- intentional defect: fails when duplicates exist
    ^^^^^^
ValueError: too many values to unpack (expected 1)
```
Full transcript: `evidence/incident-001-reproduction.md`.
Container-log equivalent once deployed to Kubernetes: `kubectl logs
<pod> -n minipay` (see `investigation/kubernetes-findings.md`).

## Process consuming the most memory
```
$ ps aux --sort=-%mem | head -6
USER       PID %CPU %MEM    VSZ   RSS COMMAND
root       233  0.6  1.5 262428 61952 python3 -m uvicorn minipay_api.main:app ...
root        56  0.0  0.8 1987960 35096 (sandbox infra process, not part of MiniPay)
postgres   215  0.0  0.7 220300 31836 postgres -D /var/lib/postgresql/16/main ...
```
The MiniPay API process is the top application-level memory consumer at
~62MB RSS — expected for a small FastAPI/uvicorn service with no
in-memory caching.

## Disk usage by directory
```
$ du -sh /home/claude/* 2>/dev/null | sort -rh
19M   /home/claude/minipay
284K  /home/claude/paysys-implementation-l2-assessment
```

## Repeatable health-check script
`evidence/healthcheck.sh` — checks the API's `/health` endpoint, a raw
TCP connect to the database port, and root disk usage, with a non-zero
exit code on any failure (suitable for cron/CI use). Real run:
```
$ DB_HOST=localhost DB_PORT=5432 ./healthcheck.sh
== MiniPay health check ==
-- API: http://localhost:8080/health --
OK
-- Database: TCP connect to localhost:5432 --
OK
-- Disk space on / --
Used: 45%
OK
== RESULT: HEALTHY ==
```

## How I'd investigate (brief)

**High CPU:** `top`/`htop` sorted by CPU to identify the process, then
`py-spy dump` (Python) or `strace -c -p <pid>` for a syscall-level
breakdown if it's not obviously one hot loop; check whether it correlates
with request volume (`kubectl top pod` / API access logs) versus a stuck
background task (e.g., a runaway retry loop — relevant here given
`callbacks.attempt_no` exists specifically to bound retries).

**Low disk space:** `df -h` to confirm which filesystem, then `du -sh
/*` narrowing down, watching especially for: container/image layers
(`docker system df`), log files that were never rotated, and — specific
to this app — an un-truncated `database/seed.sql` regenerated repeatedly
without cleanup (it's ~108k lines per run).

**Unreachable API:** work outside-in — `curl` from the same host first
(rules out DNS/ingress), then `kubectl get pods`/`get endpoints` (rules
out the exact class of bug diagnosed in INCIDENT-002: pod running but
Service has no endpoints), then pod logs, then a shell into the pod to
check outbound DB connectivity from inside the pod's network namespace
specifically (namespace-level network policy can differ from the host's).

**A process repeatedly terminating:** `kubectl get pod -n minipay -o
wide` for restart count, `kubectl describe pod` for the last termination
reason/exit code (OOMKilled vs. a probe-triggered restart vs. a crash),
and `kubectl logs <pod> --previous` to see the crashed instance's own
output, not the new one's. Specifically relevant here: a liveness probe
that depends on the database (the original bug in this app's `/health`,
fixed by adding a DB-independent `/livez` — see
`investigation/kubernetes-findings.md` finding #9) will look exactly like
"the process keeps dying" when the real issue is an upstream dependency,
not the process itself — worth ruling out before assuming a crash.

## Git
See `git log` in the repository root for commit history (used throughout
development, not just at submission time) and the `submission-v1.0` tag
on the final commit. Branch/merge strategy: see `README.md`.
