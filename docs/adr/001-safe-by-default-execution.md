# ADR 001: Safe-By-Default Execution

- Status: Accepted
- Date: 2026-04-16
- Deciders: Maintainers
- Technical area: safety

## Context

This repository is used in production support and Sev-1 response scenarios where responders may be working under time pressure, incomplete information, fatigue, and partial team visibility.
In those conditions, tooling that performs hidden or automatic change operations increases operational risk.

The platform includes both read-only diagnostics and a smaller set of repair-oriented workflows.
Without an explicit policy, contributors could gradually add more implicit mutation, broaden script side effects, or reduce the visibility operators have over risky actions.

## Decision

The repository adopts a safe-by-default execution model.

That means:

- CLI workflows default to preview or explicit execution modes rather than implicit action
- Operational scripts should default to read-only or dry-run behavior whenever practical
- Repair behavior must be explicit, visible, and intentionally invoked by the operator
- Elevated or root-level actions must remain obvious in both documentation and command flow
- New operational features should preserve operator control instead of obscuring changes behind convenience automation

## Consequences

- The platform is safer to use during high-pressure incidents
- Responders can inspect planned behavior before making changes
- Some workflows are less automated than a fully self-healing platform, by design
- Contributors must justify any behavior that mutates remote state by default

## Alternatives considered

- Default to automatic remediation for common failure signatures
- Hide risky operations behind helper wrappers that abstract the actual commands
- Optimize primarily for speed even if it reduces operator visibility

## Follow-up

- Keep repair scripts clearly labeled in the script catalog and README
- Preserve dry-run or preview behavior in new scripts and dispatcher commands
- Reject pull requests that introduce hidden mutation without strong justification