#!/usr/bin/env bash

set -u

# KPI metric summary reporter
#
# Purpose:
# - parse METRIC lines from file, directory, or stdin
# - compute platform KPI summaries for incident tooling
#
# Examples:
# - bash scripts/kpi_report.sh ./incident.log
# - bash scripts/kpi_report.sh ./snapshots --format json
# - cat ./incident.log | bash scripts/kpi_report.sh -

usage() {
  cat <<'EOF'
Usage: kpi_report.sh <source> [--format text|json]

Arguments:
- source                 File path, directory path, or '-' for stdin

Options:
- --format text|json     Output format (default: text)
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
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

raw = os.environ.get("METRIC_LINES", "")
out_format = os.environ.get("OUTPUT_FORMAT", "text")

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

if not records:
    empty = {
        "total_events": 0,
        "success_rate_pct": 0.0,
        "p50_duration_s": 0.0,
        "failure_counts_by_script": {},
        "per_script": {},
    }
    if out_format == "json":
        print(json.dumps(empty, indent=2, sort_keys=True))
    else:
        print("KPI report")
        print("- events: 0")
        print("- success_rate_pct: 0.00")
        print("- p50_duration_s: 0.00")
        print("- failures_by_script: none")
    sys.exit(0)


def to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


successes = 0
all_durations = []
failure_counts = Counter()
per_script = defaultdict(lambda: {"events": 0, "successes": 0, "durations": []})

for row in records:
    script = row.get("script", "unknown")
    status = row.get("status", "unknown").lower()
    duration = to_float(row.get("duration_s", "0"), 0.0)

    per_script[script]["events"] += 1
    per_script[script]["durations"].append(duration)
    all_durations.append(duration)

    if status == "success":
        successes += 1
        per_script[script]["successes"] += 1
    else:
        failure_counts[script] += 1

success_rate = (successes / len(records)) * 100.0 if records else 0.0
p50 = statistics.median(all_durations) if all_durations else 0.0

per_script_summary = {}
for script, info in sorted(per_script.items()):
    events = info["events"]
    script_success_rate = (info["successes"] / events) * 100.0 if events else 0.0
    script_p50 = statistics.median(info["durations"]) if info["durations"] else 0.0
    per_script_summary[script] = {
        "events": events,
        "success_rate_pct": round(script_success_rate, 2),
        "p50_duration_s": round(script_p50, 2),
    }

report = {
    "total_events": len(records),
    "success_rate_pct": round(success_rate, 2),
    "p50_duration_s": round(p50, 2),
    "failure_counts_by_script": dict(sorted(failure_counts.items())),
    "per_script": per_script_summary,
}

if out_format == "json":
    print(json.dumps(report, indent=2, sort_keys=True))
    sys.exit(0)

print("KPI report")
print(f"- events: {report['total_events']}")
print(f"- success_rate_pct: {report['success_rate_pct']:.2f}")
print(f"- p50_duration_s: {report['p50_duration_s']:.2f}")
if report["failure_counts_by_script"]:
    failures = ", ".join(
        f"{script}={count}" for script, count in report["failure_counts_by_script"].items()
    )
    print(f"- failures_by_script: {failures}")
else:
    print("- failures_by_script: none")

print("- per_script:")
for script, info in report["per_script"].items():
    print(
        f"  - {script}: events={info['events']} success_rate_pct={info['success_rate_pct']:.2f} "
        f"p50_duration_s={info['p50_duration_s']:.2f}"
    )
PY
