# Incident severity matrix

Severity is **derived, not chosen**: responders assess impact and urgency,
and priority follows from the table. This keeps a quiet failure from being
inflated for attention, and a serious one from being played down.

The values follow ServiceNow's default incident priority lookup
(impact × urgency → priority), so a record drafted here maps directly onto
the `impact`, `urgency` and `priority` fields. **Sev N means Priority N.**
Organisations tune these definitions; the ones below are this project's
defaults and are labelled as such.

## Impact: how much of the business is affected

| Value | Definition (project default) |
|---|---|
| 1 - High | Several business services, or a customer-facing critical service, affected; or regulatory/data-integrity exposure |
| 2 - Medium | One business service degraded, or a limited set of customers affected |
| 3 - Low | One internal or non-critical service affected; no customer impact |

## Urgency: how fast it gets worse, and whether there is a workaround

| Value | Definition (project default) |
|---|---|
| 1 - High | The affected service is unavailable, or data loss is in progress; no workaround |
| 2 - Medium | Degraded, or a workaround exists |
| 3 - Low | No current functional effect; can be handled in normal working hours |

## Priority (severity)

<!-- priority-matrix: kept in sync with production_debug/incident_record.py by tests -->
| Impact \ Urgency | 1 - High | 2 - Medium | 3 - Low |
|---|---|---|---|
| **1 - High** | 1 - Critical | 2 - High | 3 - Moderate |
| **2 - Medium** | 2 - High | 3 - Moderate | 4 - Low |
| **3 - Low** | 3 - Moderate | 4 - Low | 5 - Planning |

## What each severity sets in motion (project default)

| Sev | Response | Communication | Records |
|---|---|---|---|
| 1 - Critical | Immediate page; incident commander; all hands | Stakeholder updates every 30 min | INC; Problem with post-incident review **mandatory** |
| 2 - High | Page within 15 min; incident commander | Updates every hour | INC; Problem **mandatory** |
| 3 - Moderate | Ticket; respond within 4 working hours | In the record | INC; Problem when the cause is not obvious or may recur |
| 4 - Low | Ticket; next working day | In the record | INC |
| 5 - Planning | Backlog | None | Problem or story, not an INC |

## Worked examples

| Situation | Impact | Urgency | Sev |
|---|---|---|---|
| `crashloop-demo` (demo scenario): one internal service fully down; API SLO unaffected, no customers | 3 | 1 | **3** |
| Kubernetes API fast burn: platform API failing for every tenant | 1 | 1 | **1** |
| One of two workers lost; workloads rescheduling, all services serving | 2 | 2 | **3** |
| False page from a monitoring gap; platform healthy | — | — | **None**: not an incident; raise a Problem against the monitoring (proactive problem management) |

## Rules

- Record the impact and urgency **with their evidence** (an SLO panel, a
  customer report), not just the resulting number.
- Re-assess when facts change; record the change and the reason in the work
  notes. Upgrading is cheap; downgrading needs evidence.
- Do not raise severity to get attention. If a Sev 3 needs more hands, ask
  for them; the severity describes the impact, not the effort.
