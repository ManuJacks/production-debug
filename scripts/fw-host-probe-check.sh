#!/usr/bin/env bash
# fw-host-probe-check.sh - Host and port probe helper based on observed
# canada-platform-checkfirewall runtime behavior.
#
# Usage (SCP then execute):
#   scp scripts/fw-host-probe-check.sh ${SSH_USER}@${PS_HOST_01}:/tmp/
#   ssh ${SSH_USER}@${PS_HOST_01} 'bash /tmp/fw-host-probe-check.sh'
#
# Usage (stream over SSH without copying):
#   ssh ${SSH_USER}@${PS_HOST_01} 'bash -s' < scripts/fw-host-probe-check.sh
#
# Optional environment variable overrides:
#   PROBE_HOSTS       - Space-separated host list. If set, HOSTS_FILE is ignored.
#   HOSTS_FILE        - File with one hostname per line.
#                       Default: ./third_party/checkfirewall-image-1.4.13/observed-host-probes.txt
#   PROBE_PORTS       - Space-separated TCP ports to test (default: "443 80")
#   CONNECT_TIMEOUT   - TCP connect timeout seconds (default: 5)
#   CURL_TIMEOUT      - curl timeout seconds (default: 10)
#   CURL_INSECURE     - Set to 1 to use curl --insecure (default: 0)
#   SHOW_DNS          - Set to 0 to skip DNS output (default: 1)

set -euo pipefail

PROBE_HOSTS="${PROBE_HOSTS:-}"
HOSTS_FILE="${HOSTS_FILE:-./third_party/checkfirewall-image-1.4.13/observed-host-probes.txt}"
PROBE_PORTS="${PROBE_PORTS:-443 80}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-5}"
CURL_TIMEOUT="${CURL_TIMEOUT:-10}"
CURL_INSECURE="${CURL_INSECURE:-0}"
SHOW_DNS="${SHOW_DNS:-1}"

DIVIDER="========================================"

section() {
  echo ""
  echo "${DIVIDER}"
  echo "  $1"
  echo "${DIVIDER}"
}

emit_hosts() {
  if [[ -n "${PROBE_HOSTS}" ]]; then
    for h in ${PROBE_HOSTS}; do
      echo "${h}"
    done
    return
  fi

  if [[ ! -f "${HOSTS_FILE}" ]]; then
    echo "ERROR: host list file not found: ${HOSTS_FILE}" >&2
    echo "Provide PROBE_HOSTS or a valid HOSTS_FILE." >&2
    exit 1
  fi

  awk 'NF && $1 !~ /^#/' "${HOSTS_FILE}" | tr -d '\r'
}

tcp_check() {
  local host="$1"
  local port="$2"

  if command -v nc >/dev/null 2>&1; then
    if nc -z -w "${CONNECT_TIMEOUT}" "${host}" "${port}" >/dev/null 2>&1; then
      echo "OPEN"
    else
      echo "CLOSED/FILTERED"
    fi
    return
  fi

  if command -v timeout >/dev/null 2>&1; then
    if timeout "${CONNECT_TIMEOUT}" bash -c "</dev/tcp/${host}/${port}" >/dev/null 2>&1; then
      echo "OPEN"
    else
      echo "CLOSED/FILTERED"
    fi
    return
  fi

  echo "SKIPPED (nc/timeout unavailable)"
}

http_check() {
  local host="$1"
  local scheme="$2"
  local curl_opts=(-sS -o /dev/null -w "%{http_code}" --max-time "${CURL_TIMEOUT}")

  if [[ "${CURL_INSECURE}" == "1" ]]; then
    curl_opts+=(--insecure)
  fi

  if ! command -v curl >/dev/null 2>&1; then
    echo "curl unavailable"
    return
  fi

  local code
  if code=$(curl "${curl_opts[@]}" "${scheme}://${host}" 2>/dev/null); then
    echo "${code}"
  else
    echo "curl-failed"
  fi
}

section "FW HOST PROBE CHECK"
echo "Date/Time        : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Hosts source     : ${HOSTS_FILE} (ignored when PROBE_HOSTS is set)"
echo "Ports            : ${PROBE_PORTS}"
echo "Connect timeout  : ${CONNECT_TIMEOUT}s"
echo "Curl timeout     : ${CURL_TIMEOUT}s"
echo "Curl insecure    : ${CURL_INSECURE}"

host_count=0
emit_hosts | while IFS= read -r host; do
  [[ -z "${host}" ]] && continue
  host_count=$((host_count + 1))

  echo ""
  echo "Host: ${host}"

  if [[ "${SHOW_DNS}" == "1" ]]; then
    if command -v getent >/dev/null 2>&1; then
      dns_out=$(getent hosts "${host}" 2>/dev/null | awk '{print $1}' | paste -sd ',' -)
      [[ -z "${dns_out}" ]] && dns_out="unresolved"
      echo "  DNS            : ${dns_out}"
    elif command -v host >/dev/null 2>&1; then
      dns_out=$(host "${host}" 2>/dev/null | tr '\n' '; ')
      [[ -z "${dns_out}" ]] && dns_out="unresolved"
      echo "  DNS            : ${dns_out}"
    else
      echo "  DNS            : skipped (no getent/host)"
    fi
  fi

  for port in ${PROBE_PORTS}; do
    status=$(tcp_check "${host}" "${port}")
    echo "  TCP ${port}        : ${status}"
  done

  https_status=$(http_check "${host}" "https")
  http_status=$(http_check "${host}" "http")
  echo "  HTTPS /        : ${https_status}"
  echo "  HTTP  /        : ${http_status}"
done

section "COMPLETE"
echo "Probe run finished."
