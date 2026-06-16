#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# Run a SonarQube analysis of the whole monorepo against the existing server.
#
#   ./scripts/sonar-scan.sh                 # coverage (api + frontend) then scan
#   ./scripts/sonar-scan.sh --no-coverage   # scan only, reuse existing reports
#   ./scripts/sonar-scan.sh --coverage-only # generate reports, don't scan
#
# Credentials come from scripts/.sonar.env (gitignored). The scanner runs in
# Docker (sonarsource/sonar-scanner-cli) so nothing needs to be installed on
# the host. Coverage reports are produced on this same checkout so the absolute
# paths in them line up with what the scanner indexes.
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ── Load credentials ───────────────────────────────────────────────────────
ENV_FILE="scripts/.sonar.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi
: "${SONAR_HOST_URL:?Set SONAR_HOST_URL (in scripts/.sonar.env or the environment)}"
: "${SONAR_TOKEN:?Set SONAR_TOKEN (in scripts/.sonar.env or the environment)}"

DO_COVERAGE=1
DO_SCAN=1
for arg in "$@"; do
  case "$arg" in
    --no-coverage)   DO_COVERAGE=0 ;;
    --coverage-only) DO_SCAN=0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# ── Coverage ────────────────────────────────────────────────────────────────
if [[ "$DO_COVERAGE" == 1 ]]; then
  echo "==> API coverage (pytest-cov, needs Docker for testcontainers)"
  if ( cd services/api && pytest tests/ -q --tb=short \
        --cov=src/cvops_api --cov-report=xml:coverage.xml ); then
    echo "    services/api/coverage.xml written"
  else
    echo "    !! API tests failed — coverage.xml may be incomplete, continuing" >&2
  fi

  echo "==> Frontend coverage (vitest v8 → lcov)"
  if ( cd services/frontend && npm run test:coverage ); then
    echo "    services/frontend/coverage/lcov.info written"
  else
    echo "    !! Frontend tests failed — lcov may be incomplete, continuing" >&2
  fi
fi

# ── Scan ────────────────────────────────────────────────────────────────────
if [[ "$DO_SCAN" == 1 ]]; then
  echo "==> Scanning -> $SONAR_HOST_URL"
  # Persist the analyzer-plugin cache across runs so the ~50MB JS/TS plugin is
  # downloaded once (the link to the cluster is slow/flaky). ws.timeout is bumped
  # so a slow plugin download doesn't trip the default 60s socket timeout.
  CACHE_DIR="${SONAR_CACHE_DIR:-$HOME/.cache/sonar-scanner}"
  mkdir -p "$CACHE_DIR"
  docker run --rm \
    -e SONAR_HOST_URL="$SONAR_HOST_URL" \
    -e SONAR_TOKEN="$SONAR_TOKEN" \
    -e SONAR_USER_HOME="/opt/sonar-scanner/.sonar" \
    -e SONAR_SCANNER_OPTS="-Dsonar.scanner.skipJreProvisioning=true -Dsonar.scanner.socketTimeout=1200" \
    -v "$REPO_ROOT:/usr/src" \
    -v "$CACHE_DIR:/opt/sonar-scanner/.sonar" \
    sonarsource/sonar-scanner-cli:latest
  echo "==> Done. Dashboard: $SONAR_HOST_URL/dashboard?id=cvops"
fi
