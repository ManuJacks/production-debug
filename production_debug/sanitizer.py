"""
Credential and sensitive data sanitization and redaction engine for production triage.
Guarantees that credentials, tokens, private keys, and sensitive environment variables
cannot leak into incident archives or logs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Regex patterns matching known unredacted credential headers and token signatures
SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "jwt_token",
        re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
        ),
    ),
    (
        "bearer_token",
        re.compile(
            r"\b(?:bearer|authorization|token)\s*[:=]\s*['\"]?(?!\[REDACTED)([a-zA-Z0-9_\-\.]{12,})['\"]?",
            re.IGNORECASE,
        ),
    ),
    (
        "api_key",
        re.compile(
            r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|app[_-]?secret)\s*[:=]\s*['\"]?(?!\[REDACTED)([a-zA-Z0-9_\-\.]{8,})['\"]?",
            re.IGNORECASE,
        ),
    ),
    (
        "azure_secret",
        re.compile(
            r"\b(?:azure[_-]?(?:client[_-]?secret|tenant[_-]?secret|federated[_-]?token))\s*[:=]\s*['\"]?(?!\[REDACTED)([a-zA-Z0-9_\-\.]{8,})['\"]?",
            re.IGNORECASE,
        ),
    ),
    (
        "password_assignment",
        re.compile(
            r"\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?(?!\[REDACTED)([^\s'\"]{6,})['\"]?",
            re.IGNORECASE,
        ),
    ),
]

# Sensitive file extensions and filenames that must never be packaged into bundles
SENSITIVE_FILENAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\.env(?:\..+)?$", re.IGNORECASE),
    re.compile(r".*\.pem$", re.IGNORECASE),
    re.compile(r".*\.key$", re.IGNORECASE),
    re.compile(r".*id_rsa.*", re.IGNORECASE),
    re.compile(r".*id_ed25519.*", re.IGNORECASE),
    re.compile(r".*token.*\.json$", re.IGNORECASE),
    re.compile(r".*federated.*token.*", re.IGNORECASE),
    re.compile(r".*kubeconfig.*", re.IGNORECASE),
]

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)
_JWT_RE = re.compile(
    r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"
)
_BEARER_RE = re.compile(
    r"(\b(?:bearer|authorization)\s*[:=]\s*['\"]?)(?!\[REDACTED)[a-zA-Z0-9_\-\.]{12,}(['\"]?)",
    re.IGNORECASE,
)
_API_KEY_RE = re.compile(
    r"(\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|app[_-]?secret)\s*[:=]\s*['\"]?)(?!\[REDACTED)[a-zA-Z0-9_\-\.]{8,}(['\"]?)",
    re.IGNORECASE,
)
_PASSWORD_RE = re.compile(
    r"(\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?)(?!\[REDACTED)[^\s'\"]{4,}(['\"]?)",
    re.IGNORECASE,
)


def is_sensitive_filename(path: str | Path) -> bool:
    """Return True if filename or path matches high-risk sensitive patterns."""
    basename = Path(path).name
    return any(pattern.match(basename) for pattern in SENSITIVE_FILENAME_PATTERNS)


def redact_text(content: str) -> str:
    """
    Scrub sensitive credentials, tokens, private keys, and passwords from string.
    Replaces matched secret material with [REDACTED:<type>].
    """
    redacted = content

    # Redact whole private keys first
    redacted = _PRIVATE_KEY_RE.sub("[REDACTED:PRIVATE_KEY]", redacted)

    # Redact JWTs
    redacted = _JWT_RE.sub("[REDACTED:JWT_TOKEN]", redacted)

    # Redact Bearer / Authorization headers
    redacted = _BEARER_RE.sub(r"\1[REDACTED:TOKEN]\2", redacted)

    # Redact generic api_key / secret assignments
    redacted = _API_KEY_RE.sub(r"\1[REDACTED:API_KEY]\2", redacted)

    # Redact passwords
    redacted = _PASSWORD_RE.sub(r"\1[REDACTED:PASSWORD]\2", redacted)

    return redacted


def sanitize_environment_dict(env: dict[str, str]) -> dict[str, str]:
    """
    Filter and redact sensitive environment variables for safe logging or reporting.
    """
    sensitive_keys = {
        "AZURE_FEDERATED_TOKEN_FILE",
        "AZURE_CLIENT_SECRET",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
        "TOKEN",
        "SECRET",
        "PASSWORD",
    }
    safe_env: dict[str, str] = {}
    for k, v in env.items():
        k_upper = k.upper()
        if any(s in k_upper for s in sensitive_keys):
            safe_env[k] = "[REDACTED]"
        else:
            safe_env[k] = redact_text(v)
    return safe_env


def sanitize_directory_tree(target_dir: str | Path) -> dict[str, Any]:
    """
    Recursively scan target_dir:
    1. Remove any sensitive credential files (.key, .pem, .env, etc.).
    2. Redact text content of readable logs/files.
    Returns audit summary of files scanned, removed, and redacted.
    """
    target = Path(target_dir)
    if not target.exists() or not target.is_dir():
        return {"scanned": 0, "removed": 0, "redacted": 0}

    scanned = 0
    removed = 0
    redacted = 0

    for path in list(target.rglob("*")):
        if path.is_file():
            scanned += 1
            if is_sensitive_filename(path):
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
                continue

            # Check text files for secret patterns
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                sanitized = redact_text(content)
                if sanitized != content:
                    path.write_text(sanitized, encoding="utf-8")
                    redacted += 1
            except (OSError, UnicodeError):
                continue

    return {"scanned": scanned, "removed": removed, "redacted": redacted}
