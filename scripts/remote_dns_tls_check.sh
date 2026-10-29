#!/usr/bin/env bash

set -u

usage() {
  cat <<'EOF'
Usage: remote_dns_tls_check.sh <endpoint> [host ...]

Collect DNS resolution and TLS handshake diagnostics from one or more remote
hosts for a single endpoint.

Host discovery:
- explicit host arguments
- otherwise PS_HOST_* environment variables

Optional environment variables:
- SSH_USER             SSH username prefix for remote checks
- PS_SSH_TIMEOUT       SSH timeout in seconds, default: 10
- PS_SNAPSHOT_DIR      Local output directory, default: ./snapshots
- PS_TLS_PORT          Target TLS port, default: 443
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "An endpoint argument is required." >&2
  exit 2
fi

endpoint="$1"
shift

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

hosts=()
mapfile -t hosts < <(discover_hosts "$@")
if [[ ${#hosts[@]} -eq 0 ]]; then
  echo "No hosts provided and no PS_HOST_* variables found." >&2
  exit 2
fi

timestamp="$(date '+%Y%m%d-%H%M%S')"
snapshot_root="${PS_SNAPSHOT_DIR:-./snapshots}/dns-tls-${timestamp}"
mkdir -p "$snapshot_root"

ssh_timeout="${PS_SSH_TIMEOUT:-10}"
tls_port="${PS_TLS_PORT:-443}"
ssh_user_prefix=""
if [[ -n "${SSH_USER:-}" ]]; then
  ssh_user_prefix="${SSH_USER}@"
fi

remote_script=$(cat <<EOF
set -u
endpoint="$endpoint"
tls_port="$tls_port"
echo "=== HOST ==="
hostname 2>/dev/null || uname -n
echo
echo "=== DNS LOOKUP ==="
if command -v getent >/dev/null 2>&1; then
  getent hosts "$endpoint" 2>&1 || true
else
  nslookup "$endpoint" 2>&1 || true
fi
echo
echo "=== TCP CONNECTIVITY ==="
if command -v timeout >/dev/null 2>&1 && command -v bash >/dev/null 2>&1; then
  timeout 8 bash -lc "</dev/tcp/$endpoint/$tls_port" >/dev/null 2>&1 && echo "tcp connect ok" || echo "tcp connect failed"
else
  echo "timeout or bash not available for TCP test"
fi
echo
echo "=== TLS HANDSHAKE ==="
if command -v openssl >/dev/null 2>&1; then
  printf '' | openssl s_client -connect "$endpoint:$tls_port" -servername "$endpoint" -brief 2>&1 | sed -n '1,20p'
else
  echo "openssl not available"
fi
echo
echo "=== HTTPS HEAD ==="
if command -v curl >/dev/null 2>&1; then
  curl -I -sS --max-time 10 "https://$endpoint:$tls_port" 2>&1 | sed -n '1,20p'
else
  echo "curl not available"
fi
EOF
)

failed_hosts=0
for host in "${hosts[@]}"; do
  target="${ssh_user_prefix}${host}"
  output_file="${snapshot_root}/${host}.txt"
  echo "Collecting DNS/TLS diagnostics from ${target} -> ${output_file}"
  if ! ssh -o BatchMode=yes -o ConnectTimeout="$ssh_timeout" "$target" "$remote_script" >"$output_file" 2>&1; then
    echo "DNS/TLS diagnostics failed for ${target}; see ${output_file}" >&2
    failed_hosts=$((failed_hosts + 1))
  fi
done

echo "Diagnostics written to ${snapshot_root}"

if [[ $failed_hosts -gt 0 ]]; then
  echo "${failed_hosts} host(s) failed DNS/TLS diagnostics." >&2
  exit 1
fi
