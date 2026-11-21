# Demonstration video script (60–90 seconds)

A screen recording of `demo/run.sh` with voice-over. Everything shown is
produced live by the script; nothing is staged or edited into the output.

## Setup

- Terminal at least 120 columns, font 16 pt or larger, dark theme.
- A disposable cluster. Pull the diagnostic image to the nodes beforehand so
  step 2 does not wait on a large download.
- Run once off-camera to confirm the cluster is healthy, then record:

```bash
DEMO_CONTEXT=<context> DEMO_CONFIRM=<context>/production-debug-lab \
DEMO_IMAGE=<image> demo/run.sh run
```

- The full run includes about 60–90 s of waiting (rollout, the 20 s stability
  window and namespace deletion). Cut or speed up those waits in editing; do
  not cut any output that proves a property.

## Script

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:08 | Title card: **How do you debug production without making production worse?** | "During an incident, the fastest way to make things worse is to give everyone, and now every AI assistant, the power to change production while they investigate." |
| 0:08–0:18 | Step 1: crash-looping pod, `restartCount=2` | "Here's a real failure: a service crash-looping on startup." |
| 0:18–0:28 | Step 2: diagnostic pod created; restricted profile, read-only, expires in one hour | "Instead of handing out admin, we launch a short-lived diagnostic pod. It runs non-root, with a read-only filesystem, and deletes itself within an hour." |
| 0:28–0:42 | Step 3: the green `allow` and `deny` table, then the live `Forbidden` delete | "Its identity can read this one namespace, and nothing else. Every write is denied. Here it tries to delete the pod from inside, and the API server refuses." |
| 0:42–0:52 | Step 4: evidence steps `ok`, archive verified with fingerprint | "It collects structured evidence: pods, events, logs. Secrets are never requested, output is redacted, and the bundle is verified before it leaves the pod." |
| 0:52–1:08 | Step 5: MCP tool list (`readOnlyHint=True`), logs showing `missing CONFIG_URL`, out-of-scope request Forbidden, Assessment | "Now an AI assistant investigates through MCP, as the same read-only identity. It finds the root cause, a missing configuration value. When it reaches outside its scope, it's denied. It can diagnose. It cannot act." |
| 1:08–1:18 | Step 6: `identity: kubernetes-admin`, deployment configured | "The fix is applied by a human operator, with separate credentials, through a reviewed change." |
| 1:18–1:26 | Step 7: `ready=true restarts=0` | "Recovery is verified, not assumed: ready, with zero restarts across a stability window." |
| 1:26–1:30 | Step 8: namespaces removed; link to the repository | "Then everything is cleaned up. The code and tests are on GitHub." |

## Accuracy notes

- Say "read-only for this namespace", not "read-only everywhere": the
  identity is namespace-scoped by design.
- The AI's investigation in the demo is a scripted MCP client, so the run is
  reproducible. Do not describe it as an autonomous agent; an interactive
  assistant can be attached to the same server command.
- Do not quote durations or success rates beyond what the recorded run shows.
