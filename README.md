# strspc-rules

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

SteerSpec Core Rules — the canonical rule format specification for the SteerSpec ecosystem.

This repository contains the foundational rule definitions that govern how all SteerSpec
specifications are structured, versioned, and interpreted. The rules are written using the
format they themselves define (self-referential by design).

## Contents

```text
rules/
└── core/
    ├── KEYWORDS.md      RFC-2119-derived keyword semantics (MUST, SHOULD, MAY, ...)
    ├── RULE_FORMAT.md   Rule structure, identifiers, lifecycle, and versioning
    └── SYNC_CORE.md     Core entities for the SteerSpec Sync specification
```

## Versioning

Releases follow [semantic versioning](https://semver.org/) and are published as Git tags
in the format `v<MAJOR>.<MINOR>.<PATCH>` (e.g., `v0.1.0`).

Each release includes:

- The full `rules/` directory
- `LICENSE` and `NOTICE` files
- Archives: `strspc-rules-<version>.tar.gz` and `strspc-rules-<version>.zip`

## Referencing a Specific Version

Pin to a release tag to reference a stable, immutable snapshot:

```text
https://github.com/SteerSpec/strspc-rules/blob/v0.1.0/rules/core/RULE_FORMAT.md
```

Download the archive for offline use:

```text
https://github.com/SteerSpec/strspc-rules/releases/download/v0.1.0/strspc-rules-0.1.0.tar.gz
```

## License

Apache 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
