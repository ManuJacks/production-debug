"""
Automated validation and verification of incident triage bundles and diagnostics.
Generates reproducible verification digests and audits bundle contents for leak prevention.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

from production_debug.sanitizer import SENSITIVE_FILENAME_PATTERNS, SENSITIVE_PATTERNS


class BundleVerificationError(Exception):
    """Raised when an incident bundle fails integrity or safety checks."""


def compute_file_sha256(path: str | Path) -> str:
    """Calculate the hex SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_bundle_safety(bundle_dir: str | Path) -> dict[str, Any]:
    """
    Audit an uncompressed incident bundle directory before archival.
    Ensures:
    1. No sensitive files (.pem, .key, .env, kubeconfig, etc.) exist in the bundle.
    2. No plaintext credentials or JWT tokens appear in payload files.
    3. metadata.json exists and is valid JSON.

    Returns a verification report dictionary with SHA-256 digests and audit metrics.
    """
    root = Path(bundle_dir)
    if not root.exists() or not root.is_dir():
        raise BundleVerificationError(f"Bundle directory does not exist: {bundle_dir}")

    metadata_file = root / "metadata.json"
    if not metadata_file.exists():
        raise BundleVerificationError("metadata.json missing from incident bundle root")

    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleVerificationError(
            f"metadata.json is malformed JSON: {exc}"
        ) from exc

    violations: list[str] = []
    audited_files: list[dict[str, str]] = []

    for path in root.rglob("*"):
        if path.is_file():
            rel_path = path.relative_to(root).as_posix()
            # 1. Filename check
            for pattern in SENSITIVE_FILENAME_PATTERNS:
                if pattern.match(path.name):
                    violations.append(f"Forbidden credential file detected: {rel_path}")

            # 2. Text inspection for secret patterns
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                for label, pattern in SENSITIVE_PATTERNS:
                    if pattern.search(content):
                        violations.append(
                            f"Unredacted sensitive pattern '{label}' found in file: {rel_path}"
                        )
            except (OSError, UnicodeError):
                pass

            audited_files.append(
                {
                    "path": rel_path,
                    "sha256": compute_file_sha256(path),
                    "size_bytes": str(path.stat().st_size),
                }
            )

    if violations:
        raise BundleVerificationError(
            f"Safety verification failed with {len(violations)} security violation(s): "
            + "; ".join(violations)
        )

    # Calculate deterministic bundle fingerprint
    hasher = hashlib.sha256()
    for entry in sorted(audited_files, key=lambda x: x["path"]):
        hasher.update(f"{entry['path']}:{entry['sha256']}\n".encode())
    bundle_fingerprint = hasher.hexdigest()

    return {
        "status": "verified",
        "bundle_name": metadata.get("bundle_name", root.name),
        "bundle_fingerprint_sha256": bundle_fingerprint,
        "files_audited": len(audited_files),
        "manifest": audited_files,
        "metadata": metadata,
    }


def verify_bundle_archive(
    archive_path: str | Path, extract_tmp_dir: str | Path | None = None
) -> dict[str, Any]:
    """
    Extract a tar.gz bundle archive safely and verify its safety and fingerprints.
    """
    archive = Path(archive_path)
    if not archive.exists() or not archive.is_file():
        raise BundleVerificationError(f"Bundle archive file not found: {archive_path}")

    target_dir = Path(extract_tmp_dir or f"/tmp/verify-{archive.stem}")
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive, "r:gz") as tar:
        # Defense against path traversal in tar extraction
        for member in tar.getmembers():
            if member.name.startswith("/") or ".." in member.name:
                raise BundleVerificationError(
                    f"Path traversal detected in archive entry: {member.name}"
                )
        tar.extractall(path=target_dir)

    # Locate extracted root
    subdirs = [p for p in target_dir.iterdir() if p.is_dir()]
    bundle_dir = subdirs[0] if subdirs else target_dir

    return verify_bundle_safety(bundle_dir)
