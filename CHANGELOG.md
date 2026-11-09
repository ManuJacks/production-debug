# Changelog

All notable changes are recorded here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

- Added full MCP tool annotation hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) across all MCP server tools.
- Added `production_debug` package with credential sanitization, secret redaction, and deterministic bundle verification.
- Enforced incident bundle credential scrub and forbidden file pruning in `incident_bundle.sh`.
- Added comprehensive unit and security test suite covering input sanitization, injection safety, credential leak prevention, and failure handling.
- Added reproducible test reporting and artifact capture to CI workflow.
- Added blameless firefighting guidance and operational handoff expectations.
- Added Kubernetes failure-injection exercise catalog and lab structure.
- Added production deployment hardening and documentation governance improvements.
