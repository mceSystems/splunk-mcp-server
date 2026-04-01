#!/bin/sh
# Run once after cloning to enable the local git hooks:
#   sh scripts/setup-hooks.sh

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "Error: must be run inside a Git repository." >&2
    exit 1
}

if git config --local core.hooksPath "$REPO_ROOT/.githooks"; then
    chmod +x "$REPO_ROOT"/.githooks/*
    echo "Git hooks enabled — direct pushes to main are now blocked locally."
else
    echo "Failed to enable Git hooks." >&2
    exit 1
fi
