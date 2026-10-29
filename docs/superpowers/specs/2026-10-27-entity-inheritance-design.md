# Entity inheritance design (GH #35)

Design + plan for [SteerSpec/strspc-rules#35](https://github.com/SteerSpec/strspc-rules/issues/35).
Scope agreed with PLB: rules, schema and `build-schema.py` change in this repo, plus a
manager-facing contract (merge, lint, render, evaluator prompt) that strspc-manager
implements from. No manager code in this plan.

## Context

Entities support containment (`parent` / `sub_entities`) and same-entity replacement
(`supersedes`), but no specialisation. A product realm that wants `SAVACCT` to carry all of
`dev.globalbank.core:ACCT`'s rules must copy them, and the copies drift.

The issue proposes `inherits` plus "override via `supersedes`". Investigation found three
things the issue misses:

1. **`supersedes` cannot express an override.** RD006 (manager) requires the superseded
   rule to move to Retired when the superseding one reaches Implemented. A child can never
   retire a parent's rule: inherited rules are read-only references owned by the parent
   (ENT-009), cross-realm ones are dependency imports as well (RLM-005), and the
   `supersedes` schema pattern is same-realm only. Decision (PLB): a **new rule field, parent untouched**.
2. **Rule-resolve ignores realm dependencies.** The manager evaluates "every rule in every
   configured source" (`config.yaml`); `realm.json` dependencies are only used by
   realm-resolve for EUID collision checks. Decision (PLB): inheritance is **structure in
   the evaluator prompt**: inherited rules are materialised into the child's effective set
   and tagged with origin; an override is sent as "wins where the child's subject applies".
   Parent rules keep firing elsewhere. No deterministic shadowing. When the parent realm
   is also a configured source, the parent rule's own entry is annotated with the child
   rules that override it (PLB), so the evaluator can judge it `not_applicable` on the
   child's subject.
3. **Manager and CLI drop unknown JSON fields.** `entityops/version.go` marshals the Go
   struct, so any `strspc rule …` command on a file with `inherits`/`overrides` strips
   them until `entity.Entity`/`entity.Rule` gain the fields. Fixes release order:
   rules here → manager structs + resolver → CLI.

Three of the issue's open questions are already answered by existing rules:

- Q3 namespacing: rule IDs carry the EUID and RLM-006 forbids EUID collisions across
  dependencies, so `SAVACCT-001` overriding `ACCT-005` is unambiguous.
- Q5 hash: RST-001 ties a rule set to one entity. The child's hash covers its own rules.
  A cross-realm parent is frozen by the dependency `version` pin in `realm.json`; its
  changes arrive only on a dependency bump. A same-realm parent is not pinned: child and
  parent evolve together and ship in the same realm version.
- Q2 sub-entities: `parent` is containment, `inherits` is specialisation. Orthogonal;
  both allowed on the same object.

## Design

### Goals / non-goals / anti-goals

- Goal: a child entity reuses a parent's rule set without copying, in-realm or cross-realm.
- Goal: a child can replace one inherited rule for its own subject without touching the parent.
- Non-goal: multiple inheritance, mixins, merge strategies beyond override.
- Anti-goal: anything that lets a child mutate, retire or re-state a parent's rule.
- Anti-goal: an override that silently removes a parent rule from evaluation everywhere.

### Entity field `inherits` (optional, string)

```json
{ "entity": { "id": "SAVACCT", "title": "Savings Account", "inherits": "dev.globalbank.core:ACCT" } }
```

- Scalar. Short EUID in-realm, `<realm-id>:<EUID>` cross-realm (RLM-009 form).
- Target may be any entity, top-level or sub-entity (EUIDs are realm-unique, RLM-001).
- Cross-realm target's realm MUST be a declared dependency of the child's realm (RLM-005,
  effective list per RLM-014 for sub-realms).
- Chains allowed; cycles rejected; **max 3 hops** (A→B→C→D). *My call.*
- Inherited: the parent's own `rules` in state **P or I**, transitively through the chain.
  *My call:* not D (text may change), not A/R/T (not in force). Parent `sub_entities` are
  **not** inherited; sub-entities are containment, not part of the parent's rule set.
- Inherited rules stay owned by the parent: same ID, state, revision, notes, `rule_set`.
  They never appear in the child's `rules` array and never affect the child's hash.

### Rule field `overrides` (optional, string or null)

```json
{ "id": "SAVACCT-003", "overrides": "dev.globalbank.core:ACCT-005", ... }
```

- Names exactly one rule present in the child's inherited effective set: the parent's
  effective rule set after every ancestor's overrides have been applied. A rule that an
  ancestor already replaced is not a valid target; to override it again, name the
  ancestor's overriding rule instead. Same qualified /
  short form as NTE-007. *My call on the name:* `overrides`, not `supersedes`, because the
  lifecycle differs (no Retired obligation, parent untouched).
- Semantics: in the child's effective set, the overriding rule replaces the target. Outside
  the child (the parent's own context, any other child), the target is unaffected.
- One override per target per child, counting only rules that are not themselves
  superseded, so a supersession chain that restates the override (RUL-011) is not a
  conflict. Two live child rules overriding the same target is a lint error.
- `supersedes` and `overrides` are orthogonal and may coexist: when `SAVACCT-009 supersedes
  SAVACCT-003`, it restates `overrides: ACCT-005` to keep the override alive after
  SAVACCT-003 retires. *My call:* a rule that forbade both would make overrides
  un-evolvable.
- Lifecycle: the overriding rule follows the normal D→P→I path. The override is in effect
  whenever the overriding rule itself is in the evaluation set (it survives `evaluate_on`,
  default D/P/I). Retired/Terminated rules never survive, so the inherited rule reappears
  naturally, provided the resolver filters before applying overrides (see the effective
  rule set below). The P/I filter applies to what is *inherited*, not to overrides.

### Effective rule set (contract for the manager)

For entity E with chain E → P1 → … → Pn (n ≤ 3):

1. Start with Pn's own rules in P/I, then Pn-1's, …, then P1's. At each step apply that
   entity's `overrides`: remove the target from the set, add the overriding rule.
2. Add E's own rules that survive the consumer's `evaluate_on` filter (default D/P/I),
   then apply the `overrides` of those surviving rules only. Filtering before applying
   overrides is what lets an inherited target reappear when its overriding rule is
   Retired or Terminated; applying overrides first would drop both.
3. Each entry carries `owner` (the entity whose `rules` array holds it) and `inherited_by`
   (E, when owner ≠ E) and, for an overriding rule, `overrides` (the replaced ID).

The consumer's `evaluate_on` filter is applied today in `ruleeval.Evaluator.plan`, after
`RuleInput`s are built, so step 2 cannot rely on it. The effective-set builder takes the
evaluate states as an input and filters E's own rules itself before applying overrides.

### Evaluator prompt (contract for `ruleeval/prompt`)

- `RuleInput` (and `EvalRequest`, which mirrors it) gains `Owner string`,
  `InheritedBy string`, `Overrides string` and `OverriddenBy []string`.
- Batch grouping: `EntityID` is the batch grouping key and verdicts are keyed by rule ID
  within a group. An inherited entry keeps the **inheriting** entity's `EntityID`, so it is
  evaluated alongside the child's own rules, and `Owner` carries the owning entity for the
  `entity:` line. Single inheritance means one rule ID appears at most once per group.
- `writeRule` emits `inherited by: <EUID>`, `overrides: <qualified rule id>` and
  `overridden by: <rule id> (<child entity title>)` lines.
- The parent rule's own-context entry (when the parent realm is also a configured source)
  carries `OverriddenBy` listing every overriding rule from every resolved child, so the
  evaluator can judge it `not_applicable` on the child's subject. Decision (PLB): verdicts
  on a parent rule therefore depend on which child realms the consumer has configured,
  as they already depend on configured sources.
- System prompt gains one bullet: an inherited rule applies to the inheriting entity's
  subject as well as its owner's; a rule marked "overridden by" does not apply where the
  overriding entity's subject applies, and still applies to its owner's subject elsewhere.
- `prompt.Version` bumps (cache invalidation), and `CacheKey` (`ruleeval/batch.go`) mixes
  in `InheritedBy`, `Overrides` and `OverriddenBy`, otherwise the inherited entry and the
  owner-context entry of the same rule share a cache key.
- A rule evaluated through two paths (parent realm is also a source, and inherited) is sent
  once per distinct `(id, inherited_by)` pair. *Left to the builder* whether to dedupe to
  one entry with a list of inheritors.

### Resolution (contract for `rule-resolve` / `realm-resolve`)

- `rule-resolve` never reads `realm.json`; the consumer (today `strspc check`) loads each
  source's `realm.json` and calls realm-resolve, whose output is currently discarded. The
  effective-set builder takes realm-resolve's output, so `ResolvedRealm` must retain the
  parsed entity files (today it keeps only an EUID → path map).
- A parent realm that is both a dependency and a configured source raises no conflict:
  RSV005 is a collision **error** between configured sources (rule-resolve), not a dedupe,
  and dependency loading (realm-resolve) is a separate path. The parent's own-context
  entries come from the configured source; its inherited copies come from the dependency.
- **Transitive, per-hop resolution (decision, PLB).** Each hop's `inherits` target resolves
  against the effective dependency list (RLM-014) of the realm that owns *that hop's*
  entity, with that realm's own version pins. A chain X:A → Y:B → Z:C where Z is a
  dependency of Y only therefore resolves, and ENT-007 holds per hop. Dependencies of
  dependencies are loaded lazily, only when a chain reaches them, and cached by
  `(realm_id, version)`; diamond pins never need reconciling because each hop uses its own
  realm's pin. The three-hop cap bounds the extra loads.
- Chain walk with cycle detection and depth cap.

### Lint / diff codes (contract; numbers assigned by the manager)

Numbers corrected against strspc-manager v1.22.0, where RL015 (note sequence) and RD013
(note revision) were already taken: the rule-lint codes shift to RL016–RL018 and the diff
codes are RD017–RD018. These codes are introduced by SteerSpec/strspc-manager#139 (M1) and
are not in any released version yet. RR013–RR016 were free and are reserved for M2. The
realm-resolve prefix is RR; RSV is rule-resolve.

`rule-lint` has no dependency loading (RL014 skips qualified references for that reason,
RL012 is a Warning). Follow that precedent: `rule-lint` warns on what it cannot see in the
scanned files; `realm-resolve` / `rule-resolve`, which load dependencies, raise the errors.
*My call.*

| Code (proposed) | Module | Severity | Condition |
|---|---|---|---|
| RL016 | rule-lint | Warning | `inherits` target not found in the scanned files (same-realm short form), or `overrides` target not found and unqualified. Presence only: qualified cross-realm targets are skipped here, and reference-form errors (an unqualified target that names an entity in a dependency) are RR013's. |
| RL017 | rule-lint | Error | Two live rules in one entity override the same target. A rule is live unless another rule supersedes it or it is Abandoned or Terminated, so inactive historical rules never trigger it. |
| RL018 | rule-lint | Error | `inherits` chain within the scanned files is cyclic or longer than 3 hops. |
| RR013 | realm-resolve | Error | `inherits` target cannot be resolved: unknown EUID, realm not in the effective dependency set, or cross-realm reference not in qualified form. |
| RR014 | realm-resolve | Error | `inherits` chain across realms is cyclic or longer than 3 hops. |
| RR015 | realm-resolve | Error | `overrides` names a rule that is not in the entity's inherited effective set: unknown anywhere in the chain, or already replaced by an ancestor's override. |
| RR016 | realm-resolve | Warning | `overrides` target exists in the chain but is not in state P/I in the pinned parent (parent superseded or retired it; the override is dead). |
| RD017 | rule-diff | Error | `inherits` changed from one value to another, or removed, on an entity whose **base** version has a rule beyond Draft, so promoting the first rule and re-parenting in the same change passes. Adding `inherits` where there was none is allowed (it only adds rules). *My call:* re-parenting is a breaking change; do it by a new entity. |
| RD018 | rule-diff | Error | `overrides` added, removed or retargeted on a rule that has left Draft (RUL-007); supersede the rule instead. |

Migration for entities that copied a parent's rules by hand (the issue's motivation):
add `inherits`, then `strspc rule retire` each copy that duplicates a parent rule, and
`strspc rule supersede` each copy that specialises one with a new rule carrying
`overrides`. RUL-007 forbids adding `overrides` to an existing P/I rule. *My call.*

### Rendering (contract for `render`)

Markdown output of the child shows its own rules as today, then an **Inherited rules**
section listing each inherited rule with owner entity, realm and state, and marking
overridden rules as `overridden by SAVACCT-003`. Inherited rules are not repeated as if
owned. `strspc render` also has a JSON format; it gets an `inherited` array with the same
fields. No `index.json` exists in the manager today.

### What this repo ships

New core rules, all added as **Draft** via `strspc rule add --dir rules/core` and promoted
in separate PRs per the existing lifecycle. Proposed wording (IDs are the next free numbers;
confirm with `strspc` at add time):

ENT (next ID ENT-006):

- ENT-006: MAY inherit the rule set of exactly one other Entity, declared in an `inherits` field holding the parent's Entity Unique Identifier.
- ENT-007: An `inherits` reference to an Entity in another Realm MUST use the qualified form `<realm-id>:<EUID>`, and that Realm MUST be a declared dependency.
- ENT-008: An inheritance chain MUST NOT contain cycles and MUST NOT exceed three hops.
- ENT-009: An inheriting Entity acquires the parent's effective rule set, the parent's own Published and Implemented Rules together with those the parent inherits, as read-only references that remain owned by their original Entity.
- ENT-010: An inheriting Entity's Rule Set covers only the Rules it owns.

RUL (next ID RUL-009):

- RUL-009: MAY declare `overrides` naming one inherited Rule, which the declaring Rule replaces within the inheriting Entity's effective rule set only.
- RUL-010: Within an Entity, at most one Rule that is not itself superseded MAY override a given inherited Rule.
- RUL-011: A Rule that supersedes an overriding Rule MUST restate the `overrides` it takes over, or the override lapses.

ENT-007 and ENT-008 are compound; RLM-010/011 set precedent for that. *My call:* keep
them compound rather than split into four rules.

Notes (rationale) on ENT-006 and RUL-009 explaining why `overrides` is distinct from
`supersedes` and why parent rules keep applying elsewhere, added with
`strspc note add <rule-id> --type rationale --dir rules/core` (verified: the CLI supports
notes on top-level entity rules and patch-bumps the rule set).

Schema (`tools/build-schema.py`, then regenerate `rules/core/_schema/entity.v1.schema.json`):

- `entity.properties.inherits`: `{"type":"string"}` next to `parent` (line ~349), following
  the `parent` precedent. *My call:* no pattern, because the EUID length/charset already
  live in the extracted `euid_constraints` and a literal copy would drift; resolution and
  form are checked by the manager (RL016).
- `rule_schema.properties.overrides`: `oneOf` string with pattern
  `^([a-z][a-z0-9]*(\\.[a-z][a-z0-9]*)*:)?[A-Z0-9]+-\\d{3}$` or null, next to `supersedes`
  (line ~295). The rule-id part mirrors the existing hardcoded `supersedes` pattern; the
  realm prefix mirrors the SPEC realm-id grammar.
- Hardcoded structural properties, not regex-extracted from rule text.
- `bootstrap.schema.json` and `realm.v1.schema.json` are untouched (hand-maintained axioms;
  verified the bootstrap `entity` and `rules.items` objects carry no
  `additionalProperties: false`, so the new fields already pass it).
- `ruff` is not installed locally; `pip install ruff` before step 3.
- Side note for a separate chore: AGENTS.md says the CLI handles top-level entities only,
  but `strspc rule add --sub-entity` exists now.

**Sequencing (decision, PLB):** the schema properties are held back until a
strspc-manager release whose `entity.Entity` / `entity.Rule` structs carry the fields.
Publishing the schema earlier would license consumer realms to write fields that the
current CLI (1.15.0 pinned in CI) silently strips on the next `strspc rule …` command.
The struct fields MUST use `omitempty` (`Inherits string json:"inherits,omitempty"`,
`Overrides *string json:"overrides,omitempty"`), unlike `supersedes` which always writes
`null`: until this repo's schema PR lands, the live `entity.v1` schema has
`additionalProperties: false`, so an emitted `"overrides": null` would fail schema
validation and change the hash of every file the new CLI rewrites. The manager therefore
ships in two releases: M1 (struct fields plus the rule-lint and rule-diff codes), which
unblocks PR B and the CLI flags, then M2 (resolution, effective set, prompt, render).
So this repo ships two PRs:

- **PR A (now):** design doc + Draft rules ENT-006..010, RUL-009..011 + rationale notes.
  No schema change.
- **PR B (after the manager release):** `build-schema.py` change + regenerated
  `entity.v1.schema.json`, in the same PR as (or before) the Draft→Published promotion.

## Steps

1. Create a beads epic for #35 with children: PR A (this repo), manager contract issue,
   PR B (this repo, blocked on manager), CLI issue (blocked on manager).
   `bd create … --type=epic`, `bd create --parent=…`, `bd dep add`.
2. Commit this design to `docs/superpowers/specs/2026-10-27-entity-inheritance-design.md`
   (brainstorming skill convention) on branch `worktree-inherit`.
3. Add ENT-006..010 and RUL-009..011 as Draft with `strspc rule add --dir rules/core`
   and the rationale notes with `strspc note add … --dir rules/core` (both bump versions,
   timestamps, hashes). Ask PLB for the `--added-by` handle at execution time
   (`@pleberre` is the handle on existing rules).
4. `python3 tools/build-schema.py --check` (core files changed; schema itself must stay
   stable in PR A), `strspc diff rules/core --base origin/develop`,
   `strspc realm validate rules/core/ --recursive --strict`.
5. Open PR A to `develop` (conventional commit `feat(ent): …`). Do not merge.
6. Open the strspc-manager issue with the contract sections above (effective set, prompt,
   resolution, codes, render) and the struct change as its first task. Open the CLI issue
   for `strspc rule add --overrides` and `strspc entity … --inherits`, blocked on the
   manager release. Post a short design summary on #35 linking the spec and both issues.
7. **PR B, later:** `pip install ruff`; edit `tools/build-schema.py` (`inherits` next to
   `parent` at line ~349, `overrides` next to `supersedes` at line ~295); `ruff check .`,
   `ruff format .`; `python3 tools/build-schema.py`; verify `--check`; PR to `develop`.

## Verification

PR A:

- `python3 tools/build-schema.py --check` exits 0 (no schema drift).
- `strspc realm validate rules/core/ --recursive --strict` passes.
- `strspc diff rules/core --base origin/develop` reports only new Draft rules and notes,
  no skipped states.
- The design doc renders and links resolve.

PR B:

- `ruff check . && ruff format --check .` clean.
- `python3 tools/build-schema.py --check` exits 0 after regeneration.
- Hand-written fixture in the scratchpad (a `SAVACCT` file with `inherits` and one
  `overrides`) validates against the regenerated schema with `jsonschema`; a variant with
  `inherits` as an array, or `overrides` as a malformed id, is rejected. Resolution
  failures (unknown target, missing dependency) are the manager's RR013/RR015, not the
  schema's.
- Round-trip the fixture through the released `strspc rule add` and confirm the fields
  survive.

## Open for PLB

Settled as my calls above and worth a glance: `overrides` as the field name; P/I only
inherited; three-hop cap; sub-entities of the parent not inherited; `supersedes` and
`overrides` may coexist (RUL-011); override in effect whenever the overriding rule is
evaluated; re-parenting is a breaking change but first adoption is not (RD017); `inherits`
has no schema pattern (resolution is the manager's job).
