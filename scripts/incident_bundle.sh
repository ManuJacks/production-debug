#!/usr/bin/env bash

set -u

# Incident artifact bundler
#
# Purpose:
# - package selected incident artifacts into a timestamped directory and tar.gz
# - generate metadata and KPI summaries from METRIC lines when present
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

if [[ ${#artifacts[@]} -eq 0 && -e "telemetry" ]]; then
  artifacts+=("telemetry")
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
bundle_name="${bundle_name_prefix}-${timestamp}"
bundle_dir="${bundle_root_dir%/}/${bundle_name}"
payload_dir="${bundle_dir}/payload"
reports_dir="${bundle_dir}/reports"
mkdir -p "$payload_dir" "$reports_dir"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
  repo_sha="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
fi

cat >"${bundle_dir}/metadata.json" <<EOF
{
  "bundle_name": "${bundle_name}",
  "created_utc": "${timestamp}",
  "copied_artifact_count": ${copy_count},
  "repo_sha": "${repo_sha}",
  "host": "$(hostname 2>/dev/null || echo unknown)",
  "user": "${USER:-unknown}"
}
EOF

if [[ -d "$payload_dir" ]]; then
  bash "$script_dir/kpi_collect.sh" "$payload_dir" --format csv >"${reports_dir}/kpi.csv" || true
  bash "$script_dir/kpi_report.sh" "$payload_dir" >"${reports_dir}/kpi-report.txt" || true
  bash "$script_dir/kpi_report.sh" "$payload_dir" --format json >"${reports_dir}/kpi-summary.json" || true
fi

archive_path="${bundle_root_dir%/}/${bundle_name}.tar.gz"
tar -czf "$archive_path" -C "$bundle_root_dir" "$bundle_name"

echo "bundle_dir=$bundle_dir"
echo "archive_path=$archive_path"
