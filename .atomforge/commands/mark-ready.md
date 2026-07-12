# Command: mark-ready

Trigger: "mark it ready", "mark-ready srs", "mark-ready design", "mark-ready phase-01",
"mark-ready atom-03", "I'm satisfied, lock it".
Purpose: the ONLY way a document's status becomes READY. Claude never sets READY on its own.

## Steps

1. Identify the target document:
   - `srs` → `docs/srs.md`
   - `design` → `docs/design/design-guide.md`
   - `phase-NN` → the matching file in `docs/plans/`
   - `atom-NN` → the matching file in `docs/atoms/phase-*/`
   If ambiguous, ask.
2. Pre-flight check (report failures instead of marking):
   - SRS: no unresolved blocking Open Questions; every FR has ≥ 1 acceptance scenario.
   - Design guide: no unresolved blocking Open Questions; every Assets Inventory path
     exists on disk under `docs/design/assets/`.
   - Plan: every phase item traces to an FR/NFR; stack and mode are set in state.json.
   - Atom: complete code blocks (no `...`/TODO placeholders), files listed, verification
     steps present, traces to a plan item.
3. If checks pass: set `Status: READY` in the document header AND update the matching entry
   in `.atomforge/state.json` (`srs.status`, `design.status`, `plans[...]`, or
   `atoms[...].status`).
4. Confirm to the user what was locked and what the next command is.

## Rules

- READY is a statement by the HUMAN. If Claude finds the document deficient, it says so and
  waits — it does not refuse forever; the user may override with "mark ready anyway"
  (record `"readyOverride": true` on that entry in state.json).
- Editing a READY document requires explicit reopening; log the reopen in the document header
  (`Reopened: <date> — <reason>`).

## Example

> **User:** mark-ready phase-01
> **Agent:** pre-flight: every §3 item traces to an FR ✓, stack+mode set ✓ → sets
> `Status: READY` in `docs/plans/phase-01-foundation.md` and `state.json.plans` →
> "phase-01 locked. Next: `create-atoms phase-01`."
