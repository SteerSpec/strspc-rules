# Sync Core Entities

Core entities for the SteerSpec Sync specification. These define the fundamental building blocks of the synchronization system.

## SyncManifest

- [SYNCMFST-001.0/D] IS the central configuration for synchronizing AI configuration files across a GitHub organization.
- [SYNCMFST-002.0/D] MUST be stored in a dedicated central repository (source of truth).
- [SYNCMFST-003.0/D] MUST define at least one Template.
- [SYNCMFST-004.0/D] MUST define a ComponentRegistry.
- [SYNCMFST-005.0/D] HAS a manifest version in semver format.
- [SYNCMFST-006.0/D] MUST be expressed as YAML named `steerspec-sync.yml` at the repository root.
- [SYNCMFST-007.0/D] MAY define global template variables.
- [SYNCMFST-008.0/D] HAS a Blake3 hash for integrity verification.

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:

## Template

- [TMPLT-001.0/D] IS a managed file synchronized to target repositories.
- [TMPLT-002.0/D] HAS a unique template identifier (e.g., "claude-md", "agent-code-review").
- [TMPLT-003.0/D] HAS a type which MUST be one of: "claude-md", "skill", "agent", "config", "custom".
- [TMPLT-004.0/D] HAS a source path relative to the central repository.
- [TMPLT-005.0/D] HAS a destination path relative to the target repository (supports `.claude/` tree paths).
- [TMPLT-006.0/D] MUST support a rendering strategy which MUST be one of: "mustache", "marker", "full-replace".
- [TMPLT-007.0/D] When using the marker strategy, managed sections MUST be delimited by `<!-- STEERSPEC:BEGIN:section_name -->` and `<!-- STEERSPEC:END:section_name -->`.
- [TMPLT-008.0/D] MAY define template-specific variables.

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:
	- [TMPLT-006/001] Mustache is best for fully templated files. Marker is best for CLAUDE.md files where repos may have local sections between managed markers. Full-replace is best for agents and skills that should be identical everywhere.

## TemplateVersion

- [TMPLTVRS-001.0/D] HAS a version in semver format (MAJOR.MINOR.PATCH).
- [TMPLTVRS-002.0/D] HAS a Blake3 hash of the template content.
- [TMPLTVRS-003.0/D] HAS a UTC timestamp.
- [TMPLTVRS-004.0/D] MUST be immutable once created.
- [TMPLTVRS-005.0/D] IS tracked via git tags in the format `tmpl/<template-id>/v<version>`.

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:

## ComponentRegistry

- [CMPREG-001.0/D] IS the registry of target repositories for synchronization.
- [CMPREG-002.0/D] IS defined within the SyncManifest or via a `$include` directive.
- [CMPREG-003.0/D] HAS one or more ComponentTargets.
- [CMPREG-004.0/D] MAY use glob patterns for repository name matching.
- [CMPREG-005.0/D] MAY use GitHub topics for dynamic repository resolution.

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:

## ComponentTarget

- [CMPTGT-001.0/D] HAS a repository identifier in `owner/repo` format.
- [CMPTGT-002.0/D] HAS a default branch name.
- [CMPTGT-003.0/D] MAY include specific templates by identifier.
- [CMPTGT-004.0/D] MAY exclude specific templates by identifier.
- [CMPTGT-005.0/D] MAY define variable overrides for template rendering.
- [CMPTGT-006.0/D] HAS an `enabled` boolean flag (default: true).

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:

## SyncOperation

- [SYNCOP-001.0/D] IS a single execution of the synchronization process.
- [SYNCOP-002.0/D] HAS a UUID.
- [SYNCOP-003.0/D] HAS a trigger type which MUST be one of: "push", "manual", "schedule".
- [SYNCOP-004.0/D] HAS a UTC timestamp.
- [SYNCOP-005.0/D] HAS a status which MUST be one of: "pending", "running", "completed", "failed".
- [SYNCOP-006.0/D] Produces one or more SyncPullRequests for out-of-date repositories.
- [SYNCOP-007.0/D] MAY operate in dry-run mode where no PRs are created or updated.
- [SYNCOP-008.0/D] MUST record results in the DeploymentState.

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:

## SyncPullRequest

- [SYNCPR-001.0/D] IS a pull request created in a target repository to deliver a template update.
- [SYNCPR-002.0/D] MUST use a branch name in the format `steerspec-sync/<template-id>/<version>`.
- [SYNCPR-003.0/D] The PR body MUST include: previous version, new version, changelog, and diff link.
- [SYNCPR-004.0/D] MUST be labeled with a configurable label (default: `steerspec-sync`).
- [SYNCPR-005.0/D] MUST update an existing open PR for the same template rather than creating a duplicate.
- [SYNCPR-006.0/D] MUST close stale version PRs for the same template when a newer version PR is created.

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:
	- [SYNCPR-005/001] This follows the Dependabot pattern of updating PRs in place to avoid PR flooding.

## DeploymentState

- [DPLYST-001.0/D] IS the record of what template versions are deployed to which repositories.
- [DPLYST-002.0/D] MUST be stored as JSON at `.steerspec/deployment-state.json` in the central repository.
- [DPLYST-003.0/D] HAS per-repository records containing: deployed version, timestamp, PR number, and PR status.
- [DPLYST-004.0/D] MUST be updated after each SyncOperation.
- [DPLYST-005.0/D] HAS a Blake3 hash for integrity verification.

Version(s):
	- 0.1.0-draft (2026-03-07): initial draft

Notes:
