# Privilege Escalation Procedure

> **Classification**: Operational Procedure — Production Access  
> **Applies to**: `production-debug` container on Kubernetes clusters and VM/bare-metal hosts  
> **Owner**: On-call SRE / Platform Engineering  
> **Related ADR**: [ADR-001 Safe-by-Default](../adr/001-safe-by-default-execution.md), [ADR-004 No SSH by Default](../adr/004-production-access-no-ssh-by-default.md)

---

## Why Escalation Exists

The default `production-debug` pod drops all Linux capabilities and runs as non-root UID 10001. This covers 90%+ of incident triage. A small number of tools require elevated capabilities that are not granted by default:

| Tool | Required Capability | Why |
|---|---|---|
| `iptables` / `ip6tables` | `NET_ADMIN` | Read/modify netfilter chains |
| `ipvsadm` | `NET_ADMIN` | Read IPVS forwarding table (kube-proxy IPVS mode) |
| `tshark` promiscuous mode | `NET_ADMIN` + `NET_RAW` | Capture all frames on the interface |
| `ethtool` write ops | `NET_ADMIN` | Modify NIC settings (reads work without it) |
| `nsenter --net/--pid` | `SYS_PTRACE` | Enter another process's namespace |
| `nsenter --mount` | `SYS_ADMIN` | Enter another process's mount namespace |
| `crictl` | CRI socket volume mount | Inspect container runtime directly |

> [!IMPORTANT]
> `NET_ADMIN` and `SYS_ADMIN` are **privileged capabilities**. They must never be granted permanently. Use only the minimum required, only for the duration of the incident.

---

## Escalation Decision Tree

```
Start: Need a network diagnostic tool
         │
         ▼
Does it work in the standard pod?
  (kubectl apply -f k8s/debug-pod.yaml)
         │
    YES ─┤─────────────────────────────► Use standard pod. Done.
         │
        NO
         │
         ▼
Which capability is specifically needed?
         │
    NET_RAW only ─────────────────────► Standard pod already has it. Done.
         │
    NET_ADMIN (iptables/ipvsadm/ethtool)
         │
         ▼
    Open change ticket → get peer approval → use debug-pod-privileged.yaml
         │
    SYS_ADMIN (nsenter --mount)
         │
         ▼
    Requires additional approval (Staff SRE or above) → use debug-pod-privileged.yaml
         │
    hostPID needed
         │
         ▼
    Document specific PID/namespace target in incident ticket
```

---

## Procedure: Kubernetes — Elevated Debug Pod

### Step 1 — Pre-escalation Checklist

Before deploying the privileged pod you **must**:

- [ ] Have an open incident ticket (e.g. `INCIDENT-1234`)
- [ ] Have peer/team lead approval documented in the ticket
- [ ] Know the specific node you need to target (or accept cluster-wide scheduling)
- [ ] Confirm the standard pod was insufficient (document what failed)

### Step 2 — Annotate and Apply

Edit `k8s/debug-pod-privileged.yaml` to fill in the mandatory annotations:

```bash
# Either edit the YAML directly, or patch inline:
kubectl apply -f k8s/debug-pod-privileged.yaml \
  --dry-run=client  # validate first

# Pin to the node under investigation (replace with actual hostname):
# Uncomment nodeSelector in the manifest, or use:
kubectl apply -f - <<EOF
# ... (copy manifest, set nodeSelector: kubernetes.io/hostname: <node>)
EOF
```

Or use `kubectl debug` for a faster, ephemeral alternative (K8s ≥ 1.23):

```bash
# Ephemeral container on a running pod (no manifest needed):
kubectl debug -it <pod-name> -n <namespace> \
  --image=ghcr.io/manujacks/production-debug:latest \
  --target=<container-name>

# Node-level debug pod (mounts host filesystem at /host):
kubectl debug node/<node-name> -it \
  --image=ghcr.io/manujacks/production-debug:latest
```

### Step 3 — Execute Diagnostics

```bash
kubectl exec -it -n debug-system production-debug-privileged -- bash
```

Inside the container, tools that require elevated capabilities:

```bash
# iptables: view kube-proxy rules (iptables-mode clusters)
iptables -t nat -L KUBE-SERVICES -n --line-numbers

# ipvsadm: view IPVS forwarding table (ipvs-mode clusters)
ipvsadm -Ln

# tshark: dissect live traffic on eth0
tshark -i eth0 -f "port 443" -Y "http2" -a duration:30

# ngrep: pattern-match on live traffic
ngrep -d eth0 -q "GET|POST" "port 80"

# ethtool: NIC statistics and driver info
ethtool eth0
ethtool -S eth0   # per-queue statistics

# nsenter: enter pod's network namespace by PID
# 1. Find the PID of a container process on the node:
crictl ps | grep <pod-name>
crictl inspect <container-id> | jq '.info.pid'
# 2. Enter its network namespace:
nsenter --target <PID> --net -- ip addr
nsenter --target <PID> --net -- ss -tnp
nsenter --target <PID> --net -- iptables -L

# crictl: inspect containers via CRI (bypasses the K8s API)
crictl ps
crictl inspect <container-id>
crictl logs <container-id>
crictl pods
```

### Step 4 — Capture Evidence

Before exiting, always bundle diagnostics:

```bash
/usr/local/bin/incident_bundle.sh
# Bundle is written to /tmp/incident-bundle/
# Copy it out before the pod is deleted:
kubectl cp debug-system/production-debug-privileged:/tmp/incident-bundle ./incident-evidence-$(date +%Y%m%d-%H%M%S)
```

### Step 5 — Mandatory Cleanup

```bash
# Delete the privileged pod immediately after the incident
kubectl delete pod -n debug-system production-debug-privileged

# Verify removal
kubectl get pods -n debug-system
```

> [!CAUTION]
> **Never leave the privileged pod running.** Set a calendar reminder for 2 hours if you are likely to be distracted. The `restartPolicy: Never` prevents automatic recreation, but the pod object persists until deleted.

---

## Procedure: VM / Bare-Metal — Docker or Podman

For VM-based incidents where you need elevated network access:

```bash
# Standard launch (NET_ADMIN + NET_RAW already granted):
./vm/run-debug-vm.sh

# Explicit capability list for full tool coverage:
docker run --rm -it \
  --name prod-debug-elevated-$(date +%s) \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  --cap-add=SYS_PTRACE \
  --cap-add=SYS_ADMIN \
  --pid=host \
  --net=host \
  -v /run/containerd/containerd.sock:/run/containerd/containerd.sock:ro \
  -v /var/log:/var/log:ro \
  -v /var/log/incident-bundles:/tmp/incident-bundle \
  -e CONTAINER_RUNTIME_ENDPOINT=unix:///run/containerd/containerd.sock \
  ghcr.io/manujacks/production-debug:latest bash

# CRI-O runtime alternative (swap socket path):
# -v /var/run/crio/crio.sock:/run/containerd/containerd.sock:ro \
# -e CONTAINER_RUNTIME_ENDPOINT=unix:///run/containerd/containerd.sock
```

> [!WARNING]
> `--pid=host` and `--net=host` on a VM give the container visibility into **all processes and all network interfaces** on the host. This is intentional for node-level triage but must be short-lived and logged.

---

## Capability Reference

| Capability | Standard Pod | Privileged Pod | What it enables |
|---|:---:|:---:|---|
| `NET_RAW` | ✅ | ✅ | tcpdump, tshark (non-promisc), ping |
| `SYS_PTRACE` | ✅ | ✅ | strace, nsenter (process NS) |
| `NET_ADMIN` | ❌ | ✅ | iptables, ipvsadm, ethtool writes, tshark promisc |
| `SYS_ADMIN` | ❌ | ✅ | nsenter --mount, overlay FS inspection |
| `hostPID` | ❌ | ✅ | nsenter by PID, crictl via host process tree |
| CRI socket | ❌ | ✅ (volume) | crictl ps/inspect/logs |

---

## Post-Incident Requirements

1. **Close the ticket** with a summary of what was accessed and why escalation was needed.
2. **Attach the incident bundle** from Step 4 to the ticket.
3. **File a blameless post-mortem** if the incident was Sev1/Sev2 (see `docs/procedures/INCIDENT_EVIDENCE_TEMPLATE.md`).
4. **Confirm pod deletion** in the ticket comments with `kubectl get pods -n debug-system` output.
5. **Consider an ADR update** if a new tool or capability requirement was discovered that should be pre-approved for future incidents.
