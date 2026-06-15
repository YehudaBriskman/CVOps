#!/usr/bin/env bash
# ── scripts/hooks/jj/validate.sh ───────────────────────────────────────────
# jj provider — convention validator. jj never runs git hooks, so this is the
# jj-side equivalent of .githooks/{commit-msg,pre-push}: it checks the commit
# messages and bookmark names of the change you are about to push, using the
# SAME shared rules as the git hooks (scripts/hooks/lib/rules.sh).
#
# Invoked via the `jj check` alias (no args) or by pre-push.sh, which may pass
# extra bookmark names (explicit `-b NAME` push targets) as arguments.
#
# Scope:
#   • messages  — every described commit in trunk()..@ (the work being pushed;
#                 the empty, description-less working copy is skipped)
#   • bookmarks — local bookmarks on @ or @- (your current change) plus any
#                 names passed as arguments
set -euo pipefail
cd "${JJ_WORKSPACE_ROOT:?must be run via jj — try: jj check}"

# shellcheck source=../lib/rules.sh
. scripts/hooks/lib/rules.sh

status=0

# 1. Commit messages of the described commits in trunk()..@.
while IFS= read -r cid; do
  [ -n "$cid" ] || continue
  if ! jj log -r "$cid" --no-graph -T 'description' | rules_validate_message; then
    printf '  (commit %s)\n\n' "$cid" >&2
    status=1
  fi
done < <(jj log -r 'trunk()..@ & ~description("")' --no-graph -T 'change_id.short() ++ "\n"')

# 2. Bookmark names — those on the current change plus any passed explicitly.
bookmarks_here=$(jj log -r '@ | @-' --no-graph \
  -T 'separate("\n", local_bookmarks.map(|b| b.name())) ++ "\n"')

for bm in $(printf '%s\n%s\n' "$bookmarks_here" "$*" | tr ' ' '\n' | sort -u); do
  [ -n "$bm" ] || continue
  rules_validate_branch "$bm" || status=1
done

if [ "$status" -eq 0 ]; then
  printf '  \033[32m[ok] jj: commit messages + bookmark names conform.\033[0m\n'
fi
exit "$status"
