# Core Pin PRs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After `release.yml` tags `vX.Y.Z`, open one signed `chore(rules): pin dev.steerspec.core to X.Y.Z` PR in each of strspc-manager, strspc-CLI, strspc-sync and strspc-spec, and close the App's superseded pin PRs.

**Architecture:** A stdlib-only Python helper (`tools/pin_core.py`) does the file rewriting, drift and downgrade checks, so it is unit-tested locally. A reusable workflow (`pin-consumers.yml`, `workflow_call` + `workflow_dispatch`) runs it once per consumer in a matrix with a steerspec-sync App token, then opens the PR with `peter-evans/create-pull-request` and closes older App pin PRs with `gh`. `release.yml` calls it after a fresh tag.

**Tech Stack:** GitHub Actions, Python 3.12 stdlib (`unittest`, `json`, `re`, `subprocess`), `gh` CLI, `actions/create-github-app-token`, `peter-evans/create-pull-request`.

**Spec:** `docs/superpowers/specs/2026-10-27-core-pin-prs-design.md`

## Global Constraints

- Tag format: exactly `^v[0-9]+\.[0-9]+\.[0-9]+$`; `X.Y.Z` = tag without `v`. Pins written are plain `X.Y.Z`.
- Branch `chore/core-X.Y.Z`; PR title and commit headline `chore(rules): pin dev.steerspec.core to X.Y.Z`; base = consumer default branch (checked-out `main`).
- Token: `secrets.STEERSPEC_APP_ID` / `secrets.STEERSPEC_PRIVATE_KEY`, minted per consumer repo with `permission-contents: write`, `permission-pull-requests: write`. Commits signed (`sign-commits: true`).
- App PR author for filtering: `app/steerspec-sync`.
- Reuse pinned action SHAs already in `release.yml`: `actions/create-github-app-token@64ab729a6294000f5aa4a4bc0b73d1f32bc45510  # v3.3.0`, `peter-evans/create-pull-request@5f6978faf089d4d20b00c7766989d076bb2fc7f1  # v8.1.1`.
- Pins stay literal; no org variables. No edits to rule JSON or hand-maintained schemas.
- Python: ruff-clean (`ruff check .`, `ruff format --check .`), line length 120, stdlib only (no new `requirements.txt` entries).
- Conventional commits; every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never stage `.beads/issues.jsonl`.

Matrix (verbatim from the spec):

| repo | files |
| --- | --- |
| strspc-manager | `rules/realm.json`, `.strspc/config.yaml`, `docs/SPEC.md` |
| strspc-CLI | `rules/realm.json`, `.strspc/config.yaml`, `README.md`, `src/cmd/init.go`, `src/cmd/init_test.go` |
| strspc-sync | `rules/realm.json`, `.strspc/config.yaml` |
| strspc-spec | `rules/realm.json`, `README.md` |

## Review Focus

1. Bare pin with no trailing slash (``pins `strspc-rules@v1.8.0`.`` at CLI README.md:115) must be rewritten and must count as a leftover if not. Test: `test_rewrite_bare_pin_followed_by_backtick` (Task 1).
2. A longer version sharing the prefix (`1.8.01`, `1.8.0-rc1`, `1.8.0.1`) must never match OLD `1.8.0`; a pin at end of sentence (`@v1.8.0.`) must match. Test: `test_pattern_boundaries` (Task 1).
3. `realm.json` must change only the core dependency's `version` and `source`; the consumer's own `realm.version` equal to OLD must stay. Test: `test_realm_json_keeps_own_version` (Task 1).
4. A `realm.json` whose formatting would not survive a JSON round-trip must fail, not be reformatted. Test: `test_realm_json_non_canonical_format_fails` (Task 1).
5. Re-dispatching an older tag while a newer App pin PR is open must fail without opening a PR. Covered by the guard step in Task 2 and checked by `test_newer_open_pin_refused` (Task 1, `check_open_pins`).

---

### Task 1: `tools/pin_core.py` helper with unit tests

**Files:**

- Create: `tools/pin_core.py`
- Create: `tools/tests/__init__.py` (empty), `tools/tests/test_pin_core.py`
- Modify: `.github/workflows/ci.yml` — `lint-python` job, add step `Unit tests` running `python3 -m unittest discover -s tools/tests -t tools` after the ruff steps.

**Interfaces:**

- Produces (module `tools/pin_core.py`):
  - `CORE_REALM_ID = "dev.steerspec.core"`
  - `class PinError(Exception)`
  - `parse_version(v: str) -> tuple[int, int, int]` — raises `PinError` unless `^\d+\.\d+\.\d+$`.
  - `pin_regex(old: str) -> re.Pattern[str]` — matches `strspc-rules@v{old}` or `dev.steerspec.core@{old}`, with `re.escape(old)` and negative lookahead `(?![0-9]|-|\.[0-9])`. Group 1 is the prefix.
  - `read_core_version(realm_text: str) -> str` — exactly one `dependencies[]` with `realm_id == CORE_REALM_ID`, else `PinError`.
  - `rewrite_text(text: str, old: str, new: str) -> str`
  - `rewrite_realm_json(text: str, old: str, new: str) -> str` — `PinError` if `json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n" != text`; else sets the core dependency's `version = new`, `source = rewrite_text(source, old, new)`, re-serialises the same way.
  - `apply(repo_dir: Path, files: list[str], new: str) -> tuple[str, bool]` — returns `(old, changed)`. Reads OLD from `repo_dir/rules/realm.json`. `old == new` → `(old, False)`, no writes. `old > new` → `PinError("refusing to downgrade …")`. Otherwise rewrites each file (realm.json via `rewrite_realm_json`, others via `rewrite_text`); a missing or unchanged file → `PinError` naming it; then `find_leftovers` non-empty → `PinError` listing them. Writes only after all checks pass.
  - `find_leftovers(repo_dir: Path, old: str) -> list[str]` — scans `git -C repo_dir ls-files` output, skipping any path whose basename is `CHANGELOG.md` and unreadable/binary files; returns `path:line` entries matching `pin_regex(old)`.
  - `check_open_pins(branches: list[str], new: str) -> list[str]` — from head branch names, ignores those not matching `^chore/core-(\d+\.\d+\.\d+)$`; raises `PinError` if any version > new; returns the branches with version < new (to close).
  - CLI `python3 tools/pin_core.py apply --repo-dir DIR --new X.Y.Z FILE...` prints `old=…` and `changed=true|false` lines; `python3 tools/pin_core.py superseded --new X.Y.Z` reads branch names from stdin (one per line), prints the ones to close one per line. Any `PinError` → `::error::<message>` on stderr, exit 1.

- [ ] **Step 1: Write the failing tests** in `tools/tests/test_pin_core.py` (`unittest.TestCase`, temp dirs via `tempfile.TemporaryDirectory`, a `git init` + `git add` fixture helper for `apply`/`find_leftovers`). Fixture realm.json = the strspc-spec manifest (realm.version `0.1.0`, one core dep at `1.8.0` / `github://SteerSpec/strspc-rules@v1.8.0/rules/core`, 2-space indent, trailing newline). Tests and their assertions:
  - `test_pattern_boundaries`: `pin_regex("1.8.0")` matches in `@v1.8.0/rules`, ``@v1.8.0` ``, `@v1.8.0.` (end of sentence), `dev.steerspec.core@1.8.0`; does not match `@v1.8.01`, `@v1.8.0-rc1`, `@v1.8.0.1`, `@v1.6.0/`, `@v1/`, `@latest/`.
  - `test_rewrite_bare_pin_followed_by_backtick`: ``"pins `strspc-rules@v1.8.0`."`` → ``"pins `strspc-rules@v1.8.1`."``.
  - `test_rewrite_spec_readme_form`: `"depends on dev.steerspec.core@1.8.0"` → `@1.8.1`.
  - `test_realm_json_rewrites_version_and_source`: result parses with dep `version == "1.8.1"`, `source == "github://SteerSpec/strspc-rules@v1.8.1/rules/core"`, and differs from input in exactly 2 lines.
  - `test_realm_json_keeps_own_version`: fixture with `realm.version == "1.8.0"` keeps it after rewrite.
  - `test_realm_json_non_canonical_format_fails`: 4-space-indented input raises `PinError`.
  - `test_read_core_version_requires_exactly_one`: zero and two core deps both raise `PinError`.
  - `test_apply_already_pinned`: new `1.8.0` → `("1.8.0", False)`, files untouched.
  - `test_apply_refuses_downgrade`: new `1.7.9` raises `PinError` containing `downgrade`.
  - `test_apply_missing_file_fails` and `test_apply_unchanged_file_fails`: `PinError` message contains the file path; no file on disk modified.
  - `test_apply_leftover_fails`: unlisted tracked `docs/x.md` containing `strspc-rules@v1.8.0` → `PinError` containing `docs/x.md`; listed files not modified.
  - `test_leftover_ignores_changelog_and_old_fixtures`: `CHANGELOG.md` and `sub/CHANGELOG.md` with the OLD pin, and a `.go` file with `@v1.6.0/`, give `[]`.
  - `test_apply_happy_path`: README with both the `/rules/core` form and the bare form, realm.json, config.yaml → `("1.8.0", True)`, every `1.8.0` pin now `1.8.1`.
  - `test_newer_open_pin_refused`: `check_open_pins(["chore/core-1.9.0"], "1.8.1")` raises `PinError`.
  - `test_superseded_selection`: `check_open_pins(["chore/core-1.8.0", "chore/core-1.8.1", "chore/core-x", "feat/y"], "1.8.1") == ["chore/core-1.8.0"]`.

- [ ] **Step 2: Run tests, expect failure**

Run: `python3 -m unittest discover -s tools/tests -t tools -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'pin_core'` (tests do `import pin_core`; `-t tools` puts `tools/` on `sys.path`, same as the existing scripts' sibling import of `hash_util`).

- [ ] **Step 3: Implement `tools/pin_core.py`** per the Interfaces block. Module docstring states why: pins stay literal (RR004), so the release workflow edits files.

- [ ] **Step 4: Run tests, expect pass; lint**

Run: `python3 -m unittest discover -s tools/tests -t tools -v && ruff check . && ruff format --check .`
Expected: all tests OK, ruff clean.

- [ ] **Step 5: Dry-run against real consumers** (no pushes). In the scratchpad, shallow-clone the four consumers with `gh repo clone SteerSpec/<repo> -- --depth 1`, run `python3 -I tools/pin_core.py apply --repo-dir <clone> --new 1.8.1 <matrix files>` per repo, and inspect `git -C <clone> diff`.
Expected: `old=1.8.0 changed=true` for each; diffs touch exactly the same lines as manager#117, CLI#109 (README lines 105 and 115 both change), sync#69, spec#8, with `1.8.0→1.8.1`. Then run once more with `--new 1.8.0` → `changed=false`.

- [ ] **Step 6: Add the unit-test step to `ci.yml` `lint-python`, run `pre-commit run --files .github/workflows/ci.yml`, commit**

```bash
git add tools/pin_core.py tools/tests .github/workflows/ci.yml
git commit -m "feat(tools): add pin_core helper for consumer core pin bumps"
```

### Task 2: `pin-consumers.yml` reusable workflow

**Files:**

- Create: `.github/workflows/pin-consumers.yml`

**Interfaces:**

- Consumes: `tools/pin_core.py apply` / `superseded` CLI (Task 1).
- Produces: `workflow_call` input `tag` (string, required); secrets read via `secrets: inherit` (`STEERSPEC_APP_ID`, `STEERSPEC_PRIVATE_KEY`). `workflow_dispatch` input `tag` (string, required).

Header comment explains (match `release.yml` comment style): why the App token (signed commits, cross-repo, PR author ≠ approver `cnslr-bt`), why literal pins, why dispatch is main-only.

- [ ] **Step 1: Write the workflow.** `permissions: contents: read`; `concurrency: {group: pin-consumers, cancel-in-progress: false}`. One job `pin`:
  - `if: github.event_name != 'workflow_dispatch' || github.ref == 'refs/heads/main'`
  - `strategy: {fail-fast: false, matrix: {include: [...]}}` with `repo` and `files` (space-separated) from the Global Constraints table.
  - Steps, in order:
    1. **Validate tag** (`env: TAG: ${{ inputs.tag }}`, `GH_TOKEN: ${{ github.token }}`): regex from Global Constraints, then `gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$TAG"` must succeed; output `version`.
    2. `actions/checkout@v4` (this repo, for `tools/`), `actions/setup-python@v5` 3.12 (no pip install).
    3. Mint App token (`owner: SteerSpec`, `repositories: ${{ matrix.repo }}`, the two permissions).
    4. `actions/checkout@v4` `repository: SteerSpec/${{ matrix.repo }}`, `token:` App token, `path: consumer`.
    5. **Superseded / newer guard**: `gh pr list --repo SteerSpec/$REPO --state open --author app/steerspec-sync --json headRefName --jq '.[].headRefName' | python3 tools/pin_core.py superseded --new "$VERSION"` → write the result to `$GITHUB_OUTPUT` as multiline `close` (heredoc delimiter); a newer open pin fails the leg.
    6. **Rewrite**: `python3 tools/pin_core.py apply --repo-dir consumer --new "$VERSION" $FILES >> "$GITHUB_OUTPUT"` (`FILES` unquoted on purpose, word-split; comment it).
    7. **Open PR** `if: steps.rewrite.outputs.changed == 'true'`: create-pull-request with `path: consumer`, `token`, `sign-commits: true`, `branch: chore/core-${{ version }}`, `commit-message`/`title` per Global Constraints. No `add-paths`: the rewrite touches only the listed files. Body: opened by strspc-rules release workflow for `vX.Y.Z` (link `https://github.com/SteerSpec/strspc-rules/releases/tag/vX.Y.Z`), moves `dev.steerspec.core` from OLD to NEW in the listed files.
    8. **Close superseded** (runs on both changed and already-pinned paths, skip if list empty): for each branch, `gh pr close <branch> --repo … --delete-branch --comment "Superseded by dev.steerspec.core X.Y.Z (`steps.cpr.outputs.pull-request-url`, or "already pinned on main" when step 7 was skipped)."`
  - All `run:` blocks: `set -euo pipefail`; inputs passed via `env:`, never interpolated into scripts.

- [ ] **Step 2: Lint**

Run: `pre-commit run actionlint --files .github/workflows/pin-consumers.yml && pre-commit run yamllint --files .github/workflows/pin-consumers.yml`
Expected: Passed.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pin-consumers.yml
git commit -m "ci: add pin-consumers workflow opening core pin PRs in consumer repos"
```

### Task 3: call it from `release.yml` and document

**Files:**

- Modify: `.github/workflows/release.yml` — add job after `publish`.
- Modify: `AGENTS.md` — "Workflow" release bullet: after tagging, the release opens `chore(rules): pin dev.steerspec.core to X.Y.Z` PRs in the four consumers; for an existing tag dispatch `pin-consumers.yml` from `main`.
- Modify: `README.md` only if it documents the release process (check; skip otherwise).

**Interfaces:**

- Consumes: `pin-consumers.yml` `workflow_call` input `tag`.

- [ ] **Step 1: Add the job** (exactly the spec's block):

```yaml
  pin-consumers:
    needs: release
    if: needs.release.outputs.exists != 'true'
    uses: ./.github/workflows/pin-consumers.yml
    with:
      tag: ${{ needs.release.outputs.tag }}
    secrets: inherit
```

with a comment: needs `release` not `publish` (consumers resolve the tag tarball, no consumer CI reads steerspec.dev), and its failure cannot affect `release`/`publish`.

- [ ] **Step 2: Lint**

Run: `pre-commit run --all-files`
Expected: all hooks Passed (or Skipped).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml AGENTS.md
git commit -m "ci(release): open consumer core pin PRs after tagging"
```

### Task 4: PR to develop

- [ ] **Step 1:** `git push -u origin ci/core-pin-prs`, then `gh pr create --base develop` titled `ci(release): open core pin PRs in consumer repos after a release`. Body: summary, spec/plan links, verification done (unit tests, actionlint, Task 1 Step 5 dry-run diffs), what cannot be verified before `main` (App token + create-pull-request path; first real run is the v1.8.1 dispatch), and the v1.8.1 instruction: after the develop → main merge, run `gh workflow run pin-consumers.yml --repo SteerSpec/strspc-rules --ref main -f tag=v1.8.1`. Ends with the Claude Code attribution line. Do not merge.
