# production-debug

[![CI](https://github.com/ManuJacks/production-debug/actions/workflows/ci.yml/badge.svg)](https://github.com/ManuJacks/production-debug/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-hardened-blue.svg)](docs/RELEASE_POLICY.md)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ephemeral%20debug-326CE5.svg?logo=kubernetes&logoColor=white)](k8s/)
[![Azure Verified](https://img.shields.io/badge/azure-workload%20identity-0078D4.svg?logo=microsoftazure&logoColor=white)](scripts/)

> **High-signal, least-privilege Kubernetes & Azure incident diagnostics toolkit engineered to Staff/Principal SRE standards.**

📖 **New to the project or looking for deep-dive instructions?** Read the [**Detailed Implementation Guide & Architecture Deep-Dive**](docs/IMPLEMENTATION_GUIDE.md) for full walkthroughs on the container design, 4-pane tmux triage, scoped RBAC, MCP AI diagnostic server, and eBPF/Cilium dev-lab.

---

## ⚡ Why This Exists

During high-severity production incidents (Sev-1 / P1), production environments behave fundamentally differently from lower tiers due to traffic scale, strict egress firewalls, complex network security policies (NSGs), and IAM/Workload Identity boundaries.

Responders often encounter:
- **Blind spots in ad-hoc debugging**: Running unrecorded commands in ephemeral pods that destroy evidence upon pod termination.
- **Overprivileged debug roles**: Engineers granting `cluster-admin` or overly broad privileges just to inspect DNS or network sockets.
- **Sensitive data leakage**: Log archives and session dumps inadvertently capturing bearer tokens, connection strings, or customer PII.
- **Slow post-incident assembly**: Hours wasted manually reconstructing command timelines and packet captures for post-mortems.

`production-debug` solves this by standardizing incident triage into safe, observable, and reproducible workflows:
1. **No Blind Operations**: Pre-configured tmux workspaces stream pod crash loops, run continuous network/DNS diagnostics, verify Azure IMDS tokens, and pipe command logs directly into a secure evidence buffer.
2. **Least-Privilege RBAC**: Explicit read-only ClusterRoles and scoped ServiceAccounts for debugging pods.
3. **Automated Evidence Bundling**: One-touch sanitized triage bundle creation with regex secret redaction and SHA256 integrity checksums.
4. **Cloud-Native & VM Portability**: Runs seamlessly as an ephemeral Kubernetes pod, via GitOps (Flux v2), or on Linux VMs via Podman/Docker.

---

## 🏗 Architecture & Core Components

```
production-debug/
├── docker/                 # Container image definitions (multi-stage, minimal attack surface)
├── k8s/                    # Standalone ephemeral pod manifests & scoped RBAC
├── gitops/                 # Flux v2 reconciler & Kustomize overlays for cluster deployment
├── vm/                     # Single-command launchers for bare-metal / VM troubleshooting
├── scripts/                # Modular diagnostic, NSG mapping, KPI, & bundle tooling
│   ├── incident_bundle.sh  # Automated secret-sanitized incident artifact packager
│   ├── incident_preflight.sh # Environment sanity & capability check
│   ├── nsg-egress-validate.sh # Azure NSG egress validation
│   ├── remote_dns_tls_check.sh # DNS resolution & TLS handshake verifier
│   └── kpi_report.sh       # MTTR & incident duration telemetry metrics
├── profiles/               # Profile definitions for repeatable triage configurations
└── dev-lab/                # One-click Minikube & Multipass local sandboxes
```

---

## 🚀 Quick Start

### 1. Ephemeral Kubernetes Debug Pod (Recommended)

Deploy an ephemeral debug pod into your target cluster using Kustomize and scoped RBAC:

```bash
# Apply scoped RBAC and debug pod in debug-system namespace
kubectl apply -k gitops/base

# Attach directly to the debug container
kubectl exec -it -n debug-system deploy/production-debug -- /bin/bash
```

### 2. Standalone VM / Jumpbox Execution

Run the debug container directly on any Linux VM or bastion host with Docker or Podman:

```bash
# Clone the repository
git clone https://github.com/ManuJacks/production-debug.git
cd production-debug

# Launch the containerized debug session
./vm/run-debug-vm.sh
```

Or execute directly on hosts without container runtimes:
```bash
./vm/install-vm-standalone.sh --prefix /opt/production-debug
```

### 3. Local Developer Sandbox

Test diagnostic scripts and configurations locally inside a Minikube or Multipass VM:

```bash
# Minikube test loop
./dev-lab/run-minikube.sh

# Canonical Multipass VM test loop
./dev-lab/run-multipass.sh
```

---

## 🛠 Incident Response Workflows

### Preflight & Connectivity Audit
Verify toolchains, cluster reachability, and network egress before entering live operations:
```bash
./scripts/incident_preflight.sh
./scripts/remote_dns_tls_check.sh --target api.production.internal --port 443
```

### Azure NSG & Egress Mapping
Validate that network security rules and egress routes allow critical diagnostic traffic:
```bash
./scripts/azure-nsg-map-from-env.sh
./scripts/nsg-egress-validate.sh
```

### 3. Local Practice Sandbox via Multipass VM

Want to practice incident drills on a live VM without touching real production? Launch the local Multipass sandbox:

```bash
# Provision isolated VM, sync diagnostic tools, and launch practice environment
bash dev-lab/run-multipass.sh
```

Follow the hands-on practice walkthrough in [dev-lab/MULTIPASS_PRACTICE_GUIDE.md](dev-lab/MULTIPASS_PRACTICE_GUIDE.md) to practice 4-pane tmux triage, K9s navigation, Stern log streaming, and secret-sanitized incident bundling.

---

### Automated Sanitized Incident Evidence Bundling
When an incident concludes, assemble an audit-ready artifact packager with automatic secret redaction:
```bash
# Packages command logs, environment state, and diagnostic outputs with SHA256 checksums
./scripts/incident_bundle.sh --incident INC-10492 --output /tmp/bundles
```

---

## 🔒 Security & Least-Privilege Doctrine

- **Sandboxed Execution**: Ephemeral containers run unprivileged with dropped Linux capabilities (`ALL`) and add back only required tracing/network capabilities (`NET_ADMIN`, `SYS_PTRACE`) when explicitly approved.
- **Token Redaction**: Evidence bundles sanitize JWTs, Azure tokens, private keys, and common password patterns before archiving.
- **Auditable History**: Tmux sessions pipe command buffers to append-only session logs for post-mortem timelines.

---

## 🧪 Testing & Verification

Run the automated test suite and shell validations:

```bash
# Run script unit & integration tests
pytest tests/ -v

# Run ShellCheck across diagnostic scripts
shellcheck scripts/*.sh
```

---

## 📄 License & Governance

This project is licensed under the [MIT License](LICENSE). For release and evaluation standards, consult [docs/RELEASE_POLICY.md](docs/RELEASE_POLICY.md) and [docs/EVALUATION_SCORECARD.md](docs/EVALUATION_SCORECARD.md).
