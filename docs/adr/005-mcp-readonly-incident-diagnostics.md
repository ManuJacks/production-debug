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
- **Strict Read-Only Boundary**: All exposed MCP tools are strictly read-only diagnostics (e.g. `query_k8s_events`, `run_dns_probe`, `check_azure_workload_identity`, `generate_sanitized_incident_bundle`).
- **No Direct Shell Execution via MCP**: The MCP server does not provide arbitrary bash/eval tools.
- **Structured Audit Logging**: Every tool call initiated by an AI model is logged with timestamps, caller metadata, and parameters into the incident bundle.
- **Sanitized Outputs**: Outputs automatically scrub Azure bearer tokens, connection strings, and Kubernetes secret payloads before returning responses to the LLM.

## Consequences

- Positive: Enables safe AI pair-debugging during high-pressure outages without risk of catastrophic unintended side-effects.
- Costs: Adding and testing new diagnostics requires defining explicit JSON schemas and MCP tool handlers.
