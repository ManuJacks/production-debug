# Release Policy

## Versioning model

This project follows semantic versioning:

- `MAJOR`: backward-incompatible command or behavior changes
- `MINOR`: backward-compatible additions and enhancements
- `PATCH`: backward-compatible fixes and reliability improvements

## Compatibility contract

- Existing script commands and flags should remain stable across patch and minor releases.
- Breaking changes must be introduced only in a major release with explicit migration notes.

## Changelog requirements

Behavior-impacting changes must update `CHANGELOG.md` with:

1. What changed
2. Why it changed
3. Operator impact or migration guidance (if applicable)

## Deprecation policy

- Deprecated flags/commands should remain functional for at least one minor release.
- Deprecations must be documented in `CHANGELOG.md` and in script usage text where applicable.

## Release checklist

1. All CI gates pass (Python lint/tests, shell lint, secret scan, dependency audit)
2. `CHANGELOG.md` updated
3. Docs updated for any user-visible behavior
4. Version updated/tagged according to semantic versioning
5. SBOM artifact with signed provenance attestation generated and attached to release

## Supply chain controls

- All third-party GitHub Actions are pinned to immutable commit SHAs.
- Dependency vulnerability scanning runs in CI on every push via `pip-audit`.
- SBOM is generated for every CI run and uploaded as an artifact.
- KPI and evidence artifacts now include SHA256 checksum manifests in CI outputs for immediate integrity verification.
- SBOM provenance attestation via `actions/attest-build-provenance` is tracked as a future milestone (requires a public repository or an eligible GitHub plan). See Priority 3 in `docs/NEW_FEATURES.md`.
- To verify a release artifact attestation (once enabled): `gh attestation verify <artifact> --repo <owner>/<repo>`

## Third-party artifact policy

- Runtime binaries extracted from third-party images are **not committed** to this repository.
- Allowed `third_party/` content is limited to metadata and operational evidence:
	- manifest YAML,
	- provenance/readme notes,
	- observed host lists,
	- redacted sample outputs.
- CI enforces this policy by failing if tracked files under `third_party/` include runtime directories (`app/`) or common binary extensions (`.dll`, `.so`, `.dylib`, `.exe`, `.jar`, `.zip`, etc.).
- If source-level review is required, reference the upstream source repository or image digest in documentation instead of committing runtime payloads.

Current verification commands for CI artifacts:

```bash
sha256sum -c kpi-artifacts.sha256
sha256sum -c sbom.cyclonedx.sha256
```
