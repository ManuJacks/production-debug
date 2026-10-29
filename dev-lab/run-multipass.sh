#!/usr/bin/env bash
# run-multipass.sh - Provision or attach to an Ubuntu Multipass VM with production-debug
set -euo pipefail

VM_NAME="${1:-prod-debug-vm}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1. Check if Multipass VM exists, else create it
if ! multipass list | grep -q "^${VM_NAME} "; then
  echo "=== Launching new Multipass VM: ${VM_NAME} ==="
  multipass launch 24.04 --name "${VM_NAME}" --cpus 2 --memory 2G --disk 10G
else
  echo "=== Found existing Multipass VM: ${VM_NAME} ==="
fi

# 2. Transfer debug utilities to the VM
echo "=== Transferring repository to VM ==="
multipass exec "${VM_NAME}" -- mkdir -p /tmp/production-debug
multipass transfer -r "${REPO_ROOT}/scripts" "${VM_NAME}:/tmp/production-debug/scripts"
multipass transfer -r "${REPO_ROOT}/vm" "${VM_NAME}:/tmp/production-debug/vm"
multipass transfer -r "${REPO_ROOT}/docker" "${VM_NAME}:/tmp/production-debug/docker"
multipass transfer -r "${REPO_ROOT}/mcp" "${VM_NAME}:/tmp/production-debug/mcp"
multipass transfer "${REPO_ROOT}/dev-lab/MULTIPASS_PRACTICE_GUIDE.md" "${VM_NAME}:/home/ubuntu/PRACTICE_GUIDE.md" 2>/dev/null || true

# 3. Install scripts directly on the VM
echo "=== Installing tools and dependencies inside Multipass VM ==="
multipass exec "${VM_NAME}" -- sudo bash -c '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update && apt-get install -y --no-install-recommends \
    tmux jq curl bind9-dnsutils iproute2 tcpdump nmap htop bsdextrautils
  PREFIX=/usr/local/bin bash /tmp/production-debug/vm/install-vm-standalone.sh
  ln -sf /usr/local/bin/launch-tmux-triage.sh /usr/local/bin/k8s-debug-tmux
'

echo "=== Entering ${VM_NAME} interactive shell ==="
multipass shell "${VM_NAME}"
