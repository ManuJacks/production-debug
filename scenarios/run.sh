#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
NAMESPACE=${K8S_LAB_NAMESPACE:-production-debug-lab}
CONTEXT=${K8S_LAB_CONTEXT:-}

usage() {
  echo "usage: K8S_LAB_CONTEXT=<context> $0 {list|setup|cleanup|status} [scenario]"
}

require_context() {
  if [[ -z "$CONTEXT" ]]; then
    echo "error: set K8S_LAB_CONTEXT to an explicit lab context" >&2
    exit 2
  fi

  if ! kubectl config get-contexts -o name | grep -Fqx -- "$CONTEXT"; then
    echo "error: Kubernetes context not found: $CONTEXT" >&2
    exit 2
  fi
}

confirm_context() {
  echo "Target context: $CONTEXT"
  echo "Target namespace: $NAMESPACE"

  read -r -p "Type ${CONTEXT}/${NAMESPACE} to confirm: " confirmation

  if [[ "$confirmation" != "${CONTEXT}/${NAMESPACE}" ]]; then
    echo "confirmation failed; no changes made" >&2
    exit 1
  fi
}

case "${1:-}" in
  list)
    find "$ROOT_DIR" -maxdepth 1 -name '0*.yaml' -printf '%f\n' | sort
    ;;

  setup)
    require_context

    scenario=${2:?scenario is required, e.g. 01-crashloop}

    if [[ ! "$scenario" =~ ^[0-9]{2}-[a-z0-9-]+$ ]]; then
      echo "error: invalid scenario name: $scenario" >&2
      exit 2
    fi

    file="$ROOT_DIR/$scenario.yaml"
    test -f "$file" || {
      echo "scenario not found: $scenario" >&2
      exit 2
    }

    confirm_context

    kubectl --context "$CONTEXT" create namespace "$NAMESPACE" \
      --dry-run=client -o yaml |
      kubectl --context "$CONTEXT" apply -f -

    kubectl --context "$CONTEXT" -n "$NAMESPACE" apply -f "$file"

    echo "Synthetic scenario $scenario installed in namespace $NAMESPACE"
    ;;

  status)
    require_context
    kubectl --context "$CONTEXT" -n "$NAMESPACE" get pods,svc,endpointslices
    ;;

  cleanup)
    require_context
    confirm_context

    kubectl --context "$CONTEXT" delete namespace "$NAMESPACE" \
      --ignore-not-found
    ;;

  *)
    usage
    exit 2
    ;;
esac
