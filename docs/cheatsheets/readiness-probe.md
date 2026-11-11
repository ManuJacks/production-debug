# Kubernetes Troubleshooting Cheatsheet — Exercise 04
## Readiness Probes, Pod Health & Service Endpoints

### 1. Scenario

**Objective:** Diagnose and repair a Pod that is running but not ready to receive Service traffic.

Scenario manifest: `scenarios/04-readiness.yaml`

Resources:
- Deployment: `readiness-demo`
- Service: `readiness-demo`
- Container image: `nginx:1.27`
- Namespace: `production-debug-lab`

Original readiness probe:

```yaml
readinessProbe:
  httpGet:
    path: /missing
    port: 80
  periodSeconds: 2
```

The probe requests a nonexistent Nginx endpoint, resulting in HTTP 404.

### 2. Understand the three probe types

| Probe | Purpose | What happens on failure? |
|---|---|---|
| Readiness | Determines whether the container can receive traffic | Pod is marked NotReady; excluded from normal Service traffic |
| Liveness | Determines whether the container is still healthy | Kubelet restarts the container |
| Startup | Determines whether the application has finished starting | Kubelet delays liveness and readiness checks until startup succeeds |

**Remember: Running does not mean Ready.**

A container can be running normally while its readiness probe fails continuously.

### 3. Initial deployment and inspection

Use the intended HA cluster kubeconfig:

```bash
export KUBECONFIG="$HOME/.kube/kubernetes-in-finance.conf"
```

Deploy through the repository's scenario runner:

```bash
K8S_LAB_CONTEXT="kubernetes-admin@kubernetes" \
./scenarios/run.sh setup 04-readiness
```

Confirm the context when prompted.

Check the workload:

```bash
kubectl get deployments,pods -n production-debug-lab -o wide
```

Expected initial symptoms:

```text
deployment.apps/readiness-demo   0/1
pod/readiness-demo-xxxxx         0/1   Running   0
```

Interpretation:
- Container started successfully.
- No container restarts.
- Readiness probe is failing.
- Deployment has no available replicas.

### 4. Diagnose the readiness failure

Describe the Pod:

```bash
kubectl describe pod -n production-debug-lab \
  -l app=readiness-demo
```

Inspect the Events section.

Initial event observed:

```text
Readiness probe failed:
Get "http://10.244.4.57:80/missing":
dial tcp 10.244.4.57:80:
connect: connection refused
```

Later event:

```text
Readiness probe failed:
HTTP probe failed with statuscode: 404
```

**Important diagnostic distinction:**

- `Connection refused`: Application was not listening on the requested port at that moment.
- `HTTP 404`: Application responded, but the requested path was not found.
- `HTTP 200`: Successful response for this probe.

The initial connection refusal was transient during startup. The persistent fault was the HTTP 404.

### 5. Inspect Service and EndpointSlice

Use the repository status command:

```bash
K8S_LAB_CONTEXT="kubernetes-admin@kubernetes" \
./scenarios/run.sh status
```

Equivalent command:

```bash
kubectl -n production-debug-lab get pods,svc,endpointslices
```

Inspect the EndpointSlice:

```bash
kubectl get endpointslice -n production-debug-lab \
  -l kubernetes.io/service-name=readiness-demo -o yaml
```

Initial endpoint condition:

```yaml
addresses:
  - 10.244.4.57
conditions:
  ready: false
  serving: false
  terminating: false
```

The endpoint IP can still appear in the EndpointSlice even when it is not ready.

Check readiness directly:

```bash
kubectl get endpointslice -n production-debug-lab \
  -l kubernetes.io/service-name=readiness-demo \
  -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]}{" ready="}{.conditions.ready}{"\n"}{end}'
```

### 6. Inspect the live Deployment

```bash
kubectl get deployment readiness-demo \
  -n production-debug-lab -o yaml
```

Locate:

```yaml
spec:
  template:
    spec:
      containers:
      - name: app
        readinessProbe:
          httpGet:
            path: /missing
            port: 80
```

The Deployment's Pod template is the source of the configuration used to create its Pods.

Also inspect Deployment conditions:

```yaml
reason: ProgressDeadlineExceeded
message: ReplicaSet has timed out progressing.
```

This is a consequence of the Deployment failing to make its replica available, not the original application fault.

### 7. Correct the probe

The intended endpoint is Nginx's default `/` page.

Change:

```yaml
path: /missing
```

To:

```yaml
path: /
```

A targeted patch:

```bash
kubectl patch deployment readiness-demo \
  -n production-debug-lab \
  --type=strategic \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"app","readinessProbe":{"httpGet":{"path":"/"}}}]}}}}'
```

This preserves the existing port, timing, thresholds and other probe settings.

Verify the live path:

```bash
kubectl get deployment readiness-demo \
  -n production-debug-lab \
  -o jsonpath='{.spec.template.spec.containers[?(@.name=="app")].readinessProbe.httpGet.path}{"\n"}'
```

Expected:

```text
/
```

### 8. Verify recovery

Check rollout:

```bash
kubectl rollout status deployment/readiness-demo \
  -n production-debug-lab
```

Check Deployment and Pod:

```bash
kubectl get deployments,pods \
  -n production-debug-lab -o wide
```

Expected:

```text
deployment.apps/readiness-demo   1/1   1   1

pod/readiness-demo-xxxxx         1/1   Running   0
```

Check EndpointSlice readiness:

```bash
kubectl get endpointslice -n production-debug-lab \
  -l kubernetes.io/service-name=readiness-demo \
  -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]}{" ready="}{.conditions.ready}{"\n"}{end}'
```

Verified result:

```text
10.244.4.96 ready=true
```

### 9. Root cause analysis

**Root cause:** The Deployment configured an HTTP readiness probe against `/missing`, which returned HTTP 404.

**Impact:** The container remained Running, but the Pod remained NotReady. The EndpointSlice marked the endpoint `ready: false`, making it ineligible for normal Service traffic.

**Resolution:** Changed the readiness probe path to `/`, which returned a successful HTTP response.

**Recovery verification:**
- Deployment: 1/1 available.
- Pod: 1/1 Ready.
- Container restarts: 0.
- EndpointSlice: `ready: true`.

### 10. Interview troubleshooting sequence

When a Pod is Running but NotReady:

1. Check Deployment and Pod readiness.
2. Describe the Pod.
3. Inspect readiness probe configuration.
4. Review Events for connection errors, timeouts or HTTP status failures.
5. Verify the application is listening on the expected port.
6. Test the configured HTTP path from the Pod or an appropriate diagnostic container.
7. Inspect the Service selector.
8. Inspect EndpointSlice endpoint conditions.
9. Correct the underlying health check or application fault.
10. Verify rollout, Pod readiness and EndpointSlice readiness.

Avoid restarting containers or deleting Pods before understanding the failure.

### 11. Interview-ready explanation

"I encountered a Deployment where the container was Running, but the Deployment remained unavailable. I inspected the Pod events and found that its HTTP readiness probe was targeting a nonexistent Nginx path. Initially, there was a transient connection refusal while Nginx started; subsequently, the probe consistently returned HTTP 404.

I traced the impact through the Service's EndpointSlice and confirmed that the endpoint was present but marked `ready: false`. I corrected the probe path to `/`, verified the Deployment rollout, and confirmed the replacement Pod was Ready and the EndpointSlice reported `ready: true`.

The key distinction is that container process health, Pod readiness and Service endpoint eligibility are separate states."

---

**Key takeaway:** Readiness is a traffic-admission mechanism, not a container restart mechanism. Diagnose the complete path from application health check to Pod readiness to Service endpoint eligibility.
