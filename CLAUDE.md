# Claude Code Instructions

## Shell scripts and git hooks

Before committing any shell script or git hook, verify all of the following manually:

**Checklist:**
- [ ] Non-branch refs — tag pushes (`git push origin v1.0.0`) are not blocked
- [ ] Working directory — works when run from a subdirectory; use `git rev-parse --show-toplevel` for paths
- [ ] Git config scope — use `git config --local` unless global scope is explicitly intended
- [ ] File permissions — setup scripts must `chmod +x` any hooks so they work on a fresh clone
- [ ] Shell safety — use `read -r`, quote all variables

**Minimum test cases before committing a hook:**

```sh
# Tag push must be allowed
git tag v0.0.0-test && git push origin v0.0.0-test
git push origin :v0.0.0-test && git tag -d v0.0.0-test  # cleanup

# feature/ branch must be allowed
git checkout -b feature/test-hook && git push origin feature/test-hook
git push origin :feature/test-hook  # cleanup

# Push to main must be blocked
git push origin HEAD:main

# Non-feature/ branch must be blocked
git checkout -b notafeature && git push origin notafeature
git branch -D notafeature  # cleanup

# Setup script from a subdirectory must work
cd src && sh ../scripts/setup-hooks.sh && cd ..

# Setup script outside a repo must fail cleanly with exit 1
cd /tmp && sh /path/to/scripts/setup-hooks.sh
```
