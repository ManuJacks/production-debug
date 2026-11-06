# Kubernetes Failure Exercises & Interactive Triage Playbook

These exercises are designed for safe failure drilling in a disposable or dedicated lab namespace (`production-debug-lab`) using the `production-debug` toolbox container.

---

## 🧭 Triage Environment Quickstart

### 1. Where Are Your Pods? Understanding Namespaces
When you run `kubectl get pods`, kubectl queries only the **active/default namespace** unless instructed otherwise. In this lab setup:
- **`default`**: Contains baseline cluster test workloads (e.g., `nettest-worker1`, `nettest-worker2`).
- **`debug-system`**: Houses your active troubleshooting container (`production-debug`).
- **`production-debug-lab`**: Houses the failure scenarios (e.g., `crashloop-demo`).

To view pods across all namespaces at once:
```bash
kubectl get pods -A
```
To query a specific namespace:
```bash
kubectl -n production-debug-lab get pods
```

---

### 2. Entering the Debug Container & TMUX Triage Session
To attach directly to the 4-pane incident triage terminal inside the running debug pod:
```bash
kubectl -n debug-system exec -it production-debug -- tmux attach -t incident-triage
```
*Tip: If you ever detach or need to switch panes, use the tmux prefix `Ctrl+b` followed by the arrow keys (`Up`, `Down`, `Left`, `Right`). Pane 4 (Bottom-Right) is your primary logged interactive shell.*

---

## 🛠️ Exercise Walkthroughs

---

### Exercise 1: CrashLoopBackOff

#### Scenario Description
A container starts, immediately encounters an unhandled fatal condition or missing prerequisite configuration, and terminates with a non-zero exit code. The kubelet repeatedly restarts the container with an exponential backoff delay (10s, 20s, 40s... up to 5 minutes).

#### 1. Setup
From your workstation repository root:
```bash
./scenarios/run.sh setup 01-crashloop
```

#### 2. Symptom Analysis
From inside the debug container (or using your local kubectl targeting the lab namespace):
```bash
kubectl -n production-debug-lab get pods
```
**Observed Output:**
```text
NAME                              READY   STATUS             RESTARTS        AGE
crashloop-demo-6955769c7b-xqgqx   0/1     CrashLoopBackOff   6 (3m ago)      9m
```

#### 3. Investigation & Evidence Collection
First, inspect the pod's termination state and events:
```bash
kubectl -n production-debug-lab describe pod -l app=crashloop-demo
```
Key fields to inspect:
- **`State`**: `Waiting` -> `Reason: CrashLoopBackOff`
- **`Last State`**: `Terminated` -> `Exit Code: 1`, `Reason: Error`

Next, inspect the logs of the terminated container. Standard `kubectl logs` might be empty if the container is currently waiting in its backoff delay. **Always use `--previous`**:
```bash
kubectl -n production-debug-lab logs -l app=crashloop-demo --previous
```
**Observed Error:**
```text
missing CONFIG_URL
```

#### 4. Root Cause
The process exited because `CONFIG_URL` was not supplied in the container environment. The container command `["/bin/sh", "-c", "echo missing CONFIG_URL; exit 1"]` simulated a typical microservice failing fast due to absent configuration.

#### 5. Remediation & Verification
Update the deployment to inject the missing configuration:
```bash
kubectl -n production-debug-lab set env deployment/crashloop-demo CONFIG_URL="https://config.internal.lab"
```
Or patch the container command to a healthy daemon:
```bash
kubectl -n production-debug-lab set env deployment/crashloop-demo CONFIG_URL="https://config.internal.lab"
kubectl -n production-debug-lab rollout status deployment/crashloop-demo
```
Verify the pod transitions to `Running` (`1/1`):
```bash
kubectl -n production-debug-lab get pods -l app=crashloop-demo
```

#### 6. Prevention & Follow-up Controls
- Implement pre-flight validation in CI manifests.
- Use Kubernetes `ConfigMap` or secret references with optional flags disabled (`optional: false`) so the pod creation will fail with a clear `CreateContainerConfigError` rather than crashing silently at runtime.
- Set up Prometheus alerts on `kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"} > 0`.

---

### Exercise 2: ImagePullBackOff & ErrImagePull

#### Scenario Description
A deployment requests an image tag or repository that does not exist or requires private registry credentials that have not been mounted.

#### 1. Setup
```bash
./scenarios/run.sh setup 02-imagepull
```

#### 2. Triage & Diagnosis
```bash
kubectl -n production-debug-lab get pods
kubectl -n production-debug-lab describe pod -l app=imagepull-demo
```
- Distinguish manifest errors (e.g. tag `nonexistent-tag-404`) from authentication errors (`401 Unauthorized` or `403 Forbidden`).

---

### Exercise 3: Pending Pod (Scheduler Predicates)
- Identify impossible resource requests (`cpu: 999`), node selectors, and untolerated taints via `kubectl describe pod`.

---

### Exercise 4: Readiness Probe Failure
- Explain why a pod shows `Running` with `READY 0/1` and is omitted from endpoints (`kubectl get endpointslices`).

---

### Exercise 5: DNS Failure & Resolver Analysis
- Use `getent hosts`, `dig`, and examine `/etc/resolv.conf` to trace CoreDNS vs upstream resolution failures.

---

### Exercise 6: NetworkPolicy Ingress/Egress Isolation
- Diagnose dropped packets using `curl` / `nc` probes and Hubble network flow inspection.

---

### Exercise 7: Container OOMKilled vs Node Eviction
- Identify exit code `137` (128 + SIGKILL 9) and distinguish between container cgroup limits and node pressure.

---

### Exercise 8: RBAC Permission Denied
- Use `kubectl auth can-i <verb> <resource> --as=system:serviceaccount:<namespace>:<sa>` to isolate least-privilege deficiencies.
