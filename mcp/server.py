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
from typing import Any, Dict

try:
    from fastmcp import FastMCP
    mcp = FastMCP("production-debug-mcp")
except ImportError:
    mcp = None


SAFE_DOMAIN_REGEX = re.compile(r"^[a-zA-Z0-9.-]{1,253}$")
SAFE_IFACE_REGEX = re.compile(r"^[a-zA-Z0-9._-]{1,16}$")


def run_dns_probe_impl(domain: str, nameserver: str | None = None) -> Dict[str, Any]:
    """Diagnose DNS resolution, query latency, and record availability."""
    if not SAFE_DOMAIN_REGEX.match(domain):
        return {"error": "Invalid domain name format"}

    cmd = ["dig", "+noall", "+answer", "+stats", domain]
    if nameserver:
        if not SAFE_DOMAIN_REGEX.match(nameserver):
            return {"error": "Invalid nameserver format"}
        cmd.append(f"@{nameserver}")

    if not shutil.which("dig"):
        return {"error": "dig executable not found in PATH"}

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def check_azure_workload_identity_impl() -> Dict[str, Any]:
    """Audit Azure Workload Identity / IMDS environment without leaking secrets."""
    client_id = os.environ.get("AZURE_CLIENT_ID")
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    token_file = os.environ.get("AZURE_FEDERATED_TOKEN_FILE")
    authority = os.environ.get("AZURE_AUTHORITY_HOST", "https://login.microsoftonline.com/")

    report: Dict[str, Any] = {
        "azure_workload_identity": {
            "configured": bool(client_id and tenant_id and token_file),
            "client_id_present": bool(client_id),
            "tenant_id_present": bool(tenant_id),
            "token_file_present": bool(token_file and os.path.exists(token_file)),
            "authority": authority,
        },
        "imds_probe": {
            "reachable": False,
        }
    }

    # Non-destructive curl to IMDS
    if shutil.which("curl"):
        try:
            imds_cmd = ["curl", "-s", "-m", "2", "-H", "Metadata:true", "http://169.254.169.254/metadata/instance?api-version=2021-02-01"]
            proc = subprocess.run(imds_cmd, capture_output=True, text=True, timeout=3)
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
                    report["imds_probe"] = {"reachable": True, "raw_response_received": True}
        except Exception:
            pass

    return report


def capture_network_trace_summary_impl(interface: str = "eth0", duration_sec: int = 5) -> Dict[str, Any]:
    """Collect a brief packet summary trace using tcpdump."""
    if not SAFE_IFACE_REGEX.match(interface):
        return {"error": "Invalid network interface format"}

    duration = max(1, min(int(duration_sec), 30))
    if not shutil.which("tcpdump"):
        return {"error": "tcpdump not found in PATH or insufficient capabilities (NET_ADMIN/NET_RAW required)"}

    cmd = ["tcpdump", "-i", interface, "-c", "25", "-nn", "-q"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 2)
        return {
            "status": "success",
            "interface": interface,
            "packet_count": len(proc.stdout.splitlines()),
            "sample_packets": proc.stdout.splitlines()[:10],
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "interface": interface}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def generate_incident_bundle_impl(incident_id: str = "INCIDENT") -> Dict[str, Any]:
    """Generate a sanitized incident triage bundle with SHA-256 fingerprint."""
    script_path = "/usr/local/bin/incident_bundle.sh"
    if not os.path.exists(script_path):
        # Fallback to local repo location
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts/incident_bundle.sh"))

    if not os.path.exists(script_path):
        return {"error": f"incident_bundle.sh not found at {script_path}"}

    try:
        out_dir = "/tmp/incident-bundle"
        os.makedirs(out_dir, exist_ok=True)
        proc = subprocess.run([script_path, incident_id, out_dir], capture_output=True, text=True, timeout=30)
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "bundle_dir": out_dir,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


if mcp:
    @mcp.tool()
    def run_dns_probe(domain: str, nameserver: str | None = None) -> Dict[str, Any]:
        """Diagnose DNS resolution, query latency, and record availability."""
        return run_dns_probe_impl(domain, nameserver)

    @mcp.tool()
    def check_azure_workload_identity() -> Dict[str, Any]:
        """Audit Azure Workload Identity and IMDS reachability."""
        return check_azure_workload_identity_impl()

    @mcp.tool()
    def capture_network_trace_summary(interface: str = "eth0", duration_sec: int = 5) -> Dict[str, Any]:
        """Collect packet sample and network trace statistics."""
        return capture_network_trace_summary_impl(interface, duration_sec)

    @mcp.tool()
    def generate_incident_bundle(incident_id: str = "INCIDENT") -> Dict[str, Any]:
        """Generate a sanitized, redacted incident archive."""
        return generate_incident_bundle_impl(incident_id)


def main():
    if mcp:
        mcp.run()
    else:
        # Fallback JSON-RPC stdio loop if fastmcp is not installed
        import sys
        print(json.dumps({"status": "ready", "server": "production-debug-mcp-standalone"}), flush=True)
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

                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": res}), flush=True)
            except Exception as e:
                print(json.dumps({"jsonrpc": "2.0", "error": str(e)}), flush=True)


if __name__ == "__main__":
    main()
