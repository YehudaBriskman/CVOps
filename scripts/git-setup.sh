#!/bin/sh
# ── git-setup.sh ───────────────────────────────────────────────────────────
# Run once after cloning to activate the shared git hooks and project defaults.
# Usage: sh scripts/git-setup.sh

set -e

echo ""
echo "  CVOps — Git Setup"
echo "  ──────────────────────────────────────────────────────"

# ── hooks ─────────────────────────────────────────────────────────────────
git config core.hooksPath .githooks
chmod +x .githooks/commit-msg .githooks/pre-push .githooks/pre-commit .githooks/prepare-commit-msg
chmod +x scripts/hooks/jj/validate.sh scripts/hooks/jj/pre-push.sh
echo "  [ok] hooks -> .githooks (shared rules: scripts/hooks/lib/rules.sh)"
echo "  [ok] using jj? run: sh scripts/jj-setup.sh  (same rules, via jj aliases)"

# ── push ──────────────────────────────────────────────────────────────────
git config push.default current
git config push.followTags true
git config push.autoSetupRemote true
echo "  [ok] push  -> default=current, followTags, autoSetupRemote"

# ── pull / fetch ──────────────────────────────────────────────────────────
git config pull.rebase true
git config fetch.prune true
git config rebase.autoStash true
echo "  [ok] pull  -> rebase=true, fetch prune, rebase autoStash"

# ── merge ─────────────────────────────────────────────────────────────────
git config merge.ff false
echo "  [ok] merge -> no fast-forward (always creates a merge commit)"

# ── done ──────────────────────────────────────────────────────────────────
echo "  ──────────────────────────────────────────────────────"
echo "  Setup complete. Branch rules:"
echo ""
echo "  Protected:  main  develop  (no direct push, PRs required)"
echo "  Format:     [Claude-Bot/]<Type>/<3-8-kebab-word-title>"
echo "  Types:      Feat  Fix  Chore  Docs  Refactor  Style  Test  Lint"
echo ""
echo "  Example branches:"
echo "    Feat/add-dataset-versioning-api"
echo "    Claude-Bot/Fix/resolve-celery-worker-deadlock"
echo "  ──────────────────────────────────────────────────────"
echo ""
