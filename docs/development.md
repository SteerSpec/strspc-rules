# Development and CI

## Development

Prerequisites: Python 3.12+, [pre-commit](https://pre-commit.com/) and, for the rule checks, the
[`strspc` CLI](https://github.com/SteerSpec/strspc-CLI).

```bash
pip install -r requirements.txt
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

Hooks run on each commit:

| Hook | Checks |
| ---- | ------ |
| actionlint | GitHub Actions workflow syntax |
| yamllint | YAML formatting |
| markdownlint | Markdown style |
| editorconfig-checker | EditorConfig compliance |
| ruff | Python lint (pycodestyle, pyflakes, isort, bugbear, …) |
| ruff-format | Python formatting |
| commitlint | Conventional Commits message format |

To run the validation by hand:

```bash
python3 tools/build-schema.py --check                  # JSON schema
ruff check . && ruff format --check .                  # Python lint and format
python3 -m unittest discover -s tools/tests -t tools   # Unit tests
```

The rule checks of the `rules` and `check` jobs need the `strspc` CLI:

```bash
strspc realm validate rules/core/ --recursive --strict --core   # Realm manifest and entity files
strspc lint rules/core/ --strict --core                         # Entity lint
strspc diff rules/core/ --base origin/develop --strict          # Lifecycle transitions against the base
strspc check --static-only                                      # Realm resolution, no AI evaluation
```

## CI

Every pull request, release pull requests included, runs these jobs from [`ci.yml`](../.github/workflows/ci.yml):

| Job | Description |
| --- | ----------- |
| `rules` | Org `strspc-lint` workflow: realm validate, lint, lifecycle diff against the base (skipped on the `develop` to `main` release PR and the resulting `main` push) |
| `check` | Org `strspc-check` workflow, static only: resolves the realm, verifying cross-realm references |
| `lint-commits` | Conventional Commits enforcement (pull requests only) |
| `lint-python` | Ruff lint and format check, unit tests |
| `lint` | actionlint, yamllint, markdownlint, editorconfig-checker |

[`build-schema.yml`](../.github/workflows/build-schema.yml) also runs `python3 tools/build-schema.py --check`
whenever the rules, the schemas or the generator change.

[`pr-title.yml`](../.github/workflows/pr-title.yml) checks that the pull request title follows Conventional Commits:
a pull request into `develop` is squashed, so its title becomes the commit.

[`auto-approve.yml`](../.github/workflows/auto-approve.yml) runs the
[strspc-pr-review](https://github.com/SteerSpec/strspc-pr-review) action, which approves a pull request as a bot
account once CI is green and Copilot's review is clean. It never merges. A pull request that touches a file listed in
[`CODEOWNERS`](../.github/CODEOWNERS) needs a code owner's approval instead.

Release pull requests (`develop` → `main`) skip the `strspc diff` lifecycle check: they aggregate transitions that
were validated one pull request at a time on the way into `develop`.
