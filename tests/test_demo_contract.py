"""Static contract for the demo's diagnostic environment and safety guards.

These back the README security-model table: the diagnostic identity is
namespace-scoped and read-only, the pod is hardened, archives with unsafe
entries are rejected, and the demo refuses to act without naming its target.
"""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

import pytest
import yaml

from production_debug import bundle_verifier
from production_debug.bundle_verifier import (
    BundleVerificationError,
    verify_bundle_archive,
)

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "demo" / "manifests" / "diagnostics.yaml"
DEMO = ROOT / "demo" / "run.sh"


def docs_by_kind() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for doc in yaml.safe_load_all(MANIFEST.read_text()):
        out.setdefault(doc["kind"], []).append(doc)
    return out


class TestDiagnosticIdentity:
    def test_no_cluster_scoped_rbac(self):
        kinds = docs_by_kind()
        assert "ClusterRole" not in kinds
        assert "ClusterRoleBinding" not in kinds

    def test_role_is_read_only_and_excludes_sensitive_resources(self):
        (role,) = docs_by_kind()["Role"]
        assert role["metadata"]["namespace"] == "production-debug-lab"
        for rule in role["rules"]:
            assert set(rule["verbs"]) <= {"get", "list", "watch"}
            for resource in rule["resources"]:
                assert resource not in {
                    "secrets",
                    "configmaps",
                    "pods/exec",
                    "pods/attach",
                    "*",
                }
                assert "*" not in rule["apiGroups"]

    def test_binding_targets_only_the_diagnostic_service_account(self):
        (binding,) = docs_by_kind()["RoleBinding"]
        assert binding["metadata"]["namespace"] == "production-debug-lab"
        assert binding["roleRef"] == {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "Role",
            "name": "incident-reader",
        }
        assert binding["subjects"] == [
            {
                "kind": "ServiceAccount",
                "name": "incident-reader",
                "namespace": "production-debug-diag",
            }
        ]


class TestDiagnosticPod:
    def test_namespace_enforces_restricted_pod_security(self):
        (ns,) = docs_by_kind()["Namespace"]
        assert (
            ns["metadata"]["labels"]["pod-security.kubernetes.io/enforce"]
            == "restricted"
        )

    def test_pod_is_hardened_and_self_expiring(self):
        (pod,) = docs_by_kind()["Pod"]
        spec = pod["spec"]
        assert spec["serviceAccountName"] == "incident-reader"
        assert 0 < spec["activeDeadlineSeconds"] <= 3600
        assert spec["securityContext"]["runAsNonRoot"] is True
        assert spec["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
        assert "hostPID" not in spec and "hostNetwork" not in spec
        (container,) = spec["containers"]
        sc = container["securityContext"]
        assert sc["allowPrivilegeEscalation"] is False
        assert sc["readOnlyRootFilesystem"] is True
        assert sc["capabilities"]["drop"] == ["ALL"]
        assert "add" not in sc["capabilities"]
        assert "limits" in container["resources"]


class TestArchiveSafety:
    def _archive(self, tmp_path: Path, name: str, data: bytes = b"x") -> Path:
        # Build the member directly: TarFile.add() would strip a leading "/".
        archive = tmp_path / "a.tar.gz"
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        with tarfile.open(archive, "w:gz") as tar:
            tar.addfile(info, io.BytesIO(data))
        return archive

    @pytest.mark.parametrize(
        "name", ["../escape.txt", "/etc/passwd-copy", "bundle/../../x"]
    )
    def test_rejects_path_traversal(self, tmp_path, name):
        with pytest.raises(BundleVerificationError, match="Unsafe archive entry"):
            verify_bundle_archive(self._archive(tmp_path, name))

    def test_rejects_oversized_payload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bundle_verifier, "MAX_ARCHIVE_BYTES", 10)
        archive = self._archive(tmp_path, "bundle/big.log", b"x" * 11)
        with pytest.raises(BundleVerificationError, match="exceeds"):
            verify_bundle_archive(archive)


class TestDemoTargetConfirmation:
    @pytest.fixture
    def fake_kubectl(self, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        log = tmp_path / "kubectl.log"
        kubectl = bin_dir / "kubectl"
        kubectl.write_text(
            "#!/usr/bin/env bash\n"
            'echo "$*" >> "$KUBECTL_LOG"\n'
            'if [[ "$1 $2" == "config get-contexts" ]]; then echo lab-cluster; fi\n'
            'if [[ "$1 $2" == "config view" ]]; then echo https://lab.example:6443; fi\n'
        )
        kubectl.chmod(0o755)
        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "KUBECTL_LOG": str(log),
        }
        return env, log

    def run(self, env, *args):
        return subprocess.run(
            ["bash", str(DEMO), *args],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_requires_explicit_context(self, fake_kubectl):
        env, log = fake_kubectl
        env.pop("DEMO_CONTEXT", None)
        result = self.run(env, "cleanup")
        assert result.returncode != 0
        assert "DEMO_CONTEXT" in result.stderr

    def test_wrong_confirmation_changes_nothing(self, fake_kubectl):
        env, log = fake_kubectl
        env.update(
            DEMO_CONTEXT="lab-cluster", DEMO_CONFIRM="lab-cluster/some-other-namespace"
        )
        result = self.run(env, "cleanup")
        assert result.returncode != 0
        assert "confirmation failed; no changes made" in result.stderr
        assert "delete" not in log.read_text()

    def test_unknown_context_is_refused(self, fake_kubectl):
        env, log = fake_kubectl
        env.update(DEMO_CONTEXT="prod", DEMO_CONFIRM="prod/production-debug-lab")
        result = self.run(env, "cleanup")
        assert result.returncode != 0
        assert "context not found" in result.stderr
        assert "delete" not in log.read_text()
