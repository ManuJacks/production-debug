# Contributing

Changes to incident tooling must be safe to operate during a high-severity event.

## Start here

The easiest first contributions are documentation fixes, test improvements, new
scenario fixtures, and reproducible bug reports. See the [contributor roadmap](docs/CONTRIBUTOR_ROADMAP.md)
for scoped ideas that do not require production access.

For a local checkout:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest ruff
.venv/bin/pytest -q
.venv/bin/ruff check .
```

The Kubernetes demo additionally requires Docker, `kubectl`, and a disposable
cluster. Never point the demo or a new diagnostic integration at production
without explicit authorization.

## Pull requests

1. Open an issue first for behavior changes, new tools, or security-sensitive work.
2. Keep pull requests focused and describe the operator impact.
3. Include tests and documentation for changed behavior.
4. Explain any new subprocess, network access, filesystem write, privilege, or RBAC requirement.
5. Wait for CI and respond to review comments before requesting merge.

Maintainers may ask for a smaller change or a design note when a proposal
expands the tool surface or privilege boundary.

Before opening a pull request:

- Run `pytest tests/ -v` and `bash -n scripts/*.sh`.
- Run ShellCheck when available.
- Update the relevant runbook, CLI reference, and `CHANGELOG.md`.
- Add or update tests for changed command output, exit codes, and redaction behavior.
- Document security, operator, and migration impact.

Reviews should evaluate failure paths, least privilege, evidence handling, rollback, and clarity for a responder who did not author the change. We use blameless language in code, issues, reviews, game-days, and post-incident reports.
