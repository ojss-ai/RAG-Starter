# ADR-{{NNNN}}: {{TITLE}}

- Status: Proposed | Accepted | Deprecated | Superseded by ADR-{{XXXX}}
- Date: {{DATE}}
- Feature: {{NNN-slug}} (or "cross-cutting")
- Deciders: {{HUMAN}}, Claude

> RULES: One decision per ADR. ADRs are append-only history — never edit an Accepted ADR;
> supersede it with a new one. File name: `adr/NNNN-kebab-title.md`, NNNN zero-padded,
> monotonically increasing across the whole project.

## Context

What forces are at play? Constraints from the SRS ({{FR-ids}}), the existing codebase,
the constitution, and the team. 3–8 sentences. No solutions here.

## Decision

"We will …" — one unambiguous, imperative statement, then the minimum detail needed to act on
it (chosen library + version, pattern name, boundary definition).

## Options Considered

| Option | Pros | Cons | Why rejected/chosen |
|---|---|---|---|
| A (chosen) | … | … | … |
| B | … | … | … |
| C | … | … | … |

At least two real alternatives MUST be listed. "Do nothing" counts as an option.

## Consequences

- Positive: …
- Negative / debt accepted: …
- Follow-up tasks triggered: …

## Compliance

How a reviewer verifies the codebase still honors this decision (grep pattern, test name,
lint rule, directory shape).
