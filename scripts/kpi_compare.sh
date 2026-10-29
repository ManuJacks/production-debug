#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: kpi_compare.sh <baseline_source> <candidate_source> [--format text|json]

Compare KPI summaries between two telemetry sources and report deltas.

Arguments:
- baseline_source        File, directory, or '-' compatible with kpi_report.sh
- candidate_source       File, directory, or '-' compatible with kpi_report.sh

Options:
- --format text|json     Output format (default: text)
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 ]]; then
  echo "baseline_source and candidate_source are required." >&2
  exit 2
fi

baseline_source="$1"
candidate_source="$2"
shift 2

output_format="text"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --format)
      output_format="${2:-}"
      if [[ "$output_format" != "text" && "$output_format" != "json" ]]; then
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

baseline_json="$(bash scripts/kpi_report.sh "$baseline_source" --format json)"
candidate_json="$(bash scripts/kpi_report.sh "$candidate_source" --format json)"

BASELINE_JSON="$baseline_json" CANDIDATE_JSON="$candidate_json" OUTPUT_FORMAT="$output_format" python3 - <<'PY'
import json
import os
import sys


def as_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


baseline = json.loads(os.environ.get("BASELINE_JSON", "{}") or "{}")
candidate = json.loads(os.environ.get("CANDIDATE_JSON", "{}") or "{}")
out_format = os.environ.get("OUTPUT_FORMAT", "text")

b_events = int(baseline.get("total_events", 0) or 0)
c_events = int(candidate.get("total_events", 0) or 0)
b_success = as_float(baseline.get("success_rate_pct", 0.0))
c_success = as_float(candidate.get("success_rate_pct", 0.0))
b_p50 = as_float(baseline.get("p50_duration_s", 0.0))
c_p50 = as_float(candidate.get("p50_duration_s", 0.0))

comparison = {
    "baseline": {
        "total_events": b_events,
        "success_rate_pct": round(b_success, 2),
        "p50_duration_s": round(b_p50, 2),
    },
    "candidate": {
        "total_events": c_events,
        "success_rate_pct": round(c_success, 2),
        "p50_duration_s": round(c_p50, 2),
    },
    "delta": {
        "events": c_events - b_events,
        "success_rate_pct": round(c_success - b_success, 2),
        "p50_duration_s": round(c_p50 - b_p50, 2),
    },
}

if out_format == "json":
    print(json.dumps(comparison, indent=2, sort_keys=True))
    sys.exit(0)

print("KPI comparison")
print(f"- baseline_events: {comparison['baseline']['total_events']}")
print(f"- candidate_events: {comparison['candidate']['total_events']}")
print(f"- delta_events: {comparison['delta']['events']}")
print(f"- baseline_success_rate_pct: {comparison['baseline']['success_rate_pct']:.2f}")
print(f"- candidate_success_rate_pct: {comparison['candidate']['success_rate_pct']:.2f}")
print(f"- delta_success_rate_pct: {comparison['delta']['success_rate_pct']:.2f}")
print(f"- baseline_p50_duration_s: {comparison['baseline']['p50_duration_s']:.2f}")
print(f"- candidate_p50_duration_s: {comparison['candidate']['p50_duration_s']:.2f}")
print(f"- delta_p50_duration_s: {comparison['delta']['p50_duration_s']:.2f}")
PY
