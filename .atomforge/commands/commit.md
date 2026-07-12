# Command: commit

Trigger: "commit", "commit this", "generate the commit".
Gate: atom `VALIDATED` + `review-change` verdict clean (if the user insists on committing
anyway, warn once, then obey — record the override in the atom's log).

## Steps

1. Run `git status` + `git diff` to derive the message from what ACTUALLY changed — never
   from memory.
2. Build the message per Conventional Commits:
   - Format: `type(scope): subject [atom-NN]`
   - `type` ∈ `feat | fix | test | refactor | docs | chore | perf | build`
   - `scope`: the dominant module/area; subject: imperative, lowercase, ≤ 72 chars, no period.
   - Breaking change → `type(scope)!:` + `BREAKING CHANGE:` footer.
   - Body (when the diff isn't self-evident): 1–3 bullets of WHY.
3. Show the proposed message to the user for approval before committing.
4. On approval:
   - `git add <explicit paths only>` (the atom's files + its updated docs). `git add .` is
     forbidden.
   - Commit. One atom = one commit; never bundle atoms.
5. Set atom status `COMMITTED` (doc + state.json). Report the short hash.
6. If the git skill is installed (`.atomforge/skills/git.md`), its rules apply on top of these.

## Example

> **User:** commit
> **Agent:** derives from the diff → proposes
> `feat(db): add tasks table migration with user_id index [atom-02]` → user approves →
> `git add migrations/001-tasks.ts migrations/001-tasks.test.ts docs/atoms/...` → commits →
> "`a1b2c3d` — atom-02 COMMITTED. Next: `review-atom atom-03`."
