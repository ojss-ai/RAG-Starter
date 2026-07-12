# Skill: react

Category: frontend · Test runner: `npm test` (Vitest/Jest + React Testing Library)
When to use: read before planning or writing ANY React component, hook, or test.

## Setup

- Function components ONLY. Class components are forbidden (including error boundaries — use
  a library or a single documented exception with an ADR).
- TypeScript strict mode required (see typescript skill if installed; its rules stack with these).
- Structure by feature, not by kind: `src/features/<feature>/{components,hooks,api,types}.ts*`.
  A `src/components/` dir holds only truly shared, dumb UI atoms.

## Component Rules

- Components are presentational by default: props in, JSX out. Data fetching, subscriptions,
  and business logic live in custom hooks (`useXxx`), one hook per file.
- MUST NOT: business logic in JSX, `useEffect` for derived state (compute during render),
  prop drilling beyond 2 levels (lift to context or composition), default exports
  (named exports only), inline object/array literals passed to memoized children.
- State: local `useState` first; context for cross-cutting read-mostly values; a dedicated
  store (per ADR) only when justified in writing.
- Every list item needs a stable `key` derived from data, never the array index.

## Hooks

- Custom hooks MUST be pure orchestration: call other hooks, return a typed object.
- Exhaustive deps always; disabling `react-hooks/exhaustive-deps` requires an inline comment
  citing the reason.

## Testing (RTL)

- Test behavior via roles/labels (`getByRole`, `getByLabelText`) — never by class or test-id
  unless no accessible query exists.
- One behavior per test; mock at the network boundary (MSW or fetch mock), never mock child
  components except at explicit architectural seams.
- Snapshot tests are forbidden as primary assertions.

## Formatting

- Prettier defaults; ESLint with `eslint-plugin-react-hooks` errors (not warnings).
