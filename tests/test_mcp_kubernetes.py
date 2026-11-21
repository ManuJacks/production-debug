"""
Read-only contract for the Kubernetes MCP tools.

These tests are the acceptance criteria for "the AI cannot modify cluster
resources through this server": every Kubernetes tool must route through
_run_kubectl, which only permits get/describe/logs, and every argument must be
validated before it reaches kubectl.
"""

from __future__ import annotations

import inspect
import subprocess
from unittest.mock import patch

import pytest

import mcp.server as server
from mcp.server import (
    KUBECTL_READ_ONLY_VERBS,
    KubectlPolicyError,
    _run_kubectl,
    k8s_describe_pod_impl,
    k8s_get_events_impl,
    k8s_get_pod_logs_impl,
    k8s_list_pods_impl,
)

K8S_TOOLS = ["k8s_list_pods", "k8s_get_events", "k8s_describe_pod", "k8s_get_pod_logs"]

VALID_CALLS = [
    (k8s_list_pods_impl, {"namespace": "production-debug-lab"}),
    (k8s_get_events_impl, {"namespace": "production-debug-lab"}),
    (k8s_describe_pod_impl, {"namespace": "lab", "pod": "crashloop-demo-abc12"}),
    (k8s_get_pod_logs_impl, {"namespace": "lab", "pod": "web-0"}),
    (
        k8s_get_pod_logs_impl,
        {"namespace": "lab", "pod": "web-0", "container": "app", "previous": True},
    ),
]

# Global flags _run_kubectl may prepend before the verb.
GLOBAL_FLAG_PREFIXES = ("--request-timeout=", "--context")


class _Recorder:
    def __init__(self, stdout: str = "ok\n", returncode: int = 0):
        self.calls: list[list[str]] = []
        self.stdout = stdout
        self.returncode = returncode

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, "")


def _verb(cmd: list[str]) -> str:
    args = cmd[1:]
    i = 0
    while i < len(args) and args[i].startswith(GLOBAL_FLAG_PREFIXES):
        i += 2 if args[i] == "--context" else 1
    return args[i]


@pytest.fixture
def recorder():
    rec = _Recorder()
    with (
        patch("mcp.server.shutil.which", return_value="/usr/bin/kubectl"),
        patch("mcp.server.subprocess.run", rec),
    ):
        yield rec


class TestReadOnlyPolicy:
    def test_allowlist_is_exactly_read_verbs(self):
        assert KUBECTL_READ_ONLY_VERBS == frozenset({"get", "describe", "logs"})

    @pytest.mark.parametrize(
        "verb",
        [
            "delete",
            "apply",
            "create",
            "patch",
            "edit",
            "replace",
            "scale",
            "exec",
            "cp",
            "port-forward",
            "proxy",
            "debug",
            "drain",
            "cordon",
            "label",
            "annotate",
            "rollout",
            "set",
            "auth",
        ],
    )
    def test_mutating_and_interactive_verbs_are_refused(self, verb, recorder):
        with pytest.raises(KubectlPolicyError):
            _run_kubectl([verb, "pods"])
        assert recorder.calls == []

    def test_empty_command_is_refused(self, recorder):
        with pytest.raises(KubectlPolicyError):
            _run_kubectl([])

    @pytest.mark.parametrize("fn,kwargs", VALID_CALLS)
    def test_every_tool_invokes_only_read_verbs(self, fn, kwargs, recorder):
        result = fn(**kwargs)
        assert result["status"] == "success"
        assert len(recorder.calls) == 1
        assert _verb(recorder.calls[0]) in KUBECTL_READ_ONLY_VERBS

    def test_context_override_is_passed_as_flag(self, recorder):
        with patch.dict("os.environ", {"PRODUCTION_DEBUG_KUBE_CONTEXT": "minikube"}):
            k8s_list_pods_impl("lab")
        cmd = recorder.calls[0]
        assert cmd[cmd.index("--context") + 1] == "minikube"
        assert _verb(cmd) == "get"

    def test_kubernetes_tools_never_call_subprocess_directly(self):
        for fn in (
            k8s_list_pods_impl,
            k8s_get_events_impl,
            k8s_describe_pod_impl,
            k8s_get_pod_logs_impl,
        ):
            source = inspect.getsource(fn)
            assert "subprocess" not in source
            assert "_run_kubectl(" in source

    def test_registered_tools_are_annotated_read_only(self):
        for name in K8S_TOOLS:
            tool = getattr(server, name)
            ann = getattr(tool, "_mcp_annotations", None)
            if ann is None:  # fastmcp installed: decorator returns a Tool object
                pytest.skip("annotations stored by fastmcp")
            assert ann["readOnlyHint"] is True
            assert ann["destructiveHint"] is False


class TestArgumentValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "--all-namespaces",
            "-A",
            "lab;rm -rf /",
            "lab --kubeconfig=/etc/x",
            "../etc",
            "Lab",
            "a" * 64,
            None,
            123,
        ],
    )
    def test_invalid_namespace_rejected_before_kubectl(self, bad, recorder):
        for fn in (k8s_list_pods_impl, k8s_get_events_impl):
            assert fn(bad)["status"] == "error"
        assert k8s_describe_pod_impl(bad, "pod")["status"] == "error"
        assert k8s_get_pod_logs_impl(bad, "pod")["status"] == "error"
        assert recorder.calls == []

    @pytest.mark.parametrize(
        "bad", ["--previous", "-c", "pod$(id)", "pod name", "pod/../x", ""]
    )
    def test_invalid_pod_rejected(self, bad, recorder):
        assert k8s_describe_pod_impl("lab", bad)["status"] == "error"
        assert k8s_get_pod_logs_impl("lab", bad)["status"] == "error"
        assert recorder.calls == []

    def test_invalid_container_and_previous_rejected(self, recorder):
        assert k8s_get_pod_logs_impl("lab", "p", container="-f")["status"] == "error"
        assert k8s_get_pod_logs_impl("lab", "p", previous="yes")["status"] == "error"
        assert recorder.calls == []

    def test_tail_lines_is_clamped(self, recorder):
        k8s_get_pod_logs_impl("lab", "p", tail_lines=10_000_000)
        k8s_get_pod_logs_impl("lab", "p", tail_lines=-5)
        assert "--tail=1000" in recorder.calls[0]
        assert "--tail=1" in recorder.calls[1]


class TestOutputHandling:
    def test_output_is_redacted(self):
        rec = _Recorder(stdout="Authorization: Bearer abcdefghijklmnop0123456789\n")
        with (
            patch("mcp.server.shutil.which", return_value="/usr/bin/kubectl"),
            patch("mcp.server.subprocess.run", rec),
        ):
            result = k8s_get_pod_logs_impl("lab", "p")
        assert "abcdefghijklmnop0123456789" not in result["output"]
        assert "[REDACTED:TOKEN]" in result["output"]

    def test_output_is_bounded(self):
        rec = _Recorder(stdout="x" * (server.MAX_TOOL_OUTPUT_CHARS + 500))
        with (
            patch("mcp.server.shutil.which", return_value="/usr/bin/kubectl"),
            patch("mcp.server.subprocess.run", rec),
        ):
            result = k8s_list_pods_impl("lab")
        assert result["truncated"] is True
        assert len(result["output"]) == server.MAX_TOOL_OUTPUT_CHARS

    def test_forbidden_is_reported_not_raised(self):
        rec = _Recorder(stdout="", returncode=1)
        with (
            patch("mcp.server.shutil.which", return_value="/usr/bin/kubectl"),
            patch("mcp.server.subprocess.run", rec),
        ):
            result = k8s_list_pods_impl("kube-system")
        assert result["status"] == "failed"

    def test_missing_kubectl(self):
        with patch("mcp.server.shutil.which", return_value=None):
            result = k8s_list_pods_impl("lab")
        assert result["status"] == "error"
        assert "kubectl" in result["error"]

    def test_timeout(self):
        def boom(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 20)

        with (
            patch("mcp.server.shutil.which", return_value="/usr/bin/kubectl"),
            patch("mcp.server.subprocess.run", boom),
        ):
            result = k8s_get_events_impl("lab")
        assert result["status"] == "error"
        assert "timed out" in result["error"]


def test_in_cluster_calls_pass_no_config_overrides(recorder):
    """Regression: any override (e.g. --request-timeout) makes client-go skip
    in-cluster ServiceAccount config and fall back to localhost:8080."""
    with patch.dict("os.environ", {}, clear=True):
        k8s_list_pods_impl("lab")
    cmd = recorder.calls[0]
    assert cmd[1] == "get"
    assert not any(
        a.startswith(("--request-timeout", "--context", "--server")) for a in cmd
    )


def test_transient_failure_retried_once_forbidden_not():
    outcomes = iter(
        [
            subprocess.CompletedProcess(
                [], 1, "", "the server has asked for credentials"
            ),
            subprocess.CompletedProcess([], 0, "NAME\n", ""),
        ]
    )
    with (
        patch("mcp.server.shutil.which", return_value="/usr/bin/kubectl"),
        patch("mcp.server.subprocess.run", lambda *a, **k: next(outcomes)),
    ):
        result = k8s_list_pods_impl("lab")
    assert result["status"] == "success"
    assert result["attempts"] == 2

    calls = []

    def forbidden(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 1, "", "Error from server (Forbidden)")

    with (
        patch("mcp.server.shutil.which", return_value="/usr/bin/kubectl"),
        patch("mcp.server.subprocess.run", forbidden),
    ):
        result = k8s_list_pods_impl("kube-system")
    assert result["status"] == "failed"
    assert len(calls) == 1
