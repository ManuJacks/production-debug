# Kubernetes Troubleshooting Cheatsheet
## Exercise 03 — Pending Pods, Scheduling, Labels, Taints & Tolerations

**Scenario:** A Deployment has one desired replica, but its Pod remains `Pending`.

**Objective:** Identify why the scheduler cannot place the Pod, correct the Deployment's Pod template, and verify recovery.

---

## 1. Connect to the correct cluster

Avoid accidentally running commands against your default Kubernetes context.

Set the kubeconfig for the session:

```bash
export KUBECONFIG="$HOME/.kube/kubernetes-in-finance.conf"
```

Verify the active context and nodes:

```bash
kubectl config current-context
kubectl get nodes -o wide
```

Alternatively, explicitly specify the kubeconfig:

```bash
kubectl --kubeconfig="$HOME/.kube/kubernetes-in-finance.conf" get nodes
```

**Operational lesson:** Always establish which cluster you are troubleshooting before making changes.

---

## 2. Initial workload investigation

List workloads in the affected namespace:

```bash
kubectl get all -n production-debug-lab -o wide
```

List Pods:

```bash
kubectl get pods -n production-debug-lab -o wide
```

Describe the affected Pod:

```bash
kubectl describe pod <pod-name> -n production-debug-lab
```

Inspect recent namespace events:

```bash
kubectl get events -n production-debug-lab \
  --sort-by=.lastTimestamp
```

### What to look for

| Status / event | Meaning |
|---|---|
| Pending | Pod has not been scheduled or cannot proceed to running |
| FailedScheduling | Scheduler cannot find an eligible node |
| ImagePullBackOff | Image cannot be pulled |
| CrashLoopBackOff | Container repeatedly exits and restarts |
| OOMKilled | Container was terminated due to memory pressure |
| Insufficient cpu | No eligible node has enough allocatable CPU |
| Insufficient memory | No eligible node has enough allocatable memory |

**Important:** `Pending` is a phase, not a root cause. Inspect Events and Pod configuration.

---

## 3. Understand the Deployment and Pod relationship

A Deployment contains a Pod template.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example
spec:
  replicas: 1
  selector:
    matchLabels:
      app: example
  template:                  # Pod template
    metadata:
      labels:                # Labels applied to Pods
        app: example
    spec:                    # Actual Pod specification
      containers:
        - name: app
          image: busybox:1.36
```

The hierarchy is:

```text
Deployment
  └── ReplicaSet
        └── Pod
              └── Container(s)
```

Useful commands:

```bash
kubectl get deployments -n <namespace>
kubectl get replicasets -n <namespace>
kubectl get pods -n <namespace>
```

Inspect the Deployment:

```bash
kubectl get deployment <name> -n <namespace> -o yaml
```

Inspect the Pod's scheduling configuration:

```bash
kubectl get pod <pod-name> -n <namespace> \
  -o jsonpath='{.spec.nodeSelector}{"\n"}{.spec.affinity}{"\n"}{.spec.tolerations}{"\n"}'
```

**Key distinction:** Correct the Deployment's `spec.template.spec`, not the disposable Pod.

---

## 4. Labels: Pod labels versus Node labels

These are two different things.

### Pod labels

```yaml
template:
  metadata:
    labels:
      app: pending-demo
```

Used to identify and select workloads.

### Node labels

```yaml
spec:
  nodeSelector:
    kubernetes.io/os: linux
```

Used to restrict which nodes can receive a Pod.

Inspect node labels:

```bash
kubectl get nodes --show-labels
```

Inspect a specific label:

```bash
kubectl get nodes \
  -L kubernetes.io/os,node-role.kubernetes.io/control-plane
```

Inspect one node:

```bash
kubectl get node <node-name> --show-labels
```

### NodeSelector

A simple exact-match requirement:

```yaml
spec:
  nodeSelector:
    kubernetes.io/os: linux
```

The node must have the specified label and value.

If no node matches, the Pod cannot be scheduled.

---

## 5. Taints and tolerations

This was an important part of Exercise 03.

### Taints belong to Nodes

Our control-plane nodes had:

```text
node-role.kubernetes.io/control-plane:NoSchedule
```

Inspect node taints:

```bash
kubectl describe node <node-name>
```

Or inspect all nodes:

```bash
kubectl get nodes \
  -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints'
```

### Tolerations belong to Pods

A Pod can tolerate the control-plane taint:

```yaml
spec:
  template:
    spec:
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
```

Remember:

- A taint repels Pods that don't tolerate it.
- A matching toleration permits scheduling despite that taint.
- A toleration does not guarantee placement.
- Node selectors, affinity and resource requirements still apply.

### Three important taint effects

| Effect | Behaviour |
|---|---|
| NoSchedule | New Pods without matching tolerations cannot be scheduled |
| PreferNoSchedule | Scheduler tries to avoid placing Pods there |
| NoExecute | Pods without matching tolerations cannot remain; existing Pods may be evicted |

### Inspect and modify taints

Add a taint:

```bash
kubectl taint nodes <node-name> dedicated=database:NoSchedule
```

Remove a taint:

```bash
kubectl taint nodes <node-name> dedicated:NoSchedule-
```

**Production caution:** Don't remove control-plane taints simply to make a workload schedule. Understand the intended placement policy first.

---

## 6. Node affinity

Node affinity provides more expressive placement rules than `nodeSelector`.

Example: schedule only on nodes that do NOT have the control-plane label.

```yaml
spec:
  template:
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: node-role.kubernetes.io/control-plane
                    operator: DoesNotExist
```

Useful operators:

| Operator | Meaning |
|---|---|
| In | Label value must match one of the listed values |
| NotIn | Label value must not match listed values |
| Exists | Label key must exist |
| DoesNotExist | Label key must not exist |
| Gt | Numeric label value must be greater than |
| Lt | Numeric label value must be less than |

Two scheduling modes:

- `requiredDuringSchedulingIgnoredDuringExecution`: hard requirement.
- `preferredDuringSchedulingIgnoredDuringExecution`: scheduling preference.

**Remember:** `IgnoredDuringExecution` means a change to labels after scheduling does not automatically evict the running Pod.

---

## 7. CPU and memory requests

Another defect in our exercise was:

```yaml
resources:
  requests:
    cpu: "1000"
```

This means **1,000 CPU cores**, not 1,000 millicores.

Common CPU quantities:

| Quantity | CPU cores |
|---|---:|
| `1000` | 1,000 |
| `1` | 1 |
| `1000m` | 1 |
| `500m` | 0.5 |
| `100m` | 0.1 |
| `50m` | 0.05 |

Example of a modest request:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 32Mi
```

Inspect node capacity and allocatable resources:

```bash
kubectl describe nodes
```

Inspect Pod requests and limits:

```bash
kubectl get pod <pod-name> -n <namespace> -o yaml
```

Inspect resource consumption, if Metrics Server is available:

```bash
kubectl top nodes
kubectl top pods -A
```

**Important distinction:**

- Requests influence scheduling.
- Limits constrain runtime resource consumption.
- A Pod can be Pending because its requests cannot fit on any eligible node.

---

## 8. The Exercise 03 diagnosis

Our original Deployment had three independent placement problems:

**Problem 1 — Impossible node selector**

```yaml
nodeSelector:
  synthetic-lab-node: does-not-exist
```

None of the five nodes had that label.

**Problem 2 — Control-plane taints**

Three control-plane nodes had `NoSchedule` taints. The Pod had no matching toleration.

The two worker nodes were untainted.

**Problem 3 — Excessive CPU request**

```yaml
requests:
  cpu: "1000"
```

This requested 1,000 CPU cores.

The scheduler's reported event summarized node filtering:

```text
0/5 nodes are available:
2 node(s) didn't match Pod's node affinity/selector,
3 node(s) had untolerated taint(s).
```

Don't assume that this event lists every defect in the configuration. Inspect the complete Pod specification and resource requirements.

---

## 9. Corrected Deployment

Our corrected `03-fixed.yaml` used:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pending-demo
  namespace: production-debug-lab
spec:
  replicas: 1
  selector:
    matchLabels:
      app: pending-demo
  template:
    metadata:
      labels:
        app: pending-demo
    spec:
      nodeSelector:
        kubernetes.io/os: linux
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: node-role.kubernetes.io/control-plane
                    operator: DoesNotExist
      containers:
        - name: app
          image: busybox:1.36
          command: ["sh", "-c", "sleep 3600"]
          resources:
            requests:
              cpu: 100m
              memory: 32Mi
```

This:
- Selects Linux nodes.
- Excludes control-plane nodes.
- Leaves control-plane taints intact.
- Uses realistic resource requests.
- Runs a long-lived test container.

Apply:

```bash
kubectl apply -f 03-fixed.yaml
```

Check Deployment health:

```bash
kubectl get deployment pending-demo -n production-debug-lab
```

Check rollout:

```bash
kubectl rollout status deployment/pending-demo \
  -n production-debug-lab
```

Check the new Pod and its assigned node:

```bash
kubectl get pods -n production-debug-lab -o wide
```

Check the Deployment revision:

```bash
kubectl rollout history deployment/pending-demo \
  -n production-debug-lab
```

Expected result:

```text
READY   STATUS    RESTARTS   NODE
1/1     Running   0          tf-ha-worker2
```

Our actual result was `tf-ha-worker2`, with Pod IP `10.244.4.92`.

---

## 10. Deployment troubleshooting and recovery commands

Inspect rollout status:

```bash
kubectl rollout status deployment/<name> -n <namespace>
```

Inspect rollout history:

```bash
kubectl rollout history deployment/<name> -n <namespace>
```

Undo the last rollout:

```bash
kubectl rollout undo deployment/<name> -n <namespace>
```

Scale a Deployment:

```bash
kubectl scale deployment/<name> --replicas=2 -n <namespace>
```

Restart a Deployment:

```bash
kubectl rollout restart deployment/<name> -n <namespace>
```

Watch Pods:

```bash
kubectl get pods -n <namespace> -w
```

Inspect a ReplicaSet:

```bash
kubectl describe rs <replicaset-name> -n <namespace>
```

Inspect the full Deployment:

```bash
kubectl describe deployment <name> -n <namespace>
```

---

## 11. Interview troubleshooting sequence

When asked to troubleshoot a Pending Pod, work methodically:

1. Establish the correct cluster context.
2. Identify the affected namespace and Pod.
3. Run `kubectl describe pod`.
4. Read scheduler Events.
5. Inspect `nodeSelector`, affinity and tolerations.
6. Inspect node labels and taints.
7. Inspect CPU and memory requests against node allocatable capacity.
8. Inspect the owning Deployment and ReplicaSet.
9. Correct the Deployment's Pod template.
10. Apply the correction and verify scheduling, readiness and node assignment.

Don't change several things blindly. Gather evidence, identify independent constraints, and verify each correction.

---

## 12. GM interview answer

**Question:** How would you troubleshoot a Pod that remains Pending?

**Answer:**

"I would start with `kubectl describe pod` and examine the scheduler Events to understand why nodes are being rejected. I'd then inspect the Pod's scheduling requirements, including node selectors, required affinity, tolerations and resource requests, and compare those against actual node labels, taints and allocatable resources.

I'd identify whether the issue is a placement constraint, a resource-capacity issue, or another scheduling dependency. If the Pod is managed by a Deployment, I'd correct the Pod template rather than manually modifying the generated Pod.

Finally, I'd verify the rollout, confirm that the replacement Pod is assigned to an appropriate node, and check that it reaches Ready."

**The principle:** Diagnose first. Correct the source of desired state. Verify recovery.

---

## Quick command reference

| Task | Command |
|---|---|
| Current context | `kubectl config current-context` |
| List nodes | `kubectl get nodes -o wide` |
| List Pods | `kubectl get pods -A -o wide` |
| Describe Pod | `kubectl describe pod <pod>` |
| Namespace events | `kubectl get events -n <ns> --sort-by=.lastTimestamp` |
| Inspect Pod YAML | `kubectl get pod <pod> -n <ns> -o yaml` |
| Inspect Deployment | `kubectl get deployment <name> -n <ns> -o yaml` |
| Show node labels | `kubectl get nodes --show-labels` |
| Show node taints | `kubectl get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints'` |
| Node resources | `kubectl describe nodes` |
| Resource usage | `kubectl top nodes` |
| Rollout status | `kubectl rollout status deployment/<name> -n <ns>` |
| Watch Pods | `kubectl get pods -n <ns> -w` |

**Exercise 03 complete:** impossible node selector, untolerated control-plane taints, excessive CPU request, Deployment template correction, successful scheduling onto a worker.
