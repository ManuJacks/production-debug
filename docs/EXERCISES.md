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

---

#### 💡 Diagnostic Hints & Thought Process
> [!TIP]
> **How to approach a CrashLoop without guessing:**
> 1. **Do not guess or assume what the code is doing.** Kubernetes tells you the story if you check the dying process state.
> 2. **Check the Exit Code first:** Does `kubectl describe pod` show `Exit Code: 1` (application exception/fatal exit), `Exit Code: 137` (OOMKilled - out of memory), or `Exit Code: 143` (SIGTERM)?
> 3. **The `--previous` flag is essential:** When a container crashes, normal `kubectl logs` will often be empty because the new restarted container has not begun executing or is blocked by backoff delay. Adding `--previous` requests the log buffer of the container instance that *just crashed*.
> 4. **Export the live manifest:** You can view the live configuration by running `kubectl -n production-debug-lab get deployment crashloop-demo -o yaml` to see what command or environment variables were defined.

---

#### 3. Investigation & Evidence Collection
First, inspect the pod's termination state and events:
```bash
kubectl -n production-debug-lab describe pod -l app=crashloop-demo
```
Key fields to inspect:
- **`State`**: `Waiting` -> `Reason: CrashLoopBackOff`
- **`Last State`**: `Terminated` -> `Exit Code: 1`, `Reason: Error`

Next, inspect the logs of the terminated container using `--previous`:
```bash
kubectl -n production-debug-lab logs -l app=crashloop-demo --previous
```
**Observed Error:**
```text
missing CONFIG_URL
```

To inspect or modify the live manifest locally, export the deployment to a YAML file:
```bash
kubectl -n production-debug-lab get deployment crashloop-demo -o yaml > crashloop-demo.yaml
```
*(Or use `kubectl -n production-debug-lab edit deployment crashloop-demo` to edit it live in your editor.)*

---

#### 🎯 Official Solution & Answer Key
<details>
<summary><b>Click to expand Answer Key & Root Cause Explanation</b></summary>

**Root Cause:**
The container application simulates a microservice requiring an external configuration endpoint. Because `CONFIG_URL` was not supplied in the container environment or ConfigMap, the process failed fast, outputting `missing CONFIG_URL` and exiting with return code `1`. The kubelet's `restartPolicy: Always` continuously retries, producing `CrashLoopBackOff`.

**Verification Target:**
To confirm you have solved the exercise, you have proven that:
1. `Last State` is `Exit Code: 1`.
2. Dying logs confirm `missing CONFIG_URL`.
3. The manifest in `scenarios/01-crashloop.yaml` had no `env:` block defining `CONFIG_URL`.

</details>

---

#### 4. Remediation & Verification (Optional)
If you wish to patch the deployment to see it transition to a healthy `Running (1/1)` state:
```bash
kubectl -n production-debug-lab patch deployment crashloop-demo --type='strategic' -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "app",
            "env": [
              {"name": "CONFIG_URL", "value": "https://config.internal.lab"}
            ],
            "command": [
              "/bin/sh",
              "-c",
              "echo \"Config loaded from $CONFIG_URL\"; trap : TERM INT; sleep infinity & wait"
            ]
          }
        ]
      }
    }
  }
}'
```
Verify the pod transitions to `Running` (`1/1`):
```bash
kubectl -n production-debug-lab get pods -l app=crashloop-demo
```

#### 5. Prevention & Follow-up Controls
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

## Answer Keys: Exercises 2–8

### Exercise 2 — ImagePullBackOff

**Diagnosis:** Use pod events to distinguish `manifest unknown`/`not found` (bad image reference), `401`/`403` (registry authentication or authorization), and timeout/DNS errors (connectivity). Capture the image reference, latest `Failed` event, service-account pull secrets, and registry reachability without including credentials.

**Remediation:** Correct the immutable image digest or attach the approved pull secret. Roll out the change and verify the pod becomes Ready. Prevent recurrence with CI image validation, signed digests, admission verification, and alerts on `ErrImagePull`.

### Exercise 3 — Pending Pod

**Diagnosis:** `kubectl describe pod` events identify the scheduler predicate: insufficient resources, unmatched selectors/affinity, untolerated taints, or no eligible nodes. Compare requests with node allocatable capacity, not current utilization alone.

**Remediation:** Correct the placement rule, right-size the request, or add capacity. Do not remove taints or lower requests without confirming the isolation and capacity requirements. Prevent recurrence with admission checks, quotas, limit ranges, and capacity dashboards.

### Exercise 4 — Readiness Probe Failure

**Diagnosis:** `Running` describes process lifecycle; `Ready 0/1` means the readiness probe fails. Kubernetes removes the pod from Service endpoint slices while leaving the process running. Capture the probe configuration, events, logs, and the exact probe request from inside the pod.

**Remediation:** Fix the application/probe contract, including path, port, bind address, and timing. Use a startup probe for slow initialization; do not weaken readiness merely to make the pod appear healthy. Test probes in CI and alert separately on process health and endpoint availability.

### Exercise 5 — DNS Failure

**Diagnosis:** Compare `/etc/resolv.conf`, `getent hosts`, and `dig`. An unreachable resolver points to pod networking or CoreDNS; CoreDNS answers with failed upstream lookups point to upstream configuration or node egress; a single failed name points to records, search domains, or split-horizon policy.

**Remediation:** Restore CoreDNS, correct records/upstreams, or repair the policy/route blocking DNS. Capture the query, resolver configuration, CoreDNS health/logs, result, latency, and comparison from another namespace. Monitor CoreDNS errors and test representative namespaces.

### Exercise 6 — NetworkPolicy Isolation

**Diagnosis:** Establish source and destination identity, namespace, direction, port, and protocol. A policy selecting a pod denies traffic not explicitly allowed in that direction. Capture policies, labels, endpoints, route/DNS results, and a timestamped probe; use Hubble flow evidence when available.

**Remediation:** Add the narrowest allow rule and verify both positive and negative cases. Do not resolve an application-specific outage by allowing all ingress or egress. Prevent recurrence with policy-as-code tests, review, and denied-flow monitoring.

### Exercise 7 — OOMKilled versus Node Eviction

**Diagnosis:** `OOMKilled` and exit code `137` usually indicate the container exceeded its cgroup limit. Node-pressure eviction is a kubelet decision shown in pod events and often affects multiple pods. Exit code alone is not proof. Capture container state, limits/requests, memory metrics, pod events, node conditions, and other node evictions.

**Remediation:** Fix leaks or workload behavior and right-size limits for container OOM; recover node capacity and review requests, QoS, and eviction thresholds for node pressure. Alert on container OOM and node pressure separately.

### Exercise 8 — RBAC Permission Denied

**Diagnosis:** Confirm the exact identity, verb, resource, API group, and namespace. `kubectl auth can-i` distinguishes a missing permission from an incorrect resource or namespace. Capture the failed operation, sanitized authorization result, binding, and service account.

**Remediation:** Add only the missing permission at the narrowest scope, bind it to the intended identity, and re-run the exact check. If cluster-wide visibility is needed, document the incident class and approval rather than silently broadening access. Prevent recurrence with RBAC CI tests, namespace-scoped defaults, and permission reviews.
