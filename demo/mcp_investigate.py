"""
Scripted MCP investigation of the crashloop incident.

Connects to the production-debug MCP server over stdio (by default via
`kubectl exec -i` into the diagnostic pod, so every call runs under the
pod's read-only ServiceAccount), then performs the investigation an AI
assistant would: inventory tools, list pods, read events, read logs.

This script is deterministic so the demo is reproducible; an interactive
assistant (e.g. Claude Code) can be attached to the same server command.

Usage:
  python demo/mcp_investigate.py --namespace production-debug-lab -- \
      kubectl --context minikube exec -i -n production-debug-diag incident-debug \
      -- /usr/local/bin/entrypoint.sh mcp
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

WRITE_HINTS = ("delete", "apply", "create", "patch", "exec", "scale", "restart")


def _payload(result) -> dict:
    if getattr(result, "structuredContent", None):
        data = result.structuredContent
        return data.get("result", data) if isinstance(data, dict) else {}
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"output": text}
    return {}


def _show(title: str, data: dict, max_lines: int = 12) -> None:
    print(f"\n── {title} [{data.get('status', '?')}] ── {data.get('command', '')}")
    body = data.get("output") or data.get("error") or ""
    lines = body.rstrip().splitlines()
    for line in lines[-max_lines:]:
        print(f"   {line}")


async def investigate(namespace: str, server_cmd: list[str]) -> int:
    # The SDK passes only a minimal environment by default; kubectl needs
    # KUBECONFIG (and HOME) to reach the cluster for `kubectl exec`.
    params = StdioServerParameters(
        command=server_cmd[0], args=server_cmd[1:], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = (await session.list_tools()).tools
            k8s_tools = [t for t in tools if t.name.startswith("k8s_")]
            print("MCP tools exposed to the assistant:")
            for tool in tools:
                ann = tool.annotations
                ro = (
                    getattr(ann, "read_only_hint", getattr(ann, "readOnlyHint", None))
                    if ann
                    else None
                )
                print(f"   {tool.name:32s} readOnlyHint={ro}")
            unsafe = [
                t.name for t in k8s_tools if any(w in t.name for w in WRITE_HINTS)
            ]
            if unsafe or not k8s_tools:
                print(f"unexpected tool surface: {unsafe or 'no k8s tools'}")
                return 1

            pods = _payload(
                await session.call_tool("k8s_list_pods", {"namespace": namespace})
            )
            _show("Pods", pods)

            match = re.search(r"^(crashloop-demo-\S+)", pods.get("output", ""), re.M)
            if not match:
                print("crashloop pod not found")
                return 1
            pod = match.group(1)

            events = _payload(
                await session.call_tool("k8s_get_events", {"namespace": namespace})
            )
            _show("Events", events, max_lines=8)

            describe = _payload(
                await session.call_tool(
                    "k8s_describe_pod", {"namespace": namespace, "pod": pod}
                )
            )
            state = [
                line.strip()
                for line in describe.get("output", "").splitlines()
                if re.match(r"\s*(State|Reason|Exit Code|Restart Count):", line)
            ]
            print(f"\n── Container state [{describe.get('status')}] ──")
            for line in state[:6]:
                print(f"   {line}")

            logs = _payload(
                await session.call_tool(
                    "k8s_get_pod_logs",
                    {"namespace": namespace, "pod": pod, "tail_lines": 20},
                )
            )
            _show("Logs", logs, max_lines=5)

            # Out-of-scope request: the ServiceAccount cannot read kube-system.
            denied = _payload(
                await session.call_tool("k8s_list_pods", {"namespace": "kube-system"})
            )
            _show("Out-of-scope request (kube-system)", denied, max_lines=2)

            evidence = (logs.get("output", "") + describe.get("output", "")).lower()
            print("\n── Assessment ──")
            if "missing config_url" in evidence:
                print(
                    "   Fault domain : application configuration (not image, not scheduling)"
                )
                print(
                    "   Evidence     : container exits 1 at startup logging 'missing CONFIG_URL'"
                )
                print(
                    "   Next step    : operator supplies CONFIG_URL via reviewed change"
                )
                return 0
            print("   Root cause not established from collected evidence")
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--namespace", default="production-debug-lab")
    parser.add_argument("server_cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cmd = args.server_cmd[1:] if args.server_cmd[:1] == ["--"] else args.server_cmd
    if not cmd:
        parser.error("server command required after --")
    return asyncio.run(investigate(args.namespace, cmd))


if __name__ == "__main__":
    sys.exit(main())
