# PRB (example): crashloop-demo starts without required configuration

> **Worked example for the synthetic demo scenario** (`scenarios/01-crashloop`),
> written with the [Problem template](../../procedures/PROBLEM_RECORD_TEMPLATE.md).
> `crashloop-demo` is not a real service. Times come from your own recording;
> placeholders are marked `<…>`.

| Field | Value |
|---|---|
| State | Resolved |
| Related incident | INC drafted by `demo/run.sh` step 4 (`incident-output/*.incident.md`) |
| Configuration item | crashloop-demo |
| Problem owner | Platform Engineering |
| Severity of the related incident | **Sev 3** (impact 3 - Low × urgency 1 - High): one internal service fully unavailable; API SLO and customers unaffected |
| Known error | Yes: the container exits when `CONFIG_URL` is unset |
| Workaround | None needed after the fix |

## Summary

`crashloop-demo` was deployed without `CONFIG_URL`, so every container start
exited with code 1 and the pod crash-looped. Nothing outside the service was
affected. The fix supplies the value; prevention moves the check from
startup to deploy time, so a missing value blocks the rollout instead of
taking the service down.

## Impact

`crashloop-demo` had no ready replicas from deployment until the fix
(`<duration from recording>`). The platform's API availability SLO was
unaffected (error budget unchanged on the dashboard). No customer-facing
service depends on `crashloop-demo`.

## Timeline (UTC)

| Time | Event | Source |
|---|---|---|
| `<t0>` | Deployment applied without `CONFIG_URL` | Change history |
| `<t0 + ~10 min>` | `KubePodCrashLooping` fired (ticket), delivered to on-call | Alertmanager / ntfy |
| `<…>` | Diagnostic pod launched (read-only identity); evidence bundled and verified; INC drafted at Sev 3 | `demo/run.sh` steps 2–4 |
| `<…>` | Root cause identified from the previous container's log: `missing CONFIG_URL` | INC work notes; MCP investigation |
| `<…>` | Fix applied under operator credentials (CHG example) | `demo/run.sh` step 6 |
| `<…>` | Recovery verified: ready, zero restarts over the stability window | `demo/run.sh` step 7 |
| `<…>` | Alert resolved | Alertmanager / ntfy |

Time to detect is dominated by the alert's deliberate 10-minute `for`
(it tolerates crashes during rollouts); time from engagement to root cause is
minutes, because the evidence bundle already contained the failing log line.

## Root cause and contributing factors

- **Root cause:** the Deployment omitted the required `CONFIG_URL`
  environment variable; the application exits at startup without it
  (`Last State: Terminated, Reason: Error, Exit Code: 1`; log:
  `missing CONFIG_URL`).
- **Contributing:** nothing validated required configuration before rollout,
  so the failure surfaced only at runtime.

## Detection review

| Question | Answer |
|---|---|
| Did an alert fire? | Yes: `KubePodCrashLooping`, about 10 minutes after the first crash loop |
| Right severity? | Yes: ticket. A crash loop is a cause; the SLO (symptom) was unaffected, so no page |
| Should something have alerted earlier? | No. A deploy-time check (action 1) prevents it instead |
| Anything misleading? | No |

No new alert: an earlier alert would not have changed the response.

## What went well / what was hard

- Went well: the read-only evidence bundle contained the root cause; nobody
  needed write access to investigate.
- Hard: nothing; the failing value was explicit in the log.
- Lucky: the application logged the missing variable by name. Many do not.

## Action items

| # | Type | Action | Owner | Delivered by | Test / evidence | Status |
|---|---|---|---|---|---|---|
| 1 | Prevent | Validate required environment variables at deploy time (CI policy check on manifests) | Platform Engineering | CHG / PR `<…>` | Policy test fails on the original manifest, passes on the fixed one | Example |
| 2 | Mitigate | Keep the explicit startup message naming the missing variable | Service owner | Existing | Present in `01-crashloop-fixed.yaml` | Done |
| 3 | Detect | None: the existing ticket alert was adequate | — | — | Detection review above | Accepted |

## Closure criteria

Action 1 delivered with its test, or accepted as a risk by the owner.
