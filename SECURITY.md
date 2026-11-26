# Security policy

Do not commit credentials, customer data, unredacted incident bundles, private hostnames, or production access details.

Report suspected vulnerabilities privately to the repository maintainers. Include the affected component, impact, reproduction steps, and a safe mitigation if known. Do not test suspected vulnerabilities against production systems without explicit authorization.

Diagnostic output may contain sensitive network, identity, or workload information. Store bundles in an approved location, verify checksums, restrict access, and delete them according to the owning incident's retention policy.

## Diagnostic access

What the diagnostic identity, and any AI assistant using it, may read, where and when, is recorded in [ADR-SEC-001: Diagnostic access model](docs/security/ADR-SEC-001-diagnostic-access-model.md). Read it before granting access or changing `k8s/rbac.yaml`, `gitops/base/rbac.yaml` or `access/`.
