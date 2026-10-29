from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_script(
    script_name: str, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    return subprocess.run(
        ["bash", str(SCRIPTS_DIR / script_name), *args],
        capture_output=True,
        text=True,
        env=merged_env,
        cwd=PROJECT_ROOT,
        check=False,
    )


def test_support_scripts_are_valid_bash() -> None:
    for path in SCRIPTS_DIR.glob("*.sh"):
        completed = subprocess.run(
            ["bash", "-n", str(path)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


def test_incident_preflight_local_only_succeeds() -> None:
    completed = run_script("incident_preflight.sh", "--local-only")
    assert completed.returncode == 0
    assert "summary" in completed.stdout


def test_incident_preflight_emits_metrics_when_enabled() -> None:
    completed = run_script(
        "incident_preflight.sh",
        "--local-only",
        env={"PS_METRICS": "1", "INCIDENT_TAG": "test-inc"},
    )
    assert completed.returncode == 0
    assert "METRIC|" in completed.stdout
    assert "script=incident_preflight" in completed.stdout


def test_remote_dns_tls_check_requires_endpoint() -> None:
    completed = run_script("remote_dns_tls_check.sh")
    assert completed.returncode == 2
    assert "endpoint argument is required" in completed.stderr


def test_kpi_collect_requires_source() -> None:
    completed = run_script("kpi_collect.sh")
    assert completed.returncode == 2
    assert "source is required" in completed.stderr


def test_kpi_collect_from_file_csv(tmp_path: Path) -> None:
    raw_file = tmp_path / "raw.log"
    raw_file.write_text(
        "METRIC|script=test_a|status=success|exit_code=0|duration_s=5|hosts=1|failures=0\n",
        encoding="utf-8",
    )
    completed = run_script("kpi_collect.sh", str(raw_file), "--format", "csv")
    assert completed.returncode == 0
    assert "script,status,exit_code" in completed.stdout


def test_kpi_report_json(tmp_path: Path) -> None:
    sample_log = tmp_path / "sample.log"
    sample_log.write_text(
        "METRIC|script=test_a|status=success|exit_code=0|duration_s=10|hosts=1|failures=0\n"
        "METRIC|script=test_b|status=failure|exit_code=1|duration_s=20|hosts=1|failures=1\n",
        encoding="utf-8",
    )
    completed = run_script("kpi_report.sh", str(sample_log), "--format", "json")
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["total_events"] == 2
    assert payload["success_rate_pct"] == 50.0


def test_kpi_compare_reports_delta(tmp_path: Path) -> None:
    base_log = tmp_path / "base.log"
    curr_log = tmp_path / "curr.log"
    base_log.write_text(
        "METRIC|script=a|status=success|exit_code=0|duration_s=10|hosts=1|failures=0\n",
        encoding="utf-8",
    )
    curr_log.write_text(
        "METRIC|script=a|status=success|exit_code=0|duration_s=5|hosts=1|failures=0\n",
        encoding="utf-8",
    )
    completed = run_script(
        "kpi_compare.sh", str(base_log), str(curr_log), "--format", "json"
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert "delta" in payload
    assert payload["delta"]["p50_duration_s"] == -5.0


def test_incident_bundle_creates_bundle_and_archive(tmp_path: Path) -> None:
    out_dir = tmp_path / "bundle_out"
    sample_artifact = tmp_path / "diag.log"
    sample_artifact.write_text("sample triage output\n", encoding="utf-8")
    completed = run_script(
        "incident_bundle.sh", str(out_dir), str(sample_artifact), "--name", "test-inc"
    )
    assert completed.returncode == 0
    archives = list(out_dir.glob("test-inc-*.tar.gz"))
    assert len(archives) == 1


def test_fw_host_probe_requires_valid_hosts_file() -> None:
    completed = run_script(
        "fw-host-probe-check.sh", "--hosts-file", "/nonexistent/hosts.txt"
    )
    assert completed.returncode == 1
    assert "host list file not found" in completed.stderr


def test_fw_host_probe_uses_probe_hosts_without_hosts_file() -> None:
    completed = run_script(
        "fw-host-probe-check.sh",
        env={"PROBE_HOSTS": "127.0.0.1", "PROBE_PORT": "65534", "PROBE_TIMEOUT": "1"},
    )
    assert completed.returncode in (0, 1)


def test_fw_host_probe_reads_hosts_file(tmp_path: Path) -> None:
    hosts_file = tmp_path / "hosts.txt"
    hosts_file.write_text("127.0.0.1\n", encoding="utf-8")
    completed = run_script(
        "fw-host-probe-check.sh",
        "--hosts-file",
        str(hosts_file),
        env={"PROBE_PORT": "65534", "PROBE_TIMEOUT": "1"},
    )
    assert completed.returncode in (0, 1)


def test_mcp_server_dns_probe_and_azure_identity() -> None:
    from mcp.server import run_dns_probe_impl, check_azure_workload_identity_impl

    # Check Azure identity audit function
    identity_res = check_azure_workload_identity_impl()
    assert "azure_workload_identity" in identity_res
    assert "imds_probe" in identity_res

    # Check DNS probe safety guardrails
    malformed_probe = run_dns_probe_impl("bad;domain$(rm -rf /)")
    assert "error" in malformed_probe
