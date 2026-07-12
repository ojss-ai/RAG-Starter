# Command: review-atom

Trigger: "review atom-03", "review the atom", "refresh atom-03".
Gate: the atom exists. Repeatable: run as many times as needed, at any point.
Purpose: bring the atom document up to date with reality and certify it implementable.

## Steps

1. Read `.atomforge/state.json`, the atom document, its phase plan, and the CURRENT contents
   of every file the atom touches (the codebase may have moved since the atom was written).
2. Check, in order:
   - **Freshness**: does the atom's code still apply cleanly to today's codebase? Imports,
     signatures, paths, schema still correct?
   - **Completeness**: full code blocks, exact paths, verification steps, mode-appropriate
     tests (RED block in tdd mode).
   - **Traceability**: still consistent with its plan item and FR ids.
   - **New information**: anything the user said since creation that changes this atom.
3. Update the atom document directly with what you found. Append every non-trivial finding to
   the atom's `## Review Log` section (`<date> — finding — action taken`).
4. Outcome:
   - All checks pass → set atom `Status: READY` in the doc and in `state.json.atoms` (this
     command MAY set READY — certifying implementability is exactly its job).
   - Problems you cannot fix from available information → keep DRAFT, list what's missing,
     ask the user.
5. Re-running against a READY atom re-verifies it; if drift is found, status drops back to
   DRAFT and the log says why.

## Example

> **User:** review atom-02
> **Agent:** re-reads today's `src/db/*` → the atom's import path is stale after atom-01
> restructured folders → fixes the code block, logs "2026-07-10 — import path drifted —
> updated" in the Review Log → all checks pass → `READY`. "atom-02 certified. Next:
> `implement atom-02`."
