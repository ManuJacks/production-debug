# Change request (CHG) template

Every change to production, including an incident fix, goes through a Change
request. The diagnostic identity can never apply one; changes are made with
operator credentials ([ADR 005](../adr/005-mcp-readonly-incident-diagnostics.md)).

| Type | Use for | Approval |
|---|---|---|
| Standard | Pre-approved, low-risk, repeatable changes with a tested procedure | Pre-approved |
| Normal | Planned changes | Peer review and change approval before the window |
| Emergency | Restoring service during an incident | Incident commander approves; reviewed retrospectively |

---

# CHG-<id>: <what changes>

| Field | Value |
|---|---|
| Type | Standard / Normal / Emergency |
| Related records | INC-…, PRB-… (action item #…) |
| Configuration item(s) | |
| Requested by / implemented by | |
| Risk | Low / Moderate / High, with the reason |
| Planned window | |
| Pull request / commit | |

## Justification

Why this change, and what happens if it is not made.

## Implementation plan

Exact steps or the pipeline that applies them, and the identity that applies
them.

## Test plan and evidence

- **Before:** a test or reproduction that fails without this change.
- **After:** the same test passing; link the CI run.
- **In production:** the check that proves success (metric, alert resolved,
  probe), and over what window.

## Backout plan

How to revert, how long it takes, and the signal that triggers it.

## Post-implementation review

| Question | Answer |
|---|---|
| Implemented as planned? | |
| Success check met? | |
| Any unplanned impact? | |
| Related Problem action item updated? | |
