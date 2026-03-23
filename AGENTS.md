# Agent Instructions

## Critical Safety Rules

This is the **foundational data layer** for the entire SteerSpec platform. Merging to
`main` triggers a release that publishes rules and schemas to steerspec.dev. Treat every
merge to `main` as a production deploy.

**Hard stops — never violate these:**

1. **Never manually edit JSON entity files without human approval.** Use strspc-CLI
   commands when available. When manual edits are the only option (CLI doesn't support
   the operation yet), get explicit approval first.
2. **Never modify hand-maintained axiom schemas** (`bootstrap.schema.json`,
   `realm.v1.schema.json`) without explicit human approval — these are bootstrap
   trust anchors.
3. **Never delete, renumber, or reuse rule IDs.** Immutability is non-negotiable.
4. **Never commit directly to `main`.** All changes go through feature branch →
   `develop` → `main` PRs.
5. **Never force-push** to `main` or `develop`.

## Rule Manager Specification

The canonical spec lives in strspc-manager:
[`docs/SPEC.md`](https://github.com/SteerSpec/strspc-manager/blob/main/docs/SPEC.md).

This repo (strspc-rules) is the **data layer** — it defines the rules and schemas.
strspc-manager is the **engine layer** — it implements the spec.

## Self-Referential Rules

The rules in this repository govern themselves. When modifying any file under `rules/`,
the rules defined in this repository apply to those modifications. The JSON entity files
(e.g., `KWRD.json`, `RUL.json`, `RLIFRMT.json`) are the source of truth — keywords such
as MUST, SHOULD, and MAY have the precise semantics defined in `KWRD.json`. Rule structure,
lifecycle states, versioning, and immutability constraints are defined across the entity files.

This is intentional and circular: the specification is its own first consumer.

## Mutation Policy — CLI-First

The strspc-CLI is the intended interface for mutating rules and realms. It enforces
constraints (ID sequencing, state transitions, hash computation) that manual edits can
violate. **Always prefer CLI commands over direct JSON editing.**

### Available CLI commands

- Realm management: `strspc realm init`, `strspc realm add`, `strspc realm validate`,
  `strspc realm dep add/remove`
- Validation: `strspc lint`, `strspc render`

### Not yet available (manual edit with human approval)

- Rule lifecycle: `strspc rule add/update/promote/retire/abandon/supersede`
- PR validation: `strspc diff`

### Manual edit checklist (when CLI doesn't support the operation)

1. Get explicit human approval before editing any file under `rules/`
2. Read and understand the relevant entity rules (self-referential)
3. Edit the JSON entity file(s)
4. Bump `rule_set.version` and update `rule_set.timestamp`
5. Run `python3 tools/compute-hash.py` — recompute Blake3 hashes
6. Run `python3 tools/build-schema.py --check` — verify schema consistency
7. Run `ruff check . && ruff format --check .` — lint Python if touched
8. Commit on a feature branch with conventional commit message

As the CLI matures, this fallback list should shrink. Update this section when new
CLI commands ship.

## Rule Authoring Constraints

**Identifiers are permanent.**
Rule IDs (`[ENTITY-NNN.N/STATE]`) MUST NOT be reused once assigned, even after the rule is
deprecated or terminated. Assign the next sequential number.

**Draft is the only mutable state.**
Rules in Draft (`/D`) may be edited freely. Once a rule advances to Published (`/P`) or beyond,
it is immutable. Introduce changes by superseding with a new rule, not by editing the old one.

**Rule set versioning is mandatory.**
Every entity's `rule_set.version` MUST bump (semver) when any rule changes. Update
`rule_set.timestamp` and recompute `rule_set.hash` with `tools/compute-hash.py`.

**One statement per rule.**
Each rule MUST be expressed as a single phrase. Use Notes for context, rationale, or examples.

## JSON Entity System

Rules are stored as **JSON entity files** (`ENT.json`, `KWRD.json`, `NTE.json`, etc.)
validated against a JSON Schema. JSON is the sole source of truth — no Markdown rule
files are maintained in this repo.

The schema lives in `rules/core/_schema/`:

- `entity.v1.schema.json` — full schema, **generated** by `tools/build-schema.py` from the
  rules themselves (self-recursive: rules define the schema that validates the rules).
- `bootstrap.schema.json` — minimal hand-maintained axiom schema used by CI.
- `realm.v1.schema.json` — hand-maintained axiom schema for realm manifests.

### Python Tooling

| Script | Purpose |
| ------ | ------- |
| `tools/build-schema.py` | Generates `entity.v1.schema.json` from the rules; `--check` validates without overwriting |
| `tools/compute-hash.py` | Computes Blake3 content hashes for `rule_set.hash` fields |

### Python Code Quality

All Python files are linted with [Ruff](https://docs.astral.sh/ruff/) (configured in
`pyproject.toml`). Before committing Python changes:

```bash
ruff check .              # lint
ruff format --check .     # format check (use `ruff format .` to auto-fix)
```

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

- Feature branches → `develop` via PR. `develop` → `main` via PR for releases.
- Use `bd` (beads) for ALL task tracking — no markdown TODOs.
- CI gates every PR — the `validate-json`, `build-schema`, `lint-python`, `lint-commits`,
  and `lint` jobs must all pass.
- To release: open a PR from `develop` to `main`. On merge, the release workflow
  automatically bumps the semver tag based on conventional commit types (`feat`→minor,
  `fix`/etc→patch, breaking→major), publishes the GitHub release, and deploys rules
  to steerspec.dev via strspc-www.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** to avoid hanging on confirmation prompts:

```bash
cp -f source dest       # NOT: cp source dest
mv -f source dest       # NOT: mv source dest
rm -f file              # NOT: rm file
rm -rf directory        # NOT: rm -r directory
```

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:custom -->

## Issue Tracking with bd (beads)

This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs,
task lists, or other tracking methods.

### Essential Commands

```bash
bd ready                                    # find unblocked work
bd create "Title" --description="..." -t task -p 2  # create issue
bd update <id> --claim                      # claim work
bd close <id> --reason "Done"               # complete work
```

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete
until `git push` succeeds.

1. **File issues for remaining work** — create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) — linters, schema check, hash verification
3. **Update issue status** — close finished work, update in-progress items
4. **PUSH TO REMOTE** — this is MANDATORY:

   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```

5. **Verify** — all changes committed AND pushed
6. **Hand off** — provide context for next session

Work is NOT complete until `git push` succeeds. NEVER stop before pushing.

<!-- END BEADS INTEGRATION -->
