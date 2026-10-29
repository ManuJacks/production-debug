# ADR 004: Production Access - No SSH By Default, Break-Glass By Exception

- Status: Accepted
- Date: 2026-04-21
- Deciders: Maintainers
- Technical area: operations, safety, security

## Context

This repository supports high-pressure production incident response where responders may need host-level diagnostics quickly.
The existing workflow uses tmux and SSH heavily for coordination, transparency, and speed.

At the same time, modern SRE and platform-engineering guidance consistently recommends avoiding routine direct host mutation in production.
Uncontrolled SSH use increases drift, weakens reproducibility, and can reduce audit clarity if not tightly governed.

## Decision

The platform adopts a production access doctrine of no SSH by default for routine changes, with controlled break-glass SSH allowed for incident response and bounded diagnostics.

That means:

- Routine production changes must be made through version-controlled automation and approved pipelines
- Direct SSH must not be the normal path for maintenance, configuration updates, or drift correction
- Emergency SSH may be used when required to restore service or gather critical diagnostic data
- Emergency SSH usage must be time-bound, least-privilege, and linked to a ticket or incident record
- Manual actions taken through SSH must be reconciled into code/runbooks after stabilization

## Consequences

- Day-to-day operations remain reproducible, auditable, and automation-first
- Incident responders keep a practical break-glass path for urgent restoration work
- Teams must maintain access controls, session logging, and post-incident reconciliation discipline
- Contributors should prioritize script and pipeline improvements that reduce future need for manual host access

## Alternatives considered

- Permit unrestricted SSH as a normal operational practice
- Prohibit all SSH access, including during live incidents
- Keep policy implicit in team norms without explicit governance

## References

- Google Site Reliability Engineering (O'Reilly, 2016)
- The Site Reliability Workbook (O'Reilly, 2018)
- Continuous Delivery (Humble and Farley)
- The DevOps Handbook (Kim, Debois, Willis, Humble)
- Infrastructure as Code (Morris)
- GitOps operating model guidance (Weaveworks/CNCF ecosystem)
- Cloud reliability and operational excellence frameworks (for example AWS Well-Architected)
- Security control baselines for least privilege, change control, and auditability (for example NIST/CIS)