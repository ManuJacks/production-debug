"""Draft an incident (INC) record from a verified evidence bundle.

The draft uses ServiceNow incident field names (``short_description``,
``impact``, ``urgency``, ``priority``, ``cmdb_ci``, ``assignment_group``,
``work_notes``) so it can be pasted, or posted by an integration the
operator controls. This module never contacts ServiceNow or the cluster.

Design rules (docs/adr/007-incident-records-from-verified-evidence.md):

- Fail closed: the bundle archive is verified first; an unverified or unsafe
  bundle produces no record.
- Facts only: every work note is an observation quoted from a named evidence
  file. The tool never infers a root cause; hypotheses are left to
  responders and the Problem record.
- Severity is derived from impact and urgency (docs/procedures/SEVERITY_MATRIX.md),
  not chosen.

Usage:
  python3 -m production_debug.incident_record BUNDLE.tar.gz \\
      --impact 3 --urgency 1 --service crashloop-demo \\
      --short-description "crashloop-demo unavailable: container crash-looping" \\
      [--detected-at 2026-11-22T17:41:00Z --detected-by "KubePodCrashLooping"] \\
      [--format markdown|json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from production_debug.bundle_verifier import (
    BundleVerificationError,
    verify_bundle_archive,
)
from production_debug.sanitizer import redact_text

IMPACT = {
    1: "1 - High",
    2: "2 - Medium",
    3: "3 - Low",
}
URGENCY = {
    1: "1 - High",
    2: "2 - Medium",
    3: "3 - Low",
}
# ServiceNow default priority lookup: (impact, urgency) -> priority.
PRIORITY_MATRIX = {
    (1, 1): 1,
    (1, 2): 2,
    (1, 3): 3,
    (2, 1): 2,
    (2, 2): 3,
    (2, 3): 4,
    (3, 1): 3,
    (3, 2): 4,
    (3, 3): 5,
}
PRIORITY = {
    1: "1 - Critical",
    2: "2 - High",
    3: "3 - Moderate",
    4: "4 - Low",
    5: "5 - Planning",
}
LOG_LINES_QUOTED = 3


class IncidentRecordError(Exception):
    """Raised when a record cannot be drafted from the given bundle."""


def priority_for(impact: int, urgency: int) -> int:
    """Priority (severity) for an impact/urgency pair; Sev N means Priority N."""
    try:
        return PRIORITY_MATRIX[(impact, urgency)]
    except KeyError:
        raise IncidentRecordError("impact and urgency must each be 1, 2 or 3") from None


@dataclass
class Note:
    """One work-note entry: an observation quoted from an evidence file."""

    observation: str
    source: str
    time_utc: str = ""
    classification: str = "fact"


@dataclass
class Evidence:
    namespace: str = ""
    collection_status: str = ""
    started_utc: str = ""
    finished_utc: str = ""
    steps_ok: int = 0
    steps_failed: int = 0
    notes: list[Note] = field(default_factory=list)


# --- kubectl output parsing -------------------------------------------------


def parse_table(text: str) -> list[dict[str, str]]:
    """Parse kubectl's aligned table output using the header's column starts.

    Header names may contain single spaces ("LAST SEEN", "NOMINATED NODE");
    columns are separated by two or more spaces.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    header = lines[0]
    starts = [m.start() for m in re.finditer(r"(?:^|(?<=\s\s))\S", header)]
    names = [header[s:e].strip() for s, e in zip(starts, starts[1:] + [None])]
    rows = []
    for line in lines[1:]:
        values = [line[s:e].strip() for s, e in zip(starts, starts[1:] + [None])]
        rows.append(dict(zip(names, values)))
    return rows


def _to_utc(value: str) -> str:
    """kubectl describe timestamp (RFC 2822, local offset) -> ISO 8601 UTC."""
    try:
        parsed = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError):
        return ""
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_describe(text: str) -> list[dict[str, Any]]:
    """Extract per-container state from ``kubectl describe pods`` output."""
    pods: list[dict[str, Any]] = []
    pod: dict[str, Any] | None = None
    container: dict[str, Any] | None = None
    section = ""
    block = ""  # "state" or "last" while inside a State / Last State block
    for raw in text.splitlines():
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if indent == 0:
            section = key
            block = ""
            if key == "Name":
                pod = {"name": value, "containers": []}
                pods.append(pod)
            elif pod is not None and key in ("Node", "Status"):
                pod[key.lower()] = value.split("/")[0]
            continue
        if pod is None or section not in ("Containers", "Init Containers"):
            continue
        if indent == 2 and line.endswith(":") and " " not in line:
            container = {"name": line[:-1], "state": {}, "last": {}}
            pod["containers"].append(container)
            block = ""
            continue
        if container is None:
            continue
        if indent == 4:
            block = ""
            if key == "State":
                block = "state"
                container["state"]["phase"] = value
            elif key == "Last State":
                block = "last"
                container["last"]["phase"] = value
            elif key == "Restart Count":
                container["restarts"] = int(value) if value.isdigit() else value
            elif key == "Ready":
                container["ready"] = value
        elif indent == 6 and block:
            container[block][key] = value
    return pods


def _strip_log_prefix(line: str) -> tuple[str, str]:
    """``[pod/x/c] 2026-...Z message`` -> (timestamp, message)."""
    line = re.sub(r"^\[[^\]]+\]\s*", "", line)
    match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z\s?(.*)$", line)
    if match:
        return match.group(1) + "Z", match.group(2)
    return "", line


# --- evidence extraction ----------------------------------------------------


def _find_evidence_dir(root: Path) -> Path:
    manifests = sorted(root.rglob("manifest.json"))
    for manifest in manifests:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("schema") == "production-debug/k8s-evidence/v1":
            return manifest.parent
    raise IncidentRecordError(
        "bundle contains no k8s evidence manifest (production-debug/k8s-evidence/v1)"
    )


def extract_evidence(evidence_dir: Path) -> Evidence:
    """Turn an evidence directory into quoted, source-attributed facts."""
    manifest = json.loads((evidence_dir / "manifest.json").read_text(encoding="utf-8"))
    ev = Evidence(
        namespace=manifest.get("namespace", ""),
        collection_status=manifest.get("status", ""),
        started_utc=manifest.get("started_utc", ""),
        finished_utc=manifest.get("finished_utc", ""),
        steps_ok=manifest.get("summary", {}).get("ok", 0),
        steps_failed=manifest.get("summary", {}).get("failed", 0),
    )

    def read(rel: str) -> str:
        path = evidence_dir / rel
        return (
            path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        )

    for row in parse_table(read("workloads/pods.txt")):
        ev.notes.append(
            Note(
                f"Pod `{row.get('NAME', '?')}` on `{row.get('NODE', '?')}`: status {row.get('STATUS', '?')}, "
                f"ready {row.get('READY', '?')}, restarts {row.get('RESTARTS', '?')}",
                "workloads/pods.txt",
            )
        )

    for pod in parse_describe(read("pods/describe.txt")):
        for c in pod["containers"]:
            state, last = c["state"], c["last"]
            parts = [
                f"Container `{c['name']}` in pod `{pod['name']}`: {state.get('phase', '?').lower()}"
            ]
            if state.get("Reason"):
                parts[0] += f" ({state['Reason']})"
            if last.get("phase"):
                detail = last.get("Reason", last["phase"])
                if last.get("Exit Code"):
                    detail += f", exit code {last['Exit Code']}"
                parts.append(f"last terminated: {detail}")
            elif state.get("Exit Code"):
                parts.append(f"exit code {state['Exit Code']}")
            if "restarts" in c:
                parts.append(f"restart count {c['restarts']}")
            when = _to_utc(
                last.get("Finished", "")
                or state.get("Finished", "")
                or state.get("Started", "")
            )
            ev.notes.append(Note("; ".join(parts), "pods/describe.txt", when))

    warnings = [
        r
        for r in parse_table(read("workloads/events.txt"))
        if r.get("TYPE") == "Warning"
    ]
    for row in warnings[-5:]:
        ev.notes.append(
            Note(
                f"Warning event {row.get('REASON', '?')} on `{row.get('OBJECT', '?')}` "
                f"(last seen {row.get('LAST SEEN', '?')} before collection): {redact_text(row.get('MESSAGE', ''))}",
                "workloads/events.txt",
            )
        )

    for log in (
        sorted((evidence_dir / "logs").glob("*.log"))
        if (evidence_dir / "logs").is_dir()
        else []
    ):
        lines = [
            line
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        for line in lines[-LOG_LINES_QUOTED:]:
            when, message = _strip_log_prefix(line)
            instance = (
                "previous instance"
                if log.name.endswith(".previous.log")
                else "current instance"
            )
            ev.notes.append(
                Note(
                    f"Log ({instance}): `{redact_text(message)[:200]}`",
                    f"logs/{log.name}",
                    when,
                )
            )
    return ev


# --- record rendering -------------------------------------------------------


@dataclass
class RecordInput:
    short_description: str
    impact: int
    urgency: int
    service: str
    assignment_group: str = "Platform Engineering"
    opened_by: str = ""
    detected_at: str = ""
    detected_by: str = ""
    impact_statement: str = ""


def build_record(
    inputs: RecordInput, ev: Evidence, archive_name: str, fingerprint: str
) -> dict[str, Any]:
    priority = priority_for(inputs.impact, inputs.urgency)
    notes = list(ev.notes)
    if inputs.detected_at or inputs.detected_by:
        notes.insert(
            0,
            Note(
                f"Detected by {inputs.detected_by or 'alert'}",
                "operator input (alert notification)",
                inputs.detected_at,
            ),
        )
    notes.append(
        Note(
            f"Evidence collected read-only from namespace `{ev.namespace}`: {ev.collection_status} "
            f"({ev.steps_ok} steps ok, {ev.steps_failed} failed)",
            "manifest.json",
            ev.finished_utc,
        )
    )
    notes.sort(key=lambda n: (n.time_utc == "", n.time_utc))
    return {
        "number": f"DRAFT-{fingerprint[:8]}",
        "state": "New",
        "short_description": inputs.short_description,
        "description": inputs.impact_statement,
        "cmdb_ci": inputs.service,
        "category": "Software",
        "subcategory": "Kubernetes workload",
        "assignment_group": inputs.assignment_group,
        "opened_by": inputs.opened_by,
        "impact": IMPACT[inputs.impact],
        "urgency": URGENCY[inputs.urgency],
        "priority": PRIORITY[priority],
        "severity_rationale": (
            f"Impact {IMPACT[inputs.impact]} x urgency {URGENCY[inputs.urgency]} -> "
            f"priority {PRIORITY[priority]} (Sev {priority}), per docs/procedures/SEVERITY_MATRIX.md"
        ),
        "classification_notice": (
            "Priority 5 - Planning is not an incident (SEVERITY_MATRIX.md): raise a Problem or story instead."
            if priority == 5
            else ""
        ),
        "work_notes": [note.__dict__ for note in notes],
        "hypotheses": [],
        "u_evidence_bundle": archive_name,
        "u_evidence_fingerprint_sha256": fingerprint,
        "u_draft_notice": "Draft generated from verified evidence; not submitted to any system.",
    }


def render_markdown(record: dict[str, Any]) -> str:
    def esc(value: str) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    out = [
        f"# {record['number']}: {record['short_description']}",
        "",
        f"> {record['u_draft_notice']} The number is assigned on submission.",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for label, key in (
        ("State", "state"),
        ("Configuration item", "cmdb_ci"),
        ("Category", "category"),
        ("Subcategory", "subcategory"),
        ("Assignment group", "assignment_group"),
        ("Opened by", "opened_by"),
        ("Impact", "impact"),
        ("Urgency", "urgency"),
        ("Priority", "priority"),
    ):
        out.append(f"| {label} | {esc(record[key]) or '_to complete_'} |")
    out += [
        "",
        f"**Severity rationale.** {record['severity_rationale']}.",
        "",
    ]
    if record["classification_notice"]:
        out += [f"> **{record['classification_notice']}**", ""]
    out += [
        "## Description (business impact)",
        "",
        record["description"]
        or "_To complete: who is affected, how, and the evidence for it._",
        "",
        "## Work notes",
        "",
        "Every entry is quoted from the named evidence file in the verified bundle.",
        "",
        "| Time (UTC) | Observation | Classification | Source |",
        "|---|---|---|---|",
    ]
    for note in record["work_notes"]:
        out.append(
            f"| {note['time_utc'] or '—'} | {esc(note['observation'])} | {note['classification']} | `{note['source']}` |"
        )
    out += [
        "",
        "## Hypotheses",
        "",
        "None recorded by the tool: it reports facts and does not infer a root cause.",
        "Responders add hypotheses here, each with the evidence that would confirm or refute it.",
        "",
        "## Evidence",
        "",
        f"- Bundle: `{record['u_evidence_bundle']}`",
        f"- Fingerprint (SHA-256): `{record['u_evidence_fingerprint_sha256']}`",
        "",
        "## Resolution (to complete on resolve)",
        "",
        "- Resolution code:",
        "- Resolution notes:",
        "- Problem record (PRB):",
        "- Change request(s) (CHG):",
        "",
    ]
    return "\n".join(out)


def draft_from_archive(archive: Path, inputs: RecordInput) -> dict[str, Any]:
    """Verify the archive, extract its evidence and build the record."""
    with tempfile.TemporaryDirectory(prefix="production-debug-inc-") as tmp:
        try:
            report = verify_bundle_archive(archive, Path(tmp) / "x")
        except BundleVerificationError as exc:
            raise IncidentRecordError(
                f"bundle failed verification; no record drafted: {exc}"
            ) from exc
        evidence = extract_evidence(_find_evidence_dir(Path(tmp) / "x"))
        return build_record(
            inputs, evidence, archive.name, report["bundle_fingerprint_sha256"]
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Draft an INC record from a verified evidence bundle."
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--impact", type=int, required=True, choices=(1, 2, 3))
    parser.add_argument("--urgency", type=int, required=True, choices=(1, 2, 3))
    parser.add_argument("--service", required=True, help="configuration item (cmdb_ci)")
    parser.add_argument("--short-description", required=True)
    parser.add_argument("--impact-statement", default="")
    parser.add_argument("--assignment-group", default="Platform Engineering")
    parser.add_argument("--opened-by", default="")
    parser.add_argument("--detected-at", default="", help="alert time, ISO 8601 UTC")
    parser.add_argument("--detected-by", default="", help="alert name or reporter")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)

    inputs = RecordInput(
        short_description=args.short_description,
        impact=args.impact,
        urgency=args.urgency,
        service=args.service,
        assignment_group=args.assignment_group,
        opened_by=args.opened_by,
        detected_at=args.detected_at,
        detected_by=args.detected_by,
        impact_statement=args.impact_statement,
    )
    try:
        record = draft_from_archive(args.archive, inputs)
    except IncidentRecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(record, indent=2))
    else:
        print(render_markdown(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
