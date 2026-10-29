#!/usr/bin/env bash
# ==============================================================================
# launch-tmux-triage.sh: Production Incident 4-Pane Workspace
# ==============================================================================
# Pane 1 (Top-Left)    : Cluster & Pod Event Streamer
# Pane 2 (Top-Right)   : Live Network & DNS Probe Loop
# Pane 3 (Bottom-Left) : Azure IMDS / Workload Identity Audit
# Pane 4 (Bottom-Right): Interactive triage shell with pipe-logging
# ==============================================================================
set -euo pipefail

SESSION_NAME="${1:-incident-triage}"
LOG_DIR="${INCIDENT_LOG_DIR:-/tmp/incident-bundle}"
mkdir -p "$LOG_DIR"
SESSION_LOG="${LOG_DIR}/session-$(date +%Y%m%d-%H%M%S).log"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Attaching to existing session: $SESSION_NAME"
    exec tmux attach-session -t "$SESSION_NAME"
fi

echo "Initializing 4-pane triage workspace: $SESSION_NAME"
echo "Session logging enabled -> $SESSION_LOG"

# 1. Create session with Window 1 / Pane 1 (Top-Left): K8s Live TUI & Event Stream
# shellcheck disable=SC2016
tmux new-session -d -s "$SESSION_NAME" -n "triage" \
    'echo "=== [PANE 1] Live K8s Diagnostics & Event Stream ==="; \
     if command -v k9s >/dev/null 2>&1 && [ -n "${KUBECONFIG:-}" -o -f "$HOME/.kube/config" -o -f /var/run/secrets/kubernetes.io/serviceaccount/token ]; then \
       echo "Starting K9s TUI (Press q to exit to shell)..."; \
       k9s --readonly || exec bash; \
     elif command -v kubectl >/dev/null 2>&1; then \
       kubectl get events -A --sort-by=.metadata.creationTimestamp -w 2>/dev/null || \
       kubectl get pods -A --field-selector status.phase!=Running -w 2>/dev/null || \
       echo "Kubectl active. Run: kubectl get pods -A"; \
     else \
       echo "kubectl/k9s not active. Standalone Linux mode."; \
     fi; exec bash'

# 2. Split horizontally for Pane 2 (Top-Right): Network Probes
# shellcheck disable=SC2016
tmux split-window -h -t "${SESSION_NAME}:0" \
    'echo "=== [PANE 2] Continuous Network & DNS Health Monitor ==="; \
     TARGET="${PROBE_TARGET:-1.1.1.1}"; \
     while true; do \
       echo "--- [$(date +%T)] DNS & Latency Probe ($TARGET) ---"; \
       if command -v dig >/dev/null 2>&1; then dig +short +time=2 +tries=1 google.com || echo "DNS Lookup failed"; fi; \
       if command -v ping >/dev/null 2>&1; then ping -c 1 -W 2 "$TARGET" 2>/dev/null || echo "Ping failed"; fi; \
       sleep 5; \
     done'

# 3. Split bottom from Pane 1 (Bottom-Left): Azure & Identity Audit
tmux select-pane -t "${SESSION_NAME}:0.0"
# shellcheck disable=SC2016
tmux split-window -v -t "${SESSION_NAME}:0.0" \
    'echo "=== [PANE 3] Azure Workload Identity / IMDS Audit ==="; \
     if [ -n "${AZURE_CLIENT_ID:-}" ]; then \
       echo "AZURE_CLIENT_ID: $AZURE_CLIENT_ID"; \
       echo "AZURE_TENANT_ID: ${AZURE_TENANT_ID:-unset}"; \
       echo "AZURE_FEDERATED_TOKEN_FILE: ${AZURE_FEDERATED_TOKEN_FILE:-unset}"; \
     else \
       echo "Testing Azure IMDS reachability (169.254.169.254)..."; \
       curl -s -m 2 -H Metadata:true "http://169.254.169.254/metadata/instance?api-version=2021-02-01" | jq . 2>/dev/null || \
       echo "IMDS not reachable or not running in Azure VM/AKS."; \
     fi; exec bash'

# 4. Split bottom from Pane 2 (Bottom-Right): Primary Interactive Work Shell with Logging
tmux select-pane -t "${SESSION_NAME}:0.2"
tmux split-window -v -t "${SESSION_NAME}:0.2" \
    "echo '=== [PANE 4] Interactive Triage Terminal (Logged) ==='; \
     echo 'Logging session stdout/stderr to $SESSION_LOG'; \
     exec script -f -q '$SESSION_LOG' bash"

# Re-balance into clean 4-quadrant grid
tmux select-layout -t "${SESSION_NAME}:0" tiled
tmux select-pane -t "${SESSION_NAME}:0.3"

# Attach if interactive terminal
if [ -t 0 ]; then
    tmux attach-session -t "$SESSION_NAME"
fi
