# Skill: nextjs

Category: frontend · Test runner: `npm test` (unit) + `npm run test:e2e` (Playwright, if configured)
When to use: read before touching anything under `app/`, server actions, or route handlers.
Install together with the react skill — its rules apply on top.

## Setup

- **App Router ONLY** (`app/` directory). The `pages/` router is forbidden for new code; if the
  repo has `pages/`, record a migration ADR before mixing.
- All react-skill rules apply on top of these (install both skills together).

## Server/Client Boundary

- Components are Server Components by default. Add `"use client"` ONLY when the component needs
  state, effects, browser APIs, or event handlers — and push that directive as far down the
  tree as possible (leaf-first).
- Data fetching happens in Server Components / route handlers / server actions — never
  `useEffect`+`fetch` for initial data.
- Mutations go through Server Actions or route handlers (`app/api/**/route.ts`); validate all
  input server-side regardless of client validation.
- Secrets and privileged SDK calls exist ONLY in server files. Anything imported by a client
  component is public. Env vars exposed to the client MUST be prefixed `NEXT_PUBLIC_`.

## Custom Hooks (client side)

- Strict custom-hook discipline: every non-trivial piece of client logic is a `useXxx` hook in
  `src/features/<feature>/hooks/`. Components stay declarative.

## Routing & Files

- Route segment files limited to their Next.js role: `page.tsx` composes, `layout.tsx` wraps,
  `loading.tsx`/`error.tsx` for states. Business logic lives outside `app/`.
- Use `next/link` and `next/image` — raw `<a>` (internal) and `<img>` are lint errors.
- Metadata via the Metadata API (`export const metadata` / `generateMetadata`), not manual `<head>`.

## Rendering & Caching

- Choose and DOCUMENT per route: static / revalidated (`revalidate`) / dynamic. An undocumented
  `force-dynamic` is a review blocker.

## Testing

- Unit-test hooks and server actions directly; e2e-test route behavior with Playwright.
- Server Components are tested through route-level tests, not shallow rendering.
