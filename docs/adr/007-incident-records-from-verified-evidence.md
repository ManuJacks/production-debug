# ADR 007: Incident records are drafted from verified evidence

- Status: Proposed
- Date: 2026-11-22
- Deciders: Maintainers
- Technical area: operations, safety

## Context

Organisations running regulated platforms track incidents in an ITSM tool,
typically ServiceNow: an Incident (INC) to restore service, a Problem (PRB)
for root cause and the post-incident review, and Change requests (CHG) for
every fix. Those records are usually typed from memory during or after the
incident, so their timelines are reconstructed, their facts mix with
guesses, and their severity reflects how loud the incident felt.

This project already produces a sanitized, verified evidence bundle under a
read-only identity. The record should start from that evidence.

## Decision

1. `production_debug.incident_record` drafts an INC record from a bundle
   archive, in Markdown or as JSON using ServiceNow `incident` field names.
2. **Fail closed.** The archive is verified first (`bundle_verifier`); an
   unsafe or unverifiable bundle produces no record.
3. **Facts only.** Every work note is an observation quoted from a named
   evidence file, classified `fact`. The tool never infers a root cause or
   writes a hypothesis; that is the responders' job, in the record and in
   the Problem.
4. **Severity is derived.** The operator supplies impact and urgency;
   priority comes from the matrix in `docs/procedures/SEVERITY_MATRIX.md`
   (ServiceNow's default lookup). Tests keep the document and the code
   identical.
5. **No submission.** The tool never contacts ServiceNow or any other
   system. Posting the JSON is an integration the operator owns, with its
   own credentials and review.
6. Quoted log lines are passed through the sanitizer again, even though the
   bundle was sanitized when it was built.

## Consequences

- Timelines start from timestamps in the evidence, in UTC, with their
  sources, instead of recollection.
- A responder cannot set a severity without stating impact and urgency.
- The draft is deliberately incomplete: business impact, hypotheses and
  resolution need a person. The record says so instead of guessing.
- Parsing kubectl's human-readable output can break with a kubectl format
  change. Tests pin the current format; a future evidence schema version
  could store JSON output instead.

## Alternatives considered

- **Submit directly to ServiceNow.** Rejected: it would give the incident
  tooling write credentials to a system of record, the same class of access
  this project removes from the diagnostic identity.
- **Let the AI assistant write the record, including root cause.** Rejected:
  the assistant's assessment is useful input to responders, but a record of
  fact must not contain unreviewed inference.
- **Templates only.** Kept as the fallback (`docs/procedures/`), but templates
  alone do not fix reconstructed timelines.

## Follow-up

- Problem and Change records remain human-written from the templates in
  `docs/procedures/`.
- Evidence schema v2 could collect `-o json` alongside the text output to
  remove parsing of tables.
