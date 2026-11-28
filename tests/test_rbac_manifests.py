"""Contract tests for the general-purpose RBAC in k8s/ and gitops/base/ and for
scripts/grant-incident-access.sh.

The diagnostic identity must be unable to read workload namespaces until an
operator binds it into one allowlisted incident namespace; logs need a separate
explicit grant; it must never read Secrets or ConfigMaps or change anything.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "grant-incident-access.sh"
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
LAB_CONTEXT = "kubernetes-admin@kubernetes"


def _docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text()) if d]


def _roles(docs: list[dict]) -> dict[str, dict]:
    return {d["metadata"]["name"]: d for d in docs if d["kind"] == "ClusterRole"}


def _resources(role: dict) -> set[str]:
    return {r for rule in role["rules"] for r in rule["resources"]}


@pytest.fixture(params=RBAC_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def rbac_docs(request) -> list[dict]:
    return _docs(request.param)


# --- manifests ---------------------------------------------------------------


def test_rbac_copies_are_identical():
    assert RBAC_FILES[0].read_text() == RBAC_FILES[1].read_text()


def test_roles_are_read_only_and_exclude_sensitive_resources(rbac_docs):
    roles = [d for d in rbac_docs if d["kind"] in ("ClusterRole", "Role")]
    assert roles
    for role in roles:
        for rule in role["rules"]:
            assert set(rule["verbs"]) <= READ_VERBS, role["metadata"]["name"]
            assert "*" not in rule["resources"]
            assert not FORBIDDEN_RESOURCES & set(rule["resources"])


def test_three_layers_exist(rbac_docs):
    roles = _roles(rbac_docs)
    assert _resources(roles["prod-debug-cluster-reader"]) == {"nodes", "namespaces"}
    assert "pods" in _resources(roles["prod-debug-reader"])
    assert _resources(roles["prod-debug-log-reader"]) == {"pods/log"}


def test_logs_only_in_log_reader(rbac_docs):
    for name, role in _roles(rbac_docs).items():
        if name != "prod-debug-log-reader":
            assert "pods/log" not in _resources(role), name


def test_only_cluster_scoped_layer_is_bound_cluster_wide(rbac_docs):
    roles = _roles(rbac_docs)
    bindings = [d for d in rbac_docs if d["kind"] == "ClusterRoleBinding"]
    assert [b["roleRef"]["name"] for b in bindings] == ["prod-debug-cluster-reader"]
    for b in bindings:
        assert _resources(roles[b["roleRef"]["name"]]) <= {"nodes", "namespaces"}


def test_no_rolebindings_shipped(rbac_docs):
    assert not [d for d in rbac_docs if d["kind"] == "RoleBinding"]


# --- allowlists --------------------------------------------------------------


def _allowlist(env: str) -> tuple[str, list[str]]:
    context, names = "", []
    for line in (ROOT / "access" / f"{env}.namespaces").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("context="):
            context = line.removeprefix("context=")
        elif line:
            names.append(line)
    return context, names


@pytest.mark.parametrize("env", ["lab", "production"])
def test_allowlists_name_a_context_and_no_system_namespaces(env):
    context, names = _allowlist(env)
    assert context
    assert not {"kube-system", "kube-public", "kube-node-lease", "debug-system"} & set(
        names
    )
    assert len(names) == len(set(names))


def test_lab_allowlist():
    assert _allowlist("lab") == (LAB_CONTEXT, ["app-team-a", "app-team-b"])


def test_production_allowlist_starts_empty():
    assert _allowlist("production")[1] == []


# --- grant script against a fake kubectl -------------------------------------

FAKE_KUBECTL = r"""#!/usr/bin/env bash
# Minimal kubectl stand-in: tracks RoleBindings in $STATE, logs every call.
echo "$*" >> "$CALLS"
case "$1 $2" in
  "config current-context") echo "$FAKE_CONTEXT" ;;
  "get namespace") case "$*" in *go-template*) echo "${FAKE_LABEL-true}" ;; esac ;;
  "get rolebinding")
    grep -qx "$3" "$STATE" 2>/dev/null || exit 1
    case "$*" in *go-template*) sed -n 's/^    production-debug\/expires-at: "\(.*\)"$/\1/p' "$STATE.$3" ;; esac ;;
  "create -f")
    doc="$(cat)"; name="$(sed -n 's/^  name: //p' <<<"$doc" | head -n 1)"
    grep -qx "$name" "$STATE" || echo "$name" >> "$STATE"
    printf '%s\n' "$doc" > "$STATE.$name"; echo "rolebinding/$name created" ;;
  "delete rolebinding")
    shift 2
    for a in "$@"; do case "$a" in -*) break ;; *) sed -i "/^$a\$/d" "$STATE" ;; esac; done ;;
  "auth can-i")
    verb="$3"; res="$4"; ans=no
    case " $* " in *" --subresource=log "*) res="$res/log" ;; *" --subresource="*) res="$res/other" ;; esac
    case "$verb $res" in
      "list pods"|"list events"|"get deployments.apps") grep -qx prod-debug-reader "$STATE" && ans=yes ;;
      "get pods/log") grep -qx prod-debug-log-reader "$STATE" && ans=yes ;;
    esac
    echo "$ans" ;;
  *) echo "unexpected: $*" >&2; exit 99 ;;
esac
"""


@pytest.fixture
def fake(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(FAKE_KUBECTL)
    kubectl.chmod(0o755)
    state, calls = tmp_path / "state", tmp_path / "calls"
    state.touch()
    calls.touch()
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "STATE": str(state),
        "CALLS": str(calls),
        "FAKE_CONTEXT": LAB_CONTEXT,
    }

    def run(*args: str, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env={**env, **extra},
        )

    run.bindings = lambda: state.read_text().split()
    run.manifest = lambda name: yaml.safe_load((tmp_path / f"state.{name}").read_text())
    run.calls = lambda: calls.read_text()
    return run


def test_grant_allowlisted_namespace_without_logs(fake):
    result = fake("--env", "lab", "grant", "app-team-a")
    assert result.returncode == 0, result.stdout + result.stderr
    assert fake.bindings() == ["prod-debug-reader"]
    assert "get    pods/log               expected=no  actual=no" in result.stdout


def test_grant_with_logs_adds_log_binding(fake):
    result = fake("--env", "lab", "grant", "app-team-b", "--logs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(fake.bindings()) == ["prod-debug-log-reader", "prod-debug-reader"]


def test_regrant_without_logs_drops_earlier_log_grant(fake):
    fake("--env", "lab", "grant", "app-team-a", "--logs")
    result = fake("--env", "lab", "grant", "app-team-a")
    assert result.returncode == 0, result.stdout + result.stderr
    assert fake.bindings() == ["prod-debug-reader"]


def test_revoke_removes_both_bindings_without_env(fake):
    fake("--env", "lab", "grant", "app-team-a", "--logs")
    result = fake("revoke", "app-team-a")
    assert result.returncode == 0, result.stdout + result.stderr
    assert fake.bindings() == []


def test_env_from_environment_variable(fake):
    result = fake("grant", "app-team-a", PROD_DEBUG_ENV="lab")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("args", "extra", "message"),
    [
        (["grant", "app-team-a"], {}, "no environment"),
        (["--env", "lab", "grant", "kif-drill"], {}, "not in the lab allowlist"),
        (["--env", "production", "grant", "app-team-a"], {}, "is not"),
        (
            ["--env", "lab", "grant", "app-team-a"],
            {"FAKE_CONTEXT": "prod"},
            "current context",
        ),
        (["--env", "nope", "grant", "app-team-a"], {}, "no allowlist"),
        (["--env", "../lab", "grant", "app-team-a"], {}, "invalid environment"),
        (["--env", "lab", "grant", "kube-system"], {}, "system namespace"),
        (["--env", "lab", "grant", "debug-system"], {}, "system namespace"),
        (
            ["--env", "lab", "grant", "app-team-a"],
            {"FAKE_LABEL": "<no value>"},
            "not labelled",
        ),
        (
            ["--env", "lab", "grant", "app-team-a"],
            {"FAKE_LABEL": "false"},
            "not labelled",
        ),
    ],
)
def test_grant_refusals_create_nothing(fake, args, extra, message):
    result = fake(*args, **extra)
    assert result.returncode == 2
    assert message in result.stderr
    assert fake.bindings() == []
    assert "create -f" not in fake.calls()


@pytest.mark.parametrize(
    "args",
    [["grant"], ["--env"], ["revoke", "app-team-a", "--logs"], ["bogus", "app-team-a"]],
)
def test_usage_errors(fake, args):
    assert fake(*args).returncode == 2


def test_script_never_creates_cluster_wide_bindings():
    assert "clusterrolebinding" not in SCRIPT.read_text()


def test_script_is_executable():
    assert os.access(SCRIPT, os.X_OK)


def test_script_passes_subresources_to_can_i(fake):
    fake("--env", "lab", "grant", "app-team-a", "--logs")
    calls = fake.calls()
    assert "auth can-i get pods --subresource=log" in calls
    assert "auth can-i create pods --subresource=exec" in calls
    assert "pods/" not in "".join(
        line for line in calls.splitlines() if "can-i" in line
    )


def test_demo_access_checks_pass_subresources_explicitly():
    demo = (ROOT / "demo" / "run.sh").read_text()
    assert '--subresource="${resource#*/}"' in demo
    assert '"${resource%%/*}"' in demo


# --- admission policy ---------------------------------------------------------

POLICY_FILES = [
    ROOT / "k8s" / "admission-policy.yaml",
    ROOT / "gitops" / "base" / "admission-policy.yaml",
]


def _policy() -> tuple[dict, dict]:
    docs = {d["kind"]: d for d in _docs(POLICY_FILES[0])}
    return docs["ValidatingAdmissionPolicy"], docs["ValidatingAdmissionPolicyBinding"]


def test_policy_copies_are_identical():
    assert POLICY_FILES[0].read_text() == POLICY_FILES[1].read_text()


@pytest.mark.parametrize("base", ["k8s", "gitops/base"])
def test_policy_is_deployed_by_kustomization(base):
    kustomization = yaml.safe_load((ROOT / base / "kustomization.yaml").read_text())
    assert "admission-policy.yaml" in kustomization["resources"]
    # A namespace transformer would stamp a namespace onto the cluster-scoped
    # policy objects; every namespaced object sets its namespace explicitly.
    assert "namespace" not in kustomization


def test_policy_fails_closed_and_denies():
    policy, binding = _policy()
    assert policy["spec"]["failurePolicy"] == "Fail"
    assert binding["spec"]["policyName"] == policy["metadata"]["name"]
    assert binding["spec"]["validationActions"] == ["Deny"]


def test_policy_never_blocks_deletes():
    policy, _ = _policy()
    for rule in policy["spec"]["matchConstraints"]["resourceRules"]:
        assert rule["operations"] == ["CREATE", "UPDATE"]
        assert set(rule["resources"]) == {"rolebindings", "clusterrolebindings"}


def test_policy_role_names_match_rbac():
    policy, _ = _policy()
    variables = {v["name"]: v["expression"] for v in policy["spec"]["variables"]}
    in_policy = set(yaml.safe_load(variables["debugRoles"]))
    in_rbac = set(_roles(_docs(RBAC_FILES[0])))
    assert in_policy == in_rbac


def test_policy_has_five_rules_with_messages():
    policy, _ = _policy()
    validations = policy["spec"]["validations"]
    assert len(validations) == 5
    for v in validations:
        assert v["messageExpression"] and v["reason"] == "Forbidden"


# --- grant expiry (ADR-SEC-001 section 7, item 2) -----------------------------

EXPIRES = "production-debug/expires-at"


def _expiry(fake, name):
    from datetime import datetime, timezone

    value = fake.manifest(name)["metadata"]["annotations"][EXPIRES]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value), value
    expires = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return (expires - datetime.now(timezone.utc)).total_seconds()


def test_grant_expires_after_four_hours_by_default(fake):
    result = fake("--env", "lab", "grant", "app-team-a")
    assert result.returncode == 0, result.stderr
    assert 4 * 3600 - 120 < _expiry(fake, "prod-debug-reader") <= 4 * 3600
    assert "access expires at" in result.stdout


def test_ttl_applies_to_both_layers(fake):
    result = fake("--env", "lab", "grant", "app-team-b", "--logs", "--ttl", "30m")
    assert result.returncode == 0, result.stderr
    for name in ("prod-debug-reader", "prod-debug-log-reader"):
        assert 1800 - 120 < _expiry(fake, name) <= 1800


def test_grant_labels_and_subject_are_set_at_creation(fake):
    fake("--env", "lab", "grant", "app-team-a")
    rb = fake.manifest("prod-debug-reader")
    assert rb["metadata"]["labels"]["production-debug/env"] == "lab"
    assert rb["roleRef"] == {
        "apiGroup": "rbac.authorization.k8s.io",
        "kind": "ClusterRole",
        "name": "prod-debug-reader",
    }
    assert rb["subjects"] == [
        {"kind": "ServiceAccount", "name": "prod-debug-sa", "namespace": "debug-system"}
    ]


def test_regrant_replaces_the_binding_instead_of_updating_it(fake):
    fake("--env", "lab", "grant", "app-team-a", "--ttl", "1h")
    fake("--env", "lab", "grant", "app-team-a", "--ttl", "2h")
    calls = fake.calls().splitlines()
    deletes = [
        i
        for i, c in enumerate(calls)
        if c.startswith("delete rolebinding prod-debug-reader ")
    ]
    creates = [i for i, c in enumerate(calls) if c.startswith("create -f")]
    assert len(deletes) == 2 and len(creates) == 2
    assert deletes[1] < creates[1]
    assert 7200 - 120 < _expiry(fake, "prod-debug-reader") <= 7200
    assert not any(c.startswith(("apply", "label", "annotate")) for c in calls)


@pytest.mark.parametrize("ttl", ["0m", "4m", "25h", "1441m", "1d", "4", "-1h", "h"])
def test_ttl_outside_limits_is_refused(fake, ttl):
    result = fake("--env", "lab", "grant", "app-team-a", "--ttl", ttl)
    assert result.returncode == 2
    assert fake.bindings() == []


@pytest.mark.parametrize("ttl", ["5m", "24h", "1440m"])
def test_ttl_limits_are_inclusive(fake, ttl):
    assert fake("--env", "lab", "grant", "app-team-a", "--ttl", ttl).returncode == 0


def test_check_reports_expiry(fake):
    fake("--env", "lab", "grant", "app-team-a")
    result = fake("check", "app-team-a")
    assert re.search(r"prod-debug-reader\s+expires-at=\d{4}-", result.stdout)


def test_policy_requires_an_expiry_and_freezes_it():
    policy, _ = _policy()
    text = yaml.safe_dump(policy)
    assert EXPIRES in text
    assert "duration('24h10m')" in text
    assert "variables.expiresAt == variables.oldExpiresAt" in text
