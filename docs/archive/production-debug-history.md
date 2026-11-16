# Archived Blueprint: Production K8s Debug Toolkit (`production-debug`)

> Historical planning document only; it contains outdated dates, aspirational features and career-marketing language. It is not authoritative product scope or implementation status. See the [README](../../README.md), [incident-response resilience roadmap](../roadmap/incident-response-resilience.md), and [release policy](../RELEASE_POLICY.md) for current guidance.

## 1. Executive Summary & Strategy
* **Target Project Directory**: `/home/robert/Code/production-debug`
* **Objective**: Build an open-source, ephemeral Kubernetes & Azure debug container toolkit engineered to Staff/Principal SRE & Platform standards.
* **Launch Date**: Tuesday (Next Week) on LinkedIn.
* **Core Career Hook**: Position your technical authority around **Production Safety, Cloud-Native Diagnostics, Least-Privilege Incident Triage, and Post-Mortem Evidence Bundling**.

---

## 2. Architecture & Repository Structure (`production-debug`)

Starting fresh in `/home/robert/Code/production-debug`:

```text
production-debug/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # CodeQL, Gitleaks, Shellcheck, Ruff, Changelog gate
│       ├── publish-container.yml     # Multi-arch (amd64/arm64) build to GHCR + Cosign sign + Syft SBOM
│       └── kpi-publish.yml           # Automated weekly KPI telemetry aggregation
├── docker/
│   ├── Dockerfile                    # Multi-stage, minimal, debian-slim or alpine-based
│   └── entrypoint.sh                 # Environment diagnostics, Azure auth check, MOTD
├── mcp/
│   ├── server.py                     # FastMCP / JSON-RPC server exposing diagnostic tools
│   ├── tools/                        # Scoped, read-only diagnostic tools for AI agents
│   │   ├── __init__.py
│   │   ├── k8s_tools.py              # Pod, event, and node condition inspection
│   │   ├── net_tools.py              # DNS latency, TCP socket, MTU, and traceroute
│   │   └── azure_tools.py            # Managed Identity & IMDS verification
│   └── requirements.txt
├── k8s/
│   ├── debug-pod.yaml                # Standalone ephemeral pod with least-privilege caps
│   ├── debug-node-daemon.yaml        # Host-level troubleshooting daemonset/pod (optional/privileged)
│   ├── rbac.yaml                     # Recommended scoped RBAC Role & ServiceAccount
│   └── kustomization.yaml            # Easy `kubectl apply -k` deployment
├── vm/
│   ├── run-debug-vm.sh               # 1-liner to launch debug container on any Linux VM (Docker/Podman)
│   └── install-vm-standalone.sh      # Native install for VMs without container runtimes
├── gitops/
│   ├── base/
│   │   ├── rbac.yaml                 # Least-privilege ClusterRole & ServiceAccount
│   │   └── kustomization.yaml        # Kustomize manifest for debug-system namespace
│   └── clusters/production/
│       └── flux-kustomization.yaml   # Flux v2 Kustomization resource for automated reconciliation
├── dev-lab/
│   ├── run-minikube.sh               # 1-click local test loop (eval minikube docker-env + deploy pod)
│   └── run-multipass.sh              # 1-click local VM test loop (multipass launch + script transfer)
├── scripts/
│   ├── launch-tmux-triage.sh         # Instant 4-pane incident triage board + session logging
│   ├── incident-bundle.sh            # One-click sanitized bundle (redacts secrets/tokens, zips logs)
│   ├── net-triage.sh                 # Automated DNS, egress, MTU, TLS, and latency diagnostics
│   ├── azure-identity-probe.sh       # Azure Workload Identity / IMDS / NSG diagnostic
│   └── k8s-cluster-triage.sh         # Top crashlooping pods, evictions, node pressure
├── docs/
│   ├── ARCHITECTURE.md               # Security boundaries, capability model, Staff-level design notes
│   └── LINKEDIN_POST.md              # Exact copy, graphic ideas, and timing for Tuesday
├── LICENSE                           # Apache 2.0 or MIT
├── Makefile                          # Simple developer targets: `make build`, `make run`, `make test`
└── README.md                         # High-impact documentation with GIF/terminal demo and badges
```

---

## 3. Container Specification (`Dockerfile`)

### Base & Footprint
* **Base**: `debian:bookworm-slim` (recommended over Alpine for official Microsoft `az-cli` performance, glibc eBPF tools, and debugging stability).
* **Target Image Size**: < 280MB compressed.

### Tooling Stack
1. **Cloud & Cluster APIs**:
   * `kubectl` (latest stable)
   * `azure-cli` (`az`)
   * `helm`
2. **Network & Protocol Diagnostics**:
   * `curl`, `wget`, `bind9-dnsutils` (`dig`, `nslookup`), `iproute2` (`ip`, `ss`), `net-tools`, `tcpdump`, `iperf3`, `nmap`, `mtr-tiny`, `socat`, `traceroute`, `conntrack`.
3. **Security, TLS & Certificate Validation**:
   * `openssl`, `ca-certificates`.
4. **Data Manipulation, Terminal Ergonomics & Inspection**:
   * `tmux` (pre-configured multi-pane incident dashboard layout + logging), `jq`, `yq`, `ripgrep`, `htop`, `strace`, `lsof`, `tree`, `vim-tiny`.
5. **AI / Model Context Protocol (MCP) Server**:
   * Lightweight Python FastMCP / JSON-RPC server (`production-debug-mcp`) exposing sandboxed diagnostic tools directly to AI coding assistants (Claude Desktop, Cursor, Antigravity, etc.).
6. **Built-in Automation**:
   * Packaged incident bundle & diagnostic scripts in `/usr/local/bin`.

---

## 4. Tmux Diagnostic Experience & Model Context Protocol (MCP) Integration

### A. Tmux Incident Triage Workspace
When an engineer or on-call enters the debug pod:
* Runs `k8s-debug-tmux` to instantly launch a standard 4-pane incident triage board:
  * **Pane 1 (Top-Left)**: Live cluster/pod event streamer (`kubectl get events -w` / crashloop watch).
  * **Pane 2 (Top-Right)**: Real-time network & DNS probe loop (`net-triage.sh --watch`).
  * **Pane 3 (Bottom-Left)**: Azure IMDS / Workload Identity status & token audit.
  * **Pane 4 (Bottom-Right)**: Interactive shell with pipe logging automatically capturing session history to `/tmp/incident-bundle/session.log`.

### B. MCP (Model Context Protocol) Principles & Implementation
To showcase **cutting-edge Staff-level design (2026)**, the pod features an **MCP server mode**:
* **Protocol**: Exposes tools via standard JSON-RPC (over stdio or an ephemeral internal port).
* **MCP Tools Exposed**:
  1. `run_dns_probe(domain, nameserver)`: Returns parsed DNS resolution metrics & failures.
  2. `check_azure_workload_identity()`: Audits federated credential exchange and token issuance without exposing secrets.
  3. `capture_network_trace(interface, duration, filter)`: Collects a scoped pcap and returns packet distribution stats.
  4. `generate_incident_bundle()`: Generates a sanitized, redacted diagnostic zip bundle with SHA-256 fingerprint.
* **Security & Safety Guardrails**:
  * Read-only by default (no write/delete operations exposed via MCP).
  * Input sanitization preventing shell injection.
  * Audit trail logging all LLM-triggered tool calls.

---

## 4. Kubernetes Integration (`k8s/`)

### 1. `kubectl debug` (Native 1-Liner)
Highlight modern K8s ephemeral containers:
```bash
# Attach to an existing pod's network namespace:
kubectl debug -it <target-pod> --image=ghcr.io/<your-username>/production-debug:latest --target=<container-name>
```

### 2. Standalone Ephemeral Pod (`k8s/debug-pod.yaml`)
* Configured with **non-root default** execution.
* Explicit Linux capabilities opt-in (`NET_ADMIN`, `NET_RAW`, `SYS_PTRACE`) only when needed.
* Tolerations for tainted/unschedulable nodes to triage node-pressure failures.
* Support for Azure Workload Identity (`azure.workload.identity/client-id`).

---

## 5. Staff-Level Engineering Differentiators

To make hiring managers and Staff/Principal committees take notice:
1. **Zero-Secret Architecture**: Built natively for Azure Workload Identity and Kubernetes ServiceAccount IAM federation (IMDS/OIDC).
2. **AI-Native Incident Response via MCP**: Incorporates Model Context Protocol (MCP) server endpoints allowing AI agents (Claude Desktop, Cursor, Antigravity) to safely run read-only diagnostics during outages with zero hallucinated bash commands.
3. **Structured Multiplexed Operations (`tmux`)**: Auto-bootstrapped incident triage layouts with persistent session recording for post-incident review.
4. **Safety Gates & Non-Destructive Defaults**: Read-only defaults; clear dry-run execution; automatic redaction of bearer tokens and secrets during log collection.
5. **Reproducibility & Supply Chain Security**: Multi-architecture container build (`linux/amd64`, `linux/arm64`), Cosign cryptographic signing, and automated SBOM generation via GitHub Actions.

---

## 6. Tuesday LinkedIn Launch Plan

### Target Schedule
* **Date**: Tuesday morning (between 8:00 AM – 9:30 AM EST for peak technical engagement).

### LinkedIn Post Draft Outline
1. **Hook**: *"During a 2:00 AM SEV-1 incident, ad-hoc `apt install` on broken nodes and copy-pasting shell commands is an anti-pattern. Here is how we engineered an ephemeral, zero-secret Kubernetes triage container."*
2. **The Problem**: MTTR suffers from missing tools, security teams hate root SSH/privileged pods, and post-incident post-mortems lack verifiable network/state evidence.
3. **The Solution**: An open-source, production-ready debug container designed for ephemeral pod/node diagnostics, integrated with Azure Workload Identity and automated bundle redaction.
4. **Staff-Level Takeaways**:
   * Why ephemeral containers beat persistent debug sidecars.
   * Managing the tension between diagnostic capabilities (`NET_ADMIN`) and Least Privilege.
   * Automating post-incident evidence collection.
5. **Call to Action**: Link to GitHub repo + invitation for community feedback.

---

## 7. Step-by-Step Execution Plan & Status

1. **Step 1: Scaffold Repository & Core Documentation** [DONE]
   * Initialized repository structure, base workflows, and foundational architecture.
2. **Step 2: Build Dockerfile & Container Entrypoint** [DONE]
   * Built Debian Bookworm-slim Dockerfile with `kubectl`, `helm`, `az`, `bind9-dnsutils`, `tmux`, and network toolchain.
   * Built `docker/entrypoint.sh` with live Azure IMDS / Workload Identity detection and UID 10001 enforcement.
   * Created 4-pane incident triage board (`scripts/launch-tmux-triage.sh` / `k8s-debug-tmux`).
3. **Step 3: FastMCP Diagnostic Server & API Integration** [DONE]
   * Implemented JSON-RPC / FastMCP server (`mcp/server.py`) exposing read-only DNS probes, Azure identity verification, network trace summaries, and sanitized bundle generation.
4. **Step 4: Kubernetes Manifests & Scoped RBAC** [DONE]
   * Created `k8s/debug-pod.yaml`, `k8s/rbac.yaml`, and `k8s/kustomization.yaml` featuring capability dropping (`ALL`), selective adds (`NET_ADMIN`, `SYS_PTRACE`), and tainted node tolerations.
5. **Step 5: Test Suite Standardization & CI Hardening** [DONE]
   * Refactored `tests/test_support_scripts.py` to target active toolchains; achieved 100% test pass rate (13/13).
6. **Step 6: Multipass eBPF & Cilium Dev-Lab** [NEXT]
   * Provision local Ubuntu 24.04 Multipass VM running lightweight Kubernetes (`k3s` with native CNI disabled).
   * Deploy Cilium with eBPF datapath and Hubble observability enabled.
   * Validate `production-debug` pod alongside Hubble CLI/UI for live L7 packet inspection and CiliumNetworkPolicy drop audits.
7. **Step 7: LinkedIn Collateral & Staff-Level Demo** [PENDING]
   * Capture terminal GIF / asciinema showing 4-pane tmux triage + Hubble eBPF packet drop diagnostics.
   * Finalize LinkedIn post copy and schedule publication for Tuesday launch.
