# Contributor roadmap

These are intentionally scoped opportunities for improving production-debug
without access to a production cluster. Please open an issue before starting
larger changes.

## Good first contributions

- Add unit tests for an existing failure path or boundary condition.
- Improve the local MCP startup documentation and smoke test.
- Add a disposable incident scenario with manifests, expected evidence, and tests.
- Improve redaction tests with a documented synthetic example.
- Clarify a runbook, CLI reference, or least-privilege explanation.
- Test the Docker image on another supported architecture.

## Intermediate contributions

- Add a read-only diagnostic tool with input validation, bounded output, timeout
  handling, explicit MCP annotations, and focused security tests.
- Add an integration test for a Kubernetes RBAC boundary.
- Improve the demo's failure reporting and cleanup behavior.
- Add structured tool health information without exposing credentials or tokens.

## Design constraints

New diagnostics should preserve these defaults:

- no mutation of Kubernetes, cloud, host, or network configuration;
- least-privilege identity and explicit RBAC requirements;
- no shell interpolation for user-controlled values;
- bounded output, timeouts, and resource use;
- redaction of sensitive output where applicable;
- tests for denied, malformed, unavailable, and timeout cases.

Tools that write local evidence, require extra capabilities, or contact external
services must say so in their descriptions and annotations. See
`docs/IMPLEMENTATION_GUIDE.md` and `SECURITY.md` before proposing one.
