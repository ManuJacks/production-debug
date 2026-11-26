#!/usr/bin/env bash
# grant-incident-access.sh: give the production-debug ServiceAccount read-only
# access to ONE allowlisted incident namespace, and take it away afterwards.
#
#   scripts/grant-incident-access.sh --env <env> grant <namespace> [--logs]
#   scripts/grant-incident-access.sh revoke <namespace>
#   scripts/grant-incident-access.sh check  <namespace>
#
# grant  binds prod-debug-reader (workload metadata) into <namespace>, and
#        prod-debug-log-reader (pods/log) too when --logs is given. Refused
#        unless access/<env>.namespaces lists <namespace> and its context=
#        matches the current kubeconfig context.
# revoke removes both bindings. Never restricted by the allowlist.
# check  reports what the ServiceAccount can do in <namespace>.
#
# Run with operator credentials. The environment can also come from
# PROD_DEBUG_ENV. Exit codes: 0 ok, 1 access checks did not match, 2 refused.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST_DIR="${PROD_DEBUG_ALLOWLIST_DIR:-$ROOT/access}"
SA_NAMESPACE="${PROD_DEBUG_NAMESPACE:-debug-system}"
SA_NAME="${PROD_DEBUG_SA:-prod-debug-sa}"
READER_ROLE="${PROD_DEBUG_CLUSTER_ROLE:-prod-debug-reader}"
LOG_ROLE="${PROD_DEBUG_LOG_ROLE:-prod-debug-log-reader}"
READER_BINDING="${PROD_DEBUG_BINDING:-prod-debug-reader}"
LOG_BINDING="${PROD_DEBUG_LOG_BINDING:-prod-debug-log-reader}"
SUBJECT="system:serviceaccount:${SA_NAMESPACE}:${SA_NAME}"

usage() {
    echo "usage: $0 --env <env> grant <namespace> [--logs]" >&2
    echo "       $0 revoke|check <namespace>" >&2
    exit 2
}

refuse() {
    echo "refused: $*" >&2
    exit 2
}

env_name="${PROD_DEBUG_ENV:-}"
logs=no
args=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --env)
            [ "$#" -ge 2 ] || usage
            env_name="$2"
            shift 2
            ;;
        --logs)
            logs=yes
            shift
            ;;
        -*) usage ;;
        *)
            args+=("$1")
            shift
            ;;
    esac
done
[ "${#args[@]}" -eq 2 ] || usage
action="${args[0]}"
ns="${args[1]}"

case "$ns" in
    "$SA_NAMESPACE" | kube-system | kube-public | kube-node-lease)
        refuse "'$ns' is a system namespace"
        ;;
esac

# Prints the namespaces an allowlist file names, after checking its context.
check_allowlist() {
    local file="$ALLOWLIST_DIR/${env_name}.namespaces"
    local expected current
    [ -n "$env_name" ] || refuse "no environment: pass --env <env> or set PROD_DEBUG_ENV"
    case "$env_name" in
        */* | .*) refuse "invalid environment name '$env_name'" ;;
    esac
    [ -f "$file" ] || refuse "no allowlist for environment '$env_name' ($file)"
    expected="$(sed -n 's/^context=//p' "$file" | head -n 1)"
    [ -n "$expected" ] || refuse "$file has no context= line"
    current="$(kubectl config current-context)"
    [ "$current" = "$expected" ] ||
        refuse "current context '$current' is not '$expected' required by $file"
    sed -e 's/#.*//' -e 's/[[:space:]]//g' "$file" | grep -v -e '^$' -e '^context=' |
        grep -qx -- "$ns" ||
        refuse "'$ns' is not in the $env_name allowlist ($file)"
}

has_binding() {
    kubectl get rolebinding "$1" -n "$ns" >/dev/null 2>&1
}

check() {
    local workload="$1" log="$2" verb resource expected actual failed=0 sub
    while read -r verb resource expected; do
        # can-i reads "pods/log" as a pod NAMED "log": pass subresources explicitly.
        sub=()
        [[ "$resource" == */* ]] && sub=(--subresource="${resource#*/}")
        actual="$(kubectl auth can-i "$verb" "${resource%%/*}" "${sub[@]}" -n "$ns" --as="$SUBJECT" 2>/dev/null || true)"
        printf '%-6s %-22s expected=%-3s actual=%s\n' "$verb" "$resource" "$expected" "$actual"
        [ "$actual" = "$expected" ] || failed=1
    done <<CHECKS
list pods $workload
list events $workload
get deployments.apps $workload
get pods/log $log
get secrets no
get configmaps no
create pods/exec no
create pods/portforward no
delete pods no
patch deployments.apps no
CHECKS
    return "$failed"
}

bind() {
    local binding="$1" role="$2"
    kubectl create rolebinding "$binding" -n "$ns" \
        --clusterrole="$role" \
        --serviceaccount="${SA_NAMESPACE}:${SA_NAME}" \
        --dry-run=client -o yaml | kubectl apply -f -
    kubectl label rolebinding "$binding" -n "$ns" --overwrite \
        app.kubernetes.io/part-of=production-debug-toolkit \
        production-debug/env="$env_name" >/dev/null
}

case "$action" in
    grant)
        check_allowlist
        kubectl get namespace "$ns" >/dev/null
        bind "$READER_BINDING" "$READER_ROLE"
        if [ "$logs" = yes ]; then
            bind "$LOG_BINDING" "$LOG_ROLE"
        else
            # A grant without --logs must not inherit logs from an earlier grant.
            kubectl delete rolebinding "$LOG_BINDING" -n "$ns" --ignore-not-found >/dev/null
        fi
        check yes "$logs"
        ;;
    revoke)
        [ "$logs" = no ] || usage
        kubectl delete rolebinding "$READER_BINDING" "$LOG_BINDING" -n "$ns" --ignore-not-found
        check no no
        ;;
    check)
        [ "$logs" = no ] || usage
        workload=no log=no
        has_binding "$READER_BINDING" && workload=yes
        has_binding "$LOG_BINDING" && log=yes
        check "$workload" "$log"
        ;;
    *)
        usage
        ;;
esac
