# SRS — {{PROJECT_OR_FEATURE_NAME}}

- Status: IN-PROGRESS | READY
- Source: {{requirement.md | chat description | other input — the SRS supersedes it}}
- Date: {{DATE}}  <!-- Reopened: <date> — <reason> (if ever) -->

> RULES: This document describes WHAT and WHY only. Requirements never name frameworks,
> libraries, file paths, schemas, or algorithms — declared technology goes ONLY in §8. Every
> requirement gets a stable ID (`FR-#`, `NFR-#`) and MUST be independently testable. Removed
> requirements are ~~struck through~~ with a date, never deleted — the SRS is also history.

## 1. Problem Statement

One paragraph: who hurts, how, and what changes when this ships.

## 2. In Scope / Out of Scope

| In scope | Out of scope (explicitly) |
|---|---|
| … | … |

## 3. Actors

| Actor | Description |
|---|---|
| … | … |

## 4. Functional Requirements

| ID | Requirement (imperative, testable) | Priority |
|---|---|---|
| FR-1 | The system MUST … | MUST |
| FR-2 | The system MUST … | MUST |
| FR-3 | The system SHOULD … | SHOULD |

## 5. Non-Functional Requirements

| ID | Requirement | Measure |
|---|---|---|
| NFR-1 | … | e.g. p95 < 200ms |

## 6. Acceptance Scenarios (Given / When / Then)

```gherkin
Scenario: FR-1 happy path
  Given …
  When …
  Then …

Scenario: FR-1 failure path
  Given …
  When …
  Then …
```

Every FR MUST appear in at least one scenario, including one failure/edge scenario.

## 7. Open Questions

| # | Question | Blocking? | Resolution |
|---|---|---|---|
| 1 | … | yes/no | … |

All blocking questions MUST be resolved before the SRS can be marked READY.

## 8. Tech Stack (declared)

Only if the requirement source or the user declared technology choices; otherwise "To be
decided via define-stack". This section is informational — `define-stack` confirms it into
`state.json` and an ADR.

| Layer | Choice |
|---|---|
| … | … |

## 9. Readiness

- [ ] User ran `mark-ready srs` (status set by that command only — never by the author)
