# External Security Review Record

**Project:** production-debug  
**Repository:** [ManuJacks/production-debug](https://github.com/ManuJacks/production-debug)  
**Review provider:** M8ven  
**Review date:** November 23, 2026  
**Reviewed commit:** `cde3deb7679d525e0a733c6a5a7659f6ec5099e7`  
**Code hash:** `9288dd5191f89b0aaa7c05d686aaebd0b884b25b5289f0fad8a1381a651b7e0e`  
**Review status:** Disputed; finding partially valid and remediated in `f96d308` (see section 8); M8ven response pending

## 1. Purpose

This document records an independent third-party security assessment of the production-debug MCP server.

It preserves the assessment findings, the project maintainer's response, and the eventual resolution. The purpose is to maintain an auditable engineering record and demonstrate a transparent approach to external security feedback.

## 2. Assessment summary

M8ven reported a grade change from **B (November 8, 2026) to C (November 23, 2026)** following changes to the repository.

The assessment stated that it reviewed 13 Python files at commit `cde3deb`.

M8ven reported that it attempted to run the server but was unable to do so. The published grade was therefore based on static code review rather than successful runtime verification.

### Positive findings

M8ven reported:

- No credential exfiltration identified.
- No unexpected sensitive-file access identified.
- No code obfuscation identified.
- Open-source licensing and README documentation present.

### Findings requiring review

The assessment identified a mismatch involving:

`capture_network_trace_summary`

Specifically:

1. The tool was annotated as read-only through `readOnlyHint: true`.
2. The handler used `subprocess.run()`.
3. M8ven concluded that the implementation performed write, delete, or execution operations inconsistent with the declared read-only behaviour.
4. The published tool description did not adequately disclose those side effects.

The assessment recommended either correcting the annotation or changing the implementation and tool description to accurately represent its behaviour.

## 3. Maintainer response

**Status: Disputed**

The maintainer submitted a dispute through M8ven.

The dispute and any supporting explanation should be retained alongside this record.

The dispute does not, by itself, establish that the assessment is incorrect. Likewise, the published finding should not be treated as a confirmed vulnerability without examining the underlying implementation and evidence.

The relevant handler should be reviewed to establish:

- The exact subprocess command executed.
- Whether packet capture creates temporary files.
- Whether files are subsequently removed.
- Whether command arguments are fixed or externally influenced.
- Whether execution has appropriate timeouts and resource limits.
- Whether the declared MCP annotations accurately represent the implementation.

## 4. Engineering response and remediation criteria

Regardless of the dispute outcome, the following checks are appropriate:

| Area | Required consideration |
|---|---|
| MCP annotations | Accurately represent tool side effects |
| Tool description | Disclose subprocess execution and file operations |
| Command execution | Restrict commands and arguments |
| Resource controls | Bound execution time and capture size |
| Filesystem | Use controlled temporary locations and predictable cleanup |
| Permissions | Apply least-privilege execution |
| Testing | Verify success, failure, timeout and cleanup behaviour |

The objective is not to remove legitimate diagnostic functionality simply to satisfy an automated scanner. It is to ensure that the tool's declared security properties accurately describe what it does.

## 5. Evidence and references

- Repository: https://github.com/ManuJacks/production-debug
- M8ven assessment: https://m8ven.ai/mcp/manujacks/production-debug
- M8ven grade history: https://m8ven.ai/mcp/manujacks/production-debug/history
- Raw assessment: https://m8ven.ai/api/mcp/score?url=https%3A%2F%2Fgithub.com%2FManuJacks%2Fproduction-debug

**Reviewed commit:**

`cde3deb7679d525e0a733c6a5a7659f6ec5099e7`

## 6. Dispute outcome

To be completed when M8ven responds.

Record:

- Response date.
- Whether the dispute was accepted, partially accepted, or rejected.
- Any revised findings or grade.
- Any additional evidence requested.
- Any resulting code changes and their commit references.

Do not overwrite the original assessment. Preserve the original finding and append the resolution.

## 7. Project governance lesson

Security annotations and tool descriptions are part of an MCP server's trust boundary.

A diagnostic tool can have legitimate operational capabilities while still presenting a misleading security contract if its declared behaviour differs from its implementation.

External assessment should be treated as an opportunity to validate both code and the claims made about that code.

The project maintains an obligation to:

- Examine external findings objectively.
- Challenge findings when evidence warrants it.
- Correct genuine defects.
- Preserve the assessment and resolution history.
- Avoid claiming independent verification beyond what has actually been demonstrated.


## 8. Handler-level review and remediation (November 23, 2026)

Appended; sections 1–7 above are preserved as written.

### Conclusion

**Partially valid.** The scanner's stated reason (the handler calls
`subprocess.run()`) does not by itself establish a write, delete or state
change: the server's other read-only tools also run `kubectl` through
`subprocess.run()` and were not flagged. Review of the handler did, however,
find a genuine defect: at `cde3deb`, `tcpdump` ran **without `-p`**, so it
switched the interface into **promiscuous mode**. That changes interface
state, contradicting `readOnlyHint: true` and the documented claim that the
tool "does not change interface configuration".

### Review checklist (section 3)

| Question | Finding at `cde3deb` | After `f96d308` |
|---|---|---|
| Exact subprocess command | `tcpdump -i <iface> -c 25 -nn -q` | `tcpdump -p -i <iface> -c 25 -nn -q` |
| Temporary files created? | No (no `-w`/`-W`/`-G`; output captured in memory) | No; a test asserts no write flags |
| Files removed afterwards? | Not applicable | Not applicable |
| Arguments fixed or influenced? | Fixed, except the interface (allowlist `^[a-zA-Z0-9._-]{1,16}$`) and the duration (clamped to 1–30 s); argument list, no shell | Unchanged |
| Timeouts and resource limits | At most 25 packets; timeout `duration + 2` s; on timeout, captured packets were discarded | At most 25 packets; timeout = `duration_sec` (1–30 s); packets seen before the timeout are returned (`partial: true`) |
| Annotations accurate? | **No**: promiscuous mode changes interface state | Yes: `readOnlyHint: true` now holds |
| Description accurate? | Partly: claimed no interface change | States `-p`, no files, no interface or network configuration change, capability requirement |
| Permissions | Requires `NET_RAW`/`NET_ADMIN`; fails in the restricted diagnostic pod (all capabilities dropped) | Unchanged; documented |

### Remediation

- Code, tests and documentation: PR #9, merge commit
  `f96d308b9ad366c62583928815b7f80fc78bb85d` (fix commit `9447ea8`).
- Regression tests: `tests/test_mcp_and_security.py`,
  `test_network_trace_is_non_promiscuous_and_writes_nothing` (verified to
  fail with only `-p` removed) and
  `test_network_trace_quiet_interface_returns_partial_capture`.
- CI on PR #9: all checks passed, including the end-to-end demo on kind.

### Dispute position

The dispute acknowledges the promiscuous-mode defect, points to the fix, and
asks for the finding to be re-verified at `f96d308`. If the scanner continues
to flag `subprocess.run()` itself, that is a methodology difference: the
handler starts a bounded observation process but writes no files and changes
no interface, network, Kubernetes or cloud state. Record the response in
section 6.

---

**Record owner:** production-debug project maintainer  
**Last updated:** November 23, 2026 (section 8 added)  
**Next action:** Record M8ven's dispute response and re-verified grade in section 6.
