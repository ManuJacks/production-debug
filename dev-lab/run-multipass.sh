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
echo "=== Transferring production-debug scripts to VM ==="
multipass transfer -r "${REPO_ROOT}/scripts" "${VM_NAME}:/tmp/debug-scripts"
multipass transfer "${REPO_ROOT}/vm/install-vm-standalone.sh" "${VM_NAME}:/tmp/install-vm-standalone.sh"

# 3. Install scripts directly on the VM
echo "=== Installing tools inside Multipass VM ==="
multipass exec "${VM_NAME}" -- sudo bash -c 'PREFIX=/usr/local/bin bash /tmp/install-vm-standalone.sh'

echo "=== Entering ${VM_NAME} interactive shell ==="
multipass shell "${VM_NAME}"
