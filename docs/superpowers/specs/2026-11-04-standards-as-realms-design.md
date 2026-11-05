# Standards as realms design (GH #144)

Design for [SteerSpec/strspc-rules#144](https://github.com/SteerSpec/strspc-rules/issues/144).
It builds on #114, which shipped Standard References, `standard` notes and the coverage report.
Rules and schema changes belong in this repo. strspc-manager implements lint, coverage and
crosswalks from the manager-facing contract below. The consumers are
[strspc-CLI#239](https://github.com/SteerSpec/strspc-CLI/issues/239) (coverage gate) and
[strspc-manager#269](https://github.com/SteerSpec/strspc-manager/issues/269) (regressions). Status:
**proposal**. Nothing here is decided until PLB records it on #144.

## Context

[#114](https://github.com/SteerSpec/strspc-rules/issues/114) decision 1: SteerSpec doesn't hold standards' clause lists. Core is published on steerspec.dev,
so holding lists for licensed standards would redistribute them. The coverage report therefore shows
only the clauses some rule maps. That leaves three things impossible:

- **Typo checks.** Lint checks a note's standard id (RL029 to RL031), but the clause after the colon is
  free text. `owasp.asvs:2.1.11` passes.
- **Gaps.** A clause nobody mapped is invisible. There's no `unmapped` status.
- **A figure.** "80 % of ASVS L2" needs a denominator, so a CI gate can only check debt and regressions
  (#239).

The fix: the clause list is published **as a realm**, by the standard's owner or by anyone its licence
allows, and a project depends on it. SteerSpec still holds no list. A project pins one, the way it pins
core.

What already works:

- **Hosting.** A dependency `source` can be any GitHub repo
  (`github://<owner>/<repo>@<tag>/<path>`), fetched and cached like core.
- **Qualified rule references.** The `overrides` pattern accepts `<realm-id>:<EUID>-<NNN>`.
- **Immutable text.** A Published rule can't change (RUL-007), and fixes go through `supersedes` (RUL-014).

### Pilot data: OWASP ASVS 5.0.0

- **Licence:** CC BY-SA 4.0 (`OWASP/ASVS`).
- **Machine-readable release:** `OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json`,
  release `v5.0.0_release`. Each row has `chapter_id`, `section_id`, `req_id`, `req_description`, and `L`,
  the minimum level.
- **Size:** 345 requirements in 17 chapters and 80 sections, at most 16 per section.
- **Levels are cumulative:**

  | Level | Requirements |
  | --- | --- |
  | L1 | 70 |
  | L2 | 253 |
  | L3 | 345 |

- Every requirement starts "Verify that…". 130 of the 345 have more than one sentence.
- **Official edition mapping:** `5.0/mappings/mapping_v4.0.3_to_v5.0.0.yml`, with 278 entries for
  4.0.3. Each entry is counted once, by the first match in the order split, merged, covered by,
  deleted, modified, moved:

  | Kind | Entries |
  | --- | --- |
  | moved | 95 |
  | deleted (out of scope or insufficient impact) | 51 |
  | modified | 48 |
  | merged | 31 |
  | covered by another requirement | 27 |
  | split | 26 |

### Constraints from existing rules

| Rule | Consequence |
| --- | --- |
| Rule ID pattern `^[A-Z0-9]+-\d{3}$`; RLIFRMT-008, rendering only | `V1.1.1` can't be a rule ID, so the standard's own number needs a field |
| RUL-003: identifiers are never reused | ASVS 5 reuses `V1.1.1` with a new meaning, so editions can't share one realm's ID space |
| RUL-012 (Draft): `supersedes` stays within one entity | Editions move requirements across chapters, so a crosswalk is needed rather than supersession |
| RUL-004 (Published): a rule is a single phrase | Conflicts with verbatim transcription of 130 requirements |
| RULST-009: no Implemented while the governed code violates it | A standard realm governs no code, so its rules stay Published |
| RD006: a superseded rule retires when its replacement reaches Implemented | A standard rule never reaches Implemented, so a transcription fix needs its own transition |
| `realm` sets `additionalProperties: false` | Licence and attribution fields need a schema change |
| STDREF-009: no Standard Reference reaches an inheriting entity | Unchanged. A consumer links the standard itself |

## Design

### Goals / non-goals / anti-goals

- **Goal:** a project is measured against a standard's complete clause list, at a claimed level.
- **Goal:** lint rejects a mapping to a clause that doesn't exist.
- **Goal:** moving to a new edition carries mappings forward where the standard says the clause moved.
- **Non-goal:** SteerSpec holding or redistributing clause lists (#114 decision 1 stands).
- **Non-goal:** adopting a standard's text as a project's own rules (the adopt model, after #35).
- **Anti-goal:** a figure that counts a clause as covered without an Implemented rule of the project.
- **Anti-goal:** a transcription that presents itself as the standard owner's own publication.

### Standard realm layout

- One entity per chapter (`V1`) and one sub-entity per section (`V1S1`). Each requirement is a rule:
  `V1.1.1` → `V1S1-001`, numbered in the standard's order.
- **Rule field `clause`** (string): the standard's own number, `V1.1.1`. **Required on every live
  rule of a standard realm**, since the clause list and the coverage total are built from these
  labels: a rule without one would drop out of both unnoticed. Optional, and normally absent, in
  other realms. Telling the two kinds apart is open question 3. It's set while the
  rule is Draft and never changes (RUL-007). It's unique among the realm's **live** rules: those not
  superseded, Retired, Terminated or Abandoned. A rule that supersedes another must keep its
  `clause`, so a transcription fix never changes which clause a project's notes resolve to.
- **Rule field `profiles`** (optional list of strings): the levels the clause belongs to, for example
  `["L2", "L3"]` for a requirement whose minimum level is 2.
- **Realm field `profiles`**: the allowed names, in order. A rule's `profiles` must be drawn from it.
- **Realm fields `license`** (SPDX ID) and **`attribution`** (`{text, url}`). CC BY-SA requires both,
  and the transcription keeps the same licence.
- **Realm field `edition`** (string): the edition the realm transcribes, `5.0.0`. The realm `version`
  is the transcription's own release version, and it moves with fixes.
- Rule bodies are the standard's text, verbatim.
- The rules are Published once the transcription is checked. They're never Implemented.
- **Generated.** A script reads the publisher's machine-readable release and runs
  `strspc entity add` and `strspc rule add`, so hashes stay valid and no rule JSON is written by hand.
- **Transcription fixes.** A fix supersedes the rule within its section entity (RUL-014, RUL-012) and
  keeps its `clause`. The code-realm path doesn't apply: RD006 retires the superseded rule when its
  replacement reaches Implemented, and a standard rule never does. In a standard realm, the
  superseded rule moves to **Terminated** (no longer in force, RULST-008) when its replacement
  reaches Published, in the same change. This needs a transition rule specific to standard
  realms, so it depends on the realm kind (open question 3).

### Linking a Standard Reference to the realm

The Standard Reference gains two optional fields:

```json
"standards": [
  { "id": "owasp.asvs", "version": "5.0.0", "relation": "implements",
    "realm": "dev.steerspec.std.owasp.asvs.v5", "profile": "L2" }
]
```

- `realm` must name an entry of the realm's `dependencies`.
- `version` is required when `realm` is set, and must equal the linked realm's `edition`. That keeps
  STDREF-011's clause identity (id, version, clause) unambiguous. The dependency's own `version`
  pins the transcription release, not the edition.
- `profile` must name one of that realm's `profiles`, and is allowed only with `realm`.
- When `realm` is set, a `standard` note's clause (`owasp.asvs:V1.1.1`) must equal the `clause` of a
  rule in that realm, at the pinned version. Matching is exact and case-sensitive.
- When `realm` isn't set, behaviour is #114's, unchanged.

### Coverage (contract for strspc-manager `coverage`)

For a linked Standard Reference, the clause list is the `clause` labels of the linked realm's live rules,
filtered by `profile` when it's set.

- **Statuses:** `covered`, `mapped` and `lapsed` as in STDREF-012 to STDREF-015, plus **`unmapped`**:
  a clause in the list that none of the entity's coverage rule set maps, and that isn't excluded.
- **Excluded:** a clause the project declares not applicable. Each exclusion carries the clause, a
  justification, an author and a date. Where it lives (a realm-level `exclusions` list or a note
  type) is open question 4.
- **Figure:** covered ÷ (clauses in the profile − excluded), per Standard Reference. It's measured
  realm-wide: a clause counts as covered if any entity in scope covers it. Per-entity rows stay as
  today.
- `cited` is unchanged. `derived_from` gets no figure.

### Editions and crosswalks

- **One realm per edition:** `…owasp.asvs.v4` and `…owasp.asvs.v5`. The realm `version` tracks
  transcription fixes. The edition is the Standard Reference `version`.
- A newer edition's realm may ship `_crosswalk/<previous-edition>.json`. For each old `clause` it
  gives a kind and its targets:

  ```json
  { "from": "4.0.3", "entries": [
      { "clause": "1.2.4", "kind": "split", "to": ["V6.1.3", "V6.3.4"] },
      { "clause": "1.1.1", "kind": "deleted", "reason": "not in scope" } ] }
  ```

  The kinds are `moved`, `modified`, `split`, `merged`, `covered_by` and `deleted`, as in OWASP's YAML.
- **Contract for strspc-manager:**
  - A `migrate` operation proposes new `standard` notes for a project's old mappings.
  - `coverage.Compare` (#269) classifies an edition upgrade from the crosswalk:
    - The old clause is carried forward when its targets are covered.
    - It's a regression when its targets aren't covered.
    - It's no regression when the clause was `deleted`.

### Trust and naming

- A transcription that SteerSpec publishes uses its own namespace:
  `dev.steerspec.std.<publisher>.<standard>.<edition>`. Realm IDs allow no hyphens.
- A publisher's own realm uses its reverse-DNS namespace (`org.owasp.…`).
- How a publisher proves it owns a namespace relates to #135 (contributor verification and entity
  signing, with no central identity service). It isn't designed here.

### Lint and validation codes (contract; the manager assigns numbers)

- A `clause` is duplicated among a realm's live rules.
- A live rule of a standard realm has no `clause`.
- A rule that supersedes another has a different `clause`.
- A Standard Reference with `realm` has no `version`, or a `version` other than the linked realm's
  `edition`.
- A rule's `profiles` entry isn't declared on the realm.
- A Standard Reference's `realm` isn't a dependency, or its `profile` isn't declared on that realm.
- A `standard` note names a clause that the linked realm doesn't have, or has only on rules that aren't live.
- A crosswalk entry's `clause` isn't in the previous edition, or a target isn't in this one.

## What this repo ships

- STDREF rules for the `realm` and `profile` links, `unmapped`, exclusions and the figure.
- RUL rules for `clause` and `profiles`.
- RLMMNFST rules for `license`, `attribution` and `profiles`.
- A crosswalk rule set.
- Schema changes:
  - `entity.v1` (`clause`, `profiles`, the Standard Reference fields): through
    `tools/build-schema.py`, which generates `entity.v1` and `config.v1`.
  - `realm.v1` (`license`, `attribution`, `edition`, `profiles`, the Standard Reference fields):
    hand-maintained, and it needs explicit approval, as in #114.
- Every new field is optional and absent when unused, so existing files keep their bytes and their
  hashes. In strspc-manager's Go structs, that means `omitempty` on each new field.
- No transcription. The pilot realm lives in its own repo (open question 6).

## Steps

1. Decide the open questions on #144.
2. Rules and schemas, all Draft, released in a core minor version.
3. strspc-manager: struct fields, lint, coverage over linked realms, crosswalk loading, #269.
4. strspc-CLI: preserve the fields, `standards coverage` with `unmapped` and the figure, authoring
   flags, and the #239 gate with `--min-coverage`.
5. Pilot: generate ASVS 5.0.0 L1 (70 clauses), and map at least one strspc-CLI rule to it.
6. Crosswalk: generate 4.0.3 → 5.0.0 from OWASP's YAML, and check it against both pilot editions.

## Verification

- `strspc realm validate --strict` and `strspc lint --strict` pass on the pilot realm.
- `strspc standards coverage` in strspc-CLI shows `covered`, `mapped` and `unmapped` against the
  70-clause total.
- A note naming a clause that doesn't exist fails lint, and so does one naming a clause whose rules are all Terminated. After a transcription fix, a note keeps resolving to the superseding rule.
- Excluding a clause lowers the total, and the report lists the justification.
- With the crosswalk, a 4.0.3 mapping of a `moved` clause is proposed as the 5.0.0 clause.

## Open for PLB

1. **RUL-004.** 130 of 345 requirements have more than one sentence. Exempt standard realms (with a
   realm kind, question 3), or split them, which breaks the 1:1 match with the standard's numbering?
2. **`clause` as a field.** #114 used a note for mappings because of RUL-007. A clause label is set
   while the rule is Draft and never changes, so a field fits. Confirm.
3. **Realm kind.** Does a standard realm declare `"kind": "standard"`, so tools never evaluate its rules
   and lint skips checks meant for code realms? Or do `license` and `clause` imply it? The
   transcription-fix transition (superseded → Terminated when the replacement is Published) needs one
   or the other, since it must not apply to code realms.
4. **Exclusions:** a realm-level list, which is easy to audit in one place, or a note type, which
   carries author, date and revision but sits on no rule of the project's?
5. **ShareAlike reach.** Mapping by ID isn't a derivative. Inheriting the text (the adopt model) may be.
   This needs a legal read before #35-based adoption.
6. **Pilot home:** a new repo (`SteerSpec/strspc-std-owasp-asvs`), mirroring how OWASP would host it,
   or `rules/std/` here?
7. **Scope of the figure.** Above, a clause counts as covered realm-wide when any entity covers it.
   STDREF-012 is per entity. Should the figure be per entity, with the realm-wide figure derived, or
   realm-wide only?
