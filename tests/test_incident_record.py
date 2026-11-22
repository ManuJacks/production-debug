"""Incident record drafting (production_debug.incident_record).

Backs ADR 007: records are drafted only from verified bundles, contain
quoted facts with their source, never an inferred root cause, and severity
is derived from impact x urgency exactly as SEVERITY_MATRIX.md states.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

import pytest

from production_debug import incident_record as ir

ROOT = Path(__file__).resolve().parent.parent
POD = "crashloop-demo-6d5f8b7c9-x2k4p"

# Formats as produced by kubectl 1.3x (see scripts/k8s_evidence.sh).
PODS_TXT = f"""\
NAME                            READY   STATUS             RESTARTS      AGE   IP             NODE            NOMINATED NODE   READINESS GATES
{POD}   0/1     CrashLoopBackOff   4 (25s ago)   2m    10.244.3.140   tf-ha-worker1   <none>           <none>
"""

DESCRIBE_TXT = f"""\
Name:             {POD}
Namespace:        production-debug-lab
Priority:         0
Service Account:  default
Node:             tf-ha-worker1/10.97.0.2
Start Time:       Sun, 22 Nov 2026 12:40:02 -0500
Labels:           app=crashloop-demo
Status:           Running
Containers:
  app:
    Container ID:  containerd://0123
    Image:         busybox:1.36
    Command:
      /bin/sh
      -c
      echo missing CONFIG_URL; exit 1
    State:          Waiting
      Reason:       CrashLoopBackOff
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Sun, 22 Nov 2026 12:41:30 -0500
      Finished:     Sun, 22 Nov 2026 12:41:30 -0500
    Ready:          False
    Restart Count:  4
    Environment:    <none>
Conditions:
  Type              Status
  Ready             False
Events:
  Type     Reason   Age   From     Message
  ----     ------   ----  ----     -------
  Warning  BackOff  10s   kubelet  Back-off restarting failed container app
"""

EVENTS_TXT = f"""\
LAST SEEN   TYPE      REASON      OBJECT                              MESSAGE
2m          Normal    Scheduled   pod/{POD}   Successfully assigned production-debug-lab/{POD} to tf-ha-worker1
10s         Warning   BackOff     pod/{POD}   Back-off restarting failed container app in pod {POD}
"""

PREVIOUS_LOG = f"[pod/{POD}/app] 2026-11-22T17:41:30.120394811Z missing CONFIG_URL\n"


def write_evidence(root: Path, log_line: str = PREVIOUS_LOG) -> Path:
    ev = root / "evidence"
    for sub in ("cluster", "workloads", "pods", "logs"):
        (ev / sub).mkdir(parents=True)
    (ev / "workloads" / "pods.txt").write_text(PODS_TXT)
    (ev / "pods" / "describe.txt").write_text(DESCRIBE_TXT)
    (ev / "workloads" / "events.txt").write_text(EVENTS_TXT)
    (ev / "logs" / f"{POD}.previous.log").write_text(log_line)
    manifest = {
        "schema": "production-debug/k8s-evidence/v1",
        "namespace": "production-debug-lab",
        "context": "in-cluster",
        "selector": "app=crashloop-demo",
        "started_utc": "2026-11-22T17:42:01Z",
        "finished_utc": "2026-11-22T17:42:04Z",
        "status": "complete",
        "summary": {"ok": 9, "empty": 0, "unavailable": 0, "failed": 0},
        "steps": [],
    }
    (ev / "manifest.json").write_text(json.dumps(manifest))
    return ev


def make_bundle(tmp_path: Path) -> Path:
    evidence = write_evidence(tmp_path)
    out = tmp_path / "out"
    completed = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts" / "incident_bundle.sh"),
            str(out),
            str(evidence),
            "--name",
            "crashloop-demo",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    (archive,) = out.glob("crashloop-demo-*.tar.gz")
    return archive


INPUTS = ir.RecordInput(
    short_description="crashloop-demo unavailable: container crash-looping",
    impact=3,
    urgency=1,
    service="crashloop-demo",
    detected_at="2026-11-22T17:41:00Z",
    detected_by="KubePodCrashLooping (Prometheus, delivered via Alertmanager)",
)


class TestSeverity:
    def test_matrix_matches_the_documented_table(self):
        """SEVERITY_MATRIX.md and the code must not drift apart."""
        doc = (ROOT / "docs" / "procedures" / "SEVERITY_MATRIX.md").read_text()
        table = doc.split("<!-- priority-matrix")[1].split("\n\n")[0]
        rows = re.findall(r"^\| \*\*(\d) - \w+\*\* \| (.+) \|$", table, re.MULTILINE)
        assert len(rows) == 3
        for impact, cells in rows:
            for urgency, cell in enumerate(cells.split(" | "), start=1):
                priority = int(cell.split(" - ")[0])
                assert ir.priority_for(int(impact), urgency) == priority, (
                    impact,
                    urgency,
                )
                assert ir.PRIORITY[priority] == cell

    def test_demo_scenario_is_sev_3_not_sev_2(self):
        # One internal service fully down, no customer impact.
        assert ir.priority_for(impact=3, urgency=1) == 3

    def test_planning_priority_is_flagged_as_not_an_incident(self, tmp_path):
        inputs = ir.RecordInput("leftover pod", impact=3, urgency=3, service="s")
        record = ir.draft_from_archive(make_bundle(tmp_path), inputs)
        assert record["priority"] == "5 - Planning"
        assert "is not an incident" in ir.render_markdown(record)

    @pytest.mark.parametrize("impact,urgency", [(0, 1), (4, 1), (1, 0)])
    def test_out_of_range_values_are_rejected(self, impact, urgency):
        with pytest.raises(ir.IncidentRecordError):
            ir.priority_for(impact, urgency)


class TestParsing:
    def test_table_keeps_multiword_cells_and_headers(self):
        (pod,) = ir.parse_table(PODS_TXT)
        assert pod["RESTARTS"] == "4 (25s ago)"
        assert pod["NOMINATED NODE"] == "<none>"
        events = ir.parse_table(EVENTS_TXT)
        assert events[1]["LAST SEEN"] == "10s"
        assert events[1]["REASON"] == "BackOff"

    def test_describe_extracts_current_and_last_state(self):
        (pod,) = ir.parse_describe(DESCRIBE_TXT)
        (container,) = pod["containers"]
        assert container["state"] == {"phase": "Waiting", "Reason": "CrashLoopBackOff"}
        assert container["last"]["Reason"] == "Error"
        assert container["last"]["Exit Code"] == "1"
        assert container["restarts"] == 4
        assert pod["node"] == "tf-ha-worker1"


class TestDraft:
    def test_record_from_verified_bundle(self, tmp_path):
        record = ir.draft_from_archive(make_bundle(tmp_path), INPUTS)
        assert record["priority"] == "3 - Moderate"
        assert "(Sev 3)" in record["severity_rationale"]
        assert record["number"].startswith("DRAFT-")
        assert record["u_evidence_fingerprint_sha256"].startswith(record["number"][6:])

        notes = record["work_notes"]
        assert all(n["classification"] == "fact" and n["source"] for n in notes)
        observations = " ".join(n["observation"] for n in notes)
        assert "CrashLoopBackOff" in observations
        assert "last terminated: Error, exit code 1" in observations
        assert "missing CONFIG_URL" in observations
        # Chronological: detection, last crash, log line, evidence collection.
        timed = [n["time_utc"] for n in notes if n["time_utc"]]
        assert timed == sorted(timed)
        assert timed[0] == "2026-11-22T17:41:00Z"
        assert "2026-11-22T17:41:30Z" in timed

    def test_tool_never_infers_a_root_cause(self, tmp_path):
        record = ir.draft_from_archive(make_bundle(tmp_path), INPUTS)
        assert record["hypotheses"] == []
        markdown = ir.render_markdown(record)
        assert "does not infer a root cause" in markdown
        assert "root cause is" not in markdown.lower()

    def test_markdown_and_json_cli(self, tmp_path, capsys):
        archive = make_bundle(tmp_path)
        args = [
            str(archive),
            "--impact",
            "3",
            "--urgency",
            "1",
            "--service",
            "crashloop-demo",
            "--short-description",
            "crashloop-demo unavailable",
        ]
        assert ir.main(args) == 0
        assert "| Priority | 3 - Moderate |" in capsys.readouterr().out
        assert ir.main(args + ["--format", "json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        for field in (
            "short_description",
            "impact",
            "urgency",
            "priority",
            "cmdb_ci",
            "work_notes",
        ):
            assert field in payload

    def test_unsafe_bundle_produces_no_record(self, tmp_path, capsys):
        archive = tmp_path / "evil.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("../escape.txt")
            data = b"x"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        code = ir.main(
            [
                str(archive),
                "--impact",
                "3",
                "--urgency",
                "1",
                "--service",
                "s",
                "--short-description",
                "d",
            ]
        )
        captured = capsys.readouterr()
        assert code == 1
        assert captured.out == ""
        assert "no record drafted" in captured.err

    def test_quoted_log_lines_are_redacted(self, tmp_path):
        line = f"[pod/{POD}/app] 2026-11-22T17:41:30Z connecting with token=abcd1234efgh5678ijkl\n"
        evidence = ir.extract_evidence(write_evidence(tmp_path, log_line=line))
        quoted = " ".join(n.observation for n in evidence.notes)
        assert "abcd1234efgh5678ijkl" not in quoted
