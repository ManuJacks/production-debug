"""Grant reaper: removes expired production-debug grants (ADR-SEC-001 §7 item 2).

scripts/reap-expired-grants.sh runs against a fake kubectl whose RoleBinding
listing comes from FAKE_LIST, in the go-template format the script asks for.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "reap-expired-grants.sh"
MANIFESTS = [
    ROOT / "k8s" / "grant-reaper.yaml",
    ROOT / "gitops" / "base" / "grant-reaper.yaml",
]

FAKE_KUBECTL = r"""#!/usr/bin/env bash
echo "$*" >> "$CALLS"
case "$1 $2" in
  "get rolebindings") [ -n "${FAKE_FAIL:-}" ] && exit 1; cat "$FAKE_LIST" ;;
  "delete rolebinding") [ "$3" = "${FAKE_DELETE_FAILS:-}" ] && exit 1; exit 0 ;;
  *) echo "unexpected: $*" >&2; exit 99 ;;
esac
"""


def ts(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def reaper(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "kubectl").write_text(FAKE_KUBECTL)
    (bin_dir / "kubectl").chmod(0o755)
    listing, calls = tmp_path / "list", tmp_path / "calls"
    calls.touch()

    def run(rows, *args, **extra):
        listing.write_text("".join("\t".join(r) + "\n" for r in rows))
        env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "FAKE_LIST": str(listing),
            "CALLS": str(calls),
            **extra,
        }
        return subprocess.run(
            ["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env
        )

    run.deletes = lambda: [
        c for c in calls.read_text().splitlines() if c.startswith("delete")
    ]
    return run


def test_expired_grant_is_reaped_and_current_one_kept(reaper):
    result = reaper(
        [
            (
                "app-team-a",
                "prod-debug-reader",
                "prod-debug-reader",
                ts(-timedelta(minutes=1)),
            ),
            (
                "app-team-b",
                "prod-debug-reader",
                "prod-debug-reader",
                ts(timedelta(hours=1)),
            ),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert reaper.deletes() == [
        "delete rolebinding prod-debug-reader -n app-team-a --wait=false"
    ]
    assert "kept=1 reaped=1" in result.stdout


@pytest.mark.parametrize(
    "expires", ["", "<no value>", "tomorrow", "2026-11-28T00:00:00+00:00"]
)
def test_grant_without_valid_expiry_is_reaped(reaper, expires):
    result = reaper(
        [("app-team-a", "prod-debug-log-reader", "prod-debug-log-reader", expires)]
    )
    assert result.returncode == 0, result.stderr
    assert len(reaper.deletes()) == 1
    assert "no valid production-debug/expires-at" in result.stdout


def test_unrelated_bindings_are_never_touched(reaper):
    result = reaper(
        [
            ("app-team-a", "view-for-team", "view", ""),
            ("app-team-a", "prod-debug-reader", "edit", ts(-timedelta(hours=1))),
        ]
    )
    assert result.returncode == 0
    assert reaper.deletes() == []


def test_debug_role_under_another_name_is_reported_not_deleted(reaper):
    result = reaper(
        [("app-team-a", "sneaky", "prod-debug-reader", ts(-timedelta(hours=1)))]
    )
    assert result.returncode == 1
    assert reaper.deletes() == []
    assert "revoke it by hand" in result.stderr


def test_dry_run_deletes_nothing(reaper):
    result = reaper(
        [("app-team-a", "prod-debug-reader", "prod-debug-reader", "")], "--dry-run"
    )
    assert result.returncode == 0
    assert reaper.deletes() == []
    assert "would reap app-team-a/prod-debug-reader" in result.stdout


def test_failed_listing_fails_the_run(reaper):
    assert reaper([], FAKE_FAIL="1").returncode != 0


def test_failed_delete_fails_the_run_but_continues(reaper):
    result = reaper(
        [
            ("app-team-a", "prod-debug-reader", "prod-debug-reader", ""),
            ("app-team-b", "prod-debug-log-reader", "prod-debug-log-reader", ""),
        ],
        FAKE_DELETE_FAILS="prod-debug-reader",
    )
    assert result.returncode == 1
    assert len(reaper.deletes()) == 2


def test_usage_error(reaper):
    assert reaper([], "--force").returncode == 2


# --- manifests -----------------------------------------------------------------


def _docs(path: Path) -> dict[str, dict]:
    return {d["kind"]: d for d in yaml.safe_load_all(path.read_text()) if d}


def test_manifest_copies_are_identical():
    assert MANIFESTS[0].read_text() == MANIFESTS[1].read_text()


@pytest.mark.parametrize("base", ["k8s", "gitops/base"])
def test_reaper_is_deployed_by_kustomization(base):
    kustomization = yaml.safe_load((ROOT / base / "kustomization.yaml").read_text())
    assert "grant-reaper.yaml" in kustomization["resources"]


def test_configmap_embeds_the_script_exactly():
    embedded = _docs(MANIFESTS[0])["ConfigMap"]["data"]["reap-expired-grants.sh"]
    assert embedded == SCRIPT.read_text(), (
        "regenerate k8s/grant-reaper.yaml from the script"
    )


def test_reaper_can_only_list_and_delete_debug_bindings():
    rules = _docs(MANIFESTS[0])["ClusterRole"]["rules"]
    assert rules == [
        {
            "apiGroups": ["rbac.authorization.k8s.io"],
            "resources": ["rolebindings"],
            "verbs": ["list"],
        },
        {
            "apiGroups": ["rbac.authorization.k8s.io"],
            "resources": ["rolebindings"],
            "resourceNames": ["prod-debug-reader", "prod-debug-log-reader"],
            "verbs": ["delete"],
        },
    ]


def test_cronjob_runs_often_and_restricted():
    cron = _docs(MANIFESTS[0])["CronJob"]["spec"]
    assert cron["schedule"] == "*/5 * * * *"
    assert cron["concurrencyPolicy"] == "Forbid"
    pod = cron["jobTemplate"]["spec"]["template"]["spec"]
    assert pod["serviceAccountName"] == "prod-debug-grant-reaper"
    assert pod["securityContext"]["runAsNonRoot"] is True
    (container,) = pod["containers"]
    sc = container["securityContext"]
    assert sc["readOnlyRootFilesystem"] is True
    assert sc["allowPrivilegeEscalation"] is False
    assert sc["capabilities"]["drop"] == ["ALL"]
    assert ":latest" not in container["image"]


def test_script_is_executable():
    assert os.access(SCRIPT, os.X_OK)
