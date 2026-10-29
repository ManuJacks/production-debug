#!/usr/bin/env bash
# ==============================================================================
# entrypoint.sh: Production Debug Container Bootstrapper & MOTD
# ==============================================================================
set -euo pipefail

cat << 'EOF'
  ___ ___ ___  ___  _   _  ___ _____ ___ ___  _  _       ___  ___ ___ _   _  ___ 
 | _ \ _ \   \| _ \| | | |/ __|_   _|_ _/ _ \| \| | ___ |   \| __| _ ) | | |/ __|
 |  _/   / |) |   /| |_| | (__  | |  | | (_) | .` ||___|| |) | _|| _ \ |_| | (_ |
 |_| |_|_\___/|_|_\\___/ \___| |_| |___\___/|_|\_|     |___/|___|___/\___/ \___|
EOF

echo "--------------------------------------------------------------------------------"
echo "  Standard SRE & Cloud Incident Diagnostics Environment"
echo "  Mode: $([ "$(id -u)" -eq 0 ] && echo '⚠️  Privileged (root)' || echo '🛡️  Non-Root Least-Privilege (UID: 10001)')"
echo "  Time (UTC): $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
echo "--------------------------------------------------------------------------------"

# Quick environment discovery
if [ -n "${AZURE_CLIENT_ID:-}" ]; then
    echo "✓ Azure Workload Identity Active (Client ID: ${AZURE_CLIENT_ID})"
elif curl -s -m 1 -H Metadata:true "http://169.254.169.254/metadata/instance?api-version=2021-02-01" >/dev/null 2>&1; then
    echo "✓ Azure IMDS Reachable (Virtual Machine / AKS Node)"
else
    echo "ℹ Azure Metadata/Identity: Standalone / Non-Azure Environment"
fi

if [ -f /var/run/secrets/kubernetes.io/serviceaccount/token ]; then
    echo "✓ Kubernetes In-Cluster ServiceAccount Token detected"
fi

echo ""
echo "Quick Commands:"
echo "  • k8s-debug-tmux          : Launch 4-pane incident triage board"
echo "  • incident_preflight.sh   : Run cluster & environment diagnostic scan"
echo "  • remote_dns_tls_check.sh : Diagnose DNS latency and TLS handshake"
echo "  • incident_bundle.sh      : Generate sanitized evidence bundle"
echo "  • python3 /app/mcp/server.py : Run MCP JSON-RPC server"
echo "--------------------------------------------------------------------------------"

# If first arg is 'mcp', run the MCP server directly
if [ "${1:-}" = "mcp" ]; then
    exec /opt/mcp-venv/bin/python /app/mcp/server.py
fi

exec "$@"
