# Engineering Decisions and Tradeoffs

This document records the decisions that matter most when operating `production-debug` in a real incident. It is intentionally concise: the goal is to make the security boundary, operational assumptions, and future direction reviewable by someone who did not build the system.

## Threat model

The diagnostic pod is treated as sensitive infrastructure. It can observe cluster state, read workload logs, inspect network traffic, and access cloud metadata endpoints. The default workflow therefore assumes:

- responders are authenticated and authorized by the deploying organization;
- the pod may see confidential incident data;
- incident bundles are untrusted until reviewed and verified;
- a diagnostic tool must not mutate workloads by default;
- elevated node inspection is an exceptional, separately approved workflow.

This project does not provide authorization, immutable evidence storage, or complete secret detection. Those controls remain deployment responsibilities.

## Default versus elevated capabilities

The standard pod runs as UID 10001, disables privilege escalation, uses RuntimeDefault seccomp, drops all Linux capabilities, and uses a read-only root filesystem. `/tmp` and `/tmp/incident-bundle` are the only writable locations. Packet capture and node/process inspection require the separately approved privileged overlay.

`NET_ADMIN`, `NET_RAW`, and `SYS_PTRACE` are still meaningful privileges. They are retained in the default profile because the toolkit is intended to diagnose network and process failures, but the pod must not be treated as a low-trust workload. The privileged manifest adds host PID access, `SYS_ADMIN`, and a CRI socket only for an approved node-level investigation.

## Why access is granted per incident namespace

Earlier releases bound a read-only ClusterRole with a ClusterRoleBinding, on the grounds that responders compare state across the cluster and an emergency grant would be less auditable than a declared role. In practice that gave the diagnostic identity standing read access to every namespace, including ConfigMaps, whether or not an incident was open. Read-only is not harmless.

The default is now namespace-scoped. `prod-debug-reader` is a ClusterRole used as a template and bound with a RoleBinding in the incident namespace only (`scripts/grant-incident-access.sh grant <ns>`), and the binding is removed when the incident closes. The grant is still declared in Git and auditable: it is one well-known role, one well-known binding name, and the script checks the result with `kubectl auth can-i`. The only standing cluster-wide grant is read access to `nodes` and `namespaces`, which are cluster-scoped and needed to triage node pressure before a namespace is known. Secrets, ConfigMaps, `pods/exec` and write verbs are never granted.

Since ADR 008, only namespaces in the environment's allowlist (`access/<env>.namespaces`) can be granted, and container logs are a separate role granted only with `--logs`. Cross-namespace investigations bind the same role into each affected, allowlisted namespace. A cluster-wide overlay remains possible but should require explicit approval and evidence that the incident class needs it.

## Release and rollback policy

Manifests reference a release tag rather than `latest`; the GitOps overlay supplies the version used by a cluster. Production deployments should promote an immutable digest alongside the tag, record the change in the changelog, and retain the previous digest for rollback.

## Evidence handling

Bundle sanitization is best-effort pattern matching. Verification rejects known sensitive filenames and recognized credential patterns, computes per-file SHA-256 digests, and creates a deterministic bundle fingerprint. Verification is a gate for review, not proof that a bundle contains no secrets. Bundles must still be manually reviewed before sharing.

## Next hardening steps

1. Promote image digests in GitOps environments and verify signatures before deployment.
2. Add adversarial archive tests for links, duplicate entries, oversized payloads, and existing extraction directories.
3. Measure incident time-to-diagnosis and handoff completeness in game-day exercises.
