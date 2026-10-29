# New Features Roadmap

This document tracks concrete next features to push the project from strong to top-tier platform engineering maturity.

## Fastest Path To Excellence.

If this repository is judged as a platform engineering sample, the shortest path from excellent to exceptional is not adding more scripts. It is proving that the current operating model is durable, governable, and trusted under organizational pressure.

The five highest-leverage moves are:

1. Integration realism
   Add failure-path and remote-command integration coverage for the highest-risk workflows so the repo proves command wiring, not only local unit behavior.
   Why it matters: elite platform engineering is trusted because it behaves correctly in the ugly paths, not only the happy paths.

2. Release provenance and signing
   Add release-time attestation, artifact signing, and verification steps so the project demonstrates supply-chain integrity beyond basic CI hardening.
   Why it matters: top-tier platform teams treat trust in the release artifact itself as a first-class product property.

3. ADR baseline
   Record the core engineering decisions behind safe-by-default execution, telemetry contracts, and compatibility policy.
   Why it matters: a 13/10 platform is not just well built; it is legible, defensible, and durable when teams or maintainers change.

4. Operational readiness evidence
   Add game-day execution, runbook validation, and documented follow-up actions that show the repo improves real incident response outcomes over time.
   Why it matters: operational excellence is proven through repeated use and learning loops, not only through clean code and documentation.

5. Outcome reporting
   Publish KPI trend summaries, incident bundle examples, and before/after operational results that demonstrate measurable value from adoption.
   Why it matters: platform engineering reaches the next tier when it can show reduced ambiguity, faster triage, safer changes, and better handoffs with evidence.

Definition of 13/10 for this repo:

- Trusted in failure paths, not only feature paths
- Governed by explicit engineering decisions
- Verifiable from source to release artifact
- Practiced through operational drills and daily use
- Able to show measurable improvement in incident outcomes

Additional requirements to reliably argue for a 13/13 rating:

- A documented support matrix for supported operating systems, shell assumptions, tmux versions, and expected remote tooling
- A clear ownership model for who maintains the platform, reviews changes, and approves behavior-affecting releases
- Adoption evidence showing that multiple engineers or teams use the repo repeatedly in real operational workflows
- A published example incident evidence pack showing telemetry, bundle artifacts, timeline, and post-incident learning loop output
- A standing review cadence for platform health, security posture, and roadmap execution rather than one-time implementation work

## 30-60-90 Day Execution Plan

### Days 1-30: Prove the risky paths

Primary objective:

- Raise confidence in real operational behavior, not only static correctness

Deliverables:

1. Expand integration fixtures to cover `ssh`, `vault`, and `tiller` command simulation.
2. Add failure-path tests for the highest-risk scripts and dispatcher flows.
3. Split CI into clearer stages so integration failures are isolated and visible.
4. Define a lightweight release checklist that includes SBOM verification and changelog hygiene.

Success metrics:

- Integration coverage exists for at least three high-risk workflows.
- CI distinguishes unit, integration, and shell quality failures.
- No undocumented behavior-changing merge lands without changelog coverage.

### Days 31-60: Make the platform governable

Primary objective:

- Turn current engineering choices into durable platform policy

Deliverables:

1. Add ADR template and initial accepted ADRs for safe-by-default execution, telemetry contract, and compatibility strategy.
2. Add release-time provenance design, including artifact signing approach and verification commands.
3. Update README and CONTRIBUTING to link the design decisions and release governance path.
4. Define compatibility expectations for script flags, dispatcher commands, and telemetry fields.

Success metrics:

- ADR baseline exists and is referenced by contributor documentation.
- Release process has a documented trust model from source to artifact.
- Backward-compatibility expectations are explicit instead of implied.

### Days 61-90: Prove operational value

Primary objective:

- Demonstrate that the platform improves incident handling in practice

Deliverables:

1. Add a quarterly game-day checklist and runbook validation workflow.
2. Publish at least one completed exercise summary with findings and follow-up actions.
3. Capture example KPI trend outputs and a sample incident bundle artifact structure.
4. Document before-and-after operational outcomes such as faster first diagnostic output, cleaner handoffs, or fewer unsafe ad hoc commands.

Success metrics:

- At least one game-day has been executed and documented.
- KPI reporting is tied to a real operational review loop.
- The repo can show evidence of improved incident transparency, safety, or speed.

Recommended implementation order:

1. Integration realism
2. ADR baseline
3. Release provenance and signing
4. Game-day and runbook validation
5. KPI outcome reporting and adoption evidence

Recently implemented:

- Machine-readable support script catalog manifest (`scripts/script_catalog.json`) with README auto-generation and CI drift check.
- Incident bundle packager (`scripts/incident_bundle.sh`) to archive artifacts, metadata, and KPI reports for postmortems.
- KPI baseline/candidate comparison utility (`scripts/kpi_compare.sh`) for measurable before/after deltas.
- Artifactory package-resolution and 502 triage scripts now emit optional telemetry (`PS_METRICS=1`) for KPI evidence capture.
- CI release-trust additions: SHA256 manifests for SBOM and KPI evidence artifacts.
- Adoption evidence template (`docs/INCIDENT_EVIDENCE_TEMPLATE.md`) for repeatable post-incident measurement.

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

- COMPLETE: Key GitHub Actions pinned to commit SHAs.
- COMPLETE: `dependency-audit` CI job added (`pip-audit` on every push).
- COMPLETE: SBOM generation and artifact upload added.
- Remaining: signed provenance attestation and release-time artifact signing (requires repository eligibility/workflow updates).

### Feature: Stronger build integrity controls

Goal:

- Reduce CI/CD supply-chain risk and improve auditability.

Implementation steps:

1. Pin third-party GitHub Actions to commit SHAs in `.github/workflows/ci.yml`.
2. Add dependency vulnerability scan step (for Python dev dependencies and shell tooling references).
3. Add SBOM generation for release artifacts.
4. Add signed-release process notes in release policy.
5. Add a `.github/workflows/release.yml` that triggers on tag push, builds and attaches the signed SBOM to the GitHub release, and runs `gh attestation verify` as a post-release smoke check.

Definition of done:

- CI uses pinned action SHAs.
- Dependency and SBOM generation are part of merge or release flow.
- Release workflow attaches attested SBOM to the GitHub release page, verifiable via `gh attestation verify <artifact> --repo <owner>/<repo>`.

## Priority 4: Architecture Decision Records

Status:

- COMPLETE: `docs/adr/` added with ADR template and accepted baseline decisions for safety, telemetry, and compatibility.
- COMPLETE: ADR index linked from README and CONTRIBUTING.

### Feature: ADR baseline for platform safety and compatibility

Goal:

- Make engineering decisions durable and auditable.

Implementation steps:

1. Add `docs/adr/` directory with a lightweight ADR template (`docs/adr/000-template.md`).
2. Create initial ADRs:
   - `001-safe-by-default-execution.md`: documents the check-before-repair model and why it is the mandatory pattern.
   - `002-telemetry-format-and-kpi-contract.md`: documents the `METRIC|...` line format, KPI targets, and stability guarantees.
   - `003-compatibility-and-deprecation-strategy.md`: documents how script flags and command names are versioned and deprecated.
3. Link ADR index from README under Documentation map and from CONTRIBUTING under design decisions.

Definition of done:

- ADR template exists.
- At least three accepted ADRs are present and referenced by docs.

## Priority 5: Operational Readiness Program

Status:

- PARTIAL: quarterly checklist doc added at `docs/GAME_DAY_CHECKLIST.md`.
- Remaining: runbook validation script and at least one completed game-day evidence pack.

### Feature: Incident game-day and runbook validation

Goal:

- Prove that the platform actually improves incident outcomes over time.

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

## Priority 7: Operational Evidence And Trust Loop

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
