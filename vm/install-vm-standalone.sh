#!/usr/bin/env bash
# install-vm-standalone.sh - Install debug scripts directly onto a VM without container runtime
set -euo pipefail

PREFIX="${PREFIX:-/usr/local/bin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"

echo "Installing production-debug utilities directly to ${PREFIX}..."

for script in "${SCRIPT_DIR}"/*.sh; do
  target="${PREFIX}/$(basename "${script}")"
  echo "Installing $(basename "${script}") -> ${target}"
  install -m 0755 "${script}" "${target}"
done

echo "Done. All diagnostic and incident bundle scripts are now available in PATH."
