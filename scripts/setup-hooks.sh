#!/bin/sh
# Run once after cloning to enable the local git hooks:
#   sh scripts/setup-hooks.sh
git config core.hooksPath .githooks
echo "Git hooks enabled — direct pushes to main are now blocked locally."
