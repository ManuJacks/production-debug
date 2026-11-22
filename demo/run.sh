#!/usr/bin/env bash
# End-to-end incident demonstration:
#   "How do you debug production without making production worse?"
#
#   1. Break      deploy a workload that crash-loops (scenarios/01-crashloop)
#   2. Isolate    launch an ephemeral, read-only diagnostic pod
#   3. Prove      verify least privilege (allowed reads, denied writes)
#   4. Collect    gather structured evidence inside the pod; sanitize, verify, archive;
#                 draft the incident record (Sev derived from impact x urgency)
#   5. Investigate  AI-facing MCP server, running as the same read-only identity
#   6. Remediate  operator applies the reviewed fix with operator credentials
#   7. Verify     confirm recovery (rollout, readiness, no restarts over a window)
#   8. Clean up   remove every demo resource; safe to repeat
#
# Usage:
#   DEMO_CONTEXT=<ctx> [KUBECONFIG=...] demo/run.sh run|cleanup
#
# Environment:
#   DEMO_CONTEXT   kubeconfig context to target (required)
#   DEMO_CONFIRM   non-interactive confirmation; must equal "<context>/production-debug-lab"
#   DEMO_IMAGE     diagnostic image (default: ghcr.io/manujacks/production-debug:0.2.0)
#   DEMO_OUTPUT    local directory for the incident archive (default: ./incident-output)
#   DEMO_KEEP=1    skip final cleanup (inspect resources afterwards)
#   DEMO_PYTHON    python with the `mcp` SDK (default: demo/.venv/bin/python)
#   DEMO_DETECTED_AT / DEMO_DETECTED_BY
#                  optional alert time (ISO 8601 UTC) and alert name, recorded
#                  as the first work note of the drafted incident record
#
# Only use a cluster where creating and deleting the production-debug-lab and
# production-debug-diag namespaces is acceptable.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB_NS="production-debug-lab"
DIAG_NS="production-debug-diag"
SA="incident-reader"
POD="incident-debug"
SA_USER="system:serviceaccount:${DIAG_NS}:${SA}"

CONTEXT="${DEMO_CONTEXT:-}"
IMAGE="${DEMO_IMAGE:-ghcr.io/manujacks/production-debug:0.2.0}"
OUTPUT="${DEMO_OUTPUT:-$ROOT_DIR/incident-output}"
PYTHON="${DEMO_PYTHON:-$ROOT_DIR/demo/.venv/bin/python}"

bold=$'\e[1m'; green=$'\e[32m'; red=$'\e[31m'; reset=$'\e[0m'
[[ -t 1 ]] || { bold=""; green=""; red=""; reset=""; }

step_start=0
step() {
  step_start=$SECONDS
  printf '\n%s━━ %s%s\n' "$bold" "$*" "$reset"
}
done_step() { printf '%s   ✓ %s (%ss)%s\n' "$green" "$*" "$((SECONDS - step_start))" "$reset"; }
fail() { printf '%s   ✗ %s%s\n' "$red" "$*" "$reset" >&2; exit 1; }
info() { printf '   %s\n' "$*"; }

k() { kubectl --context "$CONTEXT" "$@"; }

require_target() {
  [[ -n "$CONTEXT" ]] || fail "set DEMO_CONTEXT to an explicit kubeconfig context"
  kubectl config get-contexts -o name | grep -Fqx -- "$CONTEXT" ||
    fail "context not found in kubeconfig: $CONTEXT"
  local server
  server="$(kubectl config view -o jsonpath="{.clusters[?(@.name==\"$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$CONTEXT\")].context.cluster}")\")].cluster.server}")"
  info "context : $CONTEXT"
  info "server  : $server"
  info "creates/deletes namespaces: $LAB_NS, $DIAG_NS"
  local expected="${CONTEXT}/${LAB_NS}" answer="${DEMO_CONFIRM:-}"
  if [[ -z "$answer" ]]; then
    read -r -p "   Type ${expected} to confirm: " answer
  fi
  [[ "$answer" == "$expected" ]] || fail "confirmation failed; no changes made"
}

cleanup() {
  step "Clean up demo resources"
  k delete namespace "$DIAG_NS" --ignore-not-found --wait=true --timeout=120s >/dev/null
  K8S_LAB_CONTEXT="$CONTEXT" K8S_LAB_CONFIRM="${CONTEXT}/${LAB_NS}" \
    bash "$ROOT_DIR/scenarios/run.sh" cleanup >/dev/null
  k wait --for=delete "namespace/$LAB_NS" --timeout=120s >/dev/null 2>&1 || true
  for ns in "$DIAG_NS" "$LAB_NS"; do
    if k get namespace "$ns" >/dev/null 2>&1; then
      fail "namespace still present: $ns"
    fi
  done
  done_step "namespaces $DIAG_NS and $LAB_NS removed; no cluster-scoped objects were created"
}

check_access() {
  # expect <allow|deny> <verb> <resource> <namespace|-> [subresource]
  local expect="$1" verb="$2" resource="$3" ns="$4" got
  local args=(auth can-i "$verb" "$resource" --as="$SA_USER")
  [[ "$ns" == "-" ]] && args+=(--all-namespaces) || args+=(-n "$ns")
  if k "${args[@]}" >/dev/null 2>&1; then got=allow; else got=deny; fi
  local label
  label="$(printf '%-6s %-22s %s' "$verb" "$resource" "${ns/#-/<cluster>}")"
  if [[ "$got" == "$expect" ]]; then
    printf '   %s%-5s%s %s\n' "$green" "$got" "$reset" "$label"
  else
    printf '   %s%-5s%s %s  (expected %s)\n' "$red" "$got" "$reset" "$label" "$expect"
    return 1
  fi
}

run_demo() {
  local started=$SECONDS
  command -v kubectl >/dev/null || fail "kubectl not found"
  if ! { [[ -x "$PYTHON" ]] && "$PYTHON" -c 'import mcp' 2>/dev/null; }; then
    fail "MCP client not found: python3 -m venv demo/.venv && demo/.venv/bin/pip install -r demo/requirements.txt"
  fi

  step "Target"
  require_target
  if k get namespace "$DIAG_NS" >/dev/null 2>&1; then
    fail "$DIAG_NS already exists; run: demo/run.sh cleanup"
  fi

  step "1. Break: deploy a crash-looping workload"
  K8S_LAB_CONTEXT="$CONTEXT" K8S_LAB_CONFIRM="${CONTEXT}/${LAB_NS}" \
    bash "$ROOT_DIR/scenarios/run.sh" setup 01-crashloop >/dev/null
  local restarts=0
  for _ in $(seq 1 60); do
    restarts="$(k -n "$LAB_NS" get pods -l app=crashloop-demo \
      -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null || echo 0)"
    [[ "${restarts:-0}" -ge 2 ]] && break
    sleep 3
  done
  [[ "${restarts:-0}" -ge 2 ]] || fail "workload did not enter a crash loop"
  k -n "$LAB_NS" get pods -l app=crashloop-demo | sed 's/^/   /'
  done_step "incident reproduced: restartCount=$restarts"

  step "2. Isolate: launch ephemeral read-only diagnostic pod"
  sed "s|__IMAGE__|${IMAGE}|" "$ROOT_DIR/demo/manifests/diagnostics.yaml" | k apply -f - | sed 's/^/   /'
  k -n "$DIAG_NS" wait --for=condition=Ready "pod/$POD" --timeout=300s >/dev/null ||
    fail "diagnostic pod not ready (image pullable? $IMAGE)"
  info "image: $IMAGE"
  info "pod security: restricted profile, non-root, read-only rootfs, no capabilities"
  info "lifetime: activeDeadlineSeconds=3600 (self-expires if cleanup is missed)"
  done_step "diagnostic pod ready"

  step "3. Prove least privilege for $SA_USER"
  local bad=0
  check_access allow get    pods             "$LAB_NS" || bad=1
  check_access allow get    pods/log         "$LAB_NS" || bad=1
  check_access allow list   events           "$LAB_NS" || bad=1
  check_access deny  delete pods             "$LAB_NS" || bad=1
  check_access deny  create pods/exec        "$LAB_NS" || bad=1
  check_access deny  patch  deployments.apps "$LAB_NS" || bad=1
  check_access deny  update deployments/scale "$LAB_NS" || bad=1
  check_access deny  get    secrets          "$LAB_NS" || bad=1
  check_access deny  list   configmaps       "$LAB_NS" || bad=1
  check_access deny  list   pods             kube-system || bad=1
  check_access deny  list   nodes            - || bad=1
  check_access deny  create pods             "$DIAG_NS" || bad=1
  [[ $bad -eq 0 ]] || fail "RBAC does not match the least-privilege contract"
  info "live attempt from inside the pod (server-side dry run):"
  if k -n "$DIAG_NS" exec "$POD" -- kubectl delete pod -n "$LAB_NS" --all --dry-run=server >/tmp/.pd-del.$$ 2>&1; then
    rm -f /tmp/.pd-del.$$; fail "delete was permitted"
  fi
  sed 's/^/     /' /tmp/.pd-del.$$ | head -2; rm -f /tmp/.pd-del.$$
  done_step "reads allowed in incident namespace only; every write denied"

  step "4. Collect: structured evidence, sanitized and verified"
  k -n "$DIAG_NS" exec "$POD" -- k8s_evidence.sh --namespace "$LAB_NS" \
    --selector app=crashloop-demo --output /tmp/incident-bundle/evidence 2>&1 >/dev/null | sed 's/^/   /'
  local bundle_out archive
  bundle_out="$(k -n "$DIAG_NS" exec "$POD" -- incident_bundle.sh /tmp/incident-bundle/out \
    /tmp/incident-bundle/evidence --name crashloop-demo 2>/dev/null)" || fail "bundle creation failed"
  archive="$(sed -n 's/^archive_path=//p' <<<"$bundle_out")"
  mkdir -p "$OUTPUT"
  k -n "$DIAG_NS" cp "$POD:$archive" "$OUTPUT/$(basename "$archive")" >/dev/null
  info "archive : $OUTPUT/$(basename "$archive")"
  PYTHONPATH="$ROOT_DIR" python3 -m production_debug.bundle_verifier "$OUTPUT/$(basename "$archive")" \
    >"$OUTPUT/$(basename "$archive" .tar.gz).verification.json" || fail "local verification rejected the bundle"
  python3 - "$OUTPUT/$(basename "$archive" .tar.gz).verification.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
print(f"   verified: {r['files_audited']} files, fingerprint {r['bundle_fingerprint_sha256'][:16]}…")
for e in r["manifest"]:
    if e["path"].endswith("manifest.json"):
        print(f"   evidence manifest: {e['path']}")
PY
  # Open the incident record from the verified evidence (draft; never submitted).
  # Severity is derived, not chosen: one internal service fully unavailable,
  # no customer impact -> impact 3 x urgency 1 -> Sev 3 (SEVERITY_MATRIX.md).
  local record
  record="$OUTPUT/$(basename "$archive" .tar.gz).incident.md"
  PYTHONPATH="$ROOT_DIR" python3 -m production_debug.incident_record "$OUTPUT/$(basename "$archive")" \
    --impact 3 --urgency 1 --service crashloop-demo \
    --short-description "crashloop-demo unavailable: container crash-looping" \
    --impact-statement "crashloop-demo (internal) has no ready replicas. No customer-facing service or SLO is affected." \
    --detected-at "${DEMO_DETECTED_AT:-}" --detected-by "${DEMO_DETECTED_BY:-}" \
    >"$record" || fail "incident record could not be drafted"
  info "incident: $(sed -n '1s/^# //p' "$record")"
  info "priority: $(sed -n 's/^| Priority | \(.*\) |$/\1/p' "$record") (impact 3 - Low x urgency 1 - High)"
  info "record  : $record"
  done_step "evidence collected under the diagnostic identity, verified locally, incident record drafted"

  step "5. Investigate: MCP server as the read-only identity"
  "$PYTHON" "$ROOT_DIR/demo/mcp_investigate.py" --namespace "$LAB_NS" -- \
    kubectl --context "$CONTEXT" exec -i -n "$DIAG_NS" "$POD" -- /usr/local/bin/entrypoint.sh mcp ||
    fail "MCP investigation did not establish the fault"
  done_step "fault domain identified without any write access"

  step "6. Remediate: operator applies the reviewed fix"
  info "identity: $(k auth whoami -o jsonpath='{.status.userInfo.username}' 2>/dev/null || echo operator)"
  k -n "$LAB_NS" apply -f "$ROOT_DIR/scenarios/01-crashloop-fixed.yaml" | sed 's/^/   /'
  done_step "change applied (operator credentials, not the diagnostic identity)"

  step "7. Verify recovery"
  k -n "$LAB_NS" rollout status deployment/crashloop-demo --timeout=180s | sed 's/^/   /'
  info "observing for 20s stability window…"
  sleep 20
  local status
  status="$(k -n "$LAB_NS" get pods -l app=crashloop-demo \
    -o jsonpath='{range .items[*]}{.metadata.name} ready={.status.containerStatuses[0].ready} restarts={.status.containerStatuses[0].restartCount}{"\n"}{end}')"
  printf '%s\n' "$status" | sed 's/^/   /'
  if ! grep -q 'ready=true restarts=0' <<<"$status" ||
    grep -qv 'ready=true restarts=0' <<<"$status"; then
    fail "workload not stably recovered"
  fi
  k -n "$LAB_NS" logs deployment/crashloop-demo | sed 's/^/   /'
  done_step "all pods ready with zero restarts after the stability window"

  if [[ "${DEMO_KEEP:-0}" == "1" ]]; then
    info "DEMO_KEEP=1: leaving resources in place; run demo/run.sh cleanup"
  else
    cleanup
  fi
  printf '\n%sDemo complete in %ss.%s Incident archive: %s\n' "$bold" "$((SECONDS - started))" "$reset" "$OUTPUT"
}

case "${1:-}" in
  run) run_demo ;;
  cleanup)
    step "Target"
    require_target
    cleanup
    ;;
  *)
    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
