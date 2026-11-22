# Problem record (PRB) and post-incident review template

The Problem record owns **why it happened and how it is prevented**. It holds
the post-incident review (called a Correction of Errors, COE, in some
organisations). It is required for Sev 1 and Sev 2, and for Sev 3 when the
cause is not obvious or may recur ([severity matrix](SEVERITY_MATRIX.md)).

A Problem can also be raised without an incident (*proactive problem
management*), for example from an alert review that finds a misleading alert.

Write it blameless: describe what the system allowed and what people knew at
the time, not who made a mistake.

---

# PRB-<id>: <title: the problem, not the symptom>

| Field | Value |
|---|---|
| State | New / Assess / Root Cause Analysis / Fix in Progress / Resolved / Closed |
| Related incident(s) | INC-… (or "none: proactive") |
| Configuration item | |
| Problem owner | |
| Severity of the related incident | Sev … (impact … × urgency …) |
| Review date | |
| Known error | Yes / No (a documented cause with a workaround) |
| Workaround | |

## Summary

Three sentences: what happened, the impact, what changes so it does not
happen again.

## Impact

Who and what was affected, for how long, measured how. Name the evidence
(SLO panel, error budget, customer reports). State what was *not* affected.

## Timeline (UTC)

From the incident work notes. Include detection, escalation, mitigation and
recovery, and the gaps between them.

| Time | Event | Source |
|---|---|---|
| | | |

Key intervals: time to detect, time to engage, time to mitigate, time to
recover.

## Root cause and contributing factors

- **Root cause:** the condition without which this would not have happened.
  Show the evidence; a cause without evidence is a hypothesis.
- **Contributing factors:** what made it worse, slower to detect, or harder
  to fix.
- **5 whys** (optional) when the chain is not obvious.

## Detection review

| Question | Answer |
|---|---|
| Did an alert fire? Which one, how long after the fault started? | |
| Was its severity right (page vs ticket) under the alerting policy? | |
| Should something else have alerted earlier? | |
| Was anything misleading (false alerts, missing data)? | |

Add an alert **only** when it would have shortened detection or changed the
response, and record its severity against the alerting policy. Do not add
alerts to show activity.

## What went well / what was hard

- Went well:
- Hard or slow:
- Where we got lucky:

## Action items

Every item has an owner, a due date, a type, and the record that delivers it.
Prefer **prevent** over **detect** over **mitigate**. Each fix lands with a
test that reproduces this failure.

| # | Type | Action | Owner | Due | Delivered by (CHG / PR) | Test / evidence | Status |
|---|---|---|---|---|---|---|---|
| 1 | Prevent | | | | | | Open |
| 2 | Detect | | | | | | Open |
| 3 | Mitigate | | | | | | Open |
| 4 | Process | | | | | | Open |

## Closure criteria

The Problem closes when every action item is delivered or explicitly
accepted as a risk by the owner, and the test or drill proving the fix has
run.
