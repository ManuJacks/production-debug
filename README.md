# production-debug

[![CI](https://github.com/ManuJacks/production-debug/actions/workflows/ci.yml/badge.svg)](https://github.com/ManuJacks/production-debug/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-incident%20diagnostics-326CE5?logo=kubernetes&logoColor=white)](k8s/)

**A portable, security-conscious incident diagnostics toolkit for Kubernetes, Azure and Linux infrastructure.**

`production-debug` provides a repeatable environment for investigating infrastructure incidents, collecting diagnostic evidence and supporting structured incident response. It combines Kubernetes-aware tooling, network and DNS diagnostics, Azure connectivity checks, interactive terminal workflows and synthetic failure exercises.

The project demonstrates an engineering approach to operational tooling: explicit permissions, hardened runtime configuration, reproducible workflows, documented limitations and testable troubleshooting procedures.

**Project documentation:** [Implementation Guide](docs/IMPLEMENTATION_GUIDE.md) · [Operating Model](docs/OPERATING_MODEL.md) · [CLI Reference](docs/REFERENCE_CLI.md) · [Troubleshooting Exercises](docs/EXERCISES.md)

---

## Why this project exists

During a high-severity production incident, responders need to establish what is failing, where the fault lies and what evidence supports the diagnosis.

That becomes difficult when:

- Diagnostic tools and commands differ between responders.
- Network restrictions, DNS, routing and cloud identity introduce additional fault domains.
- Engineers request excessive Kubernetes permissions simply to inspect workloads.
- Interactive troubleshooting produces fragmented logs and incomplete handoffs.
- Temporary diagnostic environments disappear before useful evidence is collected.
- Incident timelines and operational metrics must be reconstructed manually.

`production-debug` addresses these challenges by providing a consistent diagnostic environment and repeatable operating procedures.

The objective is not to automate incident command or replace engineering judgement. It is to reduce diagnostic friction, improve shared visibility and make investigations more structured and reproducible.

## Engineering principles

- **Read-only by default:** Kubernetes diagnostic permissions are explicitly defined and do not grant workload mutation privileges.
- **Hardened execution:** The Kubernetes debug pod uses non-root execution, a read-only root filesystem, dropped Linux capabilities and runtime-default seccomp.
- **Observable operations:** Interactive triage sessions capture terminal output for subsequent review.
- **Evidence-oriented response:** Selected diagnostic artifacts can be packaged with timestamped metadata and KPI reports.
- **Portable tooling:** The toolkit supports container-based execution, Kubernetes deployment and Linux VM workflows.
- **Blameless learning:** Exercises and incident procedures focus on fault domains, contributing conditions, recovery verification and systemic improvements.

---

## Architecture and components

The repository separates the runtime environment, deployment configuration, diagnostic scripts, synthetic scenarios and local practice environments.

```text
production-debug/
├── docker/                 # Container image and non-root runtime setup
├── k8s/                    # Kubernetes deployment manifests
├── gitops/                 # Kustomize and GitOps deployment configuration
├── vm/                     # Containerized and standalone VM launchers
├── scripts/                # Diagnostic and incident-response tooling
│   ├── incident_bundle.sh
│   ├── incident_preflight.sh
│   ├── launch-tmux-triage.sh
│   ├── remote_dns_tls_check.sh
│   ├── nsg-egress-validate.sh
│   └── kpi_report.sh
├── mcp/                    # MCP server component
├── profiles/               # Repeatable triage profiles
├── scenarios/              # Synthetic Kubernetes failure manifests
├── tests/                  # Automated tests
├── docs/                   # Architecture, security and operating guides
└── dev-lab/                # Minikube and Multipass practice environments
```

### Diagnostic runtime

The container packages a collection of infrastructure troubleshooting tools, including:

| Tool | Operational purpose |
|---|---|
| kubectl | Kubernetes API inspection |
| K9s | Interactive Kubernetes resource navigation |
| Stern | Multi-pod and multi-container log streaming |
| kubectx / kubens | Context and namespace navigation |
| kubectl-neat | Cleaner Kubernetes resource output |
| kubectl-tree | Resource ownership visualization |
| tmux | Persistent multi-pane diagnostic workspace |
| tcpdump / iproute2 / conntrack | Network and connection inspection |
| dig / nslookup / curl | DNS, HTTP and connectivity investigation |
| Azure CLI | Azure resource and network diagnostics |

The image is built from Debian Bookworm Slim. Kubernetes tooling versions are explicitly declared in the Dockerfile, and the Helm archive is SHA-256 verified during installation.

### Interactive triage workspace

The tmux workflow brings multiple diagnostic views into one terminal session.

Typical activities include:

- Inspecting pod status, restart counts and recent events.
- Streaming application logs.
- Checking DNS resolution and network connectivity.
- Reviewing Azure Workload Identity configuration or metadata endpoint reachability.
- Capturing terminal output for incident review.

The workspace is intended to support collaborative investigation and structured handoffs.

### Kubernetes deployment

The Kubernetes deployment uses a dedicated ServiceAccount and explicitly defined RBAC permissions.

The current ClusterRole grants cluster-wide `get`, `list` and `watch` access to selected diagnostic resources, including pods, logs, events, nodes, services, endpoints, ConfigMaps, workloads and network resources.

This is read-only access, but it is still cluster-wide. Organizations should review the resource scope against their own isolation and access requirements before deployment.

### GitOps and portability

Kustomize manifests provide a declarative deployment path that can be reconciled through Flux v2.

The project also provides VM launchers for container-based and standalone Linux troubleshooting environments.

These deployment paths share the diagnostic tooling while retaining their respective runtime and access-control requirements.

---

## Security architecture

Security is part of the runtime design rather than an afterthought.

### Kubernetes runtime controls

The debug pod manifest configures:

| Control | Configuration |
|---|---|
| User identity | Non-root UID/GID 10001 |
| Privilege escalation | Disabled |
| Linux capabilities | All dropped |
| Seccomp | RuntimeDefault |
| Root filesystem | Read-only |
| Temporary storage | Dedicated `emptyDir` volumes |
| Resource management | CPU and memory requests and limits |
| ServiceAccount | Dedicated diagnostic identity |

The Kubernetes ServiceAccount token is mounted because the toolkit needs to communicate with the Kubernetes API. Its associated permissions should therefore be treated as security-sensitive.

### Credential and evidence handling

The incident bundle script packages selected diagnostic artifacts, metadata and KPI reports.

**Important limitation:** Automated secret redaction is not currently implemented. Diagnostic output may contain sensitive information, including tokens, internal addresses, connection details or customer data.

Review and sanitize artifacts before sharing them outside the authorized incident-response group.

Session logs capture terminal output but are not tamper-proof or guaranteed append-only. Protect them using appropriate filesystem permissions, retention policies and external evidence-storage controls.

### Security boundaries

The toolkit does not independently guarantee:

- Correct authorization in every target environment.
- Azure identity authentication merely because identity configuration is detected.
- Network connectivity through restrictive firewalls or NetworkPolicies.
- Automatic sanitization of incident evidence.
- Tamper-proof or immutable evidence storage.

These remain responsibilities of the deploying organization and incident responders.

---

## Troubleshooting examples

The following workflows illustrate how the toolkit supports evidence-driven investigation. They use standard Kubernetes commands and the repository's synthetic scenarios.

The examples are laboratory demonstrations, not claims of completed production incidents.

### 1. CrashLoopBackOff — application startup failure

A synthetic startup command reports a missing CONFIG_URL and exits with status 1, simulating an application startup failure.

Inspect the workload:

```bash
kubectl get pods -n production-debug-lab
kubectl describe pod -n production-debug-lab -l app=crashloop-demo
```

Inspect the previous container execution:

```bash
kubectl logs -n production-debug-lab \
  -l app=crashloop-demo --previous
```

**Evidence to look for:**

- Container restart count.
- Exit code and termination reason.
- Previous container logs.
- Pod events and restart timing.

**Engineering lesson:** Distinguish an application startup failure from an infrastructure or scheduling failure before changing the workload.

### 2. ImagePullBackOff — image retrieval failure

**Scenario:** The workload references a synthetic image that does not exist.

Inspect pod events:

```bash
kubectl describe pod -n production-debug-lab \
  -l app=imagepull-demo
```

Inspect the configured image:

```bash
kubectl get deployment imagepull-demo \
  -n production-debug-lab \
  -o jsonpath='{.spec.template.spec.containers[*].image}'
```

**Evidence to look for:**

- Requested image and tag.
- Registry hostname.
- Pull failure messages.
- Whether the failure indicates a missing manifest, registry access issue or authentication problem.

**Engineering lesson:** Separate image-reference errors from registry connectivity and authentication failures.

The current synthetic manifest demonstrates a nonexistent image reference. Invalid registry credentials are a useful additional exercise, but are not currently configured by this manifest.

### 3. Pending pod — scheduling constraints

**Scenario:** A pod cannot be scheduled because its node selector does not match available nodes and its CPU request is deliberately high.

Inspect scheduling events:

```bash
kubectl describe pod -n production-debug-lab \
  -l app=pending-demo
```

Inspect available nodes and allocatable resources:

```bash
kubectl get nodes
kubectl describe nodes
```

**Evidence to look for:**

- Node selector requirements.
- Scheduler failure events.
- Available node capacity.
- Resource requests versus allocatable resources.

**Engineering lesson:** A Pending pod is not necessarily an application problem. Investigate scheduling predicates and cluster capacity.

### 4. Readiness failure — traffic eligibility

**Scenario:** NGINX is running, but the readiness probe checks an invalid HTTP path.

Inspect pod conditions:

```bash
kubectl describe pod -n production-debug-lab \
  -l app=readiness-demo
```

Inspect Service and EndpointSlices:

```bash
kubectl get service,endpoints -n production-debug-lab
kubectl get endpointslices -n production-debug-lab
```

**Evidence to look for:**

- Container running state.
- Readiness probe failures.
- Pod readiness condition.
- Service endpoint membership.

**Engineering lesson:** Running does not mean ready. Readiness determines whether a workload is eligible to receive Service traffic.

### 5. DNS failure — name resolution

**Scenario:** A diagnostic pod attempts to resolve a deliberately nonexistent Service name.

Inspect the pod:

```bash
kubectl describe pod -n production-debug-lab dns-demo
```

Inspect its logs:

```bash
kubectl logs -n production-debug-lab dns-demo
```

Compare with a known Kubernetes Service:

```bash
kubectl exec -n production-debug-lab dns-demo -- \
  nslookup kubernetes.default.svc.cluster.local
```

**Evidence to look for:**

- DNS lookup response.
- Resolver configuration.
- Whether known Service names resolve.
- CoreDNS pod health and relevant events.

**Engineering lesson:** Separate an invalid application hostname from resolver, cluster DNS and upstream DNS failures.

### 6. NetworkPolicy denial — traffic restrictions

**Scenario:** A default-deny ingress and egress policy is applied to the synthetic namespace.

Inspect the policy:

```bash
kubectl get networkpolicy -n production-debug-lab
kubectl describe networkpolicy deny-all-demo \
  -n production-debug-lab
```

Inspect the affected workload:

```bash
kubectl get pods -n production-debug-lab -o wide
kubectl describe pod -n production-debug-lab \
  -l app=networkpolicy-demo
```

**Evidence to look for:**

- Policy selectors.
- Ingress and egress policy types.
- Affected pod labels.
- Connectivity differences when the policy is present.

**Engineering lesson:** NetworkPolicy troubleshooting requires understanding selectors, policy direction and the behavior of the cluster's network implementation. Enforcement depends on CNI support; a policy may exist in the Kubernetes API without actually blocking traffic if the network plugin does not enforce NetworkPolicy rules.

### 7. OOMKilled — memory pressure

**Scenario:** A synthetic workload attempts to allocate more memory than its container limit permits.

Inspect the pod:

```bash
kubectl describe pod -n production-debug-lab \
  -l app=oom-demo
```

Inspect container state and restart history:

```bash
kubectl get pods -n production-debug-lab
kubectl logs -n production-debug-lab \
  -l app=oom-demo --previous
```

**Evidence to look for:**

- Container termination reason.
- Memory limit and request.
- Restart count.
- Pod and node events.

**Engineering lesson:** Distinguish container-level OOM termination from node-pressure eviction and investigate resource sizing and QoS implications.

### 8. RBAC Forbidden — authorization boundaries

**Scenario:** A dedicated ServiceAccount can read pods but does not have permission to read pod logs or deployments.

**Prerequisite:** The user running these checks must have permission to impersonate the specified ServiceAccount.

Check authorization:

```bash
kubectl auth can-i get pods \
  --as=system:serviceaccount:production-debug-lab:restricted-demo \
  -n production-debug-lab

kubectl auth can-i get pods/log \
  --as=system:serviceaccount:production-debug-lab:restricted-demo \
  -n production-debug-lab

kubectl auth can-i get deployments.apps \
  --as=system:serviceaccount:production-debug-lab:restricted-demo \
  -n production-debug-lab
```

**Expected result:** Pod reads are allowed; pod log and deployment reads are denied by the synthetic Role.

**Engineering lesson:** Use authorization checks to identify the missing permission and grant only the access required by the diagnostic task.

---

## Synthetic Kubernetes failure lab

The repository contains eight synthetic manifests for practicing controlled incident diagnosis.

| Scenario | Primary fault domain | Investigation focus |
|---|---|---|
| `01-crashloop` | Application startup | Exit state, logs, events |
| `02-imagepull` | Image distribution | Image reference, registry errors |
| `03-pending` | Scheduling | Node selectors, resource requests |
| `04-readiness` | Workload health | Probe behavior, endpoints |
| `05-dns` | Name resolution | Service DNS, resolver behavior |
| `06-networkpolicy` | Network security | Ingress and egress policy |
| `07-oom` | Resource management | Memory limits, termination |
| `08-rbac` | Authorization | ServiceAccount permissions |

### Run the exercises

Use a disposable Minikube, kind or k3s cluster.

List the available scenarios:

```bash
bash scenarios/run.sh list
```

Select the intended Kubernetes context:

```bash
export K8S_LAB_CONTEXT=minikube
```

Deploy a scenario:

```bash
bash scenarios/run.sh setup 01-crashloop
```

The runner validates the context and asks for explicit confirmation of the target context and namespace before applying resources.

Inspect scenario resources:

```bash
bash scenarios/run.sh status
```

Remove the lab namespace:

```bash
bash scenarios/run.sh cleanup
```

The default namespace is `production-debug-lab`. It can be changed using `K8S_LAB_NAMESPACE`.

**Safety warning:** Use only disposable lab clusters. Cleanup deletes the entire configured namespace and all resources within it. Review the selected context and namespace before confirming either setup or cleanup.

Each exercise should produce a documented symptom, hypothesis, fault-domain assessment, diagnostic timeline, recovery verification and blameless learning note.

See [docs/EXERCISES.md](docs/EXERCISES.md) for the exercise objectives and expected troubleshooting approach.

---

## Deployment and quick start

### Kubernetes

Apply the Kustomize deployment:

```bash
kubectl apply -k gitops/base
```

Attach to the debug pod:

```bash
kubectl exec -it -n debug-system \
  pod/production-debug -- /bin/bash
```

Review the RBAC and pod security manifests before deploying into a shared or production cluster.

### Container on a Linux VM

Clone the repository:

```bash
git clone https://github.com/ManuJacks/production-debug.git
cd production-debug
```

Launch the containerized diagnostic environment:

```bash
./vm/run-debug-vm.sh
```

### Standalone Linux installation

For hosts without Docker or Podman:

```bash
./vm/install-vm-standalone.sh --prefix /opt/production-debug
```

### Local practice environments

Minikube:

```bash
./dev-lab/run-minikube.sh
```

Multipass:

```bash
./dev-lab/run-multipass.sh
```

See [dev-lab/MULTIPASS_PRACTICE_GUIDE.md](dev-lab/MULTIPASS_PRACTICE_GUIDE.md) for the local VM practice workflow.

---

## Incident response and evidence collection

### Preflight checks

Check the diagnostic environment and target connectivity:

```bash
./scripts/incident_preflight.sh
PS_HOST_1=your-diagnostic-host \
PS_TLS_PORT=443 \
bash ./scripts/remote_dns_tls_check.sh api.production.internal
```

Replace the example hostname with an authorized target in your environment.

### Azure NSG and egress diagnostics

The Azure scripts support network-security and egress investigation:

```bash
./scripts/azure-nsg-map-from-env.sh
./scripts/nsg-egress-validate.sh
```

These workflows depend on appropriate Azure CLI authentication, environment configuration and resource permissions.

### Incident evidence bundle

Package selected diagnostic artifacts:

```bash
bash ./scripts/incident_bundle.sh /tmp/bundles ./telemetry
```

The script creates a timestamped compressed archive containing selected inputs, metadata and KPI reports.

Review the resulting contents before sharing. Automated secret redaction and tamper-proof evidence storage are not currently provided.

### Operational metrics

The project includes KPI reporting functionality intended to support incident-duration and MTTR analysis. Metrics are only as reliable as the timestamps and incident data supplied to the reporting workflow.

---

## Testing and verification

Run the automated test suite:

```bash
python3 -m pytest tests/ -v
```

Validate shell syntax:

```bash
bash -n scenarios/run.sh
```

Run ShellCheck where installed:

```bash
shellcheck scripts/*.sh scenarios/run.sh
```

Check patch whitespace:

```bash
git diff --check
```

Build the container image:

```bash
docker build -f docker/Dockerfile \
  -t production-debug:local .
```

Verify the runtime identity and key tools:

```bash
docker run --rm --entrypoint /bin/bash \
  production-debug:local -c \
  'id && kubectl version --client && helm version --short && k9s version'
```

The Kubernetes deployment, local container build and synthetic scenario runner should be tested independently. A successful container build does not establish that every diagnostic workflow works in every target cluster.

---

## Firefighting and blameless operations

The toolkit supports a structured incident-response model:

1. Establish shared visibility and confirm customer impact.
2. Identify the relevant fault domain and gather initial evidence.
3. Maintain explicit hypotheses and record observations.
4. Prefer reversible, observable diagnostic actions.
5. Preserve relevant evidence before cleanup or restart.
6. Verify recovery from the perspective of the affected service.
7. Record follow-up controls and systemic improvements.

The operating model is blameless. Investigations focus on system behavior, missing signals, contributing conditions and the controls that can prevent recurrence—not individual fault.

The toolkit supports incident command and driver/navigator/scribe collaboration, but it does not replace organizational incident-management procedures.

---

## Limitations and future development

This project is an evolving engineering reference and diagnostic toolkit. Its current boundaries are explicit:

- Kubernetes RBAC is read-only but cluster-wide in the supplied deployment.
- Automated evidence redaction is not implemented.
- Session logs are not immutable or tamper-proof.
- Azure identity configuration detection does not prove successful authentication.
- Synthetic exercises model selected failure modes and do not reproduce every production condition.
- Network diagnostics depend on the capabilities and policies of the target environment.
- The local Multipass environment does not represent independent physical infrastructure or production-grade high availability.

Future development can extend scenario coverage, improve evidence integrity and retention, expand automated verification, and deepen observability and cloud identity diagnostics.

---

## Documentation

- [Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)
- [Operating Model](docs/OPERATING_MODEL.md)
- [CLI Reference](docs/REFERENCE_CLI.md)
- [New Features](docs/NEW_FEATURES.md)
- [Troubleshooting Exercises](docs/EXERCISES.md)
- [Synthetic Proof and Evidence](docs/evidence/SYNTHETIC_PROOF.md)
- [Game Day Checklist](docs/procedures/GAME_DAY_CHECKLIST.md)
- [Incident Evidence Template](docs/procedures/INCIDENT_EVIDENCE_TEMPLATE.md)
- [Release Policy](docs/RELEASE_POLICY.md)
- [Architecture Decision Records](docs/adr/)

## License

This project is licensed under the [MIT License](LICENSE).
