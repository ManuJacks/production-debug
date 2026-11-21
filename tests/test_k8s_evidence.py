"""Evidence collector behaviour under API failure, missing resources and partial access."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "k8s_evidence.sh"
READ_VERBS = {"get", "describe", "logs", "version", "auth"}

FAKE_KUBECTL = r"""#!/usr/bin/env bash
echo "$*" >> "$KUBECTL_LOG"
# Strip global flags to find the verb.
args=()
for a in "$@"; do
  case "$a" in --request-timeout=*) ;; *) args+=("$a") ;; esac
done
if [[ "${args[0]}" == "--context" ]]; then args=("${args[@]:2}"); fi
verb="${args[0]}"
case "$FAKE_MODE" in
  flaky_version)
    if [[ "$verb" == "version" && ! -e "$FLAKY_STATE" ]]; then
      touch "$FLAKY_STATE"
      echo "error: You must be logged in to the server" >&2; exit 1
    fi
    echo "ok"; exit 0 ;;
  forbidden)
    echo 'Error from server (Forbidden): pods is forbidden' >&2; exit 1 ;;
  api_down)
    echo "The connection to the server was refused" >&2; exit 1 ;;
  missing_ns)
    if [[ "$verb" == "version" ]]; then echo '{}'; exit 0; fi
    echo 'Error from server (NotFound): namespaces "gone" not found' >&2; exit 1 ;;
  healthy)
    case "$verb" in
      get)
        if [[ " ${args[*]} " == *" jsonpath="* || " ${args[*]} " == *"-o jsonpath"* ]]; then
          printf 'web-0\n'; exit 0
        fi
        if [[ "${args[1]}" == "services,endpointslices" ]]; then exit 0; fi
        echo "NAME READY"; exit 0 ;;
      logs)
        if [[ " ${args[*]} " == *" --previous "* ]]; then
          echo 'previous terminated container "app" not found' >&2; exit 1
        fi
        echo "[pod/web-0/app] started"; exit 0 ;;
      auth) echo "pods [] [] [get list watch]"; exit 0 ;;
      *) echo "ok"; exit 0 ;;
    esac ;;
esac
"""


@pytest.fixture
def fake_env(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(FAKE_KUBECTL, encoding="utf-8")
    kubectl.chmod(0o755)
    log = tmp_path / "kubectl.log"
    env = os.environ.copy()
    env.update({"PATH": f"{bin_dir}:{env['PATH']}", "KUBECTL_LOG": str(log)})
    return env, log


def run(env, mode, *args):
    env = {**env, "FAKE_MODE": mode}
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def verbs_used(log: Path) -> set[str]:
    verbs = set()
    for line in log.read_text().splitlines():
        parts = [p for p in line.split() if not p.startswith("--request-timeout=")]
        if parts[0] == "--context":
            parts = parts[2:]
        verbs.add(parts[0])
    return verbs


def test_healthy_collection_is_complete(fake_env, tmp_path):
    env, log = fake_env
    out = tmp_path / "ev"
    res = run(env, "healthy", "--namespace", "lab", "--output", str(out))
    assert res.returncode == 0, res.stderr

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["schema"] == "production-debug/k8s-evidence/v1"
    assert manifest["status"] == "complete"
    assert manifest["summary"]["failed"] == 0
    # Missing previous logs are expected for a pod that never restarted.
    assert manifest["summary"]["unavailable"] == 1
    assert manifest["summary"]["empty"] == 1
    assert (out / "logs" / "web-0.log").read_text().startswith("[pod/web-0/app]")
    assert verbs_used(log) <= READ_VERBS


def test_api_unreachable_fails_with_manifest(fake_env, tmp_path):
    env, log = fake_env
    out = tmp_path / "ev"
    res = run(env, "api_down", "--namespace", "lab", "--output", str(out))

    assert res.returncode == 3
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["summary"]["ok"] == 0
    failed = [s for s in manifest["steps"] if s["status"] == "failed"]
    assert failed and "connection to the server was refused" in failed[0]["error"]
    assert (out / "workloads" / "pods.txt.error").exists()
    assert verbs_used(log) <= READ_VERBS


def test_missing_namespace_is_partial_not_fatal(fake_env, tmp_path):
    env, _ = fake_env
    out = tmp_path / "ev"
    res = run(env, "missing_ns", "--namespace", "gone", "--output", str(out))

    assert res.returncode == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["status"] == "partial"
    assert any("NotFound" in s.get("error", "") for s in manifest["steps"])


def test_never_requests_secrets_or_configmaps(fake_env, tmp_path):
    env, log = fake_env
    run(env, "healthy", "--namespace", "lab", "--output", str(tmp_path / "ev"))
    text = log.read_text()
    assert "secret" not in text
    assert "configmap" not in text


def test_refuses_existing_output_directory(fake_env, tmp_path):
    env, log = fake_env
    existing = tmp_path / "ev"
    existing.mkdir()
    res = run(env, "healthy", "--namespace", "lab", "--output", str(existing))
    assert res.returncode == 2
    assert not log.exists()


@pytest.mark.parametrize(
    "args",
    [
        ["--namespace", "Lab;id", "--output", "x"],
        ["--namespace", "lab"],
        ["--namespace", "lab", "--output", "x", "--selector", "app=$(id)"],
        ["--namespace", "lab", "--output", "x", "--tail", "99999"],
    ],
)
def test_rejects_invalid_arguments(fake_env, tmp_path, args):
    env, log = fake_env
    res = subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**env, "FAKE_MODE": "healthy"},
        cwd=tmp_path,
        check=False,
    )
    assert res.returncode == 2
    assert not log.exists()


def test_in_cluster_calls_pass_no_config_overrides(fake_env, tmp_path):
    """Regression: overrides break in-cluster auth inside the diagnostic pod."""
    env, log = fake_env
    run(env, "healthy", "--namespace", "lab", "--output", str(tmp_path / "ev"))
    for line in log.read_text().splitlines():
        assert "--request-timeout" not in line
        assert "--context" not in line


def test_transient_failure_is_retried_and_recorded(fake_env, tmp_path):
    env, _ = fake_env
    env = {**env, "FLAKY_STATE": str(tmp_path / "flaky")}
    out = tmp_path / "ev"
    res = run(env, "flaky_version", "--namespace", "lab", "--output", str(out))
    assert res.returncode == 0, res.stderr
    steps = json.loads((out / "manifest.json").read_text())["steps"]
    version = next(s for s in steps if s["file"] == "cluster/version.json")
    assert version["status"] == "ok"
    assert version["attempts"] == 2


def test_forbidden_is_not_retried(fake_env, tmp_path):
    env, log = fake_env
    out = tmp_path / "ev"
    run(env, "forbidden", "--namespace", "lab", "--output", str(out))
    steps = json.loads((out / "manifest.json").read_text())["steps"]
    assert all(s["attempts"] == 1 for s in steps)
