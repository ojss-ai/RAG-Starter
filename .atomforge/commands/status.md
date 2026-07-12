# Command: status

Trigger: "status", "where are we", "what's next".
Gate: none. Read-only — this command never mutates anything.

## Steps

1. Read `.atomforge/state.json`, scan `docs/plans/` and `docs/atoms/`, and run
   `git log --oneline -5` if a repo exists.
2. Report, concisely:
   - SRS: status (NONE / IN-PROGRESS / READY)
   - Design guide: status (NONE / IN-PROGRESS / READY) — omit if absent/NONE
   - Stack & mode: `state.json.stack`, `state.json.mode`, `state.json.testRunner`
   - Phases: each plan with its status (IN-PROGRESS / READY)
   - Atoms: per phase — counts by status (DRAFT / READY / IMPLEMENTED / VALIDATED / COMMITTED)
     and the current in-flight atom if any
   - Findings: any `OPEN` HIGH findings (these block validate/commit)
   - Last commits
3. End with the single most sensible next command.

## Also: session recovery

Run this command's steps 1–2 silently at the start of ANY session (or after context
compaction) before acting on other requests — state on disk always beats memory.

## Example

> **User:** status
> **Agent:** "SRS READY · stack ts/express/postgres · mode tdd · phase-01 READY
> (atom-01 ✓ COMMITTED, atom-02 ✓ COMMITTED, atom-03 DRAFT) · phase-02 IN-PROGRESS ·
> no OPEN HIGH findings · last commit `a1b2c3d` · **next: `review-atom atom-03`**."
