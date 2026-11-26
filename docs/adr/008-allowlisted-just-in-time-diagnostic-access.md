# ADR 008: Allowlisted, just-in-time diagnostic access

- Status: Accepted
- Date: 2026-11-25
- Deciders: Maintainers
- Technical area: safety, operations
- Security record: [ADR-SEC-001](../security/ADR-SEC-001-diagnostic-access-model.md) (threats, evidence, residual risks)

## Context

v0.2.0 made the general-purpose RBAC namespace-scoped. An operator bound the
read-only role into an incident namespace with
`scripts/grant-incident-access.sh` and revoked it afterwards. Any namespace
except the system ones could be granted, and container logs came with
ordinary workload metadata.

An AI assistant investigates through this identity. In a regulated
environment it must be possible to say in advance which namespaces it can
ever see, per environment, and logs need separate treatment because they can
contain credentials, tokens and personal data.

Three scopes were considered:

- A. Only `debug-system`. Safe, but it cannot diagnose anything.
- B. All namespaces except system ones. Convenient, but the reachable surface
  grows silently every time a namespace is created.
- C. An explicit allowlist of namespaces, per environment.

## Decision

1. **C, used to decide what may be granted, not as standing access.** Each
   environment has `access/<env>.namespaces`: a required `context=` line and
   the namespaces that may be granted. Being listed grants nothing. Access
   exists only between `grant` and `revoke` for one incident. Adding a
   namespace is a reviewed change in Git. The production allowlist starts
   empty.
2. **The script refuses to grant** a namespace that is not listed, a system
   namespace even if it is listed, or any namespace when the current
   kubeconfig context is not the one named in the file. That stops a lab
   allowlist from being used against production. Revoking is never
   restricted.
3. **Three layers of RBAC:**
   - Layer 1: nodes and namespaces, as a standing ClusterRoleBinding.
   - Layer 2: workload metadata (`prod-debug-reader`).
   - Layer 3: `pods/log` (`prod-debug-log-reader`), granted only with
     `--logs`.

   Re-granting without `--logs` removes an earlier log grant.
4. **Exec, port-forward, Secrets, ConfigMaps and database access are out of
   scope.** Each would need its own explicit access model.
5. **Application namespaces are owned by the platform**, not by this tool.
   The lab tenants `app-team-a` and `app-team-b` are declared in
   kubernetes-in-finance (`kubernetes/tenants/`).

## Consequences

- The set of namespaces an AI assistant can ever be granted is reviewable
  in Git, per environment.
- Without `--logs`, the MCP log tool and the evidence collector's log steps
  are Forbidden. Responders must ask for logs deliberately.
- `grant` now needs `--env`. This is a breaking change to a script released
  in 0.2.0.
- **The allowlist is enforced by the script, not by the API server.** A
  cluster-admin can still create a RoleBinding by hand. Server-side
  enforcement (for example a ValidatingAdmissionPolicy that rejects
  bindings of the `prod-debug-*` roles outside labelled namespaces) is a
  follow-up.
- Checks use `kubectl auth can-i ... --subresource=<sub>`. The
  `pods/<sub>` form names a pod and silently checks the wrong thing.
