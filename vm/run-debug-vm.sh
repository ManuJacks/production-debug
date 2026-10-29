#!/usr/bin/env bash
# run-debug-vm.sh - Launch production-debug container on any Linux VM (Docker or Podman)
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/your-org/production-debug:latest}"
CONTAINER_NAME="prod-debug-$(date +%s)"
BUNDLE_DIR="${BUNDLE_DIR:-/var/log/incident-bundles}"

mkdir -p "${BUNDLE_DIR}"

RUNTIME="docker"
if ! command -v docker &>/dev/null && command -v podman &>/dev/null; then
  RUNTIME="podman"
fi

echo "=========================================================="
echo " Launching Production Debug Container on VM via ${RUNTIME}"
echo " Image:       ${IMAGE}"
echo " Host Bundles: ${BUNDLE_DIR}"
echo "=========================================================="

${RUNTIME} run --rm -it \
  --name "${CONTAINER_NAME}" \
  --net=host \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  -v "${BUNDLE_DIR}:/tmp/incident-bundle" \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /var/log:/var/log:ro \
  "${IMAGE}" bash -c "/usr/local/bin/launch-tmux-triage.sh || bash"
