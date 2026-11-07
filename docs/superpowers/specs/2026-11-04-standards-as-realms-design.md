# Standards as realms design (GH #144)

Design for [SteerSpec/strspc-rules#144](https://github.com/SteerSpec/strspc-rules/issues/144).
It builds on #114, which shipped Standard References, `standard` notes and the coverage report.
Rules and schema changes belong in this repo. strspc-manager implements lint, coverage and
crosswalks from the manager-facing contract below. The consumers are
[strspc-CLI#239](https://github.com/SteerSpec/strspc-CLI/issues/239) (coverage gate) and
[strspc-manager#269](https://github.com/SteerSpec/strspc-manager/issues/269) (regressions). Status:
**decided**. PLB recorded the decisions on #144 on 2026-11-07, listed under [Decisions](#decisions).
The rules are in core as Draft: STDRLM, STDCWK, RUL-015 to RUL-017, RLMMNFST-008 to RLMMNFST-014,
STDREF-017 to STDREF-028 and NTE-026 to NTE-035.

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
| RUL-004 (Published): a rule is a single phrase | A requirement with more than one sentence is split into several rules (decision 1) |
| RULST-009: no Implemented while the governed code violates it | A standard realm governs no code, so its rules stay Published |
| RD006: a superseded rule retires when its replacement reaches Implemented | A standard rule never reaches Implemented, so a transcription fix needs its own transition |
| `realm` sets `additionalProperties: false` | Licence and attribution fields need a schema change |
| NTE-003, NTE-021, NTE-022 (Implemented): a note belongs to one rule and sits next to it | Exclusions are realm-level notes (decision 4), so these are superseded |
| STDREF-009: no Standard Reference reaches an inheriting entity | Unchanged. A consumer links the standard itself |

## Decisions

Recorded on #144.

1. **RUL-004: split requirements.** A requirement with more than one sentence becomes several rules,
   so RUL-004 applies to standard realms too. One clause can then be several rules
   (`V1.1.1` → `V1S1-001`, `V1S1-002`). The **clause is the unit**: a `standard` note names a clause,
   never a part of one, and coverage counts clauses.
2. **Clause label: a field on the rule.** `clause`, set while the rule is Draft and then fixed by
   RUL-007. Rules that share a clause share its value.
3. **Profiles: a list on the rule**, with the allowed names declared once on the realm. The rules of
   one clause declare the same profiles.
4. **Realm kind: an explicit field,** `"kind": "standard"`. A realm without it is a code realm.
5. **Exclusions: realm-level notes.** A new note type, `exclusion`, held in the manifest's `notes`
   array, with its own identifier, author, date and revision. This supersedes NTE-003, NTE-021 and
   NTE-022.
6. **Manifest hash: the whole manifest.** `realm.json` gets a `hash`, the Blake3 hash of the
   manifest without that field, recomputed on every change to it.
7. **Figure: per entity, plus a realm figure.** Each entity gets its own figure, and the realm figure
   counts a clause as covered when any entity of the realm tree covers it.
8. **ShareAlike reach: assume it applies.** The adopt design (#35) assumes that rendering inherited
   standard text puts the consumer's rendered rules under CC BY-SA, so tools carry the standard's
   `license` and `attribution` into that output. Mapping by clause ID isn't affected. A legal read is
   still needed before adopt ships.
9. **Pilot home: a new repo,** `SteerSpec/strspc-std-owasp-asvs`, CC BY-SA 4.0 throughout, with realm
   ID `dev.steerspec.std.owasp.asvs.v5`.
10. **STDREF-001 to STDREF-016** are published in a separate PR, after these rules settle.
11. **Note identifiers:** rule notes keep `<EUID>-NNN/NN`. Realm notes are `REALM/NNN`, because they're
    numbered across a realm, and one standard can need more than 99 exclusions.

## Design

### Goals / non-goals / anti-goals

- **Goal:** a project is measured against a standard's complete clause list, at a claimed level.
- **Goal:** lint rejects a mapping to a clause that doesn't exist.
- **Goal:** moving to a new edition carries mappings forward where the standard says the clause moved.
- **Non-goal:** SteerSpec holding or redistributing clause lists (#114 decision 1 stands).
- **Non-goal:** adopting a standard's text as a project's own rules (the adopt model, after #35).
- **Anti-goal:** a figure that counts a clause as covered without an Implemented rule of the project.
- **Anti-goal:** a transcription that presents itself as the standard owner's own publication.

"Live" below means a rule that isn't Abandoned, Retired or Terminated, and isn't a Draft rule that
supersedes another (STDRLM-014). While a transcription fix is Draft, the rule it supersedes stays
live and the fix doesn't count. When the fix is Published, the old rule is Terminated in the same
change (STDRLM-013). A rule has at most one successor that isn't Abandoned (STDRLM-016), so a
competing fix must be abandoned before another is drafted. A fix supersedes only a live rule
(STDRLM-017), so it never targets a Draft or Abandoned fix: a new fix supersedes the live rule
itself. Together these keep exactly one transcription of each rule live at any time.

### Standard realm layout (STDRLM)

- The manifest declares `"kind": "standard"` (STDRLM-001), an `edition` (STDRLM-002), a `license`
  (STDRLM-003), an `attribution` (STDRLM-015) and, optionally, the `profiles` its rules may use
  (STDRLM-004).
- One entity per chapter (`V1`) and one sub-entity per section (`V1S1`). Each requirement is one or
  more rules, numbered in the standard's order: `V1.1.1` → `V1S1-001`, or `V1S1-001` and `V1S1-002`
  when it has two sentences.
- **Rule field `clause`** (RUL-015): the standard's own number, `V1.1.1`. Every live rule of a
  standard realm has one (STDRLM-005), so no rule drops out of the clause list unnoticed. Rules outside
  standard realms have neither `clause` nor `profiles` (RUL-017).
- **The clause list** (STDRLM-006) is the distinct `clause` values of the live rules. **A clause's text**
  (STDRLM-007) is the bodies of its live rules, in rule ID order.
- **Rule field `profiles`** (RUL-016): the levels the clause belongs to, `["L2", "L3"]` for a requirement
  whose minimum level is 2. Each entry is declared on the realm (STDRLM-008), and the rules of one
  clause declare the same list (STDRLM-009).
- **Realm fields `license`** (SPDX ID, RLMMNFST-010) and **`attribution`** (`{text, url}`,
  RLMMNFST-011). A standard realm must declare both: CC BY-SA requires them, and a transcription
  credits its source whatever the licence. The transcription keeps the standard's licence.
- The realm `version` is the transcription's own release version, and it moves with fixes.
- Rule bodies are the standard's text, verbatim, split at sentence ends where needed.
- The rules are Published once the transcription is checked. They never enter Implemented
  (STDRLM-010), and tools never evaluate them against code (STDRLM-011).
- **Generated.** A script reads the publisher's machine-readable release and runs
  `strspc entity add` and `strspc rule add`, so hashes stay valid and no rule JSON is written by hand.
- **Transcription fixes.** A fix supersedes the rule within its section entity (RUL-014, RUL-012) and
  keeps its `clause` (STDRLM-012), so a project's notes keep resolving. When the fix reaches Published,
  the superseded rule moves to Terminated in the same change (STDRLM-013). RD006's path doesn't apply,
  because a standard rule never reaches Implemented.

### Linking a Standard Reference to the realm

The Standard Reference gains two optional fields:

```json
"standards": [
  { "id": "owasp.asvs", "version": "5.0.0", "relation": "implements",
    "realm": "dev.steerspec.std.owasp.asvs.v5", "profile": "L2" }
]
```

- `realm` names a standard realm that is a dependency of the declaring realm tree (STDREF-017).
- `version` is required when `realm` is set, and equals the linked realm's `edition` (STDREF-018). That
  keeps STDREF-011's clause identity (id, version, clause) unambiguous. The dependency's own `version`
  pins the transcription release, not the edition.
- `profile` is allowed only with `realm` (STDREF-019) and names one of that realm's `profiles`
  (STDREF-027).
- The clause list of the reference is the realm's, limited to the profile when one is set (STDREF-020).
- When `realm` is set, a `standard` note's clause (`owasp.asvs:V1.1.1`) must be in the linked
  realm's whole clause list, not the list narrowed by `profile` (STDREF-021). Matching is exact and
  case-sensitive. A note may map a clause above the claimed profile: the mapping is valid, and the
  figure simply doesn't count it.
- When `realm` isn't set, behaviour is #114's, unchanged.

### Realm Notes and exclusions

- A note belongs to one rule or one realm (NTE-026). A rule's notes stay where they are (NTE-027,
  NTE-028). A realm's notes sit in the `notes` array of its manifest (NTE-029, RLMMNFST-012).
- Realm note IDs are `REALM/NNN`, sequential from 001 (NTE-030). Their types are `exclusion`,
  `rationale`, `clarification` and `reference` (NTE-031). An `exclusion` is always a realm note
  (NTE-032).
- An **exclusion** declares one clause not applicable (NTE-033). Its `ref` is `<id>:<clause>` and names
  a linked Standard Reference of the realm's manifest (NTE-034). Its content is the justification. It
  carries `added_by`, `added_at` and `revision` like any note, and NTE-008 to NTE-010 apply.
- An exclusion is never deleted. It's withdrawn by retyping it to `reference` (NTE-035), as a mapping is
  (NTE-019).

```json
"notes": [
  { "id": "REALM/001", "type": "exclusion", "ref": "owasp.asvs:V3.1.1",
    "content": "The CLI renders no HTML.", "added_by": "github:pleberre",
    "added_at": "2026-11-07", "revision": 0 }
]
```

### Manifest hash

- The manifest `hash` is the Blake3 hash of the manifest without its `hash` field, computed as for a
  Rule Set Hash (RLMMNFST-013), and recomputed on every change (RLMMNFST-014).
- It covers `realm.version` and `dependencies`, so release bumps, pin PRs and strspc-sync changes must
  all recompute it. Until the CLI does that, RLMMNFST-013 and RLMMNFST-014 stay Draft and the schema
  keeps `hash` optional.

### Coverage (contract for strspc-manager `coverage`)

- **Statuses:** `covered`, `mapped` and `lapsed` as in STDREF-012 to STDREF-015, plus **excluded**
  (STDREF-022), a clause named by a Realm Note of type `exclusion` in the realm's manifest, and **`unmapped`**
  (STDREF-023), a clause of the list that is none of the others.
- **Entity figure** (STDREF-024): covered ÷ (clauses in the list − excluded).
- **Realm figure** (STDREF-025): the same, with a clause covered when any entity of the realm tree
  covers it.
- A figure whose divisor is zero, because every clause in the list is excluded, is undefined
  (STDREF-028). Reports show it as such, and a gate never treats it as 0 % or 100 %.
- `derived_from` gets no figure (STDREF-026). `cited` is unchanged.

### Editions and crosswalks (STDCWK)

- **One realm per edition:** `…owasp.asvs.v4` and `…owasp.asvs.v5`. The realm `version` tracks
  transcription fixes. The edition is the Standard Reference `version`.
- A newer edition's realm may ship `_crosswalk/<previous-edition>.json` (STDCWK-002). For each old
  clause it gives a kind and its targets:

  ```json
  { "from": "4.0.3", "entries": [
      { "clause": "1.2.4", "kind": "split", "to": ["V6.1.3", "V6.3.4"] },
      { "clause": "1.1.1", "kind": "deleted", "reason": "not in scope" } ] }
  ```

  The kinds are `moved`, `modified`, `split`, `merged`, `covered_by` and `deleted`, as in OWASP's YAML
  (STDCWK-004). Every kind but `deleted` lists targets from the realm's clause list (STDCWK-005), and an
  old clause appears in at most one entry (STDCWK-007). The rules define the format. No JSON Schema
  ships for it yet.
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

- A live rule of a standard realm has no `clause` (STDRLM-005).
- A rule outside a standard realm has a `clause` or `profiles` (RUL-017).
- A rule's `profiles` entry isn't declared on the realm (STDRLM-008).
- Live rules sharing a `clause` declare different `profiles` (STDRLM-009).
- A standard realm has no `edition`, `license` or `attribution` (STDRLM-002, STDRLM-003, STDRLM-015).
- A rule of a standard realm is Implemented (STDRLM-010).
- A rule that supersedes another has a different `clause` (STDRLM-012).
- Two rules that aren't Abandoned supersede the same rule of a standard realm (STDRLM-016).
- A rule of a standard realm supersedes a rule that isn't live (STDRLM-017).
- A superseding rule of a standard realm is Published while the rule it supersedes isn't Terminated
  (STDRLM-013).
- A Standard Reference's `realm` isn't a standard realm dependency (STDREF-017).
- A Standard Reference with `realm` has no `version`, or a `version` other than the linked realm's
  `edition` (STDREF-018).
- A `profile` without `realm`, or one the linked realm doesn't declare (STDREF-019, STDREF-027).
- A `standard` note names a clause the linked realm's list doesn't have (STDREF-021).
- A realm note's ID isn't sequential, or its type isn't allowed (NTE-030, NTE-031).
- An `exclusion` on a rule, without a `ref`, or with a `ref` naming no linked Standard Reference
  (NTE-032, NTE-034).
- A `ref` on a realm note that is neither an `exclusion` nor a `reference` withdrawn from one
  (NTE-035).
- A crosswalk entry's `clause` isn't in the previous edition, a target isn't in this one, or an old
  clause appears twice (STDCWK-005, STDCWK-007).
- The manifest `hash` doesn't match (RLMMNFST-013).

## What this repo ships

- The rules listed under Status, all Draft.
- Schema changes:
  - `entity.v1` (rule `clause` and `profiles`, Standard Reference `realm` and `profile`): through
    `tools/build-schema.py`, which generates `entity.v1` and `config.v1`.
  - `realm.v1` (`kind`, `license`, `attribution`, `edition`, `profiles`, the Standard Reference fields,
    `notes`, `hash`): hand-maintained, and it needs explicit approval, as in #114.
- Every new field is optional and absent when unused, so existing files keep their bytes and their
  hashes. In strspc-manager's Go structs, that means `omitempty` on each new field.
- No transcription. The pilot realm lives in its own repo (decision 9).

## Steps

1. ~~Decide the open questions on #144.~~ Done.
2. Rules and schemas, all Draft, released in a core minor version.
3. strspc-manager: struct fields, realm notes, the manifest hash, lint, coverage over linked realms,
   crosswalk loading, #269.
4. strspc-CLI: preserve the fields, `standards coverage` with `unmapped`, excluded and both figures,
   authoring commands for realm notes, recomputing the manifest hash on every manifest write, and the
   #239 gate with `--min-coverage`.
5. Release flow: once the CLI recomputes the hash, the release skill, `pin-consumers.yml` and
   strspc-sync stop hand-editing `realm.json`.
6. Pilot: generate ASVS 5.0.0 L1 (70 clauses) in `SteerSpec/strspc-std-owasp-asvs`, and map at least
   one strspc-CLI rule to it.
7. Crosswalk: generate 4.0.3 → 5.0.0 from OWASP's YAML, and check it against both pilot editions.

## Verification

- `strspc realm validate --strict` and `strspc lint --strict` pass on the pilot realm.
- `strspc standards coverage` in strspc-CLI shows `covered`, `mapped` and `unmapped` against the
  70-clause total.
- A note naming a clause that doesn't exist fails lint, and so does one naming a clause whose rules are
  all Terminated. After a transcription fix, a note keeps resolving to the superseding rule.
- A clause split into two rules counts once in the total, and one note covers it.
- Excluding a clause lowers the total, and the report lists the justification.
- With the crosswalk, a 4.0.3 mapping of a `moved` clause is proposed as the 5.0.0 clause.
