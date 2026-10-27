---
name: releasing-strspc-rules
description: Use when asked to release, cut, tag or ship strspc-rules or dev.steerspec.core, to bump realm.version, to open the develop to main release PR, or when a Release run, the steerspec.dev publish or a consumer pin PR failed or is missing.
---

# Releasing strspc-rules

`realm.version` in `rules/core/realm.json` is the release. Merging `develop` into
`main` makes the Release workflow tag `v<realm.version>`, publish the GitHub
release, open the strspc-www publish PR and open the consumer pin PRs. You prepare
PRs and watch runs; the user merges every PR (develop, main, strspc-www, consumers).

## 1. Pick the version

List what ships, ignoring `chore(steerspec-sync)` and `chore(release)` commits:

```bash
git fetch origin --tags
git log --oneline --no-merges $(git describe --tags --abbrev=0 origin/main)..origin/develop
```

The highest matching row wins:

| Changes since the last tag | Bump | Precedent |
| --- | --- | --- |
| Rule or entity removed or renamed; schema rejects files it accepted | MAJOR | none yet |
| Any `feat`: new rule (Draft included), state promotion, new schema capability | MINOR | 1.7.0, 1.8.0 |
| Only `fix` to rules, schemas or tools | PATCH | 1.8.1 |
| Only ci, docs, chore | No release; ask the user | |

Tell the user the version and the reason before opening any PR.

## 2. Bump PR into develop

Work from a clean tree (a separate worktree if the current one is dirty).
`strspc version` must be at least the version `release.yml` pins (1.15.0).

1. `git switch -c chore/release-X.Y.Z origin/develop`
2. Change only `realm.version` in `rules/core/realm.json`. It is the realm manifest,
   not an entity file: a hand edit is the norm (see #69), no hash, no approval.
3. `strspc realm validate rules/core/ --recursive --strict` and `python3 tools/build-schema.py --check`
4. Commit `chore(release): bump realm.version to X.Y.Z`, PR to `develop`, body = what ships.

## 3. Release PR develop into main

After the bump PR merges:

```bash
gh pr create --base main --head develop --title "chore(release): X.Y.Z"
```

Body = what ships and "merging tags vX.Y.Z and deploys to steerspec.dev" (see #70).
The lifecycle diff is skipped on this PR by design. Tell the user that merging
deploys to production, and that it must be a merge commit, not a squash: a squash
makes `main` and `develop` diverge.

## 4. After the merge: watch

- **Run:** `gh run watch $(gh run list --workflow release.yml -L1 --json databaseId -q '.[0].databaseId')`.
  Expect `release`, `publish` and `pin-consumers` green.
- **Release:** `gh release view vX.Y.Z` has the tar.gz and zip.
- **Site:** `gh pr list -R SteerSpec/strspc-www --head publish/rules-vX.Y.Z` shows one PR.
  After the user merges it, `curl -s https://steerspec.dev/rules/latest/index.json | jq -r .version`
  prints `X.Y.Z`.
- **Consumers:** one PR per repo in the `pin-consumers.yml` matrix, authored by
  `steerspec-sync[bot]`, CI running:

  ```bash
  for r in strspc-manager strspc-CLI strspc-sync strspc-spec; do
    gh pr list -R SteerSpec/$r --head chore/core-X.Y.Z
  done
  ```

Then report what is pending: the strspc-www merge, the pin merges, and downstream
releases upstream first (strspc-manager, then strspc-CLI's `go.mod`).

## Recovery

- **`Tag vX.Y.Z already exists on <sha>; skipping release`:** the bump was missed or
  reused. Open a new bump PR with a higher version. Never move or delete a tag.
- **`release` or `publish` failed after the tag was created:** `gh run rerun <id> --failed`.
  A tag on the same commit resumes the release.
- **publish: `Resource not accessible by personal access token`:** the App secrets are
  missing, so it fell back to `WWW_PAT`. Restore `STEERSPEC_APP_ID` and
  `STEERSPEC_PRIVATE_KEY`, then rerun the failed jobs.
- **A pin-consumers leg is red:** its `::error::` names the cause. Add a new pin file
  to the matrix in `pin-consumers.yml`, or sort out the named PR or branch. Then, with
  the user's OK: `gh workflow run pin-consumers.yml --ref main -f tag=vX.Y.Z`.
- **Pin PRs missing:** the same dispatch.
- **Wrong content shipped:** fix forward with a patch release.
