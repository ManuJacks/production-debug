# Incident Evidence and Handoff Template

Use this record to make an investigation reviewable and transferable. Record only information approved for the incident channel and evidence store. Do not include secret values.

## Incident and roles

- Incident ID:
- Date/time range and timezone:
- Environment and affected service(s):
- Incident commander / decision owner:
- Driver:
- Navigator:
- Scribe:
- Current status:

## Situation and impact

- Customer or operational impact:
- Known affected systems:
- Current containment state:
- Immediate risks and stop conditions:

## Timeline and observations

For each entry, distinguish the time the event occurred from the time evidence was collected when both are available.

| Time (with timezone) | Source / system | Observation or action | Classification (fact / hypothesis / recommendation) | Owner |
|---|---|---|---|---|
| | | | | |

## Decisions and actions

| Action or decision | Owner | Required authorization / approver | Status | Evidence and verification |
|---|---|---|---|---|
| | | | | |

Record proposed or completed actions separately from observed facts. Note who authorized consequential actions and where that authorization is recorded.

## Supply-chain investigation (when applicable)

- Package coordinates and versions:
- Configured and observed package sources:
- Internal artifact repositories checked and results:
- Upstream containment checks and results:
- Known consuming pipelines/builds:
- Credential references and dependent systems (references only; never values):
- Rotation status:
- Revocation status:
- Independent validation of dependent systems:

Keep internal artifact presence/removal distinct from upstream source availability/blocking. Neither alone proves the package was consumed or that the incident is contained.

## Open questions and evidence gaps

| Question or gap | Why it matters | Owner | Next check / due time |
|---|---|---|---|
| | | | |

## Handoff

- Current impact and risk:
- Verified findings:
- Current hypotheses and confidence:
- Checks already performed:
- Evidence locations:
- Next action and owner:
- Required approval or escalation:
- Explicit stop conditions:

The incoming responder should be able to continue from this record and its referenced evidence without private briefing.

## Closure and independent verification

- Recovery or containment criteria:
- Verification performed, by whom, and when:
- Remaining risks, exceptions, or unknowns:
- Follow-up actions, owners, and target dates:
- Evidence retention location and access restrictions:
- Blameless review or exercise reference:
