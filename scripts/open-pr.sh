#!/bin/sh
# ── scripts/open-pr.sh ─────────────────────────────────────────────────────
# Convention-safe PR opener.
#
# The pre-push hook (scripts/hooks/lib/rules.sh) rejects pushes from protected
# branches (main/develop/master) and from any branch whose name doesn't match
# `[Claude-Bot/]<Type>/<3-8-kebab-word-title>`. That's correct — but it leaves
# you stuck after committing on `dev` / `main` / a detached HEAD with no obvious
# next step. This script is that next step: it moves your commits onto a
# properly-named feature branch (resetting the protected branch back to its
# origin tip so it stays clean), pushes, and opens a PR assigned to you with
# any referenced issues linked.
#
# Usage:
#   scripts/open-pr.sh [-b <feature-branch>] [-B <base>] [-c <issue>]... [-n]
#
#   -b  Feature branch name. Must satisfy the branch convention. If omitted and
#       you're not already on a valid feature branch, it's derived from your
#       latest commit subject (e.g. "fix: harden X" -> Claude-Bot/Fix/harden-x).
#   -B  PR base branch (default: dev).
#   -c  Issue number to reference in the PR body (repeatable). Prefix with '!'
#       to close it, e.g. -c '!87' -> "Closes #87"; plain -c 87 -> "Relates to #87".
#   -n  Dry run: print what would happen, change nothing.
#
# Examples:
#   scripts/open-pr.sh                              # derive everything, base dev
#   scripts/open-pr.sh -B main -c 87                # base main, relate to #87
#   scripts/open-pr.sh -b Claude-Bot/Feat/add-x -c '!12'
set -eu

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "open-pr: not inside a git repository" >&2; exit 1; }
# shellcheck source=scripts/hooks/lib/rules.sh
. "$ROOT/scripts/hooks/lib/rules.sh"

# ── parse args ─────────────────────────────────────────────────────────────
FEATURE=""; BASE="dev"; DRYRUN=0; ISSUES=""
while getopts "b:B:c:nh" opt; do
  case "$opt" in
    b) FEATURE="$OPTARG" ;;
    B) BASE="$OPTARG" ;;
    c) ISSUES="$ISSUES $OPTARG" ;;
    n) DRYRUN=1 ;;
    h) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "open-pr: run with -h for usage" >&2; exit 2 ;;
  esac
done

run() { if [ "$DRYRUN" -eq 1 ]; then printf '  [dry-run] %s\n' "$*"; else eval "$@"; fi; }

command -v gh >/dev/null 2>&1 || { echo "open-pr: gh CLI not found" >&2; exit 1; }

# ── refuse to proceed with a dirty tree (branch moves would lose changes) ───
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  _rules_box '\033[31m' "open-pr — working tree not clean" \
    "Commit or stash your changes before opening a PR."
  exit 1
fi

# ── derive a conventional branch name from the latest commit subject ────────
derive_branch() {
  _subj=$(git log -1 --format=%s)
  _ctype=$(printf '%s' "$_subj" | sed -n 's/^\([a-z]*\):.*/\1/p')
  case "$_ctype" in
    feat) _btype=Feat ;; fix) _btype=Fix ;; chore) _btype=Chore ;;
    docs) _btype=Docs ;; refactor) _btype=Refactor ;; style) _btype=Style ;;
    test) _btype=Test ;; lint) _btype=Lint ;;
    *) _btype="" ;;
  esac
  [ -n "$_btype" ] || return 1
  # title -> kebab, drop empties, clamp to 8 words (pattern allows 3-8)
  _title=$(printf '%s' "$_subj" | sed 's/^[a-z]*: *//' \
            | tr '[:upper:]' '[:lower:]' \
            | sed 's/[^a-z0-9]\{1,\}/-/g; s/^-//; s/-$//' \
            | cut -d- -f1-8)
  printf 'Claude-Bot/%s/%s' "$_btype" "$_title"
}

CURRENT=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo "")

# ── decide the feature branch ───────────────────────────────────────────────
# If we're already on a valid (non-protected) feature branch and no -b was
# given, reuse it. Otherwise we must create/switch to one.
NEED_MOVE=0
if [ -z "$FEATURE" ]; then
  if [ -n "$CURRENT" ] && ! rules_is_protected "$CURRENT" \
       && printf '%s' "$CURRENT" | grep -qE "$RULES_BRANCH_PATTERN"; then
    FEATURE="$CURRENT"
  else
    FEATURE=$(derive_branch) || {
      _rules_box '\033[31m' "open-pr — could not derive a branch name" \
        "Your latest commit subject has no recognised <type>: prefix." \
        "Pass one explicitly:  scripts/open-pr.sh -b Claude-Bot/Fix/your-title"
      exit 1; }
    NEED_MOVE=1
  fi
fi

# Validate whatever we ended up with (explicit -b included).
rules_validate_branch "$FEATURE" || exit 1
[ "$FEATURE" = "$CURRENT" ] || NEED_MOVE=1

printf '\n  open-pr plan\n'
printf '  ──────────────────────────────────────────────────────\n'
printf '  source branch : %s\n' "${CURRENT:-（detached HEAD）}"
printf '  feature branch: %s\n' "$FEATURE"
printf '  PR base       : %s\n' "$BASE"
printf '  issues        : %s\n' "${ISSUES:-（none）}"
printf '  ──────────────────────────────────────────────────────\n\n'

# ── move commits onto the feature branch, keep the source branch clean ──────
if [ "$NEED_MOVE" -eq 1 ]; then
  if git show-ref --verify --quiet "refs/heads/$FEATURE"; then
    run "git checkout '$FEATURE'"
  else
    run "git branch '$FEATURE'"
    # Rewind a protected/invalid source branch back to its origin tip so the
    # commits live only on the feature branch. Skipped for detached HEAD or
    # when there's no matching upstream to rewind to.
    if [ -n "$CURRENT" ] && git show-ref --verify --quiet "refs/remotes/origin/$CURRENT"; then
      run "git reset --hard 'origin/$CURRENT'"
    elif [ -n "$CURRENT" ]; then
      printf '  note: no origin/%s to rewind to — leaving %s as-is.\n' "$CURRENT" "$CURRENT"
    fi
    run "git checkout '$FEATURE'"
  fi
fi

# ── push ────────────────────────────────────────────────────────────────────
run "git push -u origin '$FEATURE'"

# ── build PR body: commit list + issue refs + signature ─────────────────────
TITLE=$(git log -1 --format=%s "$FEATURE" 2>/dev/null || git log -1 --format=%s)
COMMITS=$(git log --format='- %s' "origin/$BASE..$FEATURE" 2>/dev/null || git log -1 --format='- %s')
ISSUE_LINES=""
for _i in $ISSUES; do
  case "$_i" in
    \!*) ISSUE_LINES="$ISSUE_LINES\nCloses #${_i#!}" ;;
    *)   ISSUE_LINES="$ISSUE_LINES\nRelates to #${_i}" ;;
  esac
done

BODY=$(printf '## Changes\n\n%s\n' "$COMMITS")
[ -n "$ISSUE_LINES" ] && BODY=$(printf '%s\n## Related\n%b\n' "$BODY" "$ISSUE_LINES")
BODY=$(printf '%s\n\n— Claude-Bot on behalf of @me\n' "$BODY")

# ── open the PR, assigned to the author ─────────────────────────────────────
if [ "$DRYRUN" -eq 1 ]; then
  printf '  [dry-run] gh pr create --base %s --head %s --assignee @me\n' "$BASE" "$FEATURE"
  printf '  --- title ---\n  %s\n  --- body ---\n%s\n' "$TITLE" "$BODY"
  exit 0
fi

gh pr create --base "$BASE" --head "$FEATURE" --assignee @me \
  --title "$TITLE" --body "$BODY"
