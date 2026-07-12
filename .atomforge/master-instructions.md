# AtomForge Master Instructions

> The framework manual. The workspace `CLAUDE.md` is a router; the files in
> `.atomforge/commands/` are the executable command definitions; THIS file holds the shared
> protocol they all assume. Precedence: commands/<cmd>.md > this file > CLAUDE.md defaults.
> Version: 1.0.0 · AtomForge by Suraj

## 1. Protocol (applies to every command)

1. Read `.atomforge/state.json` FIRST. Never trust conversational memory about statuses,
   mode, or stack.
2. Before executing any command, read `.atomforge/commands/<command>.md` in full — even if
   you think you remember it.
3. After any status change, write `state.json` back to disk immediately AND update the
   `Status:` line in the affected document. The two must never disagree; if they do, the
   document wins and state.json gets corrected.
4. READY is human-granted (via `mark-ready`), with one exception: `review-atom` may set an
   atom READY because certifying implementability is its defined job.
5. Only read `.atomforge/skills/<skill>.md` when working on that stack — but then it is binding.
6. If `.atomforge/` is missing or `state.json` is corrupt, STOP and tell the user to re-run
   setup (BOOTSTRAP.md in the framework folder).

## 2. State Model (`.atomforge/state.json`)

```json
{
  "framework": "atomforge",
  "version": "1.0.0",
  "setupDate": "2026-07-10",
  "mode": "tdd",
  "stack": ["nextjs", "postgres"],
  "testRunner": "npm test",
  "srs": { "file": "docs/srs.md", "status": "READY" },
  "design": { "file": "docs/design/design-guide.md", "status": "IN-PROGRESS",
    "sources": ["claude.ai-design-export", "logo-file"] },
  "plans": {
    "phase-01-foundation": "READY",
    "phase-02-features": "IN-PROGRESS"
  },
  "nextAtom": 6,
  "atoms": {
    "atom-01-user-model": { "phase": "phase-01", "status": "COMMITTED",
      "file": "docs/atoms/phase-01/atom-01-user-model.md" },
    "atom-05-login-api": { "phase": "phase-02", "status": "IMPLEMENTED",
      "file": "docs/atoms/phase-02/atom-05-login-api.md",
      "findings": "docs/atoms/findings/atom-05-login-api.md" }
  }
}
```

- `mode` ∈ `tdd | normal` — set once by `define-stack`, remembered forever.
- `srs.status` ∈ `NONE | IN-PROGRESS | READY`.
- `design.status` ∈ `NONE | IN-PROGRESS | READY` — written by `capture-design`. Absent or
  `NONE` = the project has no design guide; nothing downstream changes.
- Plan statuses ∈ `IN-PROGRESS | READY`.
- Atom statuses ∈ `DRAFT | READY | IMPLEMENTED | VALIDATED | COMMITTED` (monotonic; only
  `review-atom` may demote READY → DRAFT on drift).
- `nextAtom` is the global atom counter — read, assign, increment, write. Numbers are never
  reused, even for deleted atoms.

## 3. The Pipeline

```
setup (BOOTSTRAP.md)
  ├─ capture-design <export|zip|mocks|assets|text> ──► docs/design/design-guide.md
  │    (optional, any time; re-runnable) └─ mark-ready design ──► [READY]
  └─ specify <source> ──► docs/srs.md [IN-PROGRESS]
       └─ brainstorm (×N rounds, human iterates freely)
            └─ mark-ready srs ──► [READY]
                 └─ define-stack ──► state: stack, mode(tdd|normal), testRunner + ADR-0001
                      └─ create-plan ──► docs/plans/phase-NN-*.md [IN-PROGRESS]
                           └─ mark-ready phase-NN ──► [READY]
                                └─ create-atoms phase-NN ──► docs/atoms/phase-NN/atom-MM-*.md [DRAFT]
                                     └─ per atom:
                                        review-atom ──► [READY]        (repeatable)
                                        implement   ──► [IMPLEMENTED]  (only code writer)
                                        review      ──► findings H/M/L (repeatable)
                                        validate    ──► [VALIDATED]
                                        review-change ──► diff verdict
                                        commit      ──► [COMMITTED]
```

`create-plan` and `create-atoms` are usable at ANY point of development — they extend and
revise; they never silently rewrite READY documents.

## 4. Gate Matrix

| Command | Requires |
|---|---|
| specify | setup complete |
| capture-design | setup complete (independent of the SRS) |
| brainstorm | `docs/srs.md` exists |
| define-stack | SRS READY |
| create-plan | SRS READY + stack + mode set |
| create-atoms X | plan X READY |
| review-atom | atom exists |
| implement | atom READY (fix-cycles: user-approved findings) |
| review / validate | atom IMPLEMENTED |
| review-change | atom VALIDATED (advisory — runnable anytime) |
| commit | VALIDATED + clean review-change; no OPEN HIGH findings |

When a gate fails: name the unmet gate, name the command that satisfies it, stop.

**Design guide (advisory, binding once READY):** if `design.status` is `READY`, any plan or
atom that touches UI MUST source visual values (colors, fonts, spacing, radii, shadows) and
asset paths from `docs/design/design-guide.md`. A hardcoded visual value or asset not
traceable to the guide is a review finding (MEDIUM). Assets are copied from
`docs/design/assets/` into the app tree only by `implement`, via explicit copy steps in the
atom. Projects without a design guide are unaffected.

## 5. Findings Protocol (shared by review / validate)

- File: `docs/atoms/findings/atom-NN-<short-name>.md` (finding-blueprint). Append-only runs.
- Severity: HIGH (blocks validate+commit while OPEN) / MEDIUM / LOW.
- Status flow: `OPEN` → user approves → `APPROVED` → fixed via `implement` → `FIXED`;
  or user declines → `WONT-FIX <reason>`.
- Findings are proposals. No command except `implement` changes production code, and
  `implement` only fixes APPROVED findings.

## 6. Mode Semantics

- **tdd**: per atom — write test, run `testRunner`, MUST fail for the expected reason
  (capture output in the atom's Implementation Log), minimal implementation, suite green,
  refactor, still green. Code written before its test is deleted.
- **normal**: per atom — implement, then write the atom's listed tests; `validate` refuses if
  the tests don't exist or don't pass. The suite must be green before review-change.
- Both modes: never weaken, skip, or focus tests to get green; baseline pre-existing failures
  (existing codebases) are recorded in `docs/codebase-analysis.md` and must not grow.

## 7. Recovery After Compaction / New Session

Silently run the `status` command's read steps: `state.json` → active plans/atoms → last 5
git log lines. Resume from what disk says. Never restart a passed step; never re-ask the
mode or stack.
