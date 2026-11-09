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
from typing import Any

# Domain name format: RFC 1035 label compliance
SAFE_DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)
# Interface name format: typical Linux network device naming
SAFE_IFACE_REGEX = re.compile(r"^[a-zA-Z0-9._-]{1,16}$")
# Incident identifier format
SAFE_INCIDENT_ID_REGEX = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")

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

    cmd = ["tcpdump", "-i", interface.strip(), "-c", "25", "-nn", "-q"]
    try:
        proc = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=duration + 2
        )
        return {
            "status": "success",
            "interface": interface.strip(),
            "packet_count": len(proc.stdout.splitlines()),
            "sample_packets": proc.stdout.splitlines()[:10],
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "interface": interface.strip()}
    except (subprocess.SubprocessError, OSError) as exc:
        return {"status": "error", "error": str(exc)}


def generate_incident_bundle_impl(
    incident_id: str = "INCIDENT",
    output_dir: str = "/tmp/incident-bundle",
) -> dict[str, Any]:
    """Generate a sanitized incident triage bundle with SHA-256 fingerprint."""
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
    description="Collect packet sample and network trace statistics.",
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
    """Collect packet sample and network trace statistics."""
    return capture_network_trace_summary_impl(interface, duration_sec)


@_decorator_source.tool(
    name="generate_incident_bundle",
    description="Generate a sanitized, redacted incident archive.",
    annotations={
        "title": "Generate Incident Bundle",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
def generate_incident_bundle(incident_id: str = "INCIDENT") -> dict[str, Any]:
    """Generate a sanitized, redacted incident archive."""
    return generate_incident_bundle_impl(incident_id)


def main():
    if mcp:
        mcp.run()
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
