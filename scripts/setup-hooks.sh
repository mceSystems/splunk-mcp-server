#!/bin/sh
# Run once after cloning to enable the local git hooks:
#   sh scripts/setup-hooks.sh
if git config core.hooksPath .githooks; then
    echo "Git hooks enabled — direct pushes to main are now blocked locally."
else
    echo "Failed to enable Git hooks. Make sure you're running this inside a Git repository." >&2
    exit 1
fi
