# Tooling Outcome Evidence Template

Use this template to record evidence about whether an incident-tooling change improves selected exercise or operational outcomes. Lab results do not prove production impact; label the evidence source and scope.

## Incident metadata

- Incident or exercise ID:
- Date range:
- Environment:
- Services impacted:
- Responders:
- Change under evaluation:

## Before/after telemetry sources

- Baseline telemetry source:
- Candidate telemetry source:
- KPI comparison command:

```bash
bash scripts/kpi_compare.sh <baseline_source> <candidate_source>
```

## KPI deltas

Capture output from `scripts/kpi_compare.sh` here.

- Delta events:
- Delta success rate (%):
- Delta p50 duration (s):

## Failure-domain diagnostics evidence

For package resolution and 502 triage runs, capture representative output and metric lines.

- Package resolution sample output:
- 502 triage sample output:
- `METRIC|...` lines captured:

## Verification and trust evidence

- KPI artifact checksum manifest verified: yes/no
- Commands used:

```bash
sha256sum -c kpi-artifacts.sha256
```

## Adoption evidence

- Number of incidents using default toolkit panes with the new checks:
- Number of responders who executed the new checks:
- Hand-off quality notes:
- Postmortem references:

## Decision

- Promote change to standard incident workflow: yes/no
- Follow-up actions:
- Owner and target date:
