# Incident record (INC) template

The incident record tracks **restoring service**. Root cause and prevention
belong in the [Problem record](PROBLEM_RECORD_TEMPLATE.md); every fix goes
through a [Change request](CHANGE_REQUEST_TEMPLATE.md).

Draft it from verified evidence instead of typing it from memory:

```bash
python3 -m production_debug.incident_record <bundle.tar.gz> \
  --impact <1-3> --urgency <1-3> --service <ci> \
  --short-description "<service>: <symptom>" \
  --impact-statement "<who is affected, how, and the evidence>" \
  [--detected-at <ISO 8601 UTC> --detected-by "<alert or reporter>"] \
  [--format json]
```

The tool fills the fields below that it can prove from the bundle and leaves
the rest marked *to complete*. Field names in brackets are the ServiceNow
`incident` table fields (`--format json` uses them).

## Fields

| Field | Content | Filled by |
|---|---|---|
| Number [`number`] | Assigned on submission; the draft carries `DRAFT-<fingerprint>` | System |
| Short description [`short_description`] | `<service>: <symptom>`, not a cause ("crash-looping", not "bad config") | Responder |
| Description [`description`] | Business impact: who, how, since when, and the evidence for it | Responder |
| Configuration item [`cmdb_ci`] | The affected service | Responder |
| Assignment group [`assignment_group`] | Owning team | Responder |
| Impact, Urgency [`impact`, `urgency`] | Per [SEVERITY_MATRIX.md](SEVERITY_MATRIX.md), with the evidence | Responder |
| Priority [`priority`] | **Derived** from impact × urgency; never set directly | Tool |
| Work notes [`work_notes`] | Timeline of observations, each with time, source and classification (fact / hypothesis / action) | Tool (facts); responders (hypotheses, actions) |
| Evidence | Bundle name and SHA-256 fingerprint | Tool |
| Resolution code, notes | How service was restored (not why it broke) | Responder |
| Related records | Problem (PRB), Change(s) (CHG) | Responder |

## Rules

- **Facts and hypotheses stay separate.** The tool writes facts only, each
  quoted from a named evidence file. A hypothesis is written by a person,
  with what would confirm or refute it.
- **Restore first.** A workaround that restores service resolves the
  incident; the cause is pursued in the Problem record.
- **Changes to production** during the incident go through an emergency
  Change, applied with operator credentials, never the diagnostic identity.
- **Severity changes** are recorded in the work notes with the reason.
- For investigation hand-offs between responders, use the
  [incident evidence template](INCIDENT_EVIDENCE_TEMPLATE.md).
