#!/usr/bin/env bash
# test-access-guard.sh: prove the production-debug-access-guard admission
# policy against a live cluster.
#
#   scripts/test-access-guard.sh <expected-kube-context>
#
# Needs: k8s/admission-policy.yaml applied, cluster-admin credentials.
# Creates two temporary namespaces (pd-guard-approved, pd-guard-unapproved)
# and removes them on exit. Every binding case uses --dry-run=server: the
# request goes through authentication, authorization AND admission, but
# nothing is stored. Only the "existing objects" case creates a real binding.
#
# Exit 0 when every case matches its expectation, 1 otherwise, 2 on misuse.
# Walkthrough: docs/security/admission-policy-guide.md
set -euo pipefail

POLICY="production-debug-access-guard"
APPROVED="pd-guard-approved"
UNAPPROVED="pd-guard-unapproved"
LABEL="production-debug/diagnosable"
SA="debug-system:prod-debug-sa"

[ "$#" -eq 1 ] || {
    echo "usage: $0 <expected-kube-context>" >&2
    exit 2
}
current="$(kubectl config current-context)"
[ "$current" = "$1" ] || {
    echo "refused: current context is '$current', not '$1'" >&2
    exit 2
}

for kind in validatingadmissionpolicy validatingadmissionpolicybinding; do
    kubectl get "$kind" "$POLICY" >/dev/null 2>&1 || {
        echo "refused: $kind/$POLICY not found; kubectl apply -f k8s/admission-policy.yaml" >&2
        exit 2
    }
done

# shellcheck disable=SC2329  # invoked via trap
cleanup() {
    kubectl delete namespace "$APPROVED" "$UNAPPROVED" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

kubectl create namespace "$APPROVED" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl label namespace "$APPROVED" "$LABEL=true" --overwrite >/dev/null
kubectl create namespace "$UNAPPROVED" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

failed=0
n=0

# expect <allow|deny> <description> -- <kubectl args...>
expect() {
    local want="$1" desc="$2" out got
    shift 3
    n=$((n + 1))
    if out="$(kubectl "$@" 2>&1)"; then
        got=allow
    elif grep -q "ValidatingAdmissionPolicy '$POLICY'" <<<"$out"; then
        got=deny
    else
        got="error"
    fi
    if [ "$got" = "$want" ]; then
        printf ' ok   %2d %-5s %s\n' "$n" "$got" "$desc"
    else
        printf ' FAIL %2d %-5s %s (expected %s)\n' "$n" "$got" "$desc" "$want"
        printf '         %s\n' "$out"
        failed=1
    fi
}

# Policies take effect a few seconds after creation (the API server has to
# load and compile them). Wait until a known-bad request is denied.
for _ in $(seq 1 30); do
    if kubectl create rolebinding pd-guard-probe -n "$UNAPPROVED" \
        --clusterrole=prod-debug-reader --serviceaccount="$SA" --dry-run=server 2>&1 |
        grep -q "ValidatingAdmissionPolicy '$POLICY'"; then
        break
    fi
    sleep 1
done

echo "Rule 1: production-debug roles only in labelled namespaces"
expect allow "reader into labelled namespace" -- \
    create rolebinding t1 -n "$APPROVED" --clusterrole=prod-debug-reader --serviceaccount="$SA" --dry-run=server
expect allow "log reader into labelled namespace" -- \
    create rolebinding t2 -n "$APPROVED" --clusterrole=prod-debug-log-reader --serviceaccount="$SA" --dry-run=server
expect deny "reader into unlabelled namespace" -- \
    create rolebinding t3 -n "$UNAPPROVED" --clusterrole=prod-debug-reader --serviceaccount="$SA" --dry-run=server
expect deny "log reader into unlabelled namespace" -- \
    create rolebinding t4 -n "$UNAPPROVED" --clusterrole=prod-debug-log-reader --serviceaccount="$SA" --dry-run=server
expect deny "reader into kube-system" -- \
    create rolebinding t5 -n kube-system --clusterrole=prod-debug-reader --serviceaccount="$SA" --dry-run=server
expect deny "reader for ANOTHER subject, unlabelled namespace" -- \
    create rolebinding t6 -n "$UNAPPROVED" --clusterrole=prod-debug-reader --serviceaccount=default:default --dry-run=server

echo "Rule 2: workload and log layers never cluster-wide"
expect deny "ClusterRoleBinding to prod-debug-reader" -- \
    create clusterrolebinding pd-guard-t7 --clusterrole=prod-debug-reader --serviceaccount="$SA" --dry-run=server
expect deny "ClusterRoleBinding to prod-debug-log-reader" -- \
    create clusterrolebinding pd-guard-t8 --clusterrole=prod-debug-log-reader --serviceaccount="$SA" --dry-run=server
expect allow "ClusterRoleBinding to prod-debug-cluster-reader (layer 1)" -- \
    create clusterrolebinding pd-guard-t9 --clusterrole=prod-debug-cluster-reader --serviceaccount="$SA" --dry-run=server

echo "Rule 3: the production-debug identity gets production-debug roles only"
expect deny "view, by ServiceAccount, in a labelled namespace" -- \
    create rolebinding t10 -n "$APPROVED" --clusterrole=view --serviceaccount="$SA" --dry-run=server
expect deny "cluster-admin, by ServiceAccount" -- \
    create clusterrolebinding pd-guard-t11 --clusterrole=cluster-admin --serviceaccount="$SA" --dry-run=server
expect deny "cluster-admin, by User name of the ServiceAccount" -- \
    create clusterrolebinding pd-guard-t12 --clusterrole=cluster-admin --user=system:serviceaccount:debug-system:prod-debug-sa --dry-run=server
expect deny "edit, by Group of all debug-system ServiceAccounts" -- \
    create rolebinding t13 -n "$APPROVED" --clusterrole=edit --group=system:serviceaccounts:debug-system --dry-run=server

echo "Unrelated bindings are not affected"
expect allow "view for another ServiceAccount, unlabelled namespace" -- \
    create rolebinding t14 -n "$UNAPPROVED" --clusterrole=view --serviceaccount=default:default --dry-run=server

echo "Existing objects and deletes"
kubectl create rolebinding pd-guard-existing -n "$APPROVED" \
    --clusterrole=prod-debug-reader --serviceaccount="$SA" >/dev/null
kubectl label namespace "$APPROVED" "$LABEL-" >/dev/null
expect allow "binding created before the label was removed still exists" -- \
    get rolebinding pd-guard-existing -n "$APPROVED"
expect deny "but re-applying it (UPDATE) is now denied" -- \
    label rolebinding pd-guard-existing -n "$APPROVED" touched=yes --dry-run=server
expect allow "deleting it is never blocked" -- \
    delete rolebinding pd-guard-existing -n "$APPROVED"

echo
if [ "$failed" -eq 0 ]; then
    echo "all $n cases matched"
else
    echo "some cases did not match"
fi
exit "$failed"
