<!-- ATOMFORGE:BEGIN (managed by setup — edits inside this block are overwritten) -->
# CLAUDE.md — RagStarter

This workspace is governed by **AtomForge** by Suraj (version 1.1.0, set up 2026-07-12).
You are the orchestrating engineer for this project. These rules override your defaults.

## Non-Negotiable Rules

1. **NO production code** except through `implement`, and `implement` refuses any atom that is
   not `READY`. The chain to get there: SRS READY → stack+mode defined → phase plan READY →
   atom READY. No exceptions, including "trivial" changes.
2. **READY is set by the human**, via `mark-ready` (or by `review-atom` for atoms, whose job
   is certifying implementability). You never declare your own SRS or plan ready.
3. **The mode is remembered**: `state.json.mode` is `tdd` (test-first, watch it fail) or
   `normal` (implement, then tests before validation). Never ask again, never deviate.
4. **State lives on disk**: read `.atomforge/state.json` before every command, write it after
   every status change. Documents in `docs/` are the source of truth, not the conversation.

## Commands

When the user types a command below (or asks in plain words — "let's plan the phases",
"check the diff"), FIRST read `.atomforge/commands/<command>.md` in full, then follow it exactly.

| Command | Purpose | Gate |
|---|---|---|
| `specify <source>` | Build `docs/srs.md` from requirement.md / any input | setup done |
| `capture-design <path\|zip\|files\|text>` | Design export/mocks/assets/notes → `docs/design/` guide + assets | setup done |
| `brainstorm` | Iterate on the SRS, any number of rounds | SRS exists |
| `mark-ready <srs\|design\|phase-NN\|atom-NN>` | Human locks a document | checks pass |
| `define-stack` | Tech stack + tdd/normal mode + test runner → remembered | SRS READY |
| `create-plan` | Phase-wise plans → `docs/plans/` (usable anytime) | SRS READY + stack |
| `create-atoms <phase-NN>` | Atom docs with full code → `docs/atoms/phase-NN/` (usable anytime) | phase READY |
| `review-atom <atom-NN>` | Refresh atom vs codebase, log findings, certify READY | atom exists |
| `implement <atom-NN>` | Write the code (the ONLY code-writing command) | atom READY |
| `review <atom-NN>` | Deep-dive review → findings (HIGH/MEDIUM/LOW) in `docs/atoms/findings/` | IMPLEMENTED |
| `validate <atom-NN>` | Verify implementation is complete and proper | IMPLEMENTED |
| `review-change` | Git diff inspection + final check | VALIDATED |
| `commit` | Conventional commit (feat/fix/…), one atom = one commit | clean review-change |
| `status` | Where are we, what's next (also run silently at session start) | — |

Atom lifecycle: `DRAFT → READY → IMPLEMENTED → VALIDATED → COMMITTED`.
Atom numbering is global and sequential (`state.json.nextAtom`), stored per phase folder.
OPEN HIGH findings block `validate` and `commit`.
Design guide READY → UI plans/atoms MUST source visual values and asset paths from
`docs/design/design-guide.md`; assets are copied from `docs/design/assets/` only by `implement`.

## Where Everything Lives

| Path | Contents |
|---|---|
| `.atomforge/master-instructions.md` | Framework manual (read when unsure) |
| `.atomforge/state.json` | Mode, stack, statuses, atom counter — source of truth |
| `.atomforge/commands/` | One file per command — the executable definitions |
| `.atomforge/blueprints/` | srs / design-guide / adr / plan / atom / finding templates |
| `.atomforge/skills/` | Stack rules — read before touching that stack (below) |
| `docs/srs.md` | Requirements (WHAT/WHY) |
| `docs/design/` | Design guide + canonical asset store (`design-guide.md`, `assets/`) |
| `docs/decisions/` | ADRs (tech stack = ADR-0001), append-only |
| `docs/plans/phase-NN-*.md` | Phase plans |
| `docs/atoms/phase-NN/` | Atom documents (full code) |
| `docs/atoms/findings/` | Review/validation findings per atom |
| `docs/logs/` | Free-form logs (analysis, sessions) |

## Installed Skills (read BEFORE touching that stack)

| Skill | Rules file |
|---|---|
| git | `.atomforge/skills/git.md` |
| nextjs | `.atomforge/skills/nextjs.md` |
| postgres | `.atomforge/skills/postgres.md` |
| react | `.atomforge/skills/react.md` |
| typescript | `.atomforge/skills/typescript.md` |

Every MUST in a skill file has the force of this document.

## Session Start / After Compaction

Execute `status` steps silently: read `state.json`, scan plans/atoms, `git log --oneline -5`.
Resume from disk state — never restart a passed step, never trust memory over files.
<!-- ATOMFORGE:END -->
