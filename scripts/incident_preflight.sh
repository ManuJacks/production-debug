#!/usr/bin/env bash

set -u

METRIC_START_TS="$(date +%s)"
METRIC_HOSTS=0
METRIC_FAILURES=0

emit_metric() {
  local exit_code="$1"
  if [[ "${PS_METRICS:-0}" != "1" ]]; then
    return
  fi

  local end_ts duration status
  end_ts="$(date +%s)"
  duration=$((end_ts - METRIC_START_TS))
  status="success"
  if [[ "$exit_code" -ne 0 ]]; then
    status="failure"
  fi

  printf 'METRIC|script=incident_preflight|status=%s|exit_code=%s|duration_s=%s|hosts=%s|failures=%s\n' \
    "$status" "$exit_code" "$duration" "$METRIC_HOSTS" "$METRIC_FAILURES"
}

trap 'emit_metric $?' EXIT

usage() {
  cat <<'EOF'
Usage: incident_preflight.sh [--local-only] [host ...]

Checks the local workstation and optional remote hosts before starting a
multi-host tmux support session.

Host discovery:
- explicit host arguments
- otherwise PS_HOST_* environment variables

Optional environment variables:
- SSH_USER          SSH username prefix for remote checks
- PS_SSH_TIMEOUT    SSH timeout in seconds, default: 5
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

local_only=0
if [[ "${1:-}" == "--local-only" ]]; then
  local_only=1
  shift
fi

discover_hosts() {
  if [[ $# -gt 0 ]]; then
    for host in "$@"; do
      if [[ -n "$host" ]]; then
        printf '%s\n' "$host"
      fi
    done
    return
  fi

  env | awk -F= '/^PS_HOST_[0-9]+=/{print $1}' | sort | while read -r name; do
    if [[ -n "${!name}" ]]; then
      printf '%s\n' "${!name}"
    fi
  done
}

print_result() {
  local status="$1"
  local label="$2"
  local detail="$3"
  printf '[%s] %s: %s\n' "$status" "$label" "$detail"
}

failures=0
required_commands=(bash tmux ssh)

print_result INFO local-user "$(id -un)"
print_result INFO local-host "$(hostname 2>/dev/null || uname -n)"

for command_name in "${required_commands[@]}"; do
  if command -v "$command_name" >/dev/null 2>&1; then
    print_result OK "$command_name" "available"
  else
    print_result FAIL "$command_name" "missing from PATH"
    failures=$((failures + 1))
  fi
done

if command -v tmux >/dev/null 2>&1; then
  print_result INFO tmux-version "$(tmux -V 2>/dev/null || echo unknown)"
fi

ssh_timeout="${PS_SSH_TIMEOUT:-5}"
ssh_user_prefix=""
if [[ -n "${SSH_USER:-}" ]]; then
  ssh_user_prefix="${SSH_USER}@"
fi

if [[ $local_only -eq 1 ]]; then
  print_result INFO remote-checks "skipped by --local-only"
else
  hosts=()
  mapfile -t hosts < <(discover_hosts "$@")
  METRIC_HOSTS=${#hosts[@]}
  if [[ ${#hosts[@]} -eq 0 ]]; then
    print_result FAIL hosts "no hosts provided and no PS_HOST_* variables found"
    failures=$((failures + 1))
  else
    print_result INFO hosts "${#hosts[@]} target(s)"
    for host in "${hosts[@]}"; do
      target="${ssh_user_prefix}${host}"
      if ssh -o BatchMode=yes -o ConnectTimeout="$ssh_timeout" "$target" "printf 'connected:%s\\n' \"\$(hostname 2>/dev/null || uname -n)\"" >/tmp/psdebug_preflight.$$ 2>/tmp/psdebug_preflight_err.$$; then
        detail="$(tr -d '\n' </tmp/psdebug_preflight.$$)"
        print_result OK "$host" "$detail"
      else
        detail="$(tr -d '\n' </tmp/psdebug_preflight_err.$$)"
        print_result FAIL "$host" "ssh check failed${detail:+: $detail}"
        failures=$((failures + 1))
      fi
    done
    rm -f /tmp/psdebug_preflight.$$ /tmp/psdebug_preflight_err.$$
  fi
fi

METRIC_FAILURES=$failures

if [[ $failures -gt 0 ]]; then
  print_result FAIL summary "$failures check(s) failed"
  exit 1
fi

print_result OK summary "all checks passed"
