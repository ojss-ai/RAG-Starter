# Skill: typescript

Category: backend (applies anywhere TS is used) · Test runner: `npm test`
When to use: read before writing ANY TypeScript — types are the contract, these rules define it.

## Compiler Configuration (mandatory tsconfig flags)

```jsonc
{
  "compilerOptions": {
    "strict": true,                       // non-negotiable
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "verbatimModuleSyntax": true
  }
}
```

Weakening any of these flags requires an Accepted ADR.

## Type Rules

- `any` is forbidden. Unknown input is `unknown`, then narrowed with type guards or a schema
  validator (e.g. zod) at the boundary.
- `as` casts: only for provably-safe narrowing with an inline comment; `as unknown as X` is a
  review blocker.
- `// @ts-ignore` is forbidden; `// @ts-expect-error` requires a reason string.
- Domain values get branded/opaque types or enums-as-const — no bare `string` for ids, emails,
  money. `interface` for object shapes, `type` for unions/compositions.
- All exported functions have explicit return types. `null` vs `undefined`: pick one for
  "absent" per codebase (default: `undefined`) and never mix.
- Model failure in signatures: return discriminated unions / Result types for expected errors;
  throw only for programmer errors.

## Structure

- ES modules; no `namespace`. Path aliases via tsconfig `paths`, no deep `../../..` imports.
- Side-effect-free modules; entrypoints are the only place wiring happens.

## Testing

- Type-level regressions guarded with `expect-type`/`tsd` style assertions where types ARE the
  contract. `tsc --noEmit` runs in the test gate — a type error is a failing test.

## Formatting

- Prettier defaults, ESLint `@typescript-eslint` recommended-type-checked. Errors, not warnings.
