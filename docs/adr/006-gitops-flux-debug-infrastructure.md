# ADR 006: GitOps Management of Production Debugging Infrastructure via Flux

- Status: Accepted
- Date: 2026-10-29
- Deciders: Maintainers
- Technical area: gitops, security, k8s-architecture

## Context

In production environments, ad-hoc creation of debugging RBAC roles, ServiceAccounts, and diagnostic pods creates configuration drift and security blind spots. Often during incidents, engineers grant temporary `cluster-admin` privileges that are forgotten and left behind indefinitely.

To adhere to enterprise compliance and least-privilege principles, the underlying debug infrastructure must be continuously reconciled through GitOps.

## Decision

The platform uses **Flux v2 (`Kustomization` and `GitRepository` CRDs)** to govern debug infrastructure:
1. **Separation of Concerns**:
   - The **Debug Infrastructure** (Namespace `debug-system`, ServiceAccount with Azure Workload Identity annotations, and scoped read-only RBAC) is managed declaratively via Flux.
   - The **Debug Sessions** remain strictly ephemeral (spun up on-demand via `kubectl debug` or an ephemeral pod template referencing the GitOps-managed ServiceAccount).
2. **Automated Pruning**: Any manual tampering or lingering temporary privileges granted in `debug-system` are automatically reconciled and reverted by Flux.
3. **Continuous Drift Detection**: Ensures that cluster-reader roles across staging and production clusters are identical, auditable in git history, and reviewable by security teams.

## Consequences

- Positive: Zero manual `kubectl apply` needed for RBAC in production; complete git audit trail for who approved debugging permissions.
- Costs: Cluster administrators must configure Flux to point to the repository.
