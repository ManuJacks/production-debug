# CLI reference

| Command | Purpose | Exit behavior |
|---|---|---|
| `scripts/incident_preflight.sh` | Validate local and incident prerequisites | Non-zero for failed required checks |
| `scripts/remote_dns_tls_check.sh` | Check DNS, TCP, and TLS to an endpoint | Non-zero when a check fails |
| `scripts/incident_bundle.sh` | Create a redacted, checksummed evidence archive | Non-zero on invalid input or packaging failure |
| `scripts/kpi_collect.sh` | Normalize `METRIC|` records | Non-zero for missing or invalid input |
| `scripts/kpi_report.sh` | Report aggregate incident-tool metrics | Non-zero for unreadable input |
| `scripts/kpi_compare.sh` | Compare baseline and candidate metrics | Non-zero for invalid sources |
| `scripts/fw-host-probe-check.sh` | Test approved host/port reachability | Non-zero when one or more probes fail |

Run any command with `--help` for options. Treat all output as potentially sensitive and use the evidence-handling procedure before sharing it.
