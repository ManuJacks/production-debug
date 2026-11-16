# New Features Roadmap

This roadmap prioritizes one outcome: **make incident response resilient to handoffs and knowledge concentration, so the response does not depend on one person holding the whole picture.**

The existing Kubernetes, Azure, Linux and artifact diagnostics remain useful capabilities in service of that outcome. A synthetic supply-chain incident is the first demanding cross-team exercise, not a commitment to turn the project into a supply-chain scanner or to build every enterprise integration.

The project can make evidence, procedures, ownership and gaps easier to share. It cannot grant incident authority, compel organizational coordination or replace human judgment; those remain organizational responsibilities.

## What success looks like

An engineer who was not privately briefed can use the published procedures and evidence to continue an investigation, identify what is known and unknown, and make a safe handoff. The team can see who owns each action, what authorization is required, and how recovery or containment will be independently verified.

The five highest-leverage moves are:

1. **Shared incident record:** record source-attributed observations, hypotheses, decisions, owners, unknowns and verification.
2. **Runnable procedures:** make escalation, investigation boundaries, artifact response and credential rotation steps explicit without handling secret values.
3. **Handoff-tested exercises:** have a responder who lacks private context take over using only the record and evidence.
4. **Failure-path confidence:** test that the actual scripts and procedures behave clearly when dependencies are unavailable or evidence is incomplete.
5. **Evidence of outcomes:** report exercise results and follow-up actions; make no production-impact claims without real, approved evidence.

## 30-60-90 Day Execution Plan

### Days 1-30: Make the response transferable

Primary objective:

- Define and exercise the shared incident record and handoff model

Deliverables:

1. Publish the incident evidence and handoff template.
2. Add a synthetic supply-chain scenario with distinct upstream-source and internal-artifact evidence.
3. Run a handoff exercise in which a previously unbriefed responder takes over from the written record.
4. Record ambiguous authority, missing information and unsafe or unavailable procedure steps as follow-up actions.

Success metrics:

- The incoming responder can state impact, verified findings, unknowns, next owner and stop conditions without private coaching.
- Decisions and actions have explicit owners and authorization requirements.
- Exercise gaps are assigned owners rather than left as undocumented observations.

### Days 31-60: Make procedures executable

Primary objective:

- Turn the exercise gaps into reviewable procedures and reliable diagnostic behavior

Deliverables:

1. Document local incident roles, approval paths and containment escalation without relying on rank or unwritten norms.
2. Add reusable checklists for credential rotation, revocation and dependent-system validation, and for internal artifact response versus upstream blocking.
3. Add failure-path tests for the diagnostic workflows used by the exercise.
4. Keep release provenance and signing work as a separate trust objective, rather than a substitute for incident-response readiness.

Success metrics:

- A responder can follow each procedure without inventing steps during the exercise.
- Credential and artifact actions have distinct completion and verification states.
- Missing authority or integrations are surfaced as gaps, not reported as successful actions.

### Days 61-90: Prove continuity and learn

Primary objective:

- Re-run the exercise with different responders and close the most important gaps

Deliverables:

1. Run a game day using the published procedures and synthetic evidence.
2. Publish an anonymized exercise summary with gaps, owners and follow-up actions.
3. Measure handoff completeness, unresolved evidence gaps and procedure blockers.
4. Repeat with a different responder; report observed results without claiming unmeasured production improvements.

Success metrics:

- A responder outside the original exercise can continue from the record.
- Every high-priority gap has an owner and review date.
- The team can distinguish exercise evidence from production adoption evidence.

Recommended implementation order:

1. Shared incident record and handoff procedure
2. Synthetic cross-team game day
3. Close the failure-path and procedure gaps found in the exercise
4. Measure repeatability and maintain the learning loop
5. Continue release provenance and other platform-quality work as parallel objectives

Recently implemented:

- Machine-readable support script catalog manifest (`scripts/script_catalog.json`) with README auto-generation and CI drift check.
- Incident bundle packager (`scripts/incident_bundle.sh`) to archive artifacts, metadata, and KPI reports for postmortems.
- KPI baseline/candidate comparison utility (`scripts/kpi_compare.sh`) for measurable before/after deltas.
- Artifactory package-resolution and 502 triage scripts now emit optional telemetry (`PS_METRICS=1`) for KPI evidence capture.
- KPI publishing workflow emits a SHA256 manifest for its KPI output artifacts.
- Tooling outcome template (`docs/procedures/TOOLING_OUTCOME_TEMPLATE.md`) for repeatable exercise and adoption measurement.

## Priority 1: Integration Test Realism

Status:

- Baseline implemented: dispatcher integration tests with fake tool fixtures added.
- Remaining work: expand fixture matrix to cover remote SSH/Vault flows and add CI integration test stage boundaries.

### Feature: Integration harness for script execution flows

Goal:

- Validate real command wiring and failure handling, not only argument parsing.

Implementation steps:

1. Add a test fixture layer that creates temporary fake host commands (`ssh`, `tiller`, `vault` wrappers) in a test-only PATH.
2. Add integration tests for dispatcher command routing in `scripts/psdebug_ops.sh`.
3. Add failure-injection tests for high-risk scripts:
   - `scripts/rhel8_mtab_repair.sh`
   - `scripts/vault_path_probe.sh`
   - `scripts/tiller_render_diff.sh`
4. Add a CI job stage for integration tests with clear timeout boundaries.

Definition of done:

- Integration test suite runs in CI.
- At least one happy-path and one failure-path test per high-risk script.

## Priority 2: KPI Telemetry Automation

Status:

- COMPLETE: `kpi_collect.sh` and `kpi_report.sh` added with deterministic test coverage.
- COMPLETE: Weekly scheduled `kpi-publish.yml` workflow posts job summary and uploads CSV/JSON artifacts.
- COMPLETE: `docs/grafana_kpi_dashboard.json` Grafana import starter added.

### Feature: KPI collector and summary reporting

Goal:

- Turn `METRIC|...` lines into measurable weekly platform outcomes.

Implementation steps:

1. Add `scripts/kpi_collect.sh` to gather metric lines from log artifacts into normalized CSV.
2. Add `scripts/kpi_report.sh` to calculate key indicators:
   - success rate
   - p50 duration
   - failure categories by script
3. Add JSON output option for report automation.
4. Add sample dashboard import JSON under `docs/` for quick graphing in Grafana or similar.

Definition of done:

- KPI report generated automatically from sample telemetry.
- Report output is deterministic and test-covered.
- Dashboard import starter is available under `docs/`.

## Priority 3: Supply Chain and CI Hardening

Status:

- PARTIAL: Actions in `kpi-publish.yml` are pinned to commit SHAs; `ci.yml` and `publish-container.yml` still use version tags.
- COMPLETE: `dependency-audit` CI job added (`pip-audit` on every push).
- COMPLETE: Container image signing and SBOM attachment are configured in `.github/workflows/publish-container.yml`.
- Remaining: signed build-provenance attestation; it is distinct from signing the image or attaching an SBOM.

### Feature: Stronger build integrity controls

Goal:

- Reduce CI/CD supply-chain risk and improve auditability.

Implementation steps:

1. Pin third-party GitHub Actions to commit SHAs across all workflows.
2. Add dependency vulnerability scan step (for Python dev dependencies and shell tooling references).
3. Add SBOM generation for release artifacts.
4. Keep release-policy instructions aligned with the actual publishing workflow.
5. If repository eligibility and a concrete need are established, add a build-provenance attestation workflow and document how consumers verify it.

Definition of done:

- All third-party action references use immutable commit SHAs.
- Published container images are signed and have an attached SBOM.
- Any future build-provenance attestation is independently verifiable and described accurately in release documentation.

## Priority 4: Architecture Decision Records

Status:

- COMPLETE: `docs/adr/` contains accepted decisions for safe-by-default execution, telemetry, SSH access, MCP diagnostics and GitOps.
- REMAINING: compatibility and deprecation expectations are not yet captured in a dedicated ADR.

### Feature: ADR baseline for platform safety and compatibility

Goal:

- Make engineering decisions durable and auditable.

Implementation steps:

1. Add an accepted ADR for compatibility and deprecation expectations.
2. Keep the ADR directory linked from contributor and project documentation.

Definition of done:

- Compatibility and deprecation expectations are explicit.
- Existing accepted decisions remain discoverable from the README.

## Priority 5: Operational Readiness Program

Status:

- PARTIAL: quarterly checklist doc added at `docs/procedures/GAME_DAY_CHECKLIST.md`.
- Remaining: runbook validation script and at least one completed game-day evidence pack.

### Feature: Incident game-day and runbook validation

Goal:

- Prove that another responder can continue an investigation from the published procedures and evidence.

Implementation steps:

1. Add a quarterly game-day checklist doc. (complete)
2. Add runbook validation script to ensure all documented commands still execute.
3. Track outcomes from each game-day and publish improvements in changelog or release notes.

Definition of done:

- A repeatable game-day process exists.
- At least one completed run is documented with follow-up actions.

## Priority 6: Platform Productization And Adoption

### Feature: Make the repo operate like an internal platform product

Goal:

- Prove the repository is not only technically strong, but also maintainable, owned, and adoptable across teams

Implementation steps:

## Priority 7: Incident Troubleshooting Backlog (Post-Current Implementation)

Status:

- COMPLETE in toolkit: API-driven package resolution checks for Artifactory package-manager failure modes.
- COMPLETE in toolkit: API-driven 502 triage classifier for edge/proxy vs service vs backend dependency faults.
- Remaining backlog tracked below.

### Remaining item A: Token/auth expiry and identity diagnostics

Goal:

- Add focused checks for token validity windows, auth provider drift, LDAP reachability, and permission mismatch symptoms.

Candidate implementation:

1. Add `scripts/artifactory-auth-token-audit.sh`.
2. Validate API auth path, token expiry signals, and optional LDAP endpoint reachability.
3. Flag likely causes for 401/403 bursts and set-me-up credential mismatch issues.

### Remaining item B: Upgrade and HA startup preflight

Goal:

- Catch upgrade blockers and HA node bring-up failures before and immediately after rollout.

Candidate implementation:

1. Add `scripts/artifactory-upgrade-ha-preflight.sh`.
2. Validate join-key consistency, node readiness, and migration health.
3. Produce pass/fail gate output suitable for change windows.

### Remaining item C: Replication runtime lag/degradation checks

Goal:

- Extend current replication config audit with runtime liveness and lag checks.

Candidate implementation:

1. Add `scripts/artifactory-replication-runtime-check.sh`.
2. Report per-repository lag indicators, last-success age, and persistent failure states.
3. Correlate with target endpoint reachability where possible.

### Remaining item D: Artifact blob/integrity triage

Goal:

- Speed diagnosis for unknown blob or storage consistency symptoms.

Candidate implementation:

1. Add `scripts/artifactory-blob-integrity-check.sh`.
2. Probe storage API signals, problematic repository scopes, and recent missing-blob patterns.
3. Emit remediation hints based on read-only findings.

1. Add a support matrix document covering tested operating systems, tmux expectations, shell assumptions, and required remote utilities.
2. Add a lightweight ownership model describing maintainers, review expectations, and who approves behavior-impacting changes.
3. Add issue and intake templates for bug reports, feature requests, and incident improvement requests.
4. Define a release readiness checklist that includes docs, changelog, compatibility review, and operator-impact review.

Definition of done:

- Support expectations are explicit.
- Ownership and review responsibilities are visible in the repo.
- New work enters through a repeatable intake path.
- Releases behave like product releases, not only code snapshots.

## Priority 8: Operational Evidence And Trust Loop

### Feature: Publish proof that the platform improves incident handling

Goal:

- Show repeated real-world value, not only engineering intent

Implementation steps:

1. Add an anonymized sample incident evidence pack showing logs, KPI report, bundled artifacts, and a short post-incident summary.
2. Add a quarterly platform review doc or template that records adoption, KPI trend movement, operational risks, and follow-up actions.
3. Publish a small set of before-and-after outcome examples such as improved handoff quality, reduced first-diagnostic time, or safer command execution.
4. Add a lightweight scorecard in docs that shows completion status for testing realism, governance, release trust, and operational validation.

Definition of done:

- The repo contains evidence of real or simulated operational improvement.
- Platform value can be explained with artifacts, not only claims.
- Maintainers have a recurring mechanism for reviewing whether the platform is still earning trust.
