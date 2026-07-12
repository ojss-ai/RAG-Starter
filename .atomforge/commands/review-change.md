# Command: review-change

Trigger: "review change", "review the changes", "check the diff".
Gate: atom status `VALIDATED` (recommended flow) — also runnable standalone anytime.
Purpose: final pre-commit inspection of the actual git diff.

## Steps

1. Run `git status` and `git diff` (plus `git diff --staged` if anything is staged).
2. Check the diff itself:
   - **Scope**: every changed file belongs to the current atom. Unrelated drive-by changes
     are flagged — they go to their own atom/commit, not this one.
   - **Hygiene**: no debug prints, commented-out code, secrets/keys, stray formatting churn,
     accidental file-mode or lockfile changes.
   - **Completeness**: nothing the atom requires is missing from the diff (untracked files
     forgotten with `git add` are the classic).
   - **Consistency**: atom doc, findings file, and logs were updated and are part of the
     change set if they live in the repo.
3. Final check: run `state.json.testRunner` one last time on the exact working tree.
4. Report: files changed, +/- lines, verdict per check, and any flagged items with a proposed
   resolution. If clean → tell the user `commit` is next. If not → list exactly what to fix
   first (usually a fix-cycle via `implement` or splitting the diff).

## Example

> **User:** review change
> **Agent:** `git diff` → 4 files, +182/−3 → scope ✓ (all atom-02), hygiene ✗ (one
> `console.log` left in `db.ts:41`), completeness ✓, suite green ✓ → "Remove the debug line
> (quick `implement` fix-cycle), then `commit`."
