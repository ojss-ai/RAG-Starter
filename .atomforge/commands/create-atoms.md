# Command: create-atoms

Trigger: "create atoms", "create the atom", "create atoms for phase-02".
Gate: the target phase plan is READY. Usable at ANY point of development — re-runs create
atoms for newly-readied phases or additional atoms for changed plans.
Output: `docs/atoms/phase-NN/atom-MM-<short-name>.md` files.

## Numbering (global, sequential)

- Atom numbers are unique across the WHOLE project and never reused: read
  `state.json.nextAtom`, assign, increment, write back.
- Phase folders hold the atoms that belong to them: phase-01 might hold atom-01..atom-04,
  phase-02 continues with atom-05... `<short-name>` is 1–3 kebab-case words.

## Steps

1. Read `.atomforge/state.json`, the phase plan, `docs/srs.md`, relevant skill files, and —
   for existing codebases — the actual source files the atoms will touch. An atom written
   against imagined code is a defect. If `state.json.design.status` is not `NONE`/absent,
   also read `docs/design/design-guide.md`: UI atoms reference design tokens by name, use
   the guide's components/page blueprints, and include explicit asset copy steps in their
   file lists and code (e.g. `docs/design/assets/logo/logo.svg` → `public/logo.svg`).
   Once the guide is READY, a hardcoded visual value not traceable to it is a review
   finding (MEDIUM).
2. Slice the phase into atoms. One atom = one small, independently implementable and testable
   unit (≈ one sitting of work): exact files, complete code, its own verification.
3. Instantiate `.atomforge/blueprints/atom-blueprint.md` per atom, honoring `state.json.mode`:
   - `tdd` mode: atom contains the full test code (RED) and implementation code (GREEN).
   - `normal` mode: atom contains implementation code plus the tests that must exist before
     validation.
   Code blocks are COMPLETE — no `...`, no "similar to above", no TODO placeholders.
4. Register each atom in `state.json.atoms` with `status: "DRAFT"`, its phase, and file path.
5. Atoms within a phase are ordered by dependency; note cross-atom dependencies explicitly in
   each atom's header.
6. Present the list (id, name, one-line purpose). Remind: `review-atom atom-NN` refreshes and
   readies an atom; `implement atom-NN` needs the atom READY first.

## Example

> **User:** create atoms for phase-01
> **Agent:** `nextAtom` is 1 → writes `docs/atoms/phase-01/atom-01-project-scaffold.md`,
> `atom-02-db-schema-tasks.md`, `atom-03-health-endpoint.md` (each with complete test +
> implementation code) → `nextAtom` = 4 → "3 atoms created (DRAFT). Start with
> `review-atom atom-01`." Later, phase-02 atoms continue at atom-04.
