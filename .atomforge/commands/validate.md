# Command: validate

Trigger: "validate", "validate implement", "check it's implemented properly".
Gate: atom status `IMPLEMENTED`. Repeatable.
Purpose: independent verification that the atom is FULLY and PROPERLY implemented.

## Steps

1. Re-read the atom document fresh, then verify each claim against reality:
   - Every file the atom says it creates/modifies actually contains the specified behavior.
   - Run `state.json.testRunner` — full suite green, and the atom's own tests exist and pass.
   - Every verification step listed in the atom executes successfully — actually run them.
   - Acceptance scenarios for the traced FRs hold.
   - No `OPEN` HIGH findings in `docs/atoms/findings/atom-NN-*.md`.
2. Outcome:
   - **All pass** → set atom status `VALIDATED` (doc + state.json); log the validation run
     (date, suite result, checks) in the atom's `## Implementation Log`. Next: `review-change`.
   - **Anything fails** → status stays `IMPLEMENTED`. Log each failure as a finding in the
     atom's findings file (severity per impact), report to the user, and ASK how to proceed
     (fix now via `implement`, or accept-with-reason). Never quietly patch code from this
     command — validation only observes.

## Example

> **User:** validate atom-02
> **Agent:** re-runs every atom verification step → `npm test` green ✓ → atom's own tests
> exist ✓ → findings file has no OPEN HIGH ✓ → `VALIDATED`, run logged. "Next:
> `review-change`." (Had a check failed: finding logged, status stays IMPLEMENTED, user asked.)
