# Implementation Guide & Architecture Deep-Dive

This document provides detailed instructions and architectural context for the core components implemented in **`production-debug`**.

---

## 📑 Contents
1. [Overview of What Has Been Built](#1-overview-of-what-has-been-built)
2. [Container Architecture (`docker/`)](#2-container-architecture-docker)
3. [4-Pane Tmux Incident Triage Workspace](#3-4-pane-tmux-incident-triage-workspace)
4. [Kubernetes Ephemeral Manifests & Security Boundary (`k8s/`)](#4-kubernetes-ephemeral-manifests--security-boundary-k8s)
5. [Model Context Protocol (MCP) AI Diagnostic Server (`mcp/`)](#5-model-context-protocol-mcp-ai-diagnostic-server-mcp)
6. [Testing & Quality Gates (`tests/`)](#6-testing--quality-gates-tests)
7. [eBPF & Cilium Multipass Sandbox (Staff-Level Demo)](#7-ebpf--cilium-multipass-sandbox-staff-level-demo)

---

## 1. Overview of What Has Been Built

| Component | Path | Purpose |
|---|---|---|
| **Container Engine** | [`docker/Dockerfile`](../docker/Dockerfile) | Minimal Debian Bookworm slim runtime with cloud & network diagnostic toolsets. |
| **Container Bootstrapper** | [`docker/entrypoint.sh`](../docker/entrypoint.sh) | MOTD, runtime privilege detection (`UID 10001`), and Azure IMDS / Workload Identity validation. |
| **Tmux Workspace** | [`scripts/launch-tmux-triage.sh`](../scripts/launch-tmux-triage.sh) | Standard 4-pane live triage dashboard with auto-pipe session logging. |
| **K8s Pod Manifest** | [`k8s/debug-pod.yaml`](../k8s/debug-pod.yaml) | Ephemeral debug pod with non-root security context, capability drops, and node tolerations. |
| **Scoped RBAC** | [`k8s/rbac.yaml`](../k8s/rbac.yaml) | Read-only `ClusterRole` and ServiceAccount for incident investigation. |
| **Kustomize Overlay** | [`k8s/kustomization.yaml`](../k8s/kustomization.yaml) | 1-step deployment into the `debug-system` namespace. |
| **MCP AI Server** | [`mcp/server.py`](../mcp/server.py) | FastMCP / JSON-RPC server exposing read-only diagnostic tools to AI assistants. |
| **Test Suite** | [`tests/test_support_scripts.py`](../tests/test_support_scripts.py) | 100% automated test suite validating bash scripts, CLI contracts, and MCP functions. |

---

## 2. Container Architecture (`docker/`)

### Design Considerations
* **Debian vs Alpine**: `debian:bookworm-slim` was chosen over Alpine for glibc eBPF tracing support, official Microsoft Azure CLI performance, and consistent networking utility behavior (`mtr-tiny`, `tcpdump`, `bind9-dnsutils`).
* **Non-Root by Default**: The container creates and switches to `debuguser` (`UID 10001`), proving that incident responders do not need root access inside containers to run network queries and cluster inspections.

### Testing Locally
```bash
# Build the container
docker build -t production-debug:latest -f docker/Dockerfile .

# Run container interactively
docker run --rm -it production-debug:latest
```

---

## 3. 4-Pane Tmux Incident Triage Workspace

Responders run `k8s-debug-tmux` (or `bash /usr/local/bin/launch-tmux-triage.sh`) inside the debug environment to immediately establish visibility:

```
+------------------------------------+------------------------------------+
| PANE 1: Cluster & Pod Events       | PANE 2: Continuous Network Monitor |
| Live streaming `kubectl get events`| Real-time DNS & latency probe loop |
+------------------------------------+------------------------------------+
| PANE 3: Azure Identity & IMDS      | PANE 4: Primary Interactive Shell  |
| Workload Identity / IMDS audits    | Full terminal; piped to session.log|
+------------------------------------+------------------------------------+
```

* **Session Recording**: Pane 4 automatically pipes all standard output and user input to `/tmp/incident-bundle/session-<timestamp>.log` using the `script` utility, creating a tamper-resistant timeline for post-mortems.

---

## 4. Kubernetes Ephemeral Manifests & Security Boundary (`k8s/`)

### Least-Privilege Capability Profile
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
    add:
      - NET_ADMIN    # Required for socket & routing diagnostics
      - NET_RAW      # Required for ICMP ping and packet capture
      - SYS_PTRACE   # Required for process inspection & strace
```

### Deploying Scoped Pod
```bash
kubectl apply -k k8s/
kubectl exec -it -n debug-system pod/production-debug -- /bin/bash
```

---

## 5. Model Context Protocol (MCP) AI Diagnostic Server (`mcp/`)

The container includes a Model Context Protocol server exposing read-only tools to AI assistants like Claude Desktop, Cursor, and Antigravity over JSON-RPC.

### Available Tools:
1. `run_dns_probe(domain, nameserver)`: Performs sanitized DNS inspection without risk of command injection.
2. `check_azure_workload_identity()`: Audits Azure Workload Identity variables (`AZURE_CLIENT_ID`, `AZURE_FEDERATED_TOKEN_FILE`) and verifies 169.254.169.254 IMDS metadata without revealing token secrets.
3. `capture_network_trace_summary(interface, duration_sec)`: Collects a bounded sample of network packets.
4. `generate_incident_bundle(incident_id)`: Creates a sanitized incident archive with secret redaction.

### Starting MCP Server:
```bash
python3 mcp/server.py
# Or inside the container:
docker run -i production-debug:latest mcp
```

---

## 6. Testing & Quality Gates (`tests/`)

Run tests locally using pytest:
```bash
pytest tests/ -v
```

All 13 test suites validate:
* Bash syntax sanity (`bash -n`) across all operational scripts.
* CLI contract and flag validation (`incident_preflight.sh`, `kpi_collect.sh`, `kpi_report.sh`, etc.).
* Automated sanitized bundle creation and archive compression.
* MCP server functions and input validation guardrails.

---

## 7. eBPF & Cilium Multipass Sandbox (Staff-Level Demo)

To showcase advanced cloud-native networking troubleshooting:
* **Multipass VM**: Ubuntu 24.04 with kernel 6.8+ eBPF support.
* **Lightweight K8s**: `k3s` initialized with `--flannel-backend=none --disable-network-policy`.
* **Cilium CNI**: Installed with Hubble observability to inspect live L7 network flows and policy drops in real-time.
