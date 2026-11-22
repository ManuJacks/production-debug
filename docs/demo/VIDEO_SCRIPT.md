# Demonstration video script (90 seconds)

A screen recording that starts where a real incident starts: an alert. The
alert, the dashboard and every line of `demo/run.sh` output are produced live
by the same failing workload; nothing is staged or edited into the output.

The opening (alert and dashboard) needs the
[kubernetes-in-finance](https://github.com/ManuJacks/kubernetes-in-finance)
monitoring stack. Without it, record the
[standalone version](#standalone-version-no-monitoring-stack).

## The story

The thesis: the worst damage in an incident is often done by the responders
(too much access, rushed commands, and now AI assistants with write
access), not by the original failure. One workload, one incident, end to end:

1. **Detect.** `crashloop-demo` has been crash-looping; Prometheus raises
   `KubePodCrashLooping` and Alertmanager delivers it to the phone.
2. **Triage.** Grafana narrows it to one pod and shows users are not
   affected, which is why it is a ticket, not a page.
3. **Debug without making it worse.** `demo/run.sh` picks up *the same
   workload*: read-only diagnostic pod, least privilege proven, evidence
   bundle, AI investigation, operator fix, verified recovery, clean-up.
4. **Record it the way a bank does.** The incident record (INC) is opened
   from the verified evidence at a *derived* severity (Sev 3: one internal
   service down, no customers), the fix is a Change (CHG), and the Problem
   record (PRB) turns the cause into tracked prevention.
5. **Close.** The alert resolves.

## Setup

- Terminal at least 120 columns, font 16 pt or larger, dark theme.
- Pull the diagnostic image to the workers beforehand so step 2 does not
  wait on a large download.
- On the kubernetes-in-finance host: monitoring deployed
  (`13-monitoring.yml`) with kube-state-metrics (`06c-kube-state-metrics.yml`),
  and ntfy subscribed on the phone.
- Run `demo/run.sh run` once off-camera to confirm the cluster is healthy.

```bash
export KUBECONFIG=~/.kube/kubernetes-in-finance.conf
export CTX=kubernetes-admin@kubernetes
```

## Recording order

Record in this order; edit into the [script](#script) order.

1. **Break (off camera), about 15 minutes before recording:**

   ```bash
   K8S_LAB_CONTEXT=$CTX K8S_LAB_CONFIRM=$CTX/production-debug-lab \
     scenarios/run.sh setup 01-crashloop
   ```

2. **Alert (phone).** `KubePodCrashLooping` fires after the container has
   been in CrashLoopBackOff for 10 minutes; expect the ntfy notification
   about 11–12 minutes after the break (10 min `for`, scrape interval, 30 s
   Alertmanager group wait). Record the phone screen as it arrives.
3. **Triage (Grafana).** Dashboard *Platform reliability: SLO, RPO and RTO
   evidence*, time range *Last 30 minutes*. Capture:
   - *Firing alerts*: `KubePodCrashLooping`, `production-debug-lab`
   - row *Workload & pod health*: *Containers crash-looping* = 1
   - *Unhealthy pods and containers (now)*: `crashloop-demo`, `CrashLoopBackOff`
   - *Container restarts (1 h, by pod)*: the restart staircase
   - *Error budget remaining (30 d)*: unchanged
4. **Debug (terminal).** Without cleaning up first:

   ```bash
   DEMO_CONTEXT=$CTX DEMO_CONFIRM=$CTX/production-debug-lab \
   DEMO_IMAGE=<image> \
   DEMO_DETECTED_AT=<alert time, UTC, e.g. 2026-11-22T17:41:00Z> \
   DEMO_DETECTED_BY="KubePodCrashLooping (Alertmanager, ntfy)" \
   demo/run.sh run
   ```

   Step 1 re-applies the scenario (no change) and finds the crash loop
   already running, so the demo debugs the workload the alert fired on.
   Step 4 drafts the incident record with the alert as its first work note:
   `incident-output/<bundle>.incident.md`.
5. **Records (editor or GitHub).** Open the drafted INC (severity rationale
   and work notes) and the [PRB example](records/PRB-example-crashloop-demo.md)
   (action items). Fill the PRB timeline from your recording first.
6. **Resolve (phone and Grafana).** The alert resolves within about
   10 minutes of the fix: the 5-minute lookback in the rule, then
   Alertmanager's 5-minute group interval. Capture the resolved notification
   and *Containers crash-looping* back to 0.

## Script

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:10 | Phone: ntfy notification `KubePodCrashLooping`, `production-debug-lab/crashloop-demo` | "An alert. This is the moment incidents get worse: not from the failure, but from us. Too much access, a rushed command, and now AI assistants with admin rights." |
| 0:10–0:18 | Grafana: *Containers crash-looping* = 1, *Unhealthy pods* table, restart staircase, then *Error budget remaining* unchanged | "Grafana narrows it to one pod. The error budget hasn't moved, so users aren't affected: a ticket, not a page. So how do we debug it without making it worse?" |
| 0:18–0:25 | Steps 1–2: the existing crash loop, `restartCount`; diagnostic pod created, read-only, expires in one hour | "Instead of handing out admin, we launch a short-lived diagnostic pod: non-root, read-only, gone within the hour." |
| 0:25–0:35 | Step 3: the `allow` and `deny` table, then the live `Forbidden` delete | "Its identity can read this one namespace, and nothing else. Here it tries to delete the pod, and the API server refuses." |
| 0:35–0:46 | Step 4: archive verified with fingerprint, then `incident: DRAFT-…` and `priority: 3 - Moderate (impact 3 - Low x urgency 1 - High)`; cut to the drafted record's work notes | "It collects evidence, redacted and verified, and opens the incident record from it. One internal service down, no customers: Sev 3. Derived, not chosen." |
| 0:46–0:58 | Step 5: MCP tool list (`readOnlyHint=True`), logs showing `missing CONFIG_URL`, out-of-scope request Forbidden, Assessment | "An AI assistant investigates as the same read-only identity. It finds the root cause, a missing configuration value. It can diagnose. It cannot act." |
| 0:58–1:05 | Step 6: `identity: kubernetes-admin`, deployment configured | "The fix goes through a change, applied by a human with separate credentials." |
| 1:05–1:12 | Step 7: `ready=true restarts=0` | "Recovery is verified, not assumed: ready, zero restarts." |
| 1:12–1:22 | Problem record: root cause, detection review ("no new alert"), action items with *Prevent* first | "The problem record turns the cause into prevention: a deploy-time check, owned and tracked. No new alert; the existing one did its job." |
| 1:22–1:30 | Phone: resolved notification; Grafana tile back to 0; step 8 namespaces removed; repository link | "The alert resolves. The investigation never had the power to change production; only the reviewed fix did." |

The full terminal run includes about 60–90 s of waiting (rollout, the 20 s
stability window, namespace deletion). Cut or speed up those waits; do not
cut any output that proves a property.

## Accuracy notes

- **Ticket, not page, is deliberate.** In kubernetes-in-finance a crash loop
  is a cause, not a symptom; pages are reserved for user impact (SLO burn),
  imminent data loss, lost redundancy and resource exhaustion (its ADR-006).
  Say so only if the error-budget panel on screen shows no change.
- **Time to alert.** Quote only what the recording shows. The 10-minute
  `for` is chosen so a container that crashes briefly during a rollout does
  not alert; it is not a detection-time claim.
- **Sev 3, not Sev 2.** The severity comes from the matrix
  (`docs/procedures/SEVERITY_MATRIX.md`): impact 3 (one internal service,
  no customers) × urgency 1 (fully unavailable). Calling it a Sev 2 would
  contradict the "users aren't affected" line seconds earlier.
- **The INC is a draft.** It is generated from the evidence and never
  submitted anywhere; say "opens the incident record", not "files a ticket
  in ServiceNow".
- **The PRB actions are tracked, not done.** The deploy-time check is the
  example's action item, not an implemented control; say "owned and
  tracked", not "fixed".
- Say "read-only for this namespace", not "read-only everywhere": the
  identity is namespace-scoped by design.
- The AI's investigation is a scripted MCP client, so the run is
  reproducible. Do not describe it as an autonomous agent; an interactive
  assistant can be attached to the same server command.
- Do not quote durations or success rates beyond what the recorded run shows.

## Before publishing

- Crop or blur the ntfy topic name: it is the credential for the alert
  channel.
- No kubeconfig contents, Grafana password path or host names beyond the
  lab's own on screen.
- A reviewer may ask about the diagnostic pod's memory limit (1 Gi, larger
  than a lab worker's ~950 MiB). Its request (256 Mi) is what scheduling
  reserves; consider a lower limit for small clusters.

## Why not open on an OOM page?

`KubeContainerOOMKilled` pages within about 1–2 minutes and would make a
sharper opening, but `demo/run.sh` is built around `01-crashloop` (selector,
fixed manifest, the MCP client's expected root cause). Opening on an OOM
alert and then debugging a crash loop would be two incidents edited into
one. That needs `demo/run.sh` to accept a scenario (for example
`07-oom` with a `07-oom-fixed.yaml` that raises the limit) before it can be
recorded honestly.

## Standalone version (no monitoring stack)

Replace 0:00–0:18 with a title card, **How do you debug production without
making production worse?**, and the voice-over: "During an incident, the
fastest way to make things worse is to give everyone, and now every AI
assistant, the power to change production while they investigate." Start
from step 1 with a clean cluster (`demo/run.sh run` deploys the crash loop
itself). The final line becomes "Then everything is cleaned up. The code and
tests are on GitHub."
