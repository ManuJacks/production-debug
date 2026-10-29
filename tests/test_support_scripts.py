from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


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


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


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
        "incident_preflight.sh", "--local-only", env={"PS_METRICS": "1"}
    )

    assert completed.returncode == 0
    assert "METRIC|script=incident_preflight" in completed.stdout


def test_remote_docker_snapshot_requires_hosts() -> None:
    completed = run_script("remote_docker_snapshot.sh", env={"PS_HOST_01": ""})

    assert completed.returncode == 2
    assert "No hosts provided" in completed.stderr


def test_port_auth_smoke_test_requires_credentials() -> None:
    completed = run_script(
        "port_auth_smoke_test.sh",
        env={"PORT_CLIENT_ID": "", "PORT_CLIENT_SECRET": ""},
    )

    assert completed.returncode == 2
    assert "PORT_CLIENT_ID and PORT_CLIENT_SECRET must be set." in completed.stderr


def test_remote_dns_tls_check_requires_endpoint() -> None:
    completed = run_script("remote_dns_tls_check.sh")

    assert completed.returncode == 2
    assert "An endpoint argument is required." in completed.stderr


def test_remote_disk_pressure_scan_requires_hosts() -> None:
    completed = run_script("remote_disk_pressure_scan.sh", env={"PS_HOST_01": ""})

    assert completed.returncode == 2
    assert "No hosts provided" in completed.stderr


def test_jcasc_render_precheck_requires_args() -> None:
    completed = run_script("jcasc_render_precheck.sh")

    assert completed.returncode == 2
    assert "jcasc_repo_path and environment are required." in completed.stderr


def test_vault_path_probe_requires_env() -> None:
    completed = run_script(
        "vault_path_probe.sh",
        "CET-Test",
        "jenkins.erb",
        env={"VAULT_ADDR": "", "VAULT_TOKEN": ""},
    )

    assert completed.returncode == 2
    assert "VAULT_ADDR and VAULT_TOKEN must be set." in completed.stderr


def test_tiller_render_diff_requires_args() -> None:
    completed = run_script("tiller_render_diff.sh")

    assert completed.returncode == 2
    assert "jcasc_repo_path and environment are required." in completed.stderr


def test_jcasc_backup_verifier_requires_hosts() -> None:
    completed = run_script("jcasc_backup_verifier.sh", env={"PS_HOST_01": ""})

    assert completed.returncode == 2
    assert "No hosts provided" in completed.stderr


def test_jgp_image_drift_audit_requires_args() -> None:
    completed = run_script("jgp_image_drift_audit.sh")

    assert completed.returncode == 2
    assert "jgp_repo_path is required." in completed.stderr


def test_jgp_properties_expectation_check_requires_args() -> None:
    completed = run_script("jgp_properties_expectation_check.sh")

    assert completed.returncode == 2
    assert (
        "project_repo_path, pipeline_kind, and env_properties_file are required."
        in completed.stderr
    )


def test_rhel8_mtab_repair_rejects_unknown_arg() -> None:
    completed = run_script("rhel8_mtab_repair.sh", "--unknown")

    assert completed.returncode == 2
    assert "Unknown argument" in completed.stderr


def test_docker_ipv4_dns_repair_rejects_unknown_arg() -> None:
    completed = run_script("docker_ipv4_dns_repair.sh", "--unknown")

    assert completed.returncode == 2
    assert "Unknown argument" in completed.stderr


def test_kpi_collect_requires_source() -> None:
    completed = run_script("kpi_collect.sh")

    assert completed.returncode == 2
    assert "source is required." in completed.stderr


def test_kpi_collect_from_file_csv(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.log"
    metrics.write_text(
        "METRIC|script=incident_preflight|status=success|exit_code=0|duration_s=3\n"
        "METRIC|script=port_auth_smoke_test|status=failure|exit_code=1|duration_s=2\n",
        encoding="utf-8",
    )

    completed = run_script("kpi_collect.sh", str(metrics))

    assert completed.returncode == 0
    assert "script,status,exit_code,duration_s" in completed.stdout
    assert "incident_preflight,success,0,3" in completed.stdout


def test_kpi_report_json(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.log"
    metrics.write_text(
        "METRIC|script=incident_preflight|status=success|exit_code=0|duration_s=10\n"
        "METRIC|script=incident_preflight|status=failure|exit_code=1|duration_s=20\n",
        encoding="utf-8",
    )

    completed = run_script("kpi_report.sh", str(metrics), "--format", "json")

    assert completed.returncode == 0
    assert '"total_events": 2' in completed.stdout
    assert '"success_rate_pct": 50.0' in completed.stdout


def test_kpi_compare_reports_delta(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.log"
    baseline.write_text(
        "METRIC|script=incident_preflight|status=success|exit_code=0|duration_s=20\n",
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.log"
    candidate.write_text(
        "METRIC|script=incident_preflight|status=success|exit_code=0|duration_s=10\n",
        encoding="utf-8",
    )

    completed = run_script(
        "kpi_compare.sh", str(baseline), str(candidate), "--format", "json"
    )

    assert completed.returncode == 0
    assert '"p50_duration_s": -10.0' in completed.stdout


def test_incident_bundle_creates_bundle_and_archive(tmp_path: Path) -> None:
    incident_log = tmp_path / "incident.log"
    incident_log.write_text(
        "METRIC|script=incident_preflight|status=success|exit_code=0|duration_s=3\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "bundles"

    completed = run_script(
        "incident_bundle.sh",
        str(output_dir),
        str(incident_log),
        "--name",
        "smoke",
    )

    assert completed.returncode == 0
    assert "bundle_dir=" in completed.stdout
    assert "archive_path=" in completed.stdout

    lines = [line.strip() for line in completed.stdout.splitlines() if "=" in line]
    parsed = dict(line.split("=", 1) for line in lines)

    assert Path(parsed["bundle_dir"]).exists()
    assert Path(parsed["archive_path"]).exists()
    assert (Path(parsed["bundle_dir"]) / "reports" / "kpi-report.txt").exists()


def test_generate_script_catalog_stdout_contains_markers() -> None:
    completed = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "generate_script_catalog.py"), "--stdout"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )

    assert completed.returncode == 0
    assert "SCRIPT_CATALOG_START" in completed.stdout
    assert "incident_bundle.sh" in completed.stdout


def test_generate_script_catalog_check_detects_out_of_date(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"scripts":[{"command":"x","script":"x.sh","summary":"x","safety":"read-only","required_env":[]}]}',
        encoding="utf-8",
    )

    readme = tmp_path / "README.md"
    readme.write_text(
        "Header\n<!-- SCRIPT_CATALOG_START -->\nold\n<!-- SCRIPT_CATALOG_END -->\nFooter\n",
        encoding="utf-8",
    )

    check_before = subprocess.run(
        [
            "python3",
            str(SCRIPTS_DIR / "generate_script_catalog.py"),
            "--manifest",
            str(manifest),
            "--readme",
            str(readme),
            "--check",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert check_before.returncode == 1

    write = subprocess.run(
        [
            "python3",
            str(SCRIPTS_DIR / "generate_script_catalog.py"),
            "--manifest",
            str(manifest),
            "--readme",
            str(readme),
            "--write-readme",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert write.returncode == 0

    check_after = subprocess.run(
        [
            "python3",
            str(SCRIPTS_DIR / "generate_script_catalog.py"),
            "--manifest",
            str(manifest),
            "--readme",
            str(readme),
            "--check",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert check_after.returncode == 0


def test_psdebug_ops_requires_command() -> None:
    completed = run_script("psdebug_ops.sh")

    assert completed.returncode == 2
    assert "Usage: psdebug_ops.sh" in completed.stderr


def test_fw_host_probe_requires_valid_hosts_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing-hosts.txt"

    completed = run_script(
        "fw-host-probe-check.sh",
        env={"PROBE_HOSTS": "", "HOSTS_FILE": str(missing_file)},
    )

    assert completed.returncode == 1
    assert "host list file not found" in completed.stderr


def test_fw_host_probe_uses_probe_hosts_without_hosts_file() -> None:
    completed = run_script(
        "fw-host-probe-check.sh",
        env={
            "PROBE_HOSTS": "localhost",
            "PROBE_PORTS": "443",
            "SHOW_DNS": "0",
            "CURL_TIMEOUT": "1",
            "CONNECT_TIMEOUT": "1",
        },
    )

    assert completed.returncode == 0
    assert "Host: localhost" in completed.stdout
    assert "TCP 443" in completed.stdout
    assert "HTTPS /" in completed.stdout
    assert "DNS" not in completed.stdout


def test_fw_host_probe_reads_hosts_file(tmp_path: Path) -> None:
    hosts_file = tmp_path / "hosts.txt"
    hosts_file.write_text("# comment\n\nlocalhost\n", encoding="utf-8")

    completed = run_script(
        "fw-host-probe-check.sh",
        env={
            "HOSTS_FILE": str(hosts_file),
            "PROBE_PORTS": "443",
            "SHOW_DNS": "0",
            "CURL_TIMEOUT": "1",
            "CONNECT_TIMEOUT": "1",
        },
    )

    assert completed.returncode == 0
    assert "Host: localhost" in completed.stdout


def test_psdebug_ops_list_works() -> None:
    completed = run_script("psdebug_ops.sh", "list")

    assert completed.returncode == 0
    assert "preflight" in completed.stdout
    assert "kpi-report" in completed.stdout
    assert "incident-bundle" in completed.stdout
    assert "catalog-generate" in completed.stdout
    assert "docker-health" in completed.stdout
    assert "kpi-compare" in completed.stdout
    assert "artifactory-pkg-check" in completed.stdout
    assert "artifactory-502-triage" in completed.stdout


def test_artifactory_package_resolution_check_requires_base_url() -> None:
    completed = run_script("artifactory-package-resolution-check.sh")

    assert completed.returncode == 2
    assert "ART_BASE_URL must be set." in completed.stderr


def test_artifactory_502_triage_requires_base_url() -> None:
    completed = run_script("artifactory-502-triage.sh")

    assert completed.returncode == 2
    assert "ART_BASE_URL must be set." in completed.stderr


def test_artifactory_package_resolution_check_failure_path_emits_metric(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)

    write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
set -eu
out_file=""
status="200"
url=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o)
            out_file="$2"
            shift 2
            ;;
        -w)
            shift 2
            ;;
        --max-time|-sS|-u|-H)
            shift
            [[ "$1" == -* || -z "${1:-}" ]] || shift
            ;;
        http*)
            url="$1"
            shift
            ;;
        *)
            shift
            ;;
    esac
done
if [[ "$url" == *"/api/repositories/"* ]]; then
    status="404"
fi
if [[ -n "$out_file" ]]; then
    printf '{}' > "$out_file"
fi
printf '%s' "$status"
""",
    )

    merged_path = f"{fake_bin}:{os.environ.get('PATH', '')}"
    completed = run_script(
        "artifactory-package-resolution-check.sh",
        "repo-a",
        env={
            "ART_BASE_URL": "https://example.invalid/artifactory",
            "PS_METRICS": "1",
            "PATH": merged_path,
        },
    )

    assert completed.returncode == 1
    assert "Result: 1 probe(s) need attention." in completed.stdout
    assert (
        "METRIC|script=artifactory_package_resolution_check|status=failure"
        in completed.stdout
    )


def test_artifactory_502_triage_edge_network_classification_emits_metric(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)

    write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
set -eu
out_file=""
url=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o)
            out_file="$2"
            shift 2
            ;;
        -w)
            shift 2
            ;;
        --max-time|-sS|-u|-H)
            shift
            [[ "$1" == -* || -z "${1:-}" ]] || shift
            ;;
        http*)
            url="$1"
            shift
            ;;
        *)
            shift
            ;;
    esac
done
if [[ -n "$out_file" ]]; then
    printf '{}' > "$out_file"
fi
if [[ "$url" == *"/api/system/ping"* ]]; then
    printf '000'
else
    printf '200'
fi
""",
    )
    write_executable(fake_bin / "getent", "#!/usr/bin/env bash\nexit 0\n")
    write_executable(fake_bin / "openssl", "#!/usr/bin/env bash\nexit 0\n")

    merged_path = f"{fake_bin}:{os.environ.get('PATH', '')}"
    completed = run_script(
        "artifactory-502-triage.sh",
        env={
            "ART_BASE_URL": "https://example.invalid/artifactory",
            "PS_METRICS": "1",
            "PATH": merged_path,
        },
    )

    assert completed.returncode == 0
    assert "EDGE/NETWORK" in completed.stdout
    assert "METRIC|script=artifactory_502_triage|status=success" in completed.stdout
    assert "fault_domain=edge-network" in completed.stdout


def test_psdebug_ops_unknown_command() -> None:
    completed = run_script("psdebug_ops.sh", "nope")

    assert completed.returncode == 2
    assert "Unknown command" in completed.stderr
