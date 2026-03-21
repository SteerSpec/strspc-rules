# Agent Instructions

## Self-Referential Rules

The rules in this repository govern themselves. When modifying any file under `rules/`,
the rules defined in this repository apply to those modifications:

- `rules/core/KEYWORDS.md` — governs the language. Keywords such as MUST, SHOULD, and MAY
  have the precise semantics defined there. Use them consistently and correctly.
- `rules/core/RULE_FORMAT.md` — governs the structure. Every rule MUST follow the identifier
  format, lifecycle states, versioning, and immutability constraints defined there.

This is intentional and circular: the specification is its own first consumer.

## Rule Authoring Constraints

Before adding or modifying any rule, internalize these constraints from `RULE_FORMAT.md`:

**Identifiers are permanent.**
Rule IDs (`[ENTITY-NNN.N/STATE]`) MUST NOT be reused once assigned, even after the rule is
deprecated or terminated. Assign the next sequential number.

**Draft is the only mutable state.**
Rules in Draft (`/D`) may be edited freely. Once a rule advances to Published (`/P`) or beyond,
it is immutable. Introduce changes by superseding with a new rule, not by editing the old one.

**Version blocks are mandatory.**
Every entity section containing rules MUST have a `Version(s):` block. Update it when you
modify rules in that section. Format:

```text
Version(s):
	- <semver> (<YYYY-MM-DD>): <description of change>
```

**One statement per rule.**
Each rule MUST be expressed as a single phrase. Use Notes for context, rationale, or examples.

## Workflow

- Use `bd` (beads) for ALL task tracking — no markdown TODOs.
- Open a GitHub issue documenting the plan before starting any work.
- Run `python3 scripts/validate-rules.py` locally before committing.
- CI gates every PR — the validate and lint jobs must pass.
- To release a new version: update `VERSION`, commit, tag as `vX.Y.Z`, push the tag.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** to avoid hanging on confirmation prompts:

```bash
cp -f source dest       # NOT: cp source dest
mv -f source dest       # NOT: mv source dest
rm -f file              # NOT: rm file
rm -rf directory        # NOT: rm -r directory
```
