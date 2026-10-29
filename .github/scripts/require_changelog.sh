#!/usr/bin/env bash

set -euo pipefail

if [[ "${GITHUB_EVENT_NAME:-}" != "pull_request" ]]; then
  echo "Not a pull_request event; skipping changelog check."
  exit 0
fi

if [[ -z "${GITHUB_BASE_REF:-}" ]]; then
  echo "GITHUB_BASE_REF is not set." >&2
  exit 2
fi

BASE_REF="${GITHUB_BASE_REF}"

git fetch --no-tags --depth=200 origin "${BASE_REF}"

CHANGED_FILES="$(git diff --name-only "origin/${BASE_REF}...HEAD")"

if [[ -z "$CHANGED_FILES" ]]; then
  echo "No changed files detected; skipping changelog check."
  exit 0
fi

if echo "$CHANGED_FILES" | grep -qx 'CHANGELOG.md'; then
  echo "CHANGELOG.md updated."
  exit 0
fi

NON_FUNCTIONAL_ONLY=1
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  if [[ "$file" =~ ^(README\.md|CONTRIBUTING\.md|LICENSE|\.github/|docs/|tests/|\.gitignore|CHANGELOG\.md)$ ]]; then
    continue
  fi
  NON_FUNCTIONAL_ONLY=0
  break
done <<< "$CHANGED_FILES"

if [[ $NON_FUNCTIONAL_ONLY -eq 1 ]]; then
  echo "Detected docs/test/metadata-only changes; changelog update not required."
  exit 0
fi

echo "CHANGELOG.md must be updated for behavior-impacting PRs." >&2
echo "If this PR is docs/test/metadata-only, ensure only those files are changed." >&2
exit 1
