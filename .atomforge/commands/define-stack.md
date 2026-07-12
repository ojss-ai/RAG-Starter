# Command: define-stack

Trigger: "define stack", "set the tech stack", "we'll use X and Y", or automatically required
before `create-plan` when `state.json.mode` or `state.json.stack` is empty.
Gate: SRS is READY (stack decisions belong after requirements are stable).

## Steps

1. Read `.atomforge/state.json` and `docs/srs.md`.
2. **Stack**: if the SRS declared a stack, present it for confirmation. Otherwise ask the user
   (frontend? backend? database? — one question, multi-part). For an existing codebase, the
   detected stack from `docs/codebase-analysis.md` is the default.
3. **Mode**: ask the user to choose exactly one — this choice is remembered for the whole project:
   - `tdd` — every atom is implemented test-first (RED → GREEN → REFACTOR, failure captured).
   - `normal` — implementation first, tests written in the same atom before it can validate.
4. **Test runner**: derive from the stack (`npm test`, `php artisan test`, `mvn test`, …),
   confirm with the user, store in `state.json.testRunner`.
5. Write `state.json`: `stack`, `mode`, `testRunner`.
6. Record the decision as an ADR: instantiate `.atomforge/blueprints/adr-blueprint.md` →
   `docs/decisions/ADR-0001-tech-stack.md` (or next free number) with the options considered.
7. Check `.atomforge/skills/`: if the chosen stack has no matching skill file installed, tell
   the user which skills the framework offers and that they can re-run setup to add them.

## Rules

- Changing stack or mode later = new superseding ADR + explicit user confirmation; existing
  READY plans/atoms affected must be flagged for re-review.

## Example

> **User:** define-stack
> **Agent:** "SRS §8 declares TypeScript + Postgres — confirm? Which backend framework?" →
> user: Express → "TDD or normal mode?" → user: TDD → writes `state.json`
> (stack/mode/testRunner) + `docs/decisions/ADR-0001-tech-stack.md` → "Remembered. Next:
> `create-plan`."
