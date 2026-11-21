# Field report: the demo surfaced a real cluster fault

- **Date:** 2026-11-21
- **Cluster:** five-node kubeadm cluster (three control planes, two workers,
  keepalived/HAProxy API VIP, Cilium) on Multipass VMs, built from
  [kubernetes-in-finance](https://github.com/ManuJacks/kubernetes-in-finance)
- **Full incident write-up:**
  [kubernetes-in-finance: Cluster-wide Clock Drift After Host Suspend](https://github.com/ManuJacks/kubernetes-in-finance/blob/main/docs/incidents/2026-11-21-clock-drift-after-host-suspend.md)

This is an account of what the toolkit did on a real, unhealthy cluster. It
is not a synthetic scenario.

## What the tooling recorded

While validating `demo/run.sh` against the cluster, evidence collection
inside the diagnostic pod failed intermittently:

```text
failed  kubectl client/server version
failed  pod descriptions
status=partial (ok=6 failed=2)
```

The evidence manifest kept the failure text for each step:

```text
error: You must be logged in to the server
(the server has asked for the client to provide credentials)
```

A valid ServiceAccount token being rejected *some* of the time is not a
permissions problem: the same identity succeeded on other calls in the same
run. The collector marked the run `partial`, kept going, and preserved the
error text instead of discarding it.

## Where that led

| Observation | Evidence | Conclusion |
|---|---|---|
| Intermittent 401s for a valid token | `manifest.json` per-step errors | Some API servers reject the token |
| Rejections only on one API server | `service account token is not valid yet` in tf-ha-control3's log | Token issue time is in that server's future |
| Node clocks disagree by up to ~4.5 h | `chronyc tracking` on every VM | Clock skew, not auth configuration |
| chrony reaches its sources but does not correct | Ubuntu default `makestep 1 3` | Large offsets after a host suspend can only be slewed |

Investigating the same cluster then found an API server running outside the
kubelet's management for three days, because a backwards clock jump inverted
the creation-time order of its containers.

## What changed in this repository as a result

- **Bounded, recorded retries** in `scripts/k8s_evidence.sh` and the MCP
  `kubectl` helper. Transient API failures are retried up to three times;
  Forbidden and NotFound are not retried. The attempt count is written to
  the manifest, so instability remains visible as evidence instead of being
  hidden by a retry.
- **No config-override flags in-cluster.** The same validation run showed that
  `--request-timeout` makes client-go skip in-cluster ServiceAccount
  configuration. Both the collector and the MCP server now bound calls with
  process timeouts instead.

## Result

After the cluster fixes, the same demo run recorded `status=complete` with
**no retried steps** and no credential errors.

## Why it matters

The demo's purpose is to show that diagnostics can be safe. This run showed
the other half: a collector that records *how* each step failed, rather than
only whether it succeeded, turns an intermittent symptom into a lead. The
partial result was the evidence.
