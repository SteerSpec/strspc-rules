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

## Commit Format

All commits MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) specification
(enforced by commitlint on commit-msg hook and in CI):

```text
<type>[optional scope][optional !]: <description>
```

Allowed types: `feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `style`, `revert`, `test`, `perf`

Max header length: 120 characters.

Install the hook locally:

```bash
pip install pre-commit
pre-commit install --hook-type commit-msg
pre-commit install  # also install the pre-commit stage hooks
```

## Workflow

- Use `bd` (beads) for ALL task tracking — no markdown TODOs.
- Open a GitHub issue documenting the plan before starting any work.
- Run `python3 scripts/validate-rules.py` locally before committing.
- CI gates every PR — the validate, lint, and lint-commits jobs must pass.
- To release: open a PR from `develop` to `main`. On merge, the release workflow
  automatically bumps the semver tag based on conventional commit types (`feat`→minor,
  `fix`/etc→patch, breaking→major) and publishes the GitHub release with archives.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** to avoid hanging on confirmation prompts:

```bash
cp -f source dest       # NOT: cp source dest
mv -f source dest       # NOT: mv source dest
rm -f file              # NOT: rm file
rm -rf directory        # NOT: rm -r directory
```
