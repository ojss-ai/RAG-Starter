# atom-{{NN}}-{{short-name}}

- Status: DRAFT | READY | IMPLEMENTED | VALIDATED | COMMITTED
- Phase: phase-{{NN}}-{{name}} (`docs/plans/phase-{{NN}}-{{name}}.md`, item §{{x}})
- Traces: FR-{{n}}, NFR-{{n}}
- Depends on: atom-{{MM}} (or "none")
- Mode: tdd | normal (from state.json — do not choose per atom)
- Created: {{DATE}}

> RULES: An atom is one small, independently implementable and testable unit. Code blocks are
> COMPLETE — no `...`, no "similar to above", no TODOs. Exact paths only. If it doesn't fit in
> one sitting, split it before marking READY.

## Purpose

1–3 sentences: what exists after this atom that didn't before.

## Files

| Path | Action |
|---|---|
| `exact/path/file.ts` | create / modify |
| `exact/path/file.test.ts` | create / modify |

## Tests ({{tdd: write & fail FIRST | normal: must exist before validate}})

```{{lang}}
// complete test code — runnable as-is
```

Expected first run ({{tdd mode}}): FAILS with `{{exact expected failure}}`

## Implementation

```{{lang}}
// complete implementation code — runnable as-is
```

Notes: only what a junior implementer would trip on (gotchas, ordering, imports).

## Verification

1. Run `{{testRunner}}` → full suite green.
2. {{observable check: command + expected output, endpoint + expected response, UI state}}

## Review Log

<!-- review-atom appends here: <date> — finding — action taken -->

## Implementation Log

<!-- implement/validate append here: <date> — files touched — tests run — result — deviations -->
