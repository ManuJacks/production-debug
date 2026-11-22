# Changelog

All notable changes are recorded here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

- Added `production_debug/incident_record.py`: drafts a ServiceNow-style incident (INC) record (Markdown, or JSON with `incident` table field names) from a verified evidence bundle. Fails closed on an unverified bundle; work notes are source-quoted facts in UTC order, re-redacted; never infers a root cause; priority derived from impact × urgency. Never submits to any system (ADR 007).
- Demo step 4 now drafts the incident record at Sev 3 (impact 3 × urgency 1); optional `DEMO_DETECTED_AT` / `DEMO_DETECTED_BY` record the triggering alert as the first work note.
- Added incident-management procedures: severity matrix, INC, Problem (post-incident review) and Change request templates, with worked PRB and CHG examples for the demo scenario.
- CI: fixed an invalid workflow (job-level `runner` context) that prevented every CI job from running; pinned all third-party actions to commit SHAs; added `actionlint`; pinned test dependencies (PyYAML was missing from the test job).
- CI: the changelog policy now treats any path under `.github/`, `docs/` or `tests/` as non-functional (it previously matched only the bare directory names).
- Added an end-to-end incident demonstration (`demo/run.sh`): crash-looping workload, ephemeral read-only diagnostic pod (namespace-scoped Role, Pod Security `restricted`, self-expiring), least-privilege proof, evidence collection, MCP investigation, operator remediation, recovery verification and idempotent cleanup. Runs in CI on kind.
- Added `scripts/k8s_evidence.sh`: read-only Kubernetes evidence collector with a per-step `manifest.json`; continues on missing resources and API failures; bounded, recorded retries.
- Added read-only Kubernetes MCP tools (`k8s_list_pods`, `k8s_get_events`, `k8s_describe_pod`, `k8s_get_pod_logs`) restricted to `get`/`describe`/`logs`.
- Fixed: incident bundling now fails closed (no partial or unverified bundle remains) and no longer depends on the caller's working directory. Previously, sanitization silently failed outside the repository root and left unredacted content on disk.
- Fixed: redaction now covers `token=`, Azure secret assignments and `Authorization: Bearer` headers.
- Fixed: MCP stdio mode printed a banner on stdout, corrupting the JSON-RPC stream.
- Fixed: Kubernetes manifests referenced image tag `0.1.0`, which was never published; they now reference `0.2.0`.
- Pinned `fastmcp` to 4.2.4.
- Removed vendored vim plugins (`docker/vim_runtime`, `docker/vim_pack`: awesome-vimrc, bash-support, perl-support, copilot.vim, copilot-chat.vim). The image keeps full `vim` with its default configuration. This reduces image attack surface and repository size.
- Refactored `docker/Dockerfile` to a multi-stage build:
  - Stage 1 (`builder`): Compiles CPAN XS modules (`JSON::XS`, `Net::Pcap`, `Term::ReadLine::Gnu`, etc.) into `/opt/perl-vendor`, builds Python venvs (`/opt/mcp-venv`, `/opt/nettools-venv`), and downloads all static Go binaries (`kubectl`, `helm`, `k9s`, `stern`, `kubectx`, `kubens`, `kubectl-neat`, `kubectl-tree`, `crictl`, `etcdctl`, `etcdutl`, `grpcurl`, `curlie`).
  - Stage 2 (`final`): Lean runtime image copying only compiled vendor trees and static binaries, eliminating `gcc`, `make`, and `-dev` header packages to reduce attack surface and container footprint.
- Added Perl toolchain: `perl`, `perl-doc`, `cpanminus` with full CPAN network-diagnostic module suite (`JSON::XS`, `LWP::UserAgent`, `LWP::Protocol::https`, `Net::DNS`, `Net::Ping`, `IO::Socket::SSL`, `Net::SNMP`, `Net::Pcap`, `Net::Whois::Raw`, `Term::ReadLine::Gnu`).
- Added Python network diagnostic venv (`/opt/nettools-venv`): `orjson`, `requests`, `httpx`, `dnspython`, `icmplib`, `pyopenssl`, `cryptography`, `pysnmp`, `scapy`, `ipwhois`, `netaddr`, `paramiko` — documented in `mcp/requirements-nettools.txt` with inline purpose comments.
- Added `.dockerignore` to exclude `.git` dirs, vim swap files, Python cache, and CI artifacts from build context.
- Added build dependencies: `gcc`, `make`, `libssl-dev`, `libpcap-dev`, `libreadline-dev` (required for XS CPAN modules and Python native extensions).

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
