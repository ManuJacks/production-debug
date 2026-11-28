#!/usr/bin/env bash
# reap-expired-grants.sh: delete production-debug grants that have expired.
#
#   scripts/reap-expired-grants.sh [--dry-run]
#
# Looks at every RoleBinding to prod-debug-reader or prod-debug-log-reader in
# the cluster. Deletes it when its production-debug/expires-at annotation has
# passed, or when it has no valid expiry (made before expiry existed, or by
# hand around the admission guard): fail closed.
#
# Runs every 5 minutes in-cluster as the prod-debug-grant-reaper CronJob
# (k8s/grant-reaper.yaml, which embeds a copy of this file), and by hand with
# operator credentials. ADR-SEC-001 section 7, item 2.
# Exit codes: 0 ok, 1 a grant could not be removed, 2 misuse.
set -euo pipefail

EXPIRES_ANNOTATION="production-debug/expires-at"
ROLES=" prod-debug-reader prod-debug-log-reader "
# The reaper's RBAC can delete only bindings with these names.
NAMES=" prod-debug-reader prod-debug-log-reader "

dry_run=no
case "${1:-}" in
    "") ;;
    --dry-run) dry_run=yes ;;
    *)
        echo "usage: $0 [--dry-run]" >&2
        exit 2
        ;;
esac

now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# Read the list first, so a failed API call fails the run instead of looking
# like "nothing to do".
list="$(kubectl get rolebindings --all-namespaces -o go-template="$(printf '%s' \
    '{{range .items}}{{if eq .roleRef.kind "ClusterRole"}}' \
    '{{.metadata.namespace}}{{"\t"}}{{.metadata.name}}{{"\t"}}{{.roleRef.name}}{{"\t"}}' \
    "{{with .metadata.annotations}}{{index . \"$EXPIRES_ANNOTATION\"}}{{end}}" \
    '{{"\n"}}{{end}}{{end}}')")"

kept=0 reaped=0 failed=0
while IFS=$'\t' read -r ns name role expires; do
    [ -n "$ns" ] || continue
    [[ "$ROLES" == *" $role "* ]] || continue
    if [[ "$expires" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]; then
        # Same fixed format on both sides, so string order is time order.
        if [[ "$expires" > "$now" ]]; then
            kept=$((kept + 1))
            continue
        fi
        reason="expired at $expires"
    else
        reason="no valid $EXPIRES_ANNOTATION"
    fi
    if [[ "$NAMES" != *" $name "* ]]; then
        echo "cannot reap $ns/$name ($role, $reason): not a name the reaper may delete; revoke it by hand" >&2
        failed=1
        continue
    fi
    if [ "$dry_run" = yes ]; then
        echo "would reap $ns/$name ($role): $reason"
    elif kubectl delete rolebinding "$name" -n "$ns" --wait=false >/dev/null; then
        echo "reaped $ns/$name ($role): $reason"
    else
        echo "failed to reap $ns/$name ($role): $reason" >&2
        failed=1
        continue
    fi
    reaped=$((reaped + 1))
done <<<"$list"

echo "summary at $now: kept=$kept reaped=$reaped dry_run=$dry_run"
exit "$failed"
