# Changelog

All notable changes are recorded here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

- Added Perl toolchain: `perl`, `perl-doc`, `cpanminus` with full CPAN network-diagnostic module suite (`JSON::XS`, `LWP::UserAgent`, `LWP::Protocol::https`, `Net::DNS`, `Net::Ping`, `IO::Socket::SSL`, `Net::SNMP`, `Net::Pcap`, `Net::Whois::Raw`, `Term::ReadLine::Gnu`).
- Added Python network diagnostic venv (`/opt/nettools-venv`): `orjson`, `requests`, `httpx`, `dnspython`, `icmplib`, `pyopenssl`, `cryptography`, `pysnmp`, `scapy`, `ipwhois`, `netaddr`, `paramiko` — documented in `mcp/requirements-nettools.txt` with inline purpose comments.
- Installed `amix/vimrc` awesome-vimrc runtime (with `bash-support.vim` and `perl-support.vim` plugins) for `debuguser` via `install_awesome_parameterized.sh`.
- Bundled `copilot.vim` and `copilot-chat.vim` plugins (via vim 8 native packages under `~/.vim/pack/`); `copilot-language-server` intentionally excluded (no Node in container — plugin loads silently, auth mountable later).
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
