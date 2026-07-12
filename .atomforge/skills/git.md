# Skill: git

Category: system · Test oracle: n/a · Applies: every commit in this project
When to use: read before ANY git operation — branching, committing, rebasing, pushing.

## Branching

- One phase (or coherent feature) = one branch: `feat/phase-NN-<short-name>` cut from the
  default branch. Never commit work to `main`/`master` directly.
- For parallel work or risky spikes, prefer an isolated worktree:
  `git worktree add ../<repo>-phase-NN feat/phase-NN-<short-name>` — keeps the primary
  checkout clean. Remove with `git worktree remove` after merge.
- Rebase the feature branch on the default branch before opening a PR; never merge the default
  branch into the feature branch repeatedly.

## Commits (semantic, atomic)

- Format: `type(scope): subject [atom-NN]`
  - `type` ∈ `feat|fix|test|refactor|docs|chore|perf|build`
  - subject: imperative, lowercase, ≤ 72 chars, no trailing period.
  - Breaking change: `type(scope)!: …` plus a `BREAKING CHANGE:` footer.
- Exactly ONE atom per commit. The test and its implementation belong to the SAME commit
  (the commit proves the cycle); a pure-refactor step MAY be its own `refactor:` commit.
- MUST NOT commit: red suite, skipped/focused tests, commented-out code, secrets, generated
  artifacts not in .gitignore.
- `git add <explicit paths>` only. `git add .` and `git add -A` are forbidden.

## Hygiene

- `git status` and `git diff --staged` before every commit — review what you are committing.
- Never `push --force` on shared branches; `--force-with-lease` only on your own feature branch.
- Never rewrite history that has been pushed and reviewed.
