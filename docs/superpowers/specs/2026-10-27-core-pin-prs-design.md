# Core pin PRs after a release — design

Beads: `strspc-rules-60x`.

## Intent

Every strspc-rules release `vX.Y.Z` has to be followed by one
`chore(rules): pin dev.steerspec.core to X.Y.Z` PR in each consumer repo
(strspc-manager, strspc-CLI, strspc-sync, strspc-spec). Today those four PRs
are made by hand (v1.8.0: manager#117, CLI#109, sync#69, spec#8), and v1.8.1
shipped without them. The release workflow should open them itself.

Pins stay literal in the consumer manifests on purpose: RR004 requires an
exact match between `dependencies[].version` and the resolved realm, and a
literal `github://…@vX.Y.Z` source resolves the same way outside Actions.
So the automation edits files; it does not introduce variables.

## Goals

- After `release.yml` creates a new tag `vX.Y.Z`, open one PR per consumer
  that moves every `dev.steerspec.core` pin to `X.Y.Z`, with the same file
  changes as the v1.8.0 reference PRs.
- A manual way to run the same thing for an existing tag (needed once, for
  v1.8.1).
- Idempotent: re-running the release, the job, or the dispatch never creates
  a duplicate PR and never fails because the work is already done.
- Signed commits, authored by the SteerSpec GitHub App, so the consumers'
  rulesets (verified signatures, PR-only) and pr-auto-approve accept them.

## Non-goals

- Merging the PRs. Consumer CI, Copilot review and pr-auto-approve gate them
  as for any other PR.
- Running `strspc realm validate` on the consumer side inside this workflow;
  consumer CI already does it on the PR.
- Bumping consumers' `go.mod` / strspc-manager versions.
- Discovering new consumers automatically.

## Anti-goals

- A pin job failure must never block tagging, the GitHub release, or the
  strspc-www publish.
- Never open a PR that silently misses a pin. A drifted layout fails loudly
  for that repo instead.
- Never downgrade a consumer.
- No hand edits to rule JSON or hand-maintained schemas in this repo.

## Decisions (from the conversation)

- **Trigger: new tag only.** The job runs when the `release` job reports
  `exists != 'true'` (fresh tag, or resume of a run that tagged this commit).
  Merges that do not create a tag do not run it.
- **Manual trigger** for an existing tag, used once for v1.8.1.
- **Token:** the `steerspec-sync` App (`STEERSPEC_APP_ID` /
  `STEERSPEC_PRIVATE_KEY`). Verified installed on all four consumers with
  `contents: write` and `pull_requests: write`; the last release run saw the
  secrets (`HAS_APP: true`). App-authored PRs already flow through the
  consumers' gates: strspc-manager and strspc-CLI open their release-please
  PRs with this App, and every consumer's auto-approve approves as
  `cnslr-bt`, which is not the PR author. Pushes made with an App token
  (unlike `GITHUB_TOKEN`) start the consumers' CI.

## Design

### Shape

A new reusable workflow `.github/workflows/pin-consumers.yml` with two
triggers:

- `workflow_call` with input `tag` — called by `release.yml`.
- `workflow_dispatch` with input `tag` — the manual path.

`release.yml` gets one new job:

```yaml
pin-consumers:
  needs: release
  if: needs.release.outputs.exists != 'true'
  uses: ./.github/workflows/pin-consumers.yml
  with:
    tag: ${{ needs.release.outputs.tag }}
  secrets: inherit
```

It depends on `release` only, not `publish`: consumers resolve core from the
GitHub tag tarball, and no consumer CI reads steerspec.dev, so the pin PRs do
not wait for the strspc-www publish PR. Being a separate job, its failure
cannot affect `release` or `publish`; it shows as a red job, not a green
no-op (no `continue-on-error`).

*My call:* a separate reusable workflow rather than `workflow_dispatch` on
`release.yml`. Dispatching `release.yml` would run the tagging job from
whatever branch is chosen, so every existing job would need an
event-name gate; a separate file keeps the release path untouched.

### Matrix

One matrix leg per consumer, `fail-fast: false`, each with its explicit file
list (from the reference PRs):

| Repo | Files |
| --- | --- |
| strspc-manager | `rules/realm.json`, `.strspc/config.yaml`, `docs/SPEC.md` |
| strspc-CLI | `rules/realm.json`, `.strspc/config.yaml`, `README.md`, `src/cmd/init.go`, `src/cmd/init_test.go` |
| strspc-sync | `rules/realm.json`, `.strspc/config.yaml` |
| strspc-spec | `rules/realm.json`, `README.md` |

strspc-spec has no `.strspc/config.yaml`. `src/cmd/init_test.go` is not in
the original brief but CLI CI fails without it (the test spells out the
literal pin on purpose).

### Per-repo steps

0. **Dispatch guard** (*my call*): on `workflow_dispatch`, run only from
   `refs/heads/main`, so a feature branch can never drive App write tokens
   into four repos with unreviewed workflow code. `workflow_call` from the
   release job already runs on `main`.
1. **Validate the tag**: `vMAJOR.MINOR.PATCH` exactly, and it exists in
   strspc-rules (for the dispatch path). Fail otherwise.
2. **Mint an App token** scoped to that one consumer repo, with
   `permission-contents: write` and `permission-pull-requests: write`.
3. **Check out** the consumer's default branch (`main` for all four today)
   with that token.
4. **Read OLD** from the consumer's own `rules/realm.json`:
   the `dependencies[]` entry with `realm_id == "dev.steerspec.core"`. Exactly
   one such entry, else fail.
   - OLD == NEW: notice "already pinned", exit 0, no PR.
   - OLD > NEW (`sort -V`): fail, refuse to downgrade.
5. **Rewrite**, for every listed file:
   - `strspc-rules@vOLD` → `strspc-rules@vNEW`
   - `dev.steerspec.core@OLD` → `dev.steerspec.core@NEW`

   Both match only when OLD is not followed by a digit, `-`, or `.`+digit,
   so `1.8.0` never matches inside `1.8.01` or `1.8.0-rc1`. A trailing `/`
   is deliberately not required: the CLI README also writes the bare
   ``pins `strspc-rules@v1.8.0`.`` (README.md:115), and CLI#109 changed it.
   - in `rules/realm.json`, the core dependency's `version` → `NEW` (and its
     `source` via the rule above).
   Each listed file must exist and must change; a file that does not contain
   OLD means the layout drifted, so that repo fails with a message naming the
   file.
6. **Leftover check**: `git grep` (tracked files) for `strspc-rules@vOLD`
   and `dev.steerspec.core@OLD` (same boundary as step 5), excluding `CHANGELOG.md` at any depth. Any
   hit fails the repo (before a PR is opened), naming the file so it can be
   added to the matrix. It matches only the consumer's *current* pin, so
   historical mentions of older versions (test fixtures at v1.6.0, docs) never
   trip it.
7. **Open or update the PR** with `peter-evans/create-pull-request` (already
   used by the publish job, pinned to the same SHA), `sign-commits: true`,
   App token:
   - branch `chore/core-X.Y.Z` (the reference PRs' convention), base = the
     consumer's default branch
   - title and commit message `chore(rules): pin dev.steerspec.core to X.Y.Z`
   - body: says it was opened by strspc-rules' release workflow for `vX.Y.Z`,
     lists the files, links the strspc-rules release.

   The action reuses an existing branch and updates an open PR rather than
   opening another, which with step 4 makes reruns idempotent.

### Idempotency summary

| Situation | Result |
| --- | --- |
| Consumer already at NEW on its default branch | no-op, green |
| Pin PR already open from an earlier run | branch updated in place, no new PR |
| Release run re-run / resumed | same as above |
| Dispatch for an older tag than the consumer has | red, no PR |
| Layout drift (file missing, unlisted pin left) | red for that repo, others continue |
| Consumer already at NEW via another PR while the bot PR is still open | no-op; the stale bot PR is left for a human to close (*my call*) |

## Left to the builder

- Exact `jq` / `sed` invocations, including keeping `realm.json` formatting
  byte-identical apart from the two changed values.
- PR body wording.
- Whether the dispatch path also verifies that a GitHub release exists for
  the tag (tag existence is the minimum).

## After it lands

The v1.8.1 pin PRs are opened by dispatching `pin-consumers.yml` with
`tag: v1.8.1` once the workflow is on `main` (dispatch uses the workflow
file from the chosen ref; re-running the old v1.8.1 release run would use
the old `release.yml`, which has no pin job).
