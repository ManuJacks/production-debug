# ADR 005: Model Context Protocol (MCP) Read-Only Incident Diagnostics

- Status: Accepted
- Date: 2026-10-29
- Deciders: Maintainers
- Technical area: safety, ai-integration, operations

## Context

During production incidents, responders increasingly leverage AI coding assistants and agents (Claude, Cursor, Antigravity) to accelerate log analysis, telemetry synthesis, and root-cause identification.

Without a structured capability boundary, allowing an AI agent to generate ad-hoc bash commands inside a live production pod introduces severe risks:
1. Accidental cluster state mutation.
2. Secret exfiltration (environment variables, tokens).
3. Non-deterministic and un-audited command execution.

## Decision

The platform adopts the **Model Context Protocol (MCP)** as the standard interface for AI-assisted incident response.

Specifically:
- An internal MCP server runs within or adjacent to the debug container.
- **No target-system remediation through MCP**: Exposed diagnostics must not mutate target infrastructure. Generating an incident bundle writes local evidence files and is not a read-only operation on the local filesystem.
- **No Direct Shell Execution via MCP**: The MCP server does not provide arbitrary bash/eval tools.
- **Auditability**: Tool activity should be attributable and recorded where the MCP host provides caller metadata and audit storage.
- **Sensitive-output handling**: Avoid returning secret values. Where sanitization is implemented, treat it as defense in depth, not a guarantee; operators must review evidence before sharing.

## Consequences

- Positive: Enables safe AI pair-debugging during high-pressure outages without risk of catastrophic unintended side-effects.
- Costs: Adding and testing new diagnostics requires defining explicit JSON schemas and MCP tool handlers.

## Implementation status and limitations

This ADR records the intended safety contract, not proof that every control is implemented. The current server does not provide comprehensive per-tool audit logging or sanitize every diagnostic response. The bundle script attempts best-effort pattern-based redaction, which can fail without blocking bundle creation. Do not treat MCP output or generated bundles as guaranteed secret-free or tamper-proof.
