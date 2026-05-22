#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/3] Checking ignored sensitive files are not tracked..."
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "ERROR: .env is tracked by git. Remove it before publishing."
  exit 1
fi

echo "[2/3] Scanning repository files for possible secrets..."
MATCHES="$(git ls-files -co --exclude-standard | grep -Ev '^(\.env|\.venv/|__pycache__/)' | xargs -r grep -nE '(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|ghp_[0-9A-Za-z]{36}|glpat-[0-9A-Za-z_-]{20,}|-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----|password\s*[:=]\s*["'\''`][^"'\''`]{6,}["'\''`]|token\s*[:=]\s*["'\''`][^"'\''`]{10,}["'\''`]|secret\s*[:=]\s*["'\''`][^"'\''`]{10,}["'\''`])' || true)"

if [[ -n "$MATCHES" ]]; then
  echo "ERROR: potential secrets found:"
  echo "$MATCHES"
  exit 1
fi

echo "[3/4] Verifying required public files..."
MISSING=0
for file in \
  README.md \
  LICENSE \
  SECURITY.md \
  CONTRIBUTING.md \
  CODE_OF_CONDUCT.md \
  INSTALLATION.md \
  USAGE.md \
  PUBLIC_RELEASE.md \
  .env.example \
  .github/dependabot.yml \
  .github/pull_request_template.md \
  .github/ISSUE_TEMPLATE/bug_report.md \
  .github/ISSUE_TEMPLATE/feature_request.md \
  .github/ISSUE_TEMPLATE/config.yml
do
  if [[ ! -f "$file" ]]; then
    echo "ERROR: missing $file"
    MISSING=1
  fi
done

if [[ "$MISSING" -ne 0 ]]; then
  exit 1
fi

echo "[4/4] Checking markdown links in README docs map..."
for linked in INSTALLATION.md USAGE.md PUBLIC_RELEASE.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md; do
  if ! grep -q "$linked" README.md; then
    echo "ERROR: README.md does not reference $linked"
    exit 1
  fi
done

echo "Public release checks passed."
