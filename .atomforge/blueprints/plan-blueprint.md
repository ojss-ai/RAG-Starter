# phase-{{NN}}-{{short-name}}

- Status: IN-PROGRESS | READY
- Inputs: `docs/srs.md` (READY), ADRs: {{ADR-0001 …}}
- Stack: {{from state.json}} · Mode: {{tdd | normal}}
- Depends on: phase-{{MM}} (or "none")
- Created: {{DATE}}  <!-- Reopened: <date> — <reason> (if ever) -->

> RULES: A phase is a shippable, testable slice. This document says HOW at phase granularity;
> the atoms carry the actual code. Every item traces to FR/NFR ids; every design element that
> traces to nothing gets deleted (YAGNI). Skill-file MUSTs are binding on everything here.

## 1. Goal

≤ 5 sentences: what is true about the system when this phase is done.

## 2. Scope

| In this phase | Deferred to phase |
|---|---|
| FR-{{n}}, FR-{{m}} | FR-{{x}} → phase-{{NN}} |

## 3. Work Breakdown

| # | Item (imperative) | Traces | Files/areas touched | Future atom? |
|---|---|---|---|---|
| {{NN}}.1 | … | FR-{{n}} | `src/…` | yes |
| {{NN}}.2 | … | NFR-{{n}} | `db/migrations` | yes |

## 4. Data & Schema Changes

Migrations, new tables/columns/indexes. "None" if none.

## 5. Risks & Edge Cases

| Risk / edge case | Traces | Mitigation / behavior |
|---|---|---|
| … | … | … |

## 6. Test Strategy

Runner: `{{testRunner}}`. What gets unit vs integration vs e2e coverage in this phase; how the
phase's Definition of Done is verified.

## 7. Definition of Done

- [ ] Every item in §3 delivered by a COMMITTED atom
- [ ] Full suite green; no OPEN HIGH findings across this phase's atoms
- [ ] {{phase-specific observable outcome}}
