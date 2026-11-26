#!/usr/bin/env bash
# grant-incident-access.sh: give the production-debug ServiceAccount read-only
# access to ONE incident namespace, and take it away again afterwards.
#
#   scripts/grant-incident-access.sh grant  <namespace>
#   scripts/grant-incident-access.sh revoke <namespace>
#   scripts/grant-incident-access.sh check  <namespace>
#
# Run with operator credentials. The binding reuses the prod-debug-reader
# ClusterRole from k8s/rbac.yaml through a RoleBinding, so the grant is
# confined to <namespace>.
set -euo pipefail

BINDING="${PROD_DEBUG_BINDING:-prod-debug-reader}"
CLUSTER_ROLE="${PROD_DEBUG_CLUSTER_ROLE:-prod-debug-reader}"
SA_NAMESPACE="${PROD_DEBUG_NAMESPACE:-debug-system}"
SA_NAME="${PROD_DEBUG_SA:-prod-debug-sa}"
SUBJECT="system:serviceaccount:${SA_NAMESPACE}:${SA_NAME}"

usage() {
    echo "usage: $0 grant|revoke|check <namespace>" >&2
    exit 2
}

[ "$#" -eq 2 ] || usage
action="$1"
ns="$2"

case "$ns" in
    "$SA_NAMESPACE" | kube-system | kube-public | kube-node-lease)
        echo "refusing to grant incident access to system namespace '$ns'" >&2
        exit 2
        ;;
esac

check() {
    local verb resource expected actual failed=0
    while read -r verb resource expected; do
        actual="$(kubectl auth can-i "$verb" "$resource" -n "$ns" --as="$SUBJECT" 2>/dev/null || true)"
        printf '%-6s %-22s expected=%-3s actual=%s\n' "$verb" "$resource" "$expected" "$actual"
        [ "$actual" = "$expected" ] || failed=1
    done <<CHECKS
list pods $1
get pods/log $1
list events $1
get deployments.apps $1
get secrets no
get configmaps no
create pods/exec no
delete pods no
patch deployments.apps no
CHECKS
    return "$failed"
}

case "$action" in
    grant)
        kubectl get namespace "$ns" >/dev/null
        kubectl create rolebinding "$BINDING" -n "$ns" \
            --clusterrole="$CLUSTER_ROLE" \
            --serviceaccount="${SA_NAMESPACE}:${SA_NAME}" \
            --dry-run=client -o yaml | kubectl apply -f -
        kubectl label rolebinding "$BINDING" -n "$ns" --overwrite \
            app.kubernetes.io/part-of=production-debug-toolkit >/dev/null
        check yes
        ;;
    revoke)
        kubectl delete rolebinding "$BINDING" -n "$ns" --ignore-not-found
        check no
        ;;
    check)
        if kubectl get rolebinding "$BINDING" -n "$ns" >/dev/null 2>&1; then
            check yes
        else
            check no
        fi
        ;;
    *)
        usage
        ;;
esac
