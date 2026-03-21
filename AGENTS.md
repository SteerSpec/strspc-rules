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

<!-- BEGIN BEADS INTEGRATION v:1 profile:full hash:d4f96305 -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking.
Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Dolt-powered version control with native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs via Dolt:

- Each write auto-commits to Dolt history
- Use `bd dolt push`/`bd dolt pull` for remote sync
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:

   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```

5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**

- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->
