# CHG (example): supply CONFIG_URL to crashloop-demo

> **Worked example for the synthetic demo scenario**, written with the
> [Change template](../../procedures/CHANGE_REQUEST_TEMPLATE.md). This is the
> change `demo/run.sh` step 6 applies.

| Field | Value |
|---|---|
| Type | Emergency (restores service during the incident) |
| Related records | INC drafted in step 4 (Sev 3); [PRB example](PRB-example-crashloop-demo.md) |
| Configuration item | crashloop-demo |
| Implemented by | Operator (`kubernetes-admin`), not the diagnostic identity |
| Risk | Low: one internal service, currently unavailable; the change only adds configuration and a readiness probe |
| Change | `scenarios/01-crashloop-fixed.yaml` |

## Justification

The service has no ready replicas. The evidence bundle shows the cause: the
container exits because `CONFIG_URL` is unset.

## Implementation plan

```bash
kubectl -n production-debug-lab apply -f scenarios/01-crashloop-fixed.yaml
```

Applied with operator credentials. The diagnostic identity is denied every
write (proven in `demo/run.sh` step 3).

## Test plan and evidence

- **Before:** the running pod is in `CrashLoopBackOff`; previous log
  `missing CONFIG_URL` (INC work notes).
- **After:** rollout completes; pod `Ready`; **zero restarts** across the
  20-second stability window (`demo/run.sh` step 7).
- **In production:** `KubePodCrashLooping` resolves (about 10 minutes: the
  rule's 5-minute lookback plus Alertmanager's group interval).

## Backout plan

`kubectl -n production-debug-lab rollout undo deployment/crashloop-demo`
returns to the previous (failing) revision. No data is involved. Trigger:
the stability check fails.

## Post-implementation review

| Question | Answer |
|---|---|
| Implemented as planned? | Yes |
| Success check met? | Ready, zero restarts (step 7) |
| Unplanned impact? | None |
| Problem action item updated? | Action 2 confirmed; action 1 remains |
