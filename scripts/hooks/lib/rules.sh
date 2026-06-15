#!/bin/sh
# ── scripts/hooks/lib/rules.sh ─────────────────────────────────────────────
# Shared commit & branch convention rules — PROVIDER-NEUTRAL.
#
# This is the single source of truth for the project's git conventions. It is
# sourced by BOTH front-ends so `git` and `jj` enforce identical rules:
#   • git provider → .githooks/{commit-msg,pre-push}
#   • jj  provider → scripts/hooks/jj/{validate,pre-push}.sh
#
# Sourcing this file has no side effects; it only defines constants and
# validator functions. Each validator prints a formatted message to stderr and
# returns non-zero on failure, 0 on success.

RULES_PROTECTED_BRANCHES="main develop master"
RULES_BRANCH_TYPES="Feat|Fix|Chore|Docs|Refactor|Style|Test|Lint"
RULES_BRANCH_PATTERN="^(Claude-Bot/)?(${RULES_BRANCH_TYPES})/[a-z][a-z0-9]*(-[a-z0-9]+){2,7}$"
RULES_COMMIT_TYPES="feat|fix|chore|docs|refactor|style|test|lint"

# _rules_box <ansi-color> <title> [line...] — formatted error block on stderr.
_rules_box() {
  _c="$1"; _t="$2"; shift 2
  printf '\n  %b%s\033[0m\n' "$_c" "$_t" >&2
  printf '  ──────────────────────────────────────────────────────\n' >&2
  for _l in "$@"; do printf '  %s\n' "$_l" >&2; done
  printf '  ──────────────────────────────────────────────────────\n\n' >&2
}

# rules_is_protected <name> → 0 if <name> is a protected branch/bookmark.
rules_is_protected() {
  for _b in $RULES_PROTECTED_BRANCHES; do
    [ "$1" = "$_b" ] && return 0
  done
  return 1
}

# rules_validate_branch <name> → 0 ok / 1 invalid (prints guidance).
# Used for git branches and jj bookmarks alike.
rules_validate_branch() {
  _name="$1"
  if [ -z "$_name" ]; then
    return 0   # detached HEAD / no bookmark to push — nothing to validate
  fi
  if rules_is_protected "$_name"; then
    _rules_box '\033[31m' "protected branch: $_name — direct push not allowed" \
      "Open a PR from a feature branch instead." \
      "" \
      "  <Type>/<3-8-kebab-word-title>   e.g. Feat/add-dataset-versioning-api"
    return 1
  fi
  if printf '%s' "$_name" | grep -qE "$RULES_BRANCH_PATTERN"; then
    return 0
  fi
  _rules_box '\033[31m' "branch/bookmark name invalid: $_name" \
    "Format:  [Claude-Bot/]<Type>/<3-8-kebab-word-title>" \
    "Types:   Feat  Fix  Chore  Docs  Refactor  Style  Test  Lint" \
    "" \
    "Examples:" \
    "  Feat/add-jwt-auth-middleware" \
    "  Claude-Bot/Refactor/extract-celery-worker-base-class"
  return 1
}

# rules_validate_message → 0 ok / 1 invalid. Full commit message read on stdin.
rules_validate_message() {
  _msg=$(cat)
  _first=$(printf '%s\n' "$_msg" | sed -n '1p')

  # Skip machine-generated / special subjects.
  case "$_first" in
    Merge\ *|Revert\ *|fixup!*|squash!*|WIP*|wip*|Initial\ commit) return 0 ;;
  esac

  if ! printf '%s' "$_first" | grep -qE "^(${RULES_COMMIT_TYPES}): .+$"; then
    _rules_box '\033[31m' "commit message — invalid format" \
      "Required: <type>: <title>" \
      "Types:    feat  fix  chore  docs  refactor  style  test  lint" \
      "Got:      $_first" \
      "" \
      "Example:  feat: add jwt authentication middleware"
    return 1
  fi

  _title=$(printf '%s' "$_first" | sed 's/^[^:]*: //')
  _wc=$(printf '%s' "$_title" | wc -w | tr -d '[:space:]')
  if [ "$_wc" -lt 3 ] || [ "$_wc" -gt 10 ]; then
    _rules_box '\033[31m' "commit message — title word count" \
      "Title should be 3-10 words (got $_wc)." \
      "Got: $_first"
    return 1
  fi

  # Blank line after the subject (only enforced when a body is present).
  _second=$(printf '%s\n' "$_msg" | sed -n '2p')
  if [ -n "$_second" ]; then
    _rules_box '\033[33m' "commit message — missing blank line after subject" \
      "Add a blank line between the subject and the body."
    return 1
  fi

  return 0
}
