#!/usr/bin/env bash
# ── scripts/hooks/jj/pre-push.sh ───────────────────────────────────────────
# jj provider — pre-push gate. Wired as the `jj push` alias by jj-setup.sh.
# jj's own `jj git push` bypasses the git pre-push hook entirely, so this
# wrapper restores enforcement: validate first, then delegate to `jj git push`
# with every argument passed through unchanged.
#
#   jj push                         → validate + push (current change)
#   jj push -b Feat/my-bookmark     → validate that bookmark too, then push
#   jj push --dry-run               → validation still runs; push is a no-op
set -euo pipefail
cd "${JJ_WORKSPACE_ROOT:?must be run via jj — try: jj push}"

# Pull any explicit bookmark targets out of the push args so we can validate
# their names before they hit the remote (-b/--bookmark/--named NAME or =NAME).
explicit=""
prev=""
for arg in "$@"; do
  case "$prev" in
    -b|--bookmark|--named) explicit="$explicit $arg" ;;
  esac
  case "$arg" in
    -b=*|--bookmark=*|--named=*) explicit="$explicit ${arg#*=}" ;;
  esac
  prev="$arg"
done

# Run the shared validator (messages + bookmark names), passing explicit targets.
# shellcheck disable=SC2086
if ! bash scripts/hooks/jj/validate.sh $explicit; then
  printf '\n  \033[31mjj push blocked — fix the issues above.\033[0m\n\n' >&2
  exit 1
fi

exec jj git push "$@"
