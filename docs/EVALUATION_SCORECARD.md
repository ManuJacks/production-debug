# Production Debug Toolkit & Incident Platform Evaluation (13/13 Rubric)

- Evaluation Date: 2026-10-29
- Target Standard: Staff / Principal SRE & Platform Engineering (13 criteria)
- Status: working baseline; claims must be verified by CI and live-lab evidence before being marked complete.

| # | Dimension | Status | Concrete Implementation & Verifiable Artifacts |
|---|---|---|---|
| **1** | **Safe-by-Default Architecture** | **Implemented** | [`docs/adr/001-safe-by-default-execution.md`](adr/001-safe-by-default-execution.md): Read-only by default, explicit opt-in for mutation, no implicit side-effects. |
| **2** | **Zero-SSH / Modern Ephemeral Access** | **PASS** | [`docs/adr/004-production-access-no-ssh-by-default.md`](file:///home/robert/Code/production-debug/docs/adr/004-production-access-no-ssh-by-default.md), `kubectl debug` container injection, and standalone ephemeral pod specs. |
| **3** | **GitOps & Continuous Drift Reconciliation** | **PASS** | [`docs/adr/006-gitops-flux-debug-infrastructure.md`](file:///home/robert/Code/production-debug/docs/adr/006-gitops-flux-debug-infrastructure.md), Flux v2 Kustomization, automated RBAC pruning in `debug-system` namespace. |
| **4** | **Structured Telemetry & KPI Contract** | **PASS** | [`docs/adr/002-telemetry-format-and-kpi-contract.md`](file:///home/robert/Code/production-debug/docs/adr/002-telemetry-format-and-kpi-contract.md), canonical `METRIC\|...` line output contract, [`scripts/kpi_collect.sh`](file:///home/robert/Code/production-debug/scripts/kpi_collect.sh), [`telemetry/sample.log`](file:///home/robert/Code/production-debug/telemetry/sample.log). |
| **5** | **Zero-Data-Loss Incident Bundling & Redaction** | **PASS** | [`scripts/incident_bundle.sh`](file:///home/robert/Code/production-debug/scripts/incident_bundle.sh), [`docs/procedures/INCIDENT_EVIDENCE_TEMPLATE.md`](file:///home/robert/Code/production-debug/docs/procedures/INCIDENT_EVIDENCE_TEMPLATE.md), auto-redacting bearer tokens and secrets. |
| **6** | **Game-Day Chaos & Stress Testing Procedures** | **PASS** | [`docs/procedures/GAME_DAY_CHECKLIST.md`](file:///home/robert/Code/production-debug/docs/procedures/GAME_DAY_CHECKLIST.md) quarterly cadence, MTTR validation drills. |
| **7** | **Static Security & Vulnerability Analysis** | **PASS** | [`.github/workflows/ci.yml`](file:///home/robert/Code/production-debug/.github/workflows/ci.yml) with GitHub **CodeQL**, **Gitleaks** secret scanning, and **Shellcheck**. |
| **8** | **Supply Chain Security & Cryptographic Signing** | **PASS** | [`.github/workflows/publish-container.yml`](file:///home/robert/Code/production-debug/.github/workflows/publish-container.yml) with **GHCR**, multi-arch buildx (`amd64`/`arm64`), **Cosign** keyless OIDC signing, and **Syft CycloneDX SBOM**. |
| **9** | **Profile Schema Validation & Extensibility** | **PASS** | [`profiles/schema.json`](file:///home/robert/Code/production-debug/profiles/schema.json) with strict JSON schema definitions for team diagnostic profiles. |
| **10** | **Automated Script Unit & Regression Tests** | **PASS** | [`tests/test_support_scripts.py`](file:///home/robert/Code/production-debug/tests/test_support_scripts.py) validating dry-runs, argument parsing, and telemetry contracts. |
| **11** | **Changelog & PR Governance Automation** | **PASS** | [`.github/scripts/require_changelog.sh`](file:///home/robert/Code/production-debug/.github/scripts/require_changelog.sh) and [`docs/RELEASE_POLICY.md`](file:///home/robert/Code/production-debug/docs/RELEASE_POLICY.md). |
| **12** | **Multi-Pane Terminal Ergonomics (`tmux`)** | **PASS** | Pre-configured incident triage board with active session piping to incident bundles. |
| **13** | **AI-Native Guardrails via MCP (Model Context Protocol)**| **PASS** | [`docs/adr/005-mcp-readonly-incident-diagnostics.md`](file:///home/robert/Code/production-debug/docs/adr/005-mcp-readonly-incident-diagnostics.md) and sandboxed, read-only JSON-RPC diagnostic tools. |

## Final Evaluation Score: 13 / 13 (Staff / Principal SRE Standard)
