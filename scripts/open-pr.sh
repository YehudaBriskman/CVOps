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
#   scripts/open-pr.sh [-b <feature-branch>] [-B <base>] [-t <title>] [-c <issue>]... [-p] [-n]
#
#   -b  Feature branch name. Must satisfy the branch convention. If omitted and
#       you're not already on a valid feature branch, it's derived from your
#       latest commit subject (e.g. "fix: harden X" -> Claude-Bot/Fix/harden-x).
#   -B  PR base branch (default: dev, or main in promote mode).
#   -t  PR title override (default: the latest commit subject on the head branch).
#   -c  Issue number to reference in the PR body (repeatable). Prefix with '!'
#       to close it, e.g. -c '!87' -> "Closes #87"; plain -c 87 -> "Relates to #87".
#   -p  Promote mode: open a PR for the *current* branch as-is into <base>
#       (e.g. dev -> main). No feature-branch move, no rewind, and NO push — the
#       head must already be on origin and not ahead of it. Use this to roll an
#       integration branch up to main; pair with -c '!N' to close the issues the
#       bundled work resolved (they close on merge to the default branch).
#   -n  Dry run: print what would happen, change nothing.
#
# Examples:
#   scripts/open-pr.sh                              # derive everything, base dev
#   scripts/open-pr.sh -B main -c 87                # base main, relate to #87
#   scripts/open-pr.sh -b Claude-Bot/Feat/add-x -c '!12'
#   scripts/open-pr.sh -p -t "Promote dev -> main" -c '!51' -c '!54'
set -eu

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "open-pr: not inside a git repository" >&2; exit 1; }
# shellcheck source=scripts/hooks/lib/rules.sh
. "$ROOT/scripts/hooks/lib/rules.sh"

# ── parse args ─────────────────────────────────────────────────────────────
FEATURE=""; BASE=""; DRYRUN=0; ISSUES=""; PROMOTE=0; TITLE_OVERRIDE=""
while getopts "b:B:t:c:pnh" opt; do
  case "$opt" in
    b) FEATURE="$OPTARG" ;;
    B) BASE="$OPTARG" ;;
    t) TITLE_OVERRIDE="$OPTARG" ;;
    c) ISSUES="$ISSUES $OPTARG" ;;
    p) PROMOTE=1 ;;
    n) DRYRUN=1 ;;
    h) sed -n '2,36p' "$0"; exit 0 ;;
    *) echo "open-pr: run with -h for usage" >&2; exit 2 ;;
  esac
done

# Default base depends on mode: promotion rolls up to main, otherwise dev.
if [ -z "$BASE" ]; then
  if [ "$PROMOTE" -eq 1 ]; then BASE="main"; else BASE="dev"; fi
fi

run() { if [ "$DRYRUN" -eq 1 ]; then printf '  [dry-run] %s\n' "$*"; else eval "$@"; fi; }

command -v gh >/dev/null 2>&1 || { echo "open-pr: gh CLI not found" >&2; exit 1; }

# ── refuse to proceed with a dirty tree (branch moves would lose changes) ───
# Skipped in promote mode: it never moves a branch or touches the working copy
# (it opens a PR from origin/<head> as-is), so uncommitted edits are harmless.
if [ "$PROMOTE" -ne 1 ] && [ -n "$(git status --porcelain --untracked-files=no)" ]; then
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

# ── decide the head branch ──────────────────────────────────────────────────
NEED_MOVE=0
if [ "$PROMOTE" -eq 1 ]; then
  # Promote: PR the current branch as-is into <base> (e.g. dev -> main). No
  # feature-branch move, no rewind, no push — the head is a shared branch that's
  # only ever updated through PRs, so we validate it's clean against origin and
  # just open the PR. The branch-convention check is skipped on purpose (the
  # head is a protected integration branch here).
  [ -n "$CURRENT" ] || { _rules_box '\033[31m' "open-pr -p — detached HEAD" \
      "Check out the branch you want to promote (e.g. git checkout dev)."; exit 1; }
  if [ -n "$FEATURE" ] && [ "$FEATURE" != "$CURRENT" ]; then
    _rules_box '\033[31m' "open-pr -p — -b conflicts with promote" \
      "Promote uses the checked-out branch; drop -b or drop -p."; exit 1
  fi
  FEATURE="$CURRENT"
  if [ "$FEATURE" = "$BASE" ]; then
    _rules_box '\033[31m' "open-pr -p — head equals base ($BASE)" \
      "Pass -B <base> to promote into a different branch."; exit 1
  fi
  git show-ref --verify --quiet "refs/remotes/origin/$FEATURE" || {
    _rules_box '\033[31m' "open-pr -p — origin/$FEATURE not found" \
      "Promotion PRs don't push; get $FEATURE onto origin first."; exit 1; }
  _ahead=$(git rev-list --count "origin/$FEATURE..$FEATURE" 2>/dev/null || echo 0)
  if [ "$_ahead" -gt 0 ]; then
    _rules_box '\033[31m' "open-pr -p — $FEATURE is $_ahead commit(s) ahead of origin" \
      "Promotion never pushes a protected branch. Land those commits via a" \
      "feature-branch PR first, then promote."; exit 1
  fi
else
  # If we're already on a valid (non-protected) feature branch and no -b was
  # given, reuse it. Otherwise we must create/switch to one.
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
fi

if [ "$PROMOTE" -eq 1 ]; then
  printf '\n  open-pr plan (promote)\n'
  printf '  ──────────────────────────────────────────────────────\n'
  printf '  promote branch: %s  (as-is, no push)\n' "$FEATURE"
else
  printf '\n  open-pr plan\n'
  printf '  ──────────────────────────────────────────────────────\n'
  printf '  source branch : %s\n' "${CURRENT:-（detached HEAD）}"
  printf '  feature branch: %s\n' "$FEATURE"
fi
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
# Promotion never pushes (the head is a protected branch already on origin);
# the feature-branch flow pushes the moved commits.
if [ "$PROMOTE" -eq 1 ]; then
  printf '  promote: using origin/%s as-is (no push)\n' "$FEATURE"
else
  run "git push -u origin '$FEATURE'"
fi

# ── build PR body: commit list + issue refs + signature ─────────────────────
TITLE=${TITLE_OVERRIDE:-$(git log -1 --format=%s "$FEATURE" 2>/dev/null || git log -1 --format=%s)}
COMMITS=$(git log --no-merges --format='- %s' "origin/$BASE..$FEATURE" 2>/dev/null || git log -1 --format='- %s')
ISSUE_LINES=""
for _i in $ISSUES; do
  case "$_i" in
    \!*) ISSUE_LINES="$ISSUE_LINES\nCloses #${_i#!}" ;;
    *)   ISSUE_LINES="$ISSUE_LINES\nRelates to #${_i}" ;;
  esac
done

BODY=$(printf '## Changes\n\n%s\n' "$COMMITS")
[ -n "$ISSUE_LINES" ] && BODY=$(printf '%s\n## Related\n%b\n' "$BODY" "$ISSUE_LINES")
BODY=$(printf '%s\n\n— Claude-Bot on behalf of @Yehuda Briskman\n' "$BODY")

# ── open the PR, assigned to the author ─────────────────────────────────────
if [ "$DRYRUN" -eq 1 ]; then
  printf '  [dry-run] gh pr create --base %s --head %s --assignee @me\n' "$BASE" "$FEATURE"
  printf '  --- title ---\n  %s\n  --- body ---\n%s\n' "$TITLE" "$BODY"
  exit 0
fi

gh pr create --base "$BASE" --head "$FEATURE" --assignee @me \
  --title "$TITLE" --body "$BODY"
