# Skill: postgres

Category: database · Oracle: migrations run clean up AND down on a scratch DB
When to use: read before any schema change, new query, index decision, or raw SQL.

## Migration Workflow

- All schema changes via the stack's migration tool; hand-run DDL on shared environments is
  forbidden. One migration = one concern, with a working `down` or a documented irreversibility
  note.
- Never edit a shipped migration — supersede with a new one.
- Zero-downtime discipline on live tables: add columns as NULLable (or with DEFAULT on PG 11+,
  which is metadata-only), backfill in batches, then add constraints
  `NOT VALID` → `VALIDATE CONSTRAINT`. Create indexes `CONCURRENTLY` (outside the migration
  transaction — mark the migration non-transactional).
- Destructive changes require an Accepted ADR + two-phase rollout.

## Mandatory Indexing Checks

1. Every FK column indexed explicitly (Postgres does NOT auto-index FKs).
2. WHERE/JOIN/ORDER BY columns of new queries covered or consciously excluded in writing.
3. Right index type for the job: btree default; GIN for jsonb/array/full-text; partial indexes
   for skewed predicates (`WHERE deleted_at IS NULL`); covering `INCLUDE` where it kills a
   heap fetch.
4. `EXPLAIN (ANALYZE, BUFFERS)` the feature's hot queries; seq scan on a growing table is a
   blocker unless justified in the PR.

## Schema Rules

- Types: `text` over varchar(n) unless a real constraint exists; `timestamptz` always (UTC);
  `numeric` for money; `jsonb` never as a substitute for columns you query relationally.
- Identity: `BIGINT GENERATED ALWAYS AS IDENTITY` or UUIDv7; enums via CHECK constraints or
  lookup tables (native enums need an ADR — they're painful to alter).
- Constraints are the last line of defense: NOT NULL, FK, UNIQUE, CHECK at the DB level even if
  the app validates too.
- snake_case everywhere; no quoted camelCase identifiers.

## Raw Query Isolation

- Raw SQL only in the repository/data layer, named and parameterized (`$1`, bound params).
  Interpolated SQL strings are a security blocker.
- Each raw query documents why the ORM couldn't express it; prefer CTEs over nested subqueries
  for readability.

## Testing

- Migration CI: up from zero + down, on a scratch DB. Behavior tests against real Postgres
  (Testcontainers/docker), never SQLite stand-ins — dialects differ where it hurts.
