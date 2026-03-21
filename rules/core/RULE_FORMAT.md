# Rule Format Definitions

Self-contained rule format definitions for the SteerSpec Sync specification, derived from the SteerSpec CORE.

## Entity

In DDD, an **Entity** is an object that has a unique identity and a lifecycle.

- [ENT-001.0/D] IS an object that has a unique identity that persists over time.
- [ENT-002.0/D] MAY transition through multiple states during its lifecycle.
- [ENT-003.0/D] MAY possess one or more properties.
- [ENT-004.0/D] The behavior of an entity IS defined entirely by the Rules applicable to its identity, properties, and states.
- [ENT-005.0/D] HAS an Entity Unique Identifier.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

### Entity Unique Identifier

- [ENTUQID-001.0/D] MUST have a length of at least 3 and at most 18 characters.
- [ENTUQID-002.0/D] IS a string of letters or numbers only.
- [ENTUQID-003.0/D] IS unique within the Realm.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

## Rule Identifier Format

- [RLIFRMT-001.0/D] DEFINES the format that Rule Identifier must comply with within a Realm.
- [RLIFRMT-002.0/D] MUST define the starting and closing character pair, allowed values: "(,)", "{,}","[,]", default is "[,]".
- [RLIFRMT-003.0/D] MUST define the position of the Entity Unique Identifier as either the opening part of the Rule Unique Identifier or as the closing part, default is opening part.
- [RLIFRMT-004.0/D] MUST define the position of the Rule Set Unique Number as taking the opposing position of the Entity Unique Identifier.
- [RLIFRMT-005.0/D] MUST define a unique Rule Identifier split character which will separate the Entity Unique Identifier and Rule Set Unique Number, allowed values are: "-", "_", default is "-".
- [RLIFRMT-006.0/D] MUST define a Rule Revision splitter which can be either "." or "#", default is ".".
- [RLIFRMT-007.0/D] MUST define a Rule State splitter which can be either "/", "\" or "|", default is "/".

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

## Rule

A **Rule** defines a business constraint, property, or expected behavior of an entity.

- [RUL-001.0/D] DEFINES a single property of an entity or describes the behavior of that property.
- [RUL-002.0/D] IS uniquely identified using a Rule Format.
- [RUL-003.0/D] Rule identifiers MUST NOT be reused, even if the rule is deprecated or deleted.
- [RUL-004.0/D] MUST be expressed as a single phrase.
- [RUL-005.0/D] MAY be supplemented by one or more notes to provide context or clarification.
- [RUL-006.0/D] HAS a Rule State.
- [RUL-007.0/D] Once a Rule IS in State other than Draft then it is immutable.
- [RUL-008.0/D] Once a Rule IS immutable, modifications must be introduced by superseding it with a new rule.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

### Rule State

- [RULST-001.0/D] A Rule MAY have a state: Draft (D), Abandoned (A), Published (P), Implemented (I), Deprecated (D), Terminated (T).
- [RULST-002.0/D] Each State can only be applied once to a Rule.
- [RULST-003.0/D] Draft IS the initial state.
- [RULST-004.0/D] Abandoned IS a terminal state which applies to Rules which were previously in Draft.
- [RULST-005.0/D] Published applies to Rule which have been validated but aren't yet implemented.
- [RULST-006.0/D] Implemented applies to Rule which are in force.
- [RULST-007.0/D] Deprecated applies to Rule which are still in force or present but must be removed.
- [RULST-008.0/D] Terminated applies to Rule which aren't in force anymore.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

### Rule Set

A **Rule Set** groups all rules applicable to a specific entity.

- [RST-001.0/D] IS a collection of Rules associated with an Entity.
- [RST-002.0/D] HAS a Rule Set Version which uniquely defines a specific set of changes applied to it.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

#### Rule Set Version

- [RSTVRS-001.0/D] MUST be in the semantic versioning format.
- [RSTVRS-002.0/D] IS associated to a Rule Set Hash.
- [RSTVRS-003.0/D] HAS a UTC timestamp.
- [RSTVRS-004.0/D] IS automatically created when a Rule Set Change is committed in a specific Rule Set Branch.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

#### Rule Set Hash

- [RSTHSH-001.0/D] IS hash of the Rule Set content.
- [RSTHSH-002.0/D] MUST be a Blake3 hash.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:

## Notes

A **Note** is a supplemental explanation attached to a specific rule.

- [NTE-001.0/D] IS associated with a single rule and must reference the rule's identifier explicitly (e.g., `[<rule id>/<incremental note id (OOn)]`).
- [NTE-002.0/D] A Note provides clarification, context, or elaboration and must not modify the rule it supplements.
- [NTE-003.0/D] MUST be stored in the same directory as the entity and rule it references.
- [NTE-004.0/D] MAY include: Business rationale, Examples or use cases, Historical context, Clarifications of terminology.
- [NTE-005.0/D] MUST be versioned and maintained alongside the rules they support.
- [NTE-006.0/D] MUST be concise but may span multiple paragraphs if needed for clarity.

Version(s):
  - 0.1.0-draft (2026-03-07): self-contained copy for SteerSpec Sync

Notes:
