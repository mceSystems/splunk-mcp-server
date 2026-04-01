# Claude Code Instructions

## Self-review before committing

Before committing any code, review it as a critic — not as the author. Ask:

- **Edge cases**: what inputs or conditions aren't covered? (e.g. non-branch refs for a git hook, empty results, unexpected types)
- **Assumptions**: does the code assume a specific working directory, environment, or state that may not hold?
- **Scope creep**: does a config change or side effect reach beyond this repo? (e.g. `git config` without `--local`)
- **Permissions and setup**: will this work on a fresh clone with no manual steps?
- **Error handling**: are failures caught specifically, or does a bare `except`/silent pass hide bugs?
- **Accuracy**: do docstrings, comments, and README reflect what the code actually does — not what was intended?

The goal is to find issues yourself rather than having them surface in code review.
