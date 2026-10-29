#!/usr/bin/env bash

set -u

# KPI metric collector
#
# Purpose:
# - collect METRIC lines from a file, directory, or stdin
# - normalize into CSV or JSON records for downstream reporting
#
# Examples:
# - bash scripts/kpi_collect.sh ./incident.log
# - bash scripts/kpi_collect.sh ./snapshots --format json
# - cat ./incident.log | bash scripts/kpi_collect.sh - --format csv

usage() {
  cat <<'EOF'
Usage: kpi_collect.sh <source> [--format csv|json]

Arguments:
- source                 File path, directory path, or '-' for stdin

Options:
- --format csv|json      Output format (default: csv)
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  echo "source is required." >&2
  exit 2
fi

source_path="$1"
shift
output_format="csv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --format)
      output_format="${2:-}"
      if [[ "$output_format" != "csv" && "$output_format" != "json" ]]; then
        echo "Invalid --format value: $output_format" >&2
        exit 2
      fi
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$source_path" == "-" ]]; then
  metric_lines="$(cat)"
elif [[ -f "$source_path" ]]; then
  metric_lines="$(grep -h '^METRIC|' "$source_path" || true)"
elif [[ -d "$source_path" ]]; then
  metric_lines="$(grep -R -h '^METRIC|' "$source_path" 2>/dev/null || true)"
else
  echo "Source not found: $source_path" >&2
  exit 1
fi

METRIC_LINES="$metric_lines" OUTPUT_FORMAT="$output_format" python3 - <<'PY'
import csv
import io
import json
import os
import sys

raw = os.environ.get("METRIC_LINES", "")
out_format = os.environ.get("OUTPUT_FORMAT", "csv")

records = []
for line in raw.splitlines():
    line = line.strip()
    if not line.startswith("METRIC|"):
        continue
    parts = line.split("|")[1:]
    row = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        row[key] = value
    if row:
        records.append(row)

if out_format == "json":
    print(json.dumps(records, indent=2, sort_keys=True))
    sys.exit(0)

base_cols = ["script", "status", "exit_code", "duration_s"]
extra_cols = sorted({k for r in records for k in r.keys() if k not in base_cols})
columns = base_cols + extra_cols

writer = csv.DictWriter(sys.stdout, fieldnames=columns)
writer.writeheader()
for r in records:
    writer.writerow({k: r.get(k, "") for k in columns})
PY
