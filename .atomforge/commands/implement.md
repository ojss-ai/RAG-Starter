# Command: implement

Trigger: "implement atom-03", "implement", "write the code", "okay fix it" (after a review).
Gate: atom `Status: READY` — refuse otherwise and point to `review-atom`.
This is the ONLY command that writes production code.

## Steps

1. Read `.atomforge/state.json`, the atom document in full, and the relevant skill files for
   every stack this atom touches. Skill-file MUSTs are binding.
2. Execute per `state.json.mode`:

   **tdd mode** — RED → GREEN → REFACTOR:
   a. Write the test exactly as the atom specifies. Run `state.json.testRunner`.
   b. It MUST fail for the expected reason. Paste the failure output into the atom's
      `## Implementation Log`. If it passes, STOP — the test is wrong or the feature exists.
   c. Write the minimal implementation. Run the suite: new test green, nothing else broken.
   d. Refactor only what this atom dirtied; suite stays green.

   **normal mode**:
   a. Write the implementation as the atom specifies.
   b. Write/extend the tests listed in the atom. Run `state.json.testRunner` — full suite green.

3. Fix-cycles (arriving from `review` / `validate` findings): implement ONLY the findings the
   user approved, reference the finding ids in the log, and update the findings file status
   (`APPROVED` → `FIXED`).
4. Log everything in the atom's `## Implementation Log`: `<date> — files touched — tests run —
   result — deviations from the atom (if any, with reason)`.
5. If reality forces a deviation from the atom's code, UPDATE the atom document to match what
   was actually built (the atom stays truthful), and note the deviation in the log.
6. Set atom status → `IMPLEMENTED` (doc + state.json). Do NOT commit — that is the `commit`
   command, after review and validation.

## Example (tdd mode)

> **User:** implement atom-02
> **Agent:** writes `migrations/001-tasks.test.ts` → `npm test` → FAILS
> ("relation tasks does not exist" — pasted into Implementation Log) → writes the migration →
> suite green → no refactor needed → status `IMPLEMENTED`. "Not committed yet — next:
> `review atom-02` or `validate atom-02`."
