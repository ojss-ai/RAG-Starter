# Command: create-plan

Trigger: "create plan", "create the plan", "plan the phases".
Gate: SRS READY + `state.json.stack` and `state.json.mode` set (run `define-stack` first).
Usable at ANY point of development — later runs add/revise phases, they never silently rewrite
READY ones. Output: one file per phase in `docs/plans/`.

## Steps

1. Read `.atomforge/state.json`, `docs/srs.md`, every installed `.atomforge/skills/*.md`
   relevant to the stack, and any existing `docs/plans/*.md`. If `state.json.design.status`
   is not `NONE`/absent, also read `docs/design/design-guide.md` — UI phases MUST reference
   it (tokens, components, page blueprints, asset paths).
2. Split the work into 2–6 phases. A phase is a shippable, testable slice ordered by
   dependency (foundation → features → hardening). Name format:
   `docs/plans/phase-NN-<short-name>.md` (NN zero-padded, sequential).
3. For each phase, instantiate `.atomforge/blueprints/plan-blueprint.md`. Every phase item
   MUST trace to FR/NFR ids; every FR MUST land in exactly one phase. Plans MUST comply with
   every MUST in the installed skill files.
4. New plans get `Status: IN-PROGRESS`. Register each phase in `state.json.plans`
   (`"phase-01-foundation": "IN-PROGRESS"`).
5. Re-runs (plan revision):
   - IN-PROGRESS phases may be edited freely.
   - READY phases: propose the change, show a diff summary, and require the user to reopen
     before touching the file.
   - Never renumber existing phases; new work appends new phases.
6. Present each phase plan for review. Remind: `mark-ready phase-NN` locks a phase;
   `create-atoms phase-NN` is next.

## Example

> **User:** create plan
> **Agent:** produces `docs/plans/phase-01-foundation.md` (FR-1, FR-2) and
> `docs/plans/phase-02-task-crud.md` (FR-3…FR-8) → user: "move FR-8 to a new phase" →
> agent appends `phase-03-recurrence.md`, updates phase-02 (IN-PROGRESS, so editable) →
> "Review and `mark-ready phase-01` when satisfied."
