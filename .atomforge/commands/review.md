# Command: review

Trigger: "review atom-03", "review the code", "deep dive".
Gate: atom status `IMPLEMENTED` (or later). Repeatable.
Purpose: adversarial deep-dive on the implemented code — loose ends, validation gaps, depth
analysis. Findings are RECORDED and PROPOSED, never auto-fixed.

## Steps

1. Read the atom document (including its logs), the actual implemented code, the tests, the
   phase plan, and the relevant skill files.
2. Deep-dive checklist:
   - Correctness vs the atom spec and the FR acceptance scenarios.
   - Loose ends: dead code, half-wired paths, unused params, TODO left behind.
   - Validation: every external input validated? boundaries? error paths tested?
   - Depth: concurrency, N+1s/queries, resource cleanup, failure modes, security
     (injection, authz), skill-file MUST violations.
   - Design fidelity (UI atoms, when `state.json.design.status` is `READY`): every visual
     value and asset path traces to `docs/design/design-guide.md`; drift (hardcoded
     colors/fonts, wrong asset paths, ignored components) → MEDIUM finding.
   - Tests: do they actually assert behavior, or only that code ran? Any weakened/skipped?
3. Write findings to `docs/atoms/findings/atom-NN-<short-name>.md` (instantiate
   `.atomforge/blueprints/finding-blueprint.md`; append on re-runs, never overwrite):
   - Each finding: id `F-NN.n`, severity **HIGH / MEDIUM / LOW**, evidence (file:line),
     suggested fix, status `OPEN`.
4. Update the atom's `## Review Log` with a one-line pointer to the findings file.
5. Report findings to the user grouped by severity, and ask which to fix:
   - User approves (all, or specific ids) → set those findings `APPROVED`, then hand off to
     `implement` (fix-cycle) which will code them, log them, and mark them `FIXED`.
   - User declines → set `WONT-FIX` with their one-line reason.
6. HIGH findings left `OPEN` block `validate` and `commit`; say so explicitly in the report.

## Example

> **User:** review atom-02
> **Agent:** deep-dives → writes `docs/atoms/findings/atom-02-db-schema-tasks.md`:
> F-02.1 HIGH (user_id FK unindexed, `migrations/001:14`), F-02.2 LOW (missing table
> comment) → "1 HIGH blocks commit. Fix which?" → user: "fix the HIGH" → F-02.1 → APPROVED,
> hand-off to `implement`.
