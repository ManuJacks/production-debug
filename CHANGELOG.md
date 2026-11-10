# Changelog

All notable changes are recorded here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

- Upgraded `vim-tiny` to full `vim` and added `less` for improved in-container editing.
- Extended network diagnostic tooling: added `netcat-openbsd`, `fping`, `arping`, `tshark`, `ngrep`, `tcpflow`, `sslscan`, `ethtool`, `ipcalc`, `iptables`, `ipvsadm`, `util-linux` (nsenter).
- Added binary installs for `crictl` (v1.31.1), `etcdctl`+`etcdutl` (etcd v3.7.3), `grpcurl` (v1.9.1), and `curlie` (v1.7.2).
- Added `k8s/debug-pod-privileged.yaml`: elevated-capability variant for iptables/ipvsadm/tshark/nsenter/crictl during node-level incidents.
- Added `docs/procedures/PRIVILEGE_ESCALATION.md`: full approval workflow, per-tool capability reference, K8s and VM escalation procedures, and mandatory cleanup steps.
- Added full MCP tool annotation hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) across all MCP server tools.
- Added `production_debug` package with credential sanitization, secret redaction, and deterministic bundle verification.
- Enforced incident bundle credential scrub and forbidden file pruning in `incident_bundle.sh`.
- Added comprehensive unit and security test suite covering input sanitization, injection safety, credential leak prevention, and failure handling.
- Added reproducible test reporting and artifact capture to CI workflow.
- Added blameless firefighting guidance and operational handoff expectations.
- Added Kubernetes failure-injection exercise catalog and lab structure.
- Added production deployment hardening and documentation governance improvements.
