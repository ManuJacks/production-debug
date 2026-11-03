from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNNER = PROJECT_ROOT / "scenarios" / "run.sh"


def run_runner(
    *args: str,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    return subprocess.run(
        ["bash", str(RUNNER), *args],
        capture_output=True,
        text=True,
        input=input_text,
        env=merged_env,
        cwd=PROJECT_ROOT,
        check=False,
    )


@pytest.fixture
def fake_kubectl(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    log_file = tmp_path / "kubectl.log"
    executable = bin_dir / "kubectl"

    executable.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "$KUBECTL_LOG"\n'
        'if [[ "$1" == "config" && "$2" == "get-contexts" ]]; then\n'
        '  echo "minikube"\n'
        "fi\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)

    return (
        {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "KUBECTL_LOG": str(log_file),
        },
        log_file,
    )


def test_setup_requires_explicit_context() -> None:
    completed = run_runner(
        "setup",
        "01-crashloop",
        env={"K8S_LAB_CONTEXT": ""},
    )

    assert completed.returncode == 2
    assert "set K8S_LAB_CONTEXT" in completed.stderr


def test_setup_rejects_unknown_context(fake_kubectl) -> None:
    env, log_file = fake_kubectl
    env["K8S_LAB_CONTEXT"] = "unknown-context"

    completed = run_runner("setup", "01-crashloop", env=env)

    assert completed.returncode == 2
    assert "Kubernetes context not found" in completed.stderr
    assert log_file.read_text(encoding="utf-8").strip() == (
        "config get-contexts -o name"
    )


def test_setup_rejects_incorrect_confirmation(fake_kubectl) -> None:
    env, log_file = fake_kubectl
    env["K8S_LAB_CONTEXT"] = "minikube"

    completed = run_runner(
        "setup",
        "01-crashloop",
        env=env,
        input_text="no\n",
    )

    assert completed.returncode == 1
    assert "confirmation failed; no changes made" in completed.stderr
    assert log_file.read_text(encoding="utf-8").strip() == (
        "config get-contexts -o name"
    )


def test_list_does_not_require_context() -> None:
    completed = run_runner("list", env={"K8S_LAB_CONTEXT": ""})

    assert completed.returncode == 0
    assert "01-crashloop.yaml" in completed.stdout
    assert "08-rbac.yaml" in completed.stdout


def test_status_uses_explicit_context(fake_kubectl) -> None:
    env, log_file = fake_kubectl
    env["K8S_LAB_CONTEXT"] = "minikube"

    completed = run_runner("status", env=env)

    assert completed.returncode == 0
    assert "--context minikube" in log_file.read_text(encoding="utf-8")
