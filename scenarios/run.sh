#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
NAMESPACE=${K8S_LAB_NAMESPACE:-production-debug-lab}

usage() { echo "usage: $0 {list|setup|cleanup|status} [scenario]"; }
case "${1:-}" in
  list) find "$ROOT_DIR" -maxdepth 1 -name '0*.yaml' -printf '%f\n' | sort ;;
  setup)
    scenario=${2:?scenario is required, e.g. 01-crashloop}
    file="$ROOT_DIR/$scenario.yaml"
    test -f "$file" || { echo "scenario not found: $scenario" >&2; exit 2; }
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    kubectl -n "$NAMESPACE" apply -f "$file"
    echo "Synthetic scenario $scenario installed in namespace $NAMESPACE"
    ;;
  status) kubectl -n "$NAMESPACE" get pods,svc,endpoints 2>/dev/null || true ;;
  cleanup) kubectl delete namespace "$NAMESPACE" --ignore-not-found ;;
  *) usage; exit 2 ;;
esac
