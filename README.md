<div align="center">

<img src="https://steerspec.dev/assets/logo.svg" alt="SteerSpec logo" width="96" height="96">

# SteerSpec Core Rules

**The `dev.steerspec.core` realm: the rules that define how [SteerSpec](https://steerspec.dev) specifications are
structured, versioned and interpreted, for engineers who author or consume realms.**

[![CI](https://github.com/SteerSpec/strspc-rules/actions/workflows/ci.yml/badge.svg)](https://github.com/SteerSpec/strspc-rules/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/SteerSpec/strspc-rules?labelColor=161B22&color=161B22)](https://github.com/SteerSpec/strspc-rules/releases)
[![License](https://img.shields.io/badge/License-Apache%202.0-161B22.svg?labelColor=161B22)](LICENSE)

[Rules](docs/rules.md) · [Schemas and realms](docs/schemas.md) · [Development and CI](docs/development.md) ·
[Releases](docs/releases.md)

</div>

## Status

CI validates the realm, lints the entities and checks rule lifecycle transitions on every pull request, except that
the release pull request from `develop` to `main` skips the lifecycle check. The [CI page](docs/development.md#ci)
lists the jobs, and the Release badge above shows the current release.

## Use the rules

Each release is served from [steerspec.dev](https://steerspec.dev). Replace `<version>` with the latest release tag
(shown by the Release badge), for example `v1.2.3`, to pin a version:

```text
https://steerspec.dev/rules/<version>/RUL.json
```

Or download the archive for offline use, with `<version>` as the tag and `<number>` as the tag without the `v`:

```text
https://github.com/SteerSpec/strspc-rules/releases/download/<version>/strspc-rules-<number>.tar.gz
```

Other endpoints are listed under [Published at steerspec.dev](docs/releases.md#published-at-steerspecdev).

## Where to go

| Goal | Page |
| ---- | ---- |
| See which entities the realm defines | [The rules](docs/rules.md#the-rules) |
| Understand how a rule changes state | [Rule lifecycle](docs/rules.md#rule-lifecycle) |
| Understand how the schemas are generated | [Schema system](docs/schemas.md#schema-system) |
| Understand realms and cross-realm references | [Realms](docs/schemas.md#realms) |
| Fetch schemas or rules by URL | [Published at steerspec.dev](docs/releases.md#published-at-steerspecdev) |
| Run the checks locally | [Development](docs/development.md#development) |
| See what CI enforces | [CI](docs/development.md#ci) |
| Understand how a release is cut | [Releases](docs/releases.md#releases) |
| Follow the contribution rules | [Governance](#governance) |
| Report a vulnerability | [Security](#security) |

## Governance

Open source software by Consulare.

Licensed under Apache 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).

- Changes go through pull requests: feature branch to `develop`, squash-merged, then `develop` to `main` for a release.
  Prefer the [`strspc` CLI](https://github.com/SteerSpec/strspc-CLI) to editing rule JSON by hand. See [AGENTS.md](AGENTS.md).
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
- Rule identifiers are never reused, and a rule outside Draft is immutable.
- Contribution guide for all SteerSpec repositories:
  [CONTRIBUTING.md](https://github.com/SteerSpec/.github/blob/main/CONTRIBUTING.md).

## Security

Do not open a public issue for a vulnerability. Report it privately through GitHub: on this repository, go to
**Security** then **Report a vulnerability**. The
[organisation security policy](https://github.com/SteerSpec/.github/blob/main/SECURITY.md) applies.

## Community

Open an issue to discuss a change before sending a pull request. All SteerSpec repositories follow the
[code of conduct](https://github.com/SteerSpec/.github/blob/main/CODE_OF_CONDUCT.md).
