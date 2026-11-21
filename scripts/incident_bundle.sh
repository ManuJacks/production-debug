#!/usr/bin/env bash

set -euo pipefail

# Incident artifact bundler
#
# Purpose:
# - package selected incident artifacts into a timestamped directory and tar.gz
# - generate metadata and KPI summaries from METRIC lines when present
# - redact recognized secret patterns, then verify the bundle before archiving
#
# Fail-closed: if sanitization or verification fails, the partial bundle
# directory is deleted and no archive is produced.
#
# Example:
# - bash scripts/incident_bundle.sh ./bundles ./telemetry ./snapshots
# - bash scripts/incident_bundle.sh ./bundles ./incident.log --name auth-outage

usage() {
  cat <<'EOF'
Usage: incident_bundle.sh <bundle_root_dir> [artifact_path ...] [--name <bundle_name_prefix>]

Arguments:
- bundle_root_dir         Root output directory for bundle and tar.gz
- artifact_path           File or directory to include (repeatable)

Options:
- --name <prefix>         Optional bundle name prefix (default: incident)

Environment:
- PRODUCTION_DEBUG_PYTHON Python interpreter used for sanitization (default: python3)
- PRODUCTION_DEBUG_HOME   Directory containing the production_debug package
                          (default: the repository root next to this script, then /app)
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "bundle_root_dir is required." >&2
  exit 2
fi

bundle_root_dir="$1"
shift
bundle_name_prefix="incident"
artifacts=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      bundle_name_prefix="${2:-}"
      if [[ -z "$bundle_name_prefix" ]]; then
        echo "--name requires a non-empty value." >&2
        exit 2
      fi
      shift 2
      ;;
    *)
      artifacts+=("$1")
      shift
      ;;
  esac
done

if [[ ! "$bundle_name_prefix" =~ ^[A-Za-z0-9._-]{1,64}$ ]]; then
  echo "--name must match [A-Za-z0-9._-]{1,64}." >&2
  exit 2
fi

if [[ ${#artifacts[@]} -eq 0 && -e "telemetry" ]]; then
  artifacts+=("telemetry")
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PRODUCTION_DEBUG_PYTHON:-python3}"
package_path="${PRODUCTION_DEBUG_HOME:-}"
if [[ -z "$package_path" ]]; then
  if [[ -d "$script_dir/../production_debug" ]]; then
    package_path="$(cd "$script_dir/.." && pwd)"
  else
    package_path="/app"
  fi
fi

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "python3 is required for bundle sanitization; no bundle created." >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
bundle_name="${bundle_name_prefix}-${timestamp}"
bundle_dir="${bundle_root_dir%/}/${bundle_name}"
archive_path="${bundle_root_dir%/}/${bundle_name}.tar.gz"
payload_dir="${bundle_dir}/payload"
reports_dir="${bundle_dir}/reports"

if [[ -e "$bundle_dir" || -e "$archive_path" ]]; then
  echo "Bundle already exists: $bundle_dir" >&2
  exit 1
fi

completed=0
cleanup_on_failure() {
  if [[ $completed -ne 1 ]]; then
    rm -rf -- "$bundle_dir" "$archive_path"
    echo "Bundle creation failed; partial bundle removed." >&2
  fi
}
trap cleanup_on_failure EXIT

mkdir -p "$payload_dir" "$reports_dir"

run_python() {
  PYTHONPATH="${package_path}${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" "$@"
}

copy_count=0
for path in "${artifacts[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "Skipping missing artifact: $path" >&2
    continue
  fi

  name="$(basename "$path")"
  target="${payload_dir}/${name}"

  if [[ -d "$path" ]]; then
    cp -R "$path" "$target"
  else
    cp "$path" "$target"
  fi
  copy_count=$((copy_count + 1))
done

repo_sha="unknown"
if command -v git >/dev/null 2>&1; then
  repo_sha="$(git -C "$script_dir" rev-parse --short HEAD 2>/dev/null || echo unknown)"
fi

run_python - "${bundle_dir}/metadata.json" "$bundle_name" "$timestamp" \
  "$copy_count" "$repo_sha" "$(hostname 2>/dev/null || echo unknown)" \
  "${USER:-unknown}" <<'PY'
import json
import sys

path, name, created, count, sha, host, user = sys.argv[1:8]
with open(path, "w", encoding="utf-8") as fh:
    json.dump(
        {
            "bundle_name": name,
            "created_utc": created,
            "copied_artifact_count": int(count),
            "repo_sha": sha,
            "host": host,
            "user": user,
        },
        fh,
        indent=2,
    )
    fh.write("\n")
PY

bash "$script_dir/kpi_collect.sh" "$payload_dir" --format csv >"${reports_dir}/kpi.csv" || true
bash "$script_dir/kpi_report.sh" "$payload_dir" >"${reports_dir}/kpi-report.txt" || true
bash "$script_dir/kpi_report.sh" "$payload_dir" --format json >"${reports_dir}/kpi-summary.json" || true

# Remove high-risk credential files and redact recognized secret patterns.
run_python - "$bundle_dir" <<'PY'
import sys

from production_debug.sanitizer import sanitize_directory_tree

result = sanitize_directory_tree(sys.argv[1])
print(f"Sanitization complete: {result}", file=sys.stderr)
PY

# Belt-and-braces removal of high-risk files.
find "$bundle_dir" -type f \( -name "*.pem" -o -name "*.key" -o -name "*id_rsa*" -o -name ".env*" -o -name "*kubeconfig*" \) -delete

# Verify before archiving: any remaining recognized secret pattern aborts.
verification_tmp="$(mktemp)"
if ! run_python -m production_debug.bundle_verifier "$bundle_dir" >"$verification_tmp"; then
  cat "$verification_tmp" >&2
  rm -f -- "$verification_tmp"
  exit 1
fi
mv -- "$verification_tmp" "${bundle_root_dir%/}/${bundle_name}.verification.json"

tar -czf "$archive_path" -C "$bundle_root_dir" "$bundle_name"

completed=1
echo "bundle_dir=$bundle_dir"
echo "archive_path=$archive_path"
echo "verification_report=${bundle_root_dir%/}/${bundle_name}.verification.json"
