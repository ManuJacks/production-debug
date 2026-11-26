# ADR-SEC-001: Diagnostic access model for production-debug

- Status: Accepted
- Date: 2026-11-25
- Deciders: Maintainers
- Technical area: security (authorization, least privilege, AI agent access)
- Related: [ADR 004](../adr/004-production-access-no-ssh-by-default.md),
  [ADR 005](../adr/005-mcp-readonly-incident-diagnostics.md),
  [ADR 008](../adr/008-allowlisted-just-in-time-diagnostic-access.md),
  [Engineering decisions](../ENGINEERING_DECISIONS.md),
  kubernetes-in-finance `docs/runbooks/tenant-namespaces.md`

This is the security record for how the production-debug identity, and any AI
assistant using it through the MCP server, is allowed to read a Kubernetes
cluster. It records:

- the exposure that existed before
- the decision and the controls that replaced it
- a false-assurance defect found while verifying them
- the evidence
- what remains open

ADR 008 is the engineering decision. This record is the security view of
the same change.

## 1. Context

production-debug lets people and AI assistants investigate incidents under a
read-only identity, the ServiceAccount `debug-system/prod-debug-sa`.
Remediation stays with a human operator using separate credentials. The
security question is not only "can it write?" but "what can it read, where,
and when?" In financial services, read access to application namespaces is
itself sensitive:

- **ConfigMaps** often hold connection strings and endpoints.
- **Logs** can hold credentials, tokens and personal data.
- **Standing access** means an assistant can read a namespace when there is
  no incident at all.

## 2. Exposure before this decision (before PR #13)

The general-purpose manifests (`k8s/rbac.yaml`, `gitops/base/rbac.yaml`)
bound the ClusterRole `prod-debug-reader` with a **ClusterRoleBinding**
(`prod-debug-reader-binding`). The ServiceAccount could get, list and watch,
across **every namespace**, at all times:

- pods and `pods/log`
- events, services and endpoints
- **ConfigMaps**
- nodes and namespaces
- workloads, ingresses and NetworkPolicies

The demo used a correctly scoped namespaced Role, so the demo's guarantees
did not hold for the general-purpose deployment. The README listed this as a
known limitation.

On the kubernetes-in-finance HA lab cluster this binding had been live for 19
days. No pod was running under it when it was removed. No production
environment used it.

## 3. Decision

### 3.1 Three layers of read access

| Layer | ClusterRole | Grants | Bound by | Lifetime |
|---|---|---|---|---|
| 1 Infrastructure discovery | `prod-debug-cluster-reader` | nodes, namespaces | ClusterRoleBinding | standing |
| 2 Workload diagnostics | `prod-debug-reader` | pods, events, services, endpoints, EndpointSlices, Deployments, ReplicaSets, StatefulSets, DaemonSets, ingresses, NetworkPolicies | RoleBinding in one namespace | one incident |
| 3 Sensitive diagnostics | `prod-debug-log-reader` | `pods/log` | RoleBinding in one namespace, only with `--logs` | one incident |

All verbs are `get`, `list` and `watch` (logs: `get` only). Layers 2 and 3
are ClusterRoles used as templates. A RoleBinding confines them to the
namespace it lives in.

**Never granted, at any layer:**
- Secrets and ConfigMaps
- `pods/exec`, `pods/attach`, `pods/portforward` and `pods/proxy`
- any write verb

Database access is out of scope and needs its own access model.

### 3.2 Allowlisted, just-in-time grants (scope option C)

Three scopes were considered:

- A. Only `debug-system`: safe, but it cannot diagnose anything.
- B. Every non-system namespace: the reachable surface grows silently with
  each new namespace.
- C. An explicit per-environment allowlist (chosen).

The allowlist decides **what may be granted**. It is not standing access.

- `access/<env>.namespaces` holds a required `context=` line plus the
  namespaces that may be granted. Changing it is a reviewed pull request.
- `lab` lists `app-team-a` and `app-team-b`. `production` starts empty: each
  entry needs an approved change naming the namespace, its owner and the
  justification.
- `scripts/grant-incident-access.sh --env <env> grant <ns> [--logs]` creates
  the RoleBinding(s). The script then verifies the result with 10 impersonated
  `kubectl auth can-i` checks and exits non-zero if any check is unexpected.
- `revoke <ns>` removes both bindings. Revoking is never restricted.

The script refuses (exit 2) and creates nothing when:

- no environment is given
- the namespace is not on the allowlist
- the namespace is a system namespace (`kube-system`, `kube-public`,
  `kube-node-lease`, `debug-system`), even if it is listed
- the current kubeconfig context differs from the allowlist's `context=`.
  This stops a lab allowlist from being used against production.

Re-granting a namespace without `--logs` removes an earlier log grant, so a
log grant never carries over unnoticed.

### 3.3 Ownership

Application namespaces belong to the platform, not to the diagnostic tool.
The lab tenants are declared in kubernetes-in-finance `kubernetes/tenants/`
with:

- Pod Security `restricted` (enforce, warn and audit)
- a ResourceQuota
- a `kif.io/tenant` owner label

Creating a namespace there does not make it diagnosable. That takes a
separate, reviewed change to this repository's allowlist. The two repositories
therefore act as two controls run by two different owners.

### 3.4 Server-side enforcement: `production-debug-access-guard`

The script's allowlist protects only people who use the script. A
ValidatingAdmissionPolicy (`k8s/admission-policy.yaml`) makes the API server
enforce the same boundary for **every** RoleBinding and ClusterRoleBinding
create or update, whether it comes from kubectl, GitOps or automation:

1. A RoleBinding to a production-debug role is admitted only in a namespace
   labelled `production-debug/diagnosable="true"`, and never in a system
   namespace. This applies whoever the subject is.
2. `prod-debug-reader` and `prod-debug-log-reader` are never admitted in a
   ClusterRoleBinding. Only Layer 1 may be cluster-wide.
3. The production-debug identity may be bound only to production-debug
   roles. It is recognised under all three of its RBAC names: as a
   ServiceAccount, as the User `system:serviceaccount:debug-system:prod-debug-sa`,
   and through the Group `system:serviceaccounts:debug-system`. Nobody can
   give it `view`, `edit` or `cluster-admin`.

Settings:

- `failurePolicy: Fail`
- `validationActions: [Deny]`
- matches CREATE and UPDATE only, so revoking (DELETE) is never blocked

**Two approvals, two owners.** A grant now needs both:

| Approval | Owner | Enforced by |
|---|---|---|
| Namespace label `production-debug/diagnosable: "true"` | Platform, in kubernetes-in-finance `kubernetes/tenants/` | API server (this policy) and the grant script |
| Namespace in `access/<env>.namespaces` | production-debug maintainers | Grant script |

How it works, how to test it, how to debug it, and rehearsal drills:
[admission-policy-guide.md](admission-policy-guide.md).

## 4. Threats and controls

| Threat | Control |
|---|---|
| AI assistant reads namespaces unrelated to the incident | Layer 2 bound per namespace; allowlist; `prod-debug-reader` never bound cluster-wide (contract test) |
| Standing read access with no open incident | No RoleBindings shipped (contract test); grant/revoke per incident |
| Credentials or personal data exposed through logs | Logs are Layer 3, granted only with `--logs`; re-grant drops it |
| Configuration secrets exposed through ConfigMaps | ConfigMaps and Secrets are never granted (contract test on every role) |
| Lab allowlist applied to the production cluster | Required `context=` match before any grant |
| Unreviewed growth of diagnosable scope | Allowlist in Git; new namespaces are not diagnosable by default |
| Diagnostic identity changes or executes in workloads | Read verbs only; no exec, attach, port-forward or proxy (contract test) |
| Access checks give false assurance | Subresources checked with `--subresource` (section 5); script and demo fail on unexpected results |
| Someone bypasses the script and binds a debug role by hand or through GitOps | Admission policy Rule 1: unlabelled namespaces denied server-side |
| Debug identity silently given broader roles (`view`, `edit`, `cluster-admin`) | Admission policy Rule 3, covering the ServiceAccount, User and Group forms |
| Workload or log layer bound cluster-wide | Admission policy Rule 2 and the manifest contract test |
| A broken policy expression fails open | `failurePolicy: Fail`; contract test; 17 live cases in CI |

## 5. Defect found during verification: `can-i` false assurance

`kubectl auth can-i get pods/log` does **not** check the log subresource. The
`resource/name` form asks whether the identity can get *a pod named `log`*.
The correct form is `kubectl auth can-i get pods --subresource=log`.

Live verification showed `can-i get pods/log` returning `yes` while an actual
log request from the pod was Forbidden. Before this fix, these checks passed
regardless of RBAC:

- the demo's `pods/log`, `pods/exec` and `deployments/scale` checks, which
  are 3 of the 12 checks in its "least-privilege proof"
- the grant script's checks in v0.2.0

The demo's `exec` and `scale` denials happened to be correct, because a pod
named `exec` cannot be created either. They did not prove what they claimed,
though. `demo/run.sh`, the grant script and the README example now pass
`--subresource`, and contract tests assert it.

**Lesson recorded:** a security check that has never been seen to fail proves
nothing. The positive control ("as admin, `can-i create pods
--subresource=exec` → yes") is part of the verification below.

## 6. Verification evidence (2026-11-25)

**HA lab cluster** (kubeadm v1.36.6, 3 control planes, 2 workers, Cilium),
from inside the `production-debug` pod (image `0.2.0`) and by impersonation:

| Check | Result |
|---|---|
| Old `prod-debug-reader-binding` deleted, new manifests applied | Only `prod-debug-cluster-reader` is bound cluster-wide |
| Before grant: `list pods -A`, `configmaps -A`, `secrets -A`, `pods -n kube-system` | Forbidden |
| Before grant: `list nodes`, `list namespaces` | allowed (Layer 1) |
| `grant kif-drill` (not listed) / `--env production` / no `--env` | Refused, exit 2, no binding |
| `--env lab grant app-team-a` | Pods readable; logs Forbidden; `app-team-b` Forbidden |
| `grant app-team-a --logs` | Logs readable |
| Re-grant without `--logs` | Logs Forbidden again |
| `revoke` | All checks `no`; no `production-debug-toolkit` RoleBindings remain |
| Positive control: admin `can-i create pods --subresource=exec` | yes |

**Automated checks:**

- `tests/test_rbac_manifests.py`:
  - **Manifest contract:** read-only verbs; no sensitive resources; logs only
    in Layer 3; only Layer 1 bound cluster-wide; no RoleBindings shipped; the
    two RBAC copies identical.
  - **Allowlist contract:** no system namespaces; `context=` required;
    production list empty.
  - **Script behaviour against a fake kubectl:** grant, logs, re-grant,
    revoke, eight refusal paths that must create nothing, and `--subresource`
    usage.
- kubernetes-in-finance `tests/test_tenant_namespaces.py`: tenants enforce
  `restricted`, have quotas, and run compliant workloads.
- CI runs the corrected demo end to end on kind for every pull request.
- `scripts/test-access-guard.sh` runs 17 live admission cases (all three
  rules, unrelated bindings, existing objects, UPDATE and DELETE) using
  `--dry-run=server`. CI runs them on kind for every pull request.
- On the HA lab cluster (2026-11-25):
  - all 17 cases matched
  - `grant app-team-a --logs`, then reading logs from the pod, then `revoke`,
    all succeeded with the policy active
  - before the platform label was applied, the grant was refused by both the
    script and the API server
  - `status.typeChecking` is empty

## 7. Residual risks and follow-ups

1. **Resolved by section 3.4, with remaining limits:**
   - A cluster-admin can delete or change the policy. That is now a
     deliberate change to a security control; API audit logging (item 3)
     would record it.
   - Rule 3 does not catch bindings to the broad groups
     `system:serviceaccounts` or `system:authenticated`. Matching them could
     block the API server's reconciliation of built-in bindings such as
     `system:basic-user`. Accepted risk.
   - Admission does not re-check existing objects. Removing the label leaves
     open grants in place, so they must be revoked too.
   - A broken `Fail` policy blocks every RoleBinding and ClusterRoleBinding
     write in the cluster. Policy changes must be tested on kind or with a
     scratch copy first (guide, section 5, item 7).
2. **Grants do not expire.** Access lasts until `revoke` is run. A forgotten
   revoke leaves standing access in that namespace. Follow-up: an expiry
   annotation on the binding plus a reaper, or a short-lived token-based
   grant.
3. **No API audit trail yet.** The kubernetes-in-finance cluster does not
   enable API server audit logging, so grants, revokes and the identity's
   reads are not recorded server-side. Follow-up: an audit policy in the
   kubeadm configuration.
4. **Layer 1 is standing.** Node and namespace objects expose node names,
   addresses, capacity and namespace names cluster-wide. This is accepted,
   because it is needed to triage node pressure before a namespace is known.
5. **Layer 2 still includes some potentially sensitive metadata.** Pod specs
   and environment variables set inline in workload specs are readable once
   Layer 2 is granted. Secrets referenced by name are not readable.
6. **The general-purpose debug pod has no self-expiry.** It mounts a
   ServiceAccount token (`automountServiceAccountToken: true`) and has no
   `activeDeadlineSeconds`, unlike the demo pod. Follow-up: align it with the
   demo pod.
7. **Breaking CLI change.** `grant` requires `--env` since this change. The
   v0.2.0 form (`grant <ns>`) is refused.

## 8. Change history

| Date | Change | Reference |
|---|---|---|
| 2026-11-25 | Cluster-wide ClusterRoleBinding replaced by per-namespace RoleBinding; ConfigMaps removed | PR #13 (`790b9ae`), released in v0.2.0 (`a59c0c1`) |
| 2026-11-25 | Old binding removed from the HA lab cluster; v0.2.0 manifests applied | Operator action, verified as in section 6 |
| 2026-11-25 | Tenant namespaces `app-team-a`, `app-team-b` | kubernetes-in-finance PR #7 |
| 2026-11-25 | Allowlist, log layer, `can-i` subresource fix, this record | PR #15, ADR 008 |
| 2026-11-25 | Admission policy `production-debug-access-guard`, platform approval label, live test script, study guide | This PR; kubernetes-in-finance tenant label PR |
