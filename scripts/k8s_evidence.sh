#!/usr/bin/env bash

set -euo pipefail

# Read-only Kubernetes evidence collector.
#
# Collects pod state, events, workload status, descriptions and logs for one
# namespace into a structured directory with a manifest.json describing every
# collection step and its outcome.
#
# Design constraints:
# - Only read verbs are used: get, describe, logs, auth can-i, version.
# - Secrets and ConfigMap contents are never requested.
# - A failed or empty step is recorded and collection continues.
#
# Exit status: 0 when at least one step succeeded, 3 when every step failed,
# 2 on usage error.

usage() {
  cat <<'EOF'
Usage: k8s_evidence.sh --namespace <ns> --output <dir> [--context <ctx>] [--selector <label-selector>]

Options:
- --namespace <ns>        Namespace to collect from (required)
- --output <dir>          Output directory; must not already exist (required)
- --context <ctx>         kubeconfig context (omit when running in-cluster)
- --selector <selector>   Limit pod descriptions and logs to matching pods
- --tail <lines>          Log lines per container (default: 500, max: 5000)

Environment:
- KUBECTL                 kubectl binary (default: kubectl)
- K8S_TIMEOUT_SECONDS     Per-command time limit in seconds (default: 20)
EOF
}

namespace=""
output_dir=""
context=""
selector=""
tail_lines=500

while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace) namespace="${2:-}"; shift 2 ;;
    --output) output_dir="${2:-}"; shift 2 ;;
    --context) context="${2:-}"; shift 2 ;;
    --selector) selector="${2:-}"; shift 2 ;;
    --tail) tail_lines="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! "$namespace" =~ ^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$ ]]; then
  echo "error: --namespace must be a valid Kubernetes namespace name" >&2
  exit 2
fi
if [[ -z "$output_dir" ]]; then
  echo "error: --output is required" >&2
  exit 2
fi
if [[ -e "$output_dir" ]]; then
  echo "error: output directory already exists: $output_dir" >&2
  exit 2
fi
if [[ -n "$selector" && ! "$selector" =~ ^[A-Za-z0-9._/=,!-]{1,253}$ ]]; then
  echo "error: --selector contains unsupported characters" >&2
  exit 2
fi
if [[ ! "$tail_lines" =~ ^[0-9]{1,4}$ ]] || ((tail_lines < 1 || tail_lines > 5000)); then
  echo "error: --tail must be between 1 and 5000" >&2
  exit 2
fi

KUBECTL="${KUBECTL:-kubectl}"
timeout_secs="${K8S_TIMEOUT_SECONDS:-20}"
[[ "$timeout_secs" =~ ^[0-9]{1,3}$ ]] || { echo "error: K8S_TIMEOUT_SECONDS must be an integer" >&2; exit 2; }

# Bound each call with coreutils timeout rather than --request-timeout: any
# config override (including a request timeout) makes client-go skip the
# in-cluster ServiceAccount config, which breaks collection inside the pod.
kubectl_base=(timeout --kill-after=5 "$timeout_secs" "$KUBECTL")
if [[ -n "$context" ]]; then
  kubectl_base+=("--context" "$context")
fi

mkdir -p "$output_dir"/{cluster,workloads,pods,logs}
steps_file="$output_dir/.steps.tsv"
: >"$steps_file"

ok_count=0
fail_count=0

# collect <relative_output_file> <description> <--|--optional> <kubectl args...>
# Runs a read-only kubectl command, stores stdout, records the outcome.
# With --optional, a failure is recorded as "unavailable" and does not
# degrade the overall status (e.g. previous logs for a never-restarted pod).
collect() {
  local rel="$1" desc="$2" optional=0
  [[ "$3" == "--optional" ]] && optional=1
  shift 3
  local verb="$1"
  case "$verb" in
    get|describe|logs|version|auth) ;;
    *) echo "refusing non-read-only verb: $verb" >&2; exit 70 ;;
  esac

  local out="$output_dir/$rel" err rc status attempt
  err="$(mktemp)"
  # Bounded retry for transient API errors (e.g. a degraded control plane).
  # The attempt count is recorded so instability remains visible as evidence.
  for attempt in 1 2 3; do
    set +e
    "${kubectl_base[@]}" "$@" >"$out" 2>"$err"
    rc=$?
    set -e
    [[ $rc -eq 0 ]] && break
    grep -qiE 'forbidden|notfound|not found' "$err" && break
    [[ $attempt -lt 3 ]] && sleep 1
  done

  if [[ $rc -eq 0 && -s "$out" && "$verb" == "logs" ]] &&
    ! grep -qv 'unable to retrieve container logs' "$out"; then
    # kubectl exits 0 but the runtime has already discarded the container.
    cp "$out" "$err"
    rc=1
  fi

  if [[ $rc -eq 0 && -s "$out" ]]; then
    status="ok"
  elif [[ $rc -eq 0 ]]; then
    status="empty"
  elif [[ $optional -eq 1 ]]; then
    status="unavailable"
  else
    status="failed"
  fi

  if [[ "$status" == "unavailable" ]]; then
    rm -f -- "$out"
  elif [[ "$status" == "failed" ]]; then
    fail_count=$((fail_count + 1))
    # Keep the error text as evidence of why the step failed.
    cp "$err" "$out.error"
  else
    ok_count=$((ok_count + 1))
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$rel" "$desc" "$status" "$rc" "$attempt" \
    "$(head -c 300 "$err" | tr '\t\n' '  ')" >>"$steps_file"
  rm -f -- "$err"
  printf '  %-7s %s\n' "$status" "$desc" >&2
}

echo "Collecting read-only evidence from namespace '$namespace'..." >&2
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Cluster and identity context
collect cluster/version.json "kubectl client/server version" -- version -o json
collect cluster/permissions.txt "effective RBAC permissions in namespace" -- auth can-i --list -n "$namespace"
collect cluster/namespace.txt "namespace status (needs cluster-scope read)" --optional get namespace "$namespace" -o wide

# Workload state
collect workloads/pods.txt "pods (wide)" -- get pods -n "$namespace" -o wide
collect workloads/workloads.txt "deployments, replicasets, statefulsets, daemonsets" -- get deployments,replicasets,statefulsets,daemonsets -n "$namespace" -o wide
collect workloads/services.txt "services and endpointslices" -- get services,endpointslices -n "$namespace" -o wide
collect workloads/events.txt "events (oldest first)" -- get events -n "$namespace" --sort-by=.lastTimestamp

selector_args=()
if [[ -n "$selector" ]]; then
  selector_args=(-l "$selector")
fi

collect pods/describe.txt "pod descriptions" -- describe pods -n "$namespace" "${selector_args[@]}"

# Per-pod logs: current and previous container instances.
pod_list="$("${kubectl_base[@]}" get pods -n "$namespace" "${selector_args[@]}" \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true)"

while IFS= read -r pod; do
  [[ -z "$pod" ]] && continue
  [[ "$pod" =~ ^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$ ]] || continue
  collect "logs/${pod}.log" "logs: $pod (current)" -- logs -n "$namespace" "$pod" --all-containers --prefix --timestamps --tail="$tail_lines"
  collect "logs/${pod}.previous.log" "logs: $pod (previous instance)" --optional logs -n "$namespace" "$pod" --all-containers --prefix --timestamps --previous --tail="$tail_lines"
done <<<"$pod_list"

finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ((ok_count > 0 && fail_count == 0)); then
  overall="complete"
elif ((ok_count > 0)); then
  overall="partial"
else
  overall="failed"
fi

python3 - "$steps_file" "$output_dir/manifest.json" "$namespace" "${context:-in-cluster}" \
  "${selector:-}" "$started" "$finished" "$overall" <<'PY'
import json
import sys

steps_path, manifest_path, namespace, context, selector, started, finished, overall = sys.argv[1:9]
steps = []
with open(steps_path, encoding="utf-8") as fh:
    for line in fh:
        rel, desc, status, rc, attempts, err = line.rstrip("\n").split("\t", 5)
        step = {
            "file": rel,
            "description": desc,
            "status": status,
            "exit_code": int(rc),
            "attempts": int(attempts),
        }
        if status in ("failed", "unavailable"):
            step["error"] = err.strip()
        steps.append(step)

manifest = {
    "schema": "production-debug/k8s-evidence/v1",
    "namespace": namespace,
    "context": context,
    "selector": selector or None,
    "started_utc": started,
    "finished_utc": finished,
    "status": overall,
    "read_only_verbs": ["get", "describe", "logs", "auth can-i", "version"],
    "excluded": ["secrets", "configmap data"],
    "summary": {
        "ok": sum(s["status"] == "ok" for s in steps),
        "empty": sum(s["status"] == "empty" for s in steps),
        "unavailable": sum(s["status"] == "unavailable" for s in steps),
        "failed": sum(s["status"] == "failed" for s in steps),
    },
    "steps": steps,
}
with open(manifest_path, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2)
    fh.write("\n")
PY
rm -f -- "$steps_file"

echo "evidence_dir=$output_dir" >&2
echo "status=$overall (ok=$ok_count failed=$fail_count)" >&2
echo "$output_dir"

if [[ "$overall" == "failed" ]]; then
  exit 3
fi
