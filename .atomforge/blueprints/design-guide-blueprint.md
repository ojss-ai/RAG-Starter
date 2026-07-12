# Design Guide — {{PROJECT_OR_FEATURE_NAME}}

- Status: IN-PROGRESS | READY
- Date: {{DATE}}  <!-- Reopened: <date> — <reason> (if ever) -->

> RULES: This document is the single source of truth for the project's visual design. Every
> value states its provenance (source file, "approximate — from mock", or "stated by user")
> and is NEVER invented. Assets referenced here live under `docs/design/assets/` — the
> canonical store; only `implement` copies them into the app source tree. When
> `state.json.design.status` is READY, every UI-touching plan and atom MUST source visual
> values and asset paths from this guide.

## 1. Source & Provenance

| Provided | Kind | When | Capture run |
|---|---|---|---|
| {{e.g. my-site-design.zip (claude.ai/design export)}} | export | {{DATE}} | 1 |

## 2. Brand & Logo

| File | Variant | Usage notes |
|---|---|---|
| `docs/design/assets/logo/{{logo.svg}}` | {{primary / dark / favicon}} | {{where/how used}} |

## 3. Color Palette

| Token | Value | Role | Source |
|---|---|---|---|
| {{--color-primary}} | {{#E91E63}} | {{primary actions, links}} | {{assets/css/styles.css}} |

## 4. Typography

| Token | Value | Usage | Source |
|---|---|---|---|
| {{font-family-base}} | {{Inter, sans-serif}} | {{body text}} | {{assets/css/styles.css}} |

Scale: {{e.g. 12 / 14 / 16 / 20 / 24 / 32 / 48}} · Weights: {{400 / 600 / 700}} ·
Font files: {{assets/fonts/… or external link}}

## 5. Spacing & Layout

- Spacing scale: {{e.g. 4 / 8 / 16 / 24 / 32 / 64}}
- Grid / max content width: {{…}}
- Breakpoints: {{e.g. 640 / 768 / 1024 / 1280}}
- Radii: {{…}} · Shadows: {{…}}

## 6. Components

One subsection per recurring pattern observed (nav, hero, cards, buttons, forms, footer, …):

### {{Component name}}

- Description: {{structure and behavior in 1–3 lines}}
- Reference: {{stored file + selector, e.g. `assets/css/styles.css` `.card`}}

## 7. Page Blueprints

One subsection per page in the provided design:

### {{Page name}}

- Layout: {{sections in order, column structure}}
- Components used: {{nav, hero, card grid, footer}}
- Reference: {{e.g. `assets/pages/index.html` or mock image path}}

## 8. Assets Inventory

Every file under `docs/design/assets/`. `mark-ready design` verifies each path exists.

| Path | Type | Purpose | Source |
|---|---|---|---|
| `docs/design/assets/logo/{{logo.svg}}` | logo | {{brand mark}} | {{export}} |
| `docs/design/assets/css/{{styles.css}}` | stylesheet | {{canonical design CSS}} | {{export}} |

## 9. Open Questions

| # | Question | Blocking? | Resolution |
|---|---|---|---|
| 1 | {{e.g. CSS says #E91E63 but the notes say "pink" — which wins?}} | yes/no | … |

All blocking questions MUST be resolved before the guide can be marked READY.

## 10. Capture Log (append-only)

| Date | Inputs processed | Sections touched |
|---|---|---|
| {{DATE}} | {{export zip}} | {{all}} |

## 11. Readiness

- [ ] User ran `mark-ready design` (status set by that command only — never by the author)
