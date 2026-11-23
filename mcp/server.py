"""
Model Context Protocol (MCP) server for production-debug diagnostics.
Exposes sandboxed, read-only SRE diagnostic tools via standard JSON-RPC.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any

try:
    from production_debug.sanitizer import redact_text
except ImportError:  # running as a script: make the repo/app root importable
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from production_debug.sanitizer import redact_text

# Domain name format: RFC 1035 label compliance
SAFE_DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)
# Interface name format: typical Linux network device naming
SAFE_IFACE_REGEX = re.compile(r"^[a-zA-Z0-9._-]{1,16}$")
# Incident identifier format
SAFE_INCIDENT_ID_REGEX = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")
# Kubernetes names: RFC 1123 label (namespace, container) and subdomain (pod)
K8S_LABEL_REGEX = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
K8S_SUBDOMAIN_REGEX = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")

# The only kubectl verbs the MCP server may ever invoke. Enforced centrally in
# _run_kubectl; mutation is additionally denied by the ServiceAccount's RBAC.
KUBECTL_READ_ONLY_VERBS = frozenset({"get", "describe", "logs"})
KUBECTL_TIMEOUT_SEC = 20
MAX_TOOL_OUTPUT_CHARS = 64_000

# Tool annotation definitions adhering to MCP spec requirements:
# Explicit non-null booleans for readOnlyHint, destructiveHint, idempotentHint, openWorldHint.
DNS_PROBE_ANNOTATIONS: dict[str, Any] = {
    "title": "DNS Probe",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

AZURE_IDENTITY_ANNOTATIONS: dict[str, Any] = {
    "title": "Azure Workload Identity Check",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

NETWORK_TRACE_ANNOTATIONS: dict[str, Any] = {
    "title": "Network Trace Summary",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}

INCIDENT_BUNDLE_ANNOTATIONS: dict[str, Any] = {
    "title": "Generate Incident Bundle",
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


K8S_READ_ANNOTATIONS: dict[str, Any] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


class KubectlPolicyError(ValueError):
    """Raised when a kubectl invocation would violate the read-only policy."""


def _run_kubectl(args: list[str]) -> dict[str, Any]:
    """Run a read-only kubectl command and return redacted, bounded output.

    The verb allowlist is enforced here so that no tool can construct a
    mutating command, even by mistake.
    """
    if not args or args[0] not in KUBECTL_READ_ONLY_VERBS:
        raise KubectlPolicyError(f"kubectl verb not permitted: {args[:1]}")

    kubectl = shutil.which("kubectl")
    if not kubectl:
        return {"status": "error", "error": "kubectl executable not found in PATH"}

    # No --request-timeout: any config override makes client-go skip the
    # in-cluster ServiceAccount config. The subprocess timeout bounds the call.
    cmd = [kubectl]
    context = os.environ.get("PRODUCTION_DEBUG_KUBE_CONTEXT")
    if context:
        cmd += ["--context", context]
    cmd += args

    try:
        # One retry for transient API failures; authorization and not-found
        # errors are definitive and returned immediately.
        for attempt in (1, 2):
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=KUBECTL_TIMEOUT_SEC,
            )
            if proc.returncode == 0 or re.search(
                r"forbidden|notfound|not found", proc.stderr, re.IGNORECASE
            ):
                break
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": f"kubectl timed out after {KUBECTL_TIMEOUT_SEC}s",
        }
    except (subprocess.SubprocessError, OSError) as exc:
        return {"status": "error", "error": str(exc)}

    stdout = redact_text(proc.stdout)
    truncated = len(stdout) > MAX_TOOL_OUTPUT_CHARS
    result: dict[str, Any] = {
        "status": "success" if proc.returncode == 0 else "failed",
        "command": "kubectl " + " ".join(args),
        "output": stdout[-MAX_TOOL_OUTPUT_CHARS:] if truncated else stdout,
        "truncated": truncated,
        "attempts": attempt,
    }
    if proc.returncode != 0:
        result["error"] = redact_text(proc.stderr.strip())[:2000]
    return result


def _invalid(field: str) -> dict[str, Any]:
    return {
        "status": "error",
        "error": f"Invalid {field}: must be a valid Kubernetes name.",
    }


def k8s_list_pods_impl(namespace: str) -> dict[str, Any]:
    """List pods with status, restarts, node and IP."""
    if not isinstance(namespace, str) or not K8S_LABEL_REGEX.match(namespace):
        return _invalid("namespace")
    return _run_kubectl(["get", "pods", "-n", namespace, "-o", "wide"])


def k8s_get_events_impl(namespace: str) -> dict[str, Any]:
    """List namespace events, oldest first."""
    if not isinstance(namespace, str) or not K8S_LABEL_REGEX.match(namespace):
        return _invalid("namespace")
    return _run_kubectl(["get", "events", "-n", namespace, "--sort-by=.lastTimestamp"])


def k8s_describe_pod_impl(namespace: str, pod: str) -> dict[str, Any]:
    """Describe a single pod: container states, exit codes, probes, events."""
    if not isinstance(namespace, str) or not K8S_LABEL_REGEX.match(namespace):
        return _invalid("namespace")
    if not isinstance(pod, str) or not K8S_SUBDOMAIN_REGEX.match(pod):
        return _invalid("pod")
    return _run_kubectl(["describe", "pod", pod, "-n", namespace])


def k8s_get_pod_logs_impl(
    namespace: str,
    pod: str,
    container: str | None = None,
    previous: bool = False,
    tail_lines: int = 200,
) -> dict[str, Any]:
    """Fetch recent logs for a pod, optionally from the previous container instance."""
    if not isinstance(namespace, str) or not K8S_LABEL_REGEX.match(namespace):
        return _invalid("namespace")
    if not isinstance(pod, str) or not K8S_SUBDOMAIN_REGEX.match(pod):
        return _invalid("pod")
    if container is not None and (
        not isinstance(container, str) or not K8S_LABEL_REGEX.match(container)
    ):
        return _invalid("container")
    if not isinstance(previous, bool):
        return {"status": "error", "error": "previous must be a boolean"}
    try:
        tail = max(1, min(int(tail_lines), 1000))
    except (TypeError, ValueError):
        return {"status": "error", "error": "tail_lines must be an integer"}

    args = ["logs", pod, "-n", namespace, f"--tail={tail}", "--timestamps"]
    args += ["-c", container] if container else ["--all-containers", "--prefix"]
    if previous:
        args.append("--previous")
    return _run_kubectl(args)


def run_dns_probe_impl(
    domain: str,
    nameserver: str | None = None,
) -> dict[str, Any]:
    """Diagnose DNS resolution, query latency, and record availability."""
    if not isinstance(domain, str) or not SAFE_DOMAIN_REGEX.match(domain.strip()):
        return {
            "status": "error",
            "error": "Invalid domain name format. Must be a valid hostname without special shell characters.",
        }

    cmd = ["dig", "+noall", "+answer", "+stats", domain.strip()]
    if nameserver is not None:
        if not isinstance(nameserver, str) or not SAFE_DOMAIN_REGEX.match(
            nameserver.strip()
        ):
            return {
                "status": "error",
                "error": "Invalid nameserver format. Must be a valid hostname or IP address.",
            }
        cmd.append(f"@{nameserver.strip()}")

    if not shutil.which("dig"):
        return {"status": "error", "error": "dig executable not found in PATH"}

    try:
        proc = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=10
        )
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "DNS resolution timed out after 10s"}
    except (subprocess.SubprocessError, OSError) as exc:
        return {"status": "error", "error": str(exc)}


def check_azure_workload_identity_impl() -> dict[str, Any]:
    """Audit Azure Workload Identity / IMDS environment without leaking secrets."""
    client_id = os.environ.get("AZURE_CLIENT_ID")
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    token_file = os.environ.get("AZURE_FEDERATED_TOKEN_FILE")
    authority = os.environ.get(
        "AZURE_AUTHORITY_HOST", "https://login.microsoftonline.com/"
    )

    report: dict[str, Any] = {
        "azure_workload_identity": {
            "configured": bool(client_id and tenant_id and token_file),
            "client_id_present": bool(client_id),
            "tenant_id_present": bool(tenant_id),
            "token_file_present": bool(token_file and os.path.exists(token_file)),
            "authority": authority,
        },
        "imds_probe": {
            "reachable": False,
        },
    }

    # Non-destructive curl to Azure Instance Metadata Service (IMDS)
    if shutil.which("curl"):
        try:
            imds_cmd = [
                "curl",
                "-s",
                "-m",
                "2",
                "-H",
                "Metadata:true",
                "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
            ]
            proc = subprocess.run(
                imds_cmd, check=False, capture_output=True, text=True, timeout=3
            )
            if proc.returncode == 0 and proc.stdout:
                try:
                    data = json.loads(proc.stdout)
                    compute = data.get("compute", {})
                    report["imds_probe"] = {
                        "reachable": True,
                        "vmId": compute.get("vmId"),
                        "location": compute.get("location"),
                        "resourceGroupName": compute.get("resourceGroupName"),
                        "osType": compute.get("osType"),
                    }
                except json.JSONDecodeError:
                    report["imds_probe"] = {
                        "reachable": True,
                        "raw_response_received": True,
                    }
        except (subprocess.SubprocessError, OSError):
            report["imds_probe"] = {"reachable": False}

    return report


def capture_network_trace_summary_impl(
    interface: str = "eth0", duration_sec: int = 5
) -> dict[str, Any]:
    """Collect a brief packet summary trace using tcpdump."""
    if not isinstance(interface, str) or not SAFE_IFACE_REGEX.match(interface.strip()):
        return {
            "status": "error",
            "error": "Invalid network interface format. Alphanumeric, dot, dash, and underscore only.",
        }

    try:
        duration = max(1, min(int(duration_sec), 30))
    except (ValueError, TypeError):
        return {
            "status": "error",
            "error": "duration_sec must be an integer between 1 and 30",
        }

    if not shutil.which("tcpdump"):
        return {
            "status": "error",
            "error": "tcpdump not found in PATH or insufficient capabilities (NET_ADMIN/NET_RAW required)",
        }

    # -p: never put the interface into promiscuous mode. Without it tcpdump
    # changes the interface flags, so the tool would not be read-only.
    # No -w: captures are summarised in memory, never written to disk.
    cmd = ["tcpdump", "-p", "-i", interface.strip(), "-c", "25", "-nn", "-q"]
    try:
        proc = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=duration
        )
        lines = proc.stdout.splitlines()
        return {
            "status": "success",
            "interface": interface.strip(),
            "partial": False,
            "packet_count": len(lines),
            "sample_packets": lines[:10],
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        # A quiet interface may not reach 25 packets within the window: return
        # what was observed instead of discarding it.
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        lines = output.splitlines()
        return {
            "status": "success",
            "interface": interface.strip(),
            "partial": True,
            "packet_count": len(lines),
            "sample_packets": lines[:10],
            "stderr": "",
        }
    except (subprocess.SubprocessError, OSError) as exc:
        return {"status": "error", "error": str(exc)}


def generate_incident_bundle_impl(
    incident_id: str = "INCIDENT",
    output_dir: str = "/tmp/incident-bundle",
) -> dict[str, Any]:
    """Create an incident bundle using the script's best-effort sanitization."""
    if not isinstance(incident_id, str) or not SAFE_INCIDENT_ID_REGEX.match(
        incident_id.strip()
    ):
        return {
            "status": "error",
            "error": "Invalid incident_id format. Alphanumeric, hyphen, and underscore only.",
        }

    # First check relative path within repo, then system path
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../scripts/incident_bundle.sh")
    )
    if not os.path.exists(script_path):
        script_path = "/usr/local/bin/incident_bundle.sh"

    if not os.path.exists(script_path):
        return {
            "status": "error",
            "error": f"incident_bundle.sh not found at {script_path}",
        }

    try:
        os.makedirs(output_dir, exist_ok=True)
        proc = subprocess.run(
            [script_path, output_dir, "--name", incident_id.strip()],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "bundle_dir": output_dir,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": "Incident bundle creation timed out after 30s",
        }
    except (subprocess.SubprocessError, OSError) as exc:
        return {"status": "error", "error": str(exc)}


# Initialize FastMCP if available, otherwise provide mock decorator pattern
try:
    from fastmcp import FastMCP

    mcp = FastMCP("production-debug-mcp")
except ImportError:
    mcp = None


class _MockDecorator:
    @staticmethod
    def tool(
        name: str | None = None,
        description: str | None = None,
        annotations: dict[str, Any] | None = None,
    ):
        def decorator(fn):
            fn._mcp_tool_name = name or fn.__name__
            fn._mcp_tool_description = description or fn.__doc__
            fn._mcp_annotations = annotations or {}
            return fn

        return decorator


_decorator_source = mcp if mcp is not None else _MockDecorator


@_decorator_source.tool(
    name="run_dns_probe",
    description="Diagnose DNS resolution, query latency, and record availability.",
    annotations={
        "title": "DNS Probe",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def run_dns_probe(domain: str, nameserver: str | None = None) -> dict[str, Any]:
    """Diagnose DNS resolution, query latency, and record availability."""
    return run_dns_probe_impl(domain, nameserver)


@_decorator_source.tool(
    name="check_azure_workload_identity",
    description="Audit Azure Workload Identity and IMDS reachability.",
    annotations={
        "title": "Azure Workload Identity Check",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
def check_azure_workload_identity() -> dict[str, Any]:
    """Audit Azure Workload Identity and IMDS reachability."""
    return check_azure_workload_identity_impl()


@_decorator_source.tool(
    name="capture_network_trace_summary",
    description=(
        "Read-only local packet observation using tcpdump in non-promiscuous "
        "mode (-p); returns up to 25 packet summaries observed within "
        "duration_sec (max 30 s). It runs a transient tcpdump subprocess with "
        "a capture socket, but writes no files and does not change interface "
        "or network configuration. Requires packet-capture capabilities."
    ),
    annotations={
        "title": "Network Trace Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
def capture_network_trace_summary(
    interface: str = "eth0", duration_sec: int = 5
) -> dict[str, Any]:
    """Read-only local packet observation with bounded tcpdump capture."""
    return capture_network_trace_summary_impl(interface, duration_sec)


@_decorator_source.tool(
    name="generate_incident_bundle",
    description="Create an incident archive with best-effort sensitive-pattern redaction.",
    annotations={
        "title": "Generate Incident Bundle",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
def generate_incident_bundle(incident_id: str = "INCIDENT") -> dict[str, Any]:
    """Create an incident archive with best-effort sensitive-pattern redaction."""
    return generate_incident_bundle_impl(incident_id)


@_decorator_source.tool(
    name="k8s_list_pods",
    description="Read-only: list pods in a namespace with status, restart count, node and IP.",
    annotations={
        "title": "List Pods",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def k8s_list_pods(namespace: str) -> dict[str, Any]:
    """List pods in a namespace (read-only)."""
    return k8s_list_pods_impl(namespace)


@_decorator_source.tool(
    name="k8s_get_events",
    description="Read-only: list events in a namespace, oldest first.",
    annotations={
        "title": "Get Events",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def k8s_get_events(namespace: str) -> dict[str, Any]:
    """List namespace events (read-only)."""
    return k8s_get_events_impl(namespace)


@_decorator_source.tool(
    name="k8s_describe_pod",
    description="Read-only: describe a pod, including container states, exit codes, probes and events.",
    annotations={
        "title": "Describe Pod",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def k8s_describe_pod(namespace: str, pod: str) -> dict[str, Any]:
    """Describe a pod (read-only)."""
    return k8s_describe_pod_impl(namespace, pod)


@_decorator_source.tool(
    name="k8s_get_pod_logs",
    description="Read-only: fetch recent pod logs; set previous=true for the last terminated container instance.",
    annotations={
        "title": "Get Pod Logs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def k8s_get_pod_logs(
    namespace: str,
    pod: str,
    container: str | None = None,
    previous: bool = False,
    tail_lines: int = 200,
) -> dict[str, Any]:
    """Fetch pod logs (read-only)."""
    return k8s_get_pod_logs_impl(namespace, pod, container, previous, tail_lines)


def main():
    if mcp:
        mcp.run(show_banner=False)
    else:
        # Fallback JSON-RPC stdio loop if fastmcp is not installed
        import sys

        print(
            json.dumps(
                {"status": "ready", "server": "production-debug-mcp-standalone"}
            ),
            flush=True,
        )
        for line in sys.stdin:
            try:
                req = json.loads(line)
                method = req.get("method")
                params = req.get("params", {})
                req_id = req.get("id")

                if method == "run_dns_probe":
                    res = run_dns_probe_impl(**params)
                elif method == "check_azure_workload_identity":
                    res = check_azure_workload_identity_impl()
                elif method == "capture_network_trace_summary":
                    res = capture_network_trace_summary_impl(**params)
                elif method == "generate_incident_bundle":
                    res = generate_incident_bundle_impl(**params)
                elif method == "k8s_list_pods":
                    res = k8s_list_pods_impl(**params)
                elif method == "k8s_get_events":
                    res = k8s_get_events_impl(**params)
                elif method == "k8s_describe_pod":
                    res = k8s_describe_pod_impl(**params)
                elif method == "k8s_get_pod_logs":
                    res = k8s_get_pod_logs_impl(**params)
                else:
                    res = {"error": f"Unknown method {method}"}

                print(
                    json.dumps({"jsonrpc": "2.0", "id": req_id, "result": res}),
                    flush=True,
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                print(json.dumps({"jsonrpc": "2.0", "error": str(e)}), flush=True)


if __name__ == "__main__":
    main()
