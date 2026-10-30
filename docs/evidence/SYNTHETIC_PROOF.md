# Synthetic proof pack

This repository intentionally uses synthetic evidence only. The names, registry domains, images, namespaces, logs, and outcomes in the lab are fictional and must not be replaced with former-employer data.

## Proof protocol

For each scenario:

1. Run `bash scenarios/run.sh setup <scenario>` in a disposable cluster.
2. Capture `kubectl describe`, logs, events, and the hypothesis timeline.
3. Diagnose the fault domain before changing the workload.
4. Apply the smallest recovery and verify the result.
5. Save a redacted bundle and record the cleanup command.
6. Add one systemic follow-up and one signal that would have shortened diagnosis.

The resulting proof demonstrates repeatable incident response, not historical production access. A completed exercise record should include cluster type/version, scenario revision, timestamps, commands, evidence checksum, recovery result, and blameless learning notes.
