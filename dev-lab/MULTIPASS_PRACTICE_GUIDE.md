# Multipass Incident Practice & Hands-On Triage Lab

This hands-on guide walks you through practicing realistic incident triage drills inside an isolated Ubuntu Multipass VM using the Staff SRE toolkit.

---

## 1. Quick Start: Launch Your Practice VM

From the repository root on your workstation:

```bash
# Ensure multipass is installed on your workstation (snap install multipass / brew install multipass)
bash dev-lab/run-multipass.sh
```

This script will:
1. Spin up an Ubuntu 24.04 VM (`prod-debug-vm`) with 2 CPUs, 2GB RAM.
2. Synchronize the `scripts/`, `vm/`, and `docker/` directories.
3. Install base networking diagnostics (`tcpdump`, `dig`, `tmux`, `jq`, `nmap`).
4. Drop you directly into the VM's interactive shell.

*(To reconnect later: `multipass shell prod-debug-vm`)*

---

## 2. Interactive Hands-On Practice Drills

### Drill A: Multi-Pane Live Incident Board (`tmux`)
Launch the 4-quadrant triage workspace:
```bash
k8s-debug-tmux
# or: launch-tmux-triage.sh incident-test-01
```
What you will see in real time:
- **Pane 1 (Top-Left)**: K8s events / K9s TUI (falls back to standalone status if no cluster attached).
- **Pane 2 (Top-Right)**: Continuous DNS & ping latency loop (probing `1.1.1.1` and `google.com`).
- **Pane 3 (Bottom-Left)**: Azure Workload Identity & IMDS audit (checks reachability to `169.254.169.254`).
- **Pane 4 (Bottom-Right)**: Your primary interactive terminal — all typing is **automatically logged** via `script` into `/tmp/incident-bundle/session-*.log`.

**Tmux Navigation Cheat Sheet:**
- `Ctrl+b` then `Arrow Key`: Move between quadrants.
- `Ctrl+b` then `z`: Zoom in/out of the active pane.
- `Ctrl+b` then `d`: Detach without killing your monitoring session.
- Reattach anytime with: `k8s-debug-tmux`.

---

### Drill B: Kubernetes Staff SRE Diagnostic Tools
To practice with a live cluster inside Multipass:
```bash
# Optional: Install lightweight k3s or minikube in the VM:
curl -sfL https://get.k3s.io | sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# 1. K9s Interactive TUI
k9s --readonly

# 2. Multi-pod log tailing with Stern
stern -n kube-system "coredns.*"

# 3. Fast namespace / context switching
kubens kube-system
kubectx

# 4. Strip messy metadata with kubectl-neat
kubectl get configmap coredns -o yaml | kubectl-neat

# 5. Visual tree inspection of controllers and pods
kubectl tree deployment coredns -n kube-system
```

---

### Drill C: Automated Secret-Sanitized Evidence Bundling
Simulate an incident response and package evidence for post-mortem:
```bash
# Run preflight sanity check
incident_preflight.sh

# Run remote DNS & TLS verification
remote_dns_tls_check.sh github.com 443

# Package everything into a sanitized archive
incident_bundle.sh /tmp/incident-bundle /tmp/incident-bundle/session-*.log --name outage-p1
```
The output `.tar.gz` will contain:
- Timestamped metadata (`metadata.json`).
- Sanitized command history (redacted bearer tokens & credentials).
- KPI MTTR duration metrics.

---

### Drill D: Clean Up
When you are done testing:
```bash
# On your host workstation:
multipass stop prod-debug-vm
multipass delete --purge prod-debug-vm
```
