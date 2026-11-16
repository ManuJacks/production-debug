# Operating model: firefighting and learning

## Purpose

Make incident response resilient to handoffs and knowledge concentration. No single responder should have to carry the complete technical picture, decision history and next steps alone. This is a systems goal, not an expectation that every responder know every subsystem.

## During an incident

The immediate objective is to reduce customer impact while preserving the ability to learn. The incident commander owns priorities and stop conditions; the driver executes commands; the navigator maintains hypotheses and next checks; the scribe records decisions, timestamps and evidence locations. Assign people to roles explicitly; titles or technical seniority alone do not establish incident authority.

Use the smallest reversible action that tests the current hypothesis. Announce commands before execution, avoid destructive cleanup until evidence is captured, and record why an action was safe enough to take.

If containment authority, approval requirements or investigation boundaries are unclear, pause the proposed action and escalate through the organization's designated incident process. The toolkit can make observations and gaps visible; it does not grant authorization.

## Blameless review

Post-incident reviews focus on system behavior and organizational conditions. Include contributing factors, missing or misleading signals, unsafe defaults, recovery friction, and concrete owners for prevention work. Do not infer intent or competence from an outcome.

## Handoff minimum

A handoff must include impact, timeline, current hypothesis, tested hypotheses, commands already run, evidence paths, current risk, next action, and explicit stop conditions.

The incoming responder should be able to continue from the written record without relying on private context from the outgoing responder. Mark unknowns and unverified actions explicitly; do not turn an absence of evidence into a claim that a system is safe or contained.

## Evidence handling

Capture raw output only where approved, redact before sharing, checksum finalized bundles, and document retention and access. Never paste tokens, private keys, or customer data into chat or tickets.

Use the [incident evidence template](procedures/INCIDENT_EVIDENCE_TEMPLATE.md) to record observations, decisions, action ownership and verification. Bundle sanitization is best-effort; inspect artifacts before sharing.
