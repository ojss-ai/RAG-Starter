# Command: capture-design

Trigger: "capture-design <path | zip | files | description>", "capture the design",
"here is my design export", "use this mock/logo/brand css".
Input: any mix of — a claude.ai/design export (extracted folder or zip), mock images
(PNG/JPG), loose asset files (logo, brand CSS, palette doc, fonts), or a written description
of the desired look. Gate: setup complete. Independent of the SRS — usable before or after
`specify`. Output: `docs/design/design-guide.md` + assets under `docs/design/assets/`.

## Steps

1. Read `.atomforge/state.json`. If `design.status` is `READY`, warn the user that the guide
   is locked and ask whether to reopen (reopening sets status back to `IN-PROGRESS` and logs
   `Reopened: <date> — <reason>` in the guide header).
2. Classify each input: (a) export folder, (b) zip archive, (c) mock image(s), (d) loose
   asset file(s), (e) written description. Multiple inputs in one run are fine. If a given
   path does not exist, name it and stop.
3. Zip → extract to a TEMP directory (never into the project), then treat as (a). If the
   archive is unreadable, report it and ask for the extracted folder instead.
4. Run the analysis per the `design-capture` agent definition: in Claude Code dispatch the
   `design-capture` subagent (`.claude/agents/design-capture.md`); in any other harness
   execute the same procedure inline (the agent file is the procedure).
5. Write or merge `docs/design/design-guide.md` from
   `.atomforge/blueprints/design-guide-blueprint.md`, and copy every provided/extracted
   asset into `docs/design/assets/{logo,css,images,fonts}/`. Every copied file gets a row
   in the guide's Assets Inventory. Values derived from images only are flagged
   `(approximate — from mock)`. Conflicting inputs become Open Questions — never pick
   silently, never discard previously captured values.
6. Set `state.json.design = { "file": "docs/design/design-guide.md",
   "status": "IN-PROGRESS", "sources": [<input kinds>] }` and append a Capture Log entry
   (date · inputs processed · sections touched).
7. Present the guide section by section (≤ 40 lines per chunk). Remind: iterate by
   re-running `capture-design` with more inputs; lock with `mark-ready design`. Once READY,
   every UI-touching plan and atom MUST source visual values and asset paths from this guide.

## Rules

- This command writes ONLY under `docs/design/` and `state.json`. It never touches source
  code — atoms copy assets into the app tree during `implement`.
- Re-runs merge: update the relevant sections, append to the Capture Log, keep history.
- Unknowns go to Open Questions, never invented. Two inputs disagree → record both.

## Example

> **User:** capture-design C:\Downloads\my-site-design.zip
> **Agent:** extracts zip to temp → parses 3 HTML pages + styles.css → design guide with
> 9 color tokens, type scale, 6 components, 3 page blueprints → copies `logo.svg`,
> `styles.css`, 4 images into `docs/design/assets/` → `state.json.design = IN-PROGRESS` →
> presents the guide → "Add more inputs by re-running `capture-design`; lock with
> `mark-ready design`."
