"""
Automated validation and verification of incident triage bundles and diagnostics.
Generates reproducible verification digests and audits bundle contents for leak prevention.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from production_debug.sanitizer import SENSITIVE_FILENAME_PATTERNS, SENSITIVE_PATTERNS


class BundleVerificationError(Exception):
    """Raised when an incident bundle fails integrity or safety checks."""


MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


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

    if extract_tmp_dir is None:
        temp_context = tempfile.TemporaryDirectory(prefix="production-debug-verify-")
        target_dir = Path(temp_context.name)
    else:
        target_dir = Path(extract_tmp_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        if any(target_dir.iterdir()):
            raise BundleVerificationError("Extraction directory must be empty")
        temp_context = None

    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            if len(members) > MAX_ARCHIVE_FILES:
                raise BundleVerificationError("Archive contains too many entries")
            total_size = 0
            names: set[str] = set()
            for member in members:
                path = Path(member.name)
                if (
                    not member.name
                    or path.is_absolute()
                    or ".." in path.parts
                    or member.name in names
                    or member.issym()
                    or member.islnk()
                    or not (member.isfile() or member.isdir())
                ):
                    raise BundleVerificationError(
                        f"Unsafe archive entry: {member.name}"
                    )
                names.add(member.name)
                if member.isfile():
                    total_size += member.size
                    if total_size > MAX_ARCHIVE_BYTES:
                        raise BundleVerificationError(
                            "Archive uncompressed payload exceeds 512 MiB"
                        )
            # Entries were screened above; the "data" filter is defense in depth.
            tar.extractall(path=target_dir, filter="data")

        subdirs = [p for p in target_dir.iterdir() if p.is_dir()]
        bundle_dir = subdirs[0] if len(subdirs) == 1 else target_dir
        return verify_bundle_safety(bundle_dir)
    finally:
        if temp_context is not None:
            temp_context.cleanup()


def main(argv: list[str] | None = None) -> int:
    """Verify a bundle directory or .tar.gz archive; print a JSON report.

    Exit status: 0 verified, 1 verification failed, 2 usage error.
    """
    import sys

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(
            "usage: python3 -m production_debug.bundle_verifier <bundle_dir|bundle.tar.gz>",
            file=sys.stderr,
        )
        return 2

    target = Path(args[0])
    try:
        if target.is_dir():
            report = verify_bundle_safety(target)
        else:
            report = verify_bundle_archive(target)
    except BundleVerificationError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
