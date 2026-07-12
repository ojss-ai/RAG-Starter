# Command: brainstorm

Trigger: "brainstorm", "let's rethink X", any design/requirement discussion before the SRS is READY.
Gate: `docs/srs.md` exists (run `specify` first). Repeatable: unlimited rounds.

## Steps

1. Read `.atomforge/state.json` and `docs/srs.md` in full — every round starts from the
   document on disk, not from memory of earlier rounds.
2. Socratic mode: explore the user's new angle with ONE question at a time; prefer
   multiple-choice. Surface trade-offs and at least one alternative they didn't mention.
3. Apply agreed changes DIRECTLY to `docs/srs.md`: update requirements, renumber nothing
   (retired requirements get `~~strikethrough~~ (removed <date>)` so history is visible),
   append new FR/NFR ids at the end.
4. Keep `srs.status = "IN-PROGRESS"` the whole time. Never set READY yourself.
5. Each round ends with a one-paragraph summary of what changed in the SRS and the reminder:
   `mark-ready srs` locks it when they're satisfied.

## Rules

- Brainstorming after READY: allowed only if the user explicitly reopens (status returns to
  IN-PROGRESS; any READY plans/atoms affected by the change must be flagged for re-review).
- Never write code or plans from this command.

## Example

> **User:** brainstorm — do tasks really need subtasks?
> **Agent:** explores the trade-off with one question at a time → user decides to drop them →
> strikes FR-5 through in `docs/srs.md` with the date → "Changed: FR-5 removed. Lock with
> `mark-ready srs` when satisfied."
