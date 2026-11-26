# Diagnostic access allowlists

One file per environment: `<env>.namespaces`. It lists the only namespaces
that `scripts/grant-incident-access.sh --env <env> grant` will bind the
production-debug ServiceAccount into. A namespace that is not listed cannot
be granted, even by an operator in a hurry. Adding one is a reviewed change
in Git.

Format:

- `context=<kubeconfig context>` (required): the cluster this allowlist is
  for. The script refuses to grant if the current context differs, so a lab
  allowlist cannot be used against production.
- One namespace per line. `#` starts a comment.

Being listed grants nothing by itself. Access exists only between
`grant` and `revoke` for one incident. Logs need an explicit `--logs`.

Revoking is never restricted by the allowlist: removing access always works.

The allowlist is one of two approvals. The platform must also label the
namespace `production-debug/diagnosable: "true"` (kubernetes-in-finance
`kubernetes/tenants/`). The `production-debug-access-guard` admission policy
enforces that label in the API server, whether or not this script is used. See
[docs/security/admission-policy-guide.md](../docs/security/admission-policy-guide.md).
