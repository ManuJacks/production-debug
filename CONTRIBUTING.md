# Contributing

Changes to incident tooling must be safe to operate during a high-severity event.

Before opening a pull request:

- Run `pytest tests/ -v` and `bash -n scripts/*.sh`.
- Run ShellCheck when available.
- Update the relevant runbook, CLI reference, and `CHANGELOG.md`.
- Add or update tests for changed command output, exit codes, and redaction behavior.
- Document security, operator, and migration impact.

Reviews should evaluate failure paths, least privilege, evidence handling, rollback, and clarity for a responder who did not author the change. We use blameless language in code, issues, reviews, game-days, and post-incident reports.
