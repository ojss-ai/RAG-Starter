# Command: specify

Trigger: "specify", "specify design", "build the SRS from <file/description>"
Input: a requirement source — `requirement.md`, any file the user points to, or plain
description in chat. Gate: setup complete. Output: `docs/srs.md`.

## Steps

1. Read `.atomforge/state.json`. If `srs.status` is `READY`, warn the user that the SRS is
   locked and ask whether to reopen it (reopening sets status back to `IN-PROGRESS`).
2. Read the requirement source in full. If the user gave only a vague sentence, ask up to 3
   targeted questions (purpose, actors, success criteria) before drafting — otherwise draft first.
   If the source is design material (a design export, mocks, logo/CSS files, or purely visual
   requirements), point the user to `capture-design` — that content belongs in the design
   guide, not the SRS. The SRS stays WHAT/WHY; functional requirements extracted from a
   design ("the site MUST have a pricing page") still belong here.
3. Instantiate `.atomforge/blueprints/srs-blueprint.md` → `docs/srs.md`:
   - Fill every section. Requirements are testable, numbered `FR-#` / `NFR-#`.
   - WHAT and WHY only. If the source names technologies, capture them in the SRS
     "Tech Stack (declared)" section — do not scatter tech through requirements.
   - Unknowns go to Open Questions, never invented.
4. Set `state.json.srs.status = "IN-PROGRESS"`. If the source declared a tech stack, also
   record it in `state.json.stack` (define-stack will confirm later).
5. Present the draft section by section (≤ 40 lines per chunk).
6. Tell the user: iterate with `brainstorm`, lock with `mark-ready srs`. The original
   requirement file is theirs — they may delete it or keep it; `docs/srs.md` is now the
   source of truth and must never reference the original file's path.

## Example

> **User:** specify requirement.md
> **Agent:** reads the file → drafts `docs/srs.md` with FR-1…FR-8, scenarios, 2 open
> questions → presents section by section → "Iterate with `brainstorm`; lock with
> `mark-ready srs`."
