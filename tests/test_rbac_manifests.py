"""Contract tests for the general-purpose RBAC in k8s/ and gitops/base/.

The diagnostic identity must be unable to read workload namespaces until an
operator binds it into one incident namespace, and must never be able to read
Secrets or ConfigMaps or change anything.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RBAC_FILES = [ROOT / "k8s" / "rbac.yaml", ROOT / "gitops" / "base" / "rbac.yaml"]
READ_VERBS = {"get", "list", "watch"}
FORBIDDEN_RESOURCES = {
    "secrets",
    "configmaps",
    "pods/exec",
    "pods/attach",
    "pods/portforward",
    "pods/proxy",
}


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


@pytest.fixture(params=RBAC_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def rbac_docs(request) -> list[dict]:
    return _docs(request.param)


def test_rbac_copies_are_identical():
    assert RBAC_FILES[0].read_text() == RBAC_FILES[1].read_text()


def test_roles_are_read_only_and_exclude_sensitive_resources(rbac_docs):
    roles = [d for d in rbac_docs if d["kind"] in ("ClusterRole", "Role")]
    assert roles
    for role in roles:
        for rule in role["rules"]:
            assert set(rule["verbs"]) <= READ_VERBS, role["metadata"]["name"]
            assert "*" not in rule["resources"]
            assert not FORBIDDEN_RESOURCES & set(rule["resources"]), role["metadata"][
                "name"
            ]


def test_namespaced_reader_is_never_bound_cluster_wide(rbac_docs):
    cluster_bindings = [d for d in rbac_docs if d["kind"] == "ClusterRoleBinding"]
    for binding in cluster_bindings:
        assert binding["roleRef"]["name"] != "prod-debug-reader"


def test_cluster_wide_grant_covers_only_cluster_scoped_objects(rbac_docs):
    roles = {d["metadata"]["name"]: d for d in rbac_docs if d["kind"] == "ClusterRole"}
    for binding in (d for d in rbac_docs if d["kind"] == "ClusterRoleBinding"):
        role = roles[binding["roleRef"]["name"]]
        resources = {r for rule in role["rules"] for r in rule["resources"]}
        assert resources <= {"nodes", "namespaces"}


def test_grant_script_binds_reader_with_rolebinding():
    script = (ROOT / "scripts" / "grant-incident-access.sh").read_text()
    assert "kubectl create rolebinding" in script
    assert '--clusterrole="$CLUSTER_ROLE"' in script
    assert "clusterrolebinding" not in script


@pytest.mark.parametrize("ns", ["kube-system", "debug-system", "kube-public"])
def test_grant_script_refuses_system_namespaces(ns):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "grant-incident-access.sh"), "grant", ns],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2
    assert "refusing" in result.stderr


def test_grant_script_requires_action_and_namespace():
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "grant-incident-access.sh"), "grant"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
