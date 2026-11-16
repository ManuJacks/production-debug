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
5. For container releases, verify the published image signature and confirm that its SBOM is attached. A signed build-provenance attestation is not currently published by the configured workflow.

## Supply chain controls

- Third-party GitHub Actions in `kpi-publish.yml` are pinned to immutable commit SHAs. Other workflows still use version tags; pin them before claiming repository-wide immutability.
- Dependency vulnerability scanning runs in CI on every push via `pip-audit`.
- The container publish workflow signs the published image and attaches a CycloneDX SBOM to it.
- The KPI publishing workflow includes a SHA256 manifest for its KPI output artifacts.
- A separate signed build-provenance attestation is not currently configured; do not describe the SBOM attachment or image signature as an attestation.
- Verify the published image signature and attached SBOM by immutable image digest before relying on them.

## Third-party artifact policy

- Runtime binaries extracted from third-party images are **not committed** to this repository.
- Allowed `third_party/` content is limited to metadata and operational evidence:
	- manifest YAML,
	- provenance/readme notes,
	- observed host lists,
	- redacted sample outputs.
- CI enforces this policy by failing if tracked files under `third_party/` include runtime directories (`app/`) or common binary extensions (`.dll`, `.so`, `.dylib`, `.exe`, `.jar`, `.zip`, etc.).
- If source-level review is required, reference the upstream source repository or image digest in documentation instead of committing runtime payloads.

Current verification command for the KPI publishing artifact:

```bash
sha256sum -c kpi-artifacts.sha256
```
