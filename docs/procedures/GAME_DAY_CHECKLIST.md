# Incident Game-Day Checklist

Use this checklist to run repeatable quarterly incident exercises and prove that the platform improves real production response behavior.

## Purpose

- Rehearse the shared tmux incident workflow under stress-like conditions.
- Validate that key runbooks and support scripts still work end to end.
- Capture measurable before/after evidence for operational outcomes.

## Cadence and ownership

- Frequency: quarterly (minimum).
- Owner: platform incident tooling owner.
- Required participants: incident commander, primary operator, secondary responder, observer/scribe.
- Recommended duration: 60 to 90 minutes.

## Pre-exercise checklist (T-14 to T-1 days)

- Confirm exercise date, participants, and communication channel.
- Select one scenario from the scenario catalog below.
- Confirm exercise environment and safety constraints.
- Confirm all responders can attach to a shared tmux session host.
- Confirm required environment variables are available on the host.
- Confirm baseline telemetry source exists for KPI delta comparison.
- Confirm evidence destination path for logs and artifacts.

## Scenario catalog (starter)

Pick one scenario each quarter and rotate coverage.

1. Vault unreachable
- Trigger condition: simulated network or auth failure to Vault.
- Expected tools: profiles/incident-toolkit.json and scripts/vault_path_probe.sh.
- Success criteria: responders classify failure domain and produce a validated next action list.

2. Jenkins agent degradation
- Trigger condition: queue growth and agent unavailability.
- Expected tools: profiles/multi-host.json, scripts/docker-health.sh, scripts/jcasc_render_precheck.sh.
- Success criteria: responders identify bottleneck component and verify mitigation path.

3. Artifact resolution disruption
- Trigger condition: package fetch failures and intermittent 502 responses.
- Expected tools: profiles/incident-toolkit.json, scripts/artifactory-package-resolution-check.sh, scripts/artifactory-502-triage.sh.
- Success criteria: responders classify fault domain and capture metric lines for evidence.

## Execution checklist (exercise day)

### A. Kickoff (10 minutes)

- State scenario, boundaries, and stop conditions.
- Assign roles: commander, driver, navigator, scribe.
- Start a shared tmux incident session.
- Confirm all participants can attach and observe commands.

### B. Runbook validation (15 to 25 minutes)

- Run local preflight checks.
- Run the scenario-specific script set.
- Validate at least one success path and one failure path output.
- Confirm script outputs are understandable by a non-driver responder.
- Record any command ambiguity, missing parameters, or unsafe defaults.

### C. Telemetry and evidence validation (15 to 20 minutes)

- Capture METRIC lines from scenario scripts (when available).
- Generate KPI report for the candidate exercise data.
- Generate KPI baseline delta report.
- Verify KPI checksum artifact generation command path.
- Draft evidence notes using docs/INCIDENT_EVIDENCE_TEMPLATE.md.

### D. Teamwork and handoff validation (10 to 15 minutes)

- Perform one role swap (driver to navigator or navigator to driver).
- Perform one handoff simulation to another responder.
- Confirm new responder can continue without private context.
- Record blockers to follow-the-sun continuity.

## Exit criteria

All criteria should be true before the exercise is marked complete.

- Shared session model validated by at least two responders.
- Scenario classified with explicit fault domain and next checks.
- Runbook path executed without hidden or private steps.
- KPI summary and KPI delta generated.
- Evidence template populated for the exercise.
- Follow-up actions assigned with owners and target dates.

## Scoring rubric

Use this lightweight score to track improvement quarter over quarter.

- 0: not attempted.
- 1: attempted but incomplete.
- 2: completed with minor issues.
- 3: completed cleanly and repeatably.

Score each dimension:

- Shared visibility and teamwork.
- Runbook clarity and completeness.
- Script reliability in failure paths.
- Evidence capture quality.
- Handoff readiness.

Total score target: 12 or higher (out of 15).

## Follow-up actions checklist

- Open remediation items for every blocker found.
- Link each blocker to a backlog item in docs/NEW_FEATURES.md or issue tracker.
- Add one changelog entry if a behavior-affecting fix is delivered.
- Schedule next quarterly game-day with a different scenario.

## Exercise record template

- Exercise ID:
- Date:
- Scenario:
- Participants:
- What worked:
- What failed:
- KPI delta summary:
- Evidence artifact locations:
- Follow-up actions and owners:
- Target completion date:
