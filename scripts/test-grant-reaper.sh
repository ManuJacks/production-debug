#!/usr/bin/env bash
# test-grant-reaper.sh: prove the prod-debug-grant-reaper CronJob against a
# live cluster.
#
#   scripts/test-grant-reaper.sh <expected-kube-context> [image]
#
# Needs: k8s/rbac.yaml, k8s/admission-policy.yaml and k8s/grant-reaper.yaml
# applied, cluster-admin credentials. [image] overrides the reaper image for
# this test's Job only (CI passes the image it just built).
#
# Creates namespace pd-reaper-test with two grants: one expiring in 20 s and
# one in an hour. Runs one Job from the CronJob and checks that it removed
# the first and kept the second. Also checks the reaper's RBAC limits.
# Removes everything it created on exit. Exit 0 pass, 1 fail, 2 misuse.
set -euo pipefail

NS="pd-reaper-test"
SYS="debug-system"
JOB="pd-reaper-test-$(date +%s)"
REAPER="system:serviceaccount:${SYS}:prod-debug-grant-reaper"
EXPIRES="production-debug/expires-at"

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || {
    echo "usage: $0 <expected-kube-context> [image]" >&2
    exit 2
}
current="$(kubectl config current-context)"
[ "$current" = "$1" ] || {
    echo "refused: current context is '$current', not '$1'" >&2
    exit 2
}
image="${2:-}"
kubectl -n "$SYS" get cronjob prod-debug-grant-reaper >/dev/null || {
    echo "refused: cronjob/prod-debug-grant-reaper not found; kubectl apply -f k8s/grant-reaper.yaml" >&2
    exit 2
}

# shellcheck disable=SC2329  # invoked via trap
cleanup() {
    kubectl -n "$SYS" delete job "$JOB" --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl delete namespace "$NS" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

failed=0
pass() { echo " ok   $*"; }
fail() {
    echo " FAIL $*"
    failed=1
}

at() { date -u -d "$1" +%Y-%m-%dT%H:%M:%SZ; }
grant() { # name role expires
    kubectl create rolebinding "$1" -n "$NS" --clusterrole="$2" \
        --serviceaccount="${SYS}:prod-debug-sa" --dry-run=client -o yaml |
        kubectl annotate --local -f - "$EXPIRES=$3" -o yaml |
        kubectl create -f - >/dev/null
}

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl label namespace "$NS" production-debug/diagnosable=true --overwrite >/dev/null

# verify <description> <command...>: ok when the command succeeds.
verify() {
    local desc="$1"
    shift
    if "$@"; then pass "$desc"; else fail "$desc"; fi
}
# shellcheck disable=SC2329  # can, exists and missing are called through verify
can() { [ "$(kubectl auth can-i "${@:2}" --as="$REAPER" 2>/dev/null || true)" = "$1" ]; }
# shellcheck disable=SC2329
exists() { kubectl get rolebinding "$1" -n "$NS" >/dev/null 2>&1; }
# shellcheck disable=SC2329
missing() { ! exists "$1"; }

echo "RBAC: the reaper can only take production-debug grants away"
verify "may list RoleBindings" can yes list rolebindings -A
verify "may delete prod-debug-reader" can yes delete rolebinding/prod-debug-reader -n "$NS"
verify "may not delete other RoleBindings" can no delete rolebinding/other -n "$NS"
for verb in create update patch; do
    verify "may not $verb RoleBindings" can no "$verb" rolebindings -n "$NS"
done
verify "may not read Secrets" can no get secrets -n "$NS"

echo "Reaping"
grant prod-debug-reader prod-debug-reader "$(at '+20 seconds')"
grant prod-debug-log-reader prod-debug-log-reader "$(at '+1 hour')"
sleep 25

kubectl -n "$SYS" create job "$JOB" --from=cronjob/prod-debug-grant-reaper --dry-run=client -o json |
    python3 -c '
import json, sys
job = json.load(sys.stdin)
if sys.argv[1]:
    job["spec"]["template"]["spec"]["containers"][0]["image"] = sys.argv[1]
print(json.dumps(job))' "$image" |
    kubectl create -f - >/dev/null
verify "reaper Job completed" \
    kubectl -n "$SYS" wait --for=condition=complete "job/$JOB" --timeout=180s
kubectl -n "$SYS" logs "job/$JOB" 2>/dev/null | sed 's/^/      /' || true
verify "expired grant removed" missing prod-debug-reader
verify "unexpired grant kept" exists prod-debug-log-reader
echo
if [ "$failed" -eq 0 ]; then
    echo "grant reaper: all checks passed"
else
    echo "grant reaper: some checks failed"
fi
exit "$failed"
