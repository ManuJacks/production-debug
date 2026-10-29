# ADR 002: Telemetry Format And KPI Contract

- Status: Accepted
- Date: 2026-04-16
- Deciders: Maintainers
- Technical area: telemetry

## Context

The repository includes support scripts that may run during real incidents, preflight checks, and operational diagnostics.
If outcomes are not captured in a stable format, the project cannot demonstrate whether it improves incident handling over time.

The platform already includes telemetry collection, report generation, weekly KPI publishing, and a Grafana starter dashboard.
Those capabilities require a contract that contributors can rely on when extending scripts and reporting logic.

## Decision

The canonical telemetry output contract is the structured `METRIC|...` summary line emitted by supported scripts when `PS_METRICS=1` is enabled.

The contract is defined as follows:

- A single structured summary line is emitted at script completion when telemetry mode is enabled
- The line begins with `METRIC|`
- Core fields include script name, status, exit code, and duration in seconds
- Additional fields may be appended for script-specific context as long as they preserve parseability
- KPI collection and reporting scripts must continue to support this contract in a backward-compatible way within a release line

## Consequences

- Scripts can be measured consistently across incidents and environments
- KPI pipelines remain deterministic and automation-friendly
- Contributors must treat telemetry fields as a compatibility surface, not disposable log text
- Changes to telemetry semantics require documentation and migration consideration

## Alternatives considered

- Free-form human-readable log summaries only
- Per-script custom telemetry output without a common contract
- Centralized metrics emission through a separate service dependency

## Follow-up

- Keep KPI tooling and README examples aligned with the `METRIC|...` contract
- Document compatibility expectations when telemetry fields are added or changed
- Add tests when collector or report behavior changes