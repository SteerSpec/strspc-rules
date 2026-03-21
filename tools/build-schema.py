#!/usr/bin/env python3
"""Generate entity.v1.schema.json from core rule JSON files.

The schema is derived from the rules themselves, making the system
self-recursive: rules define the schema, the schema validates the rules.

Two-phase validation:
  1. Bootstrap schema validates structural shape (the axiom)
  2. This builder reads rules, extracts constraints, produces the full schema
  3. The full schema validates the core files (self-check)

Usage:
  python3 tools/build-schema.py [--check]

  --check  Verify the committed schema matches what would be generated.
           Exit 1 if stale. Used by CI.
"""

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent.parent
CORE_DIR = ROOT / "rules" / "core"
SCHEMA_DIR = CORE_DIR / "_schema"
BOOTSTRAP_SCHEMA = SCHEMA_DIR / "bootstrap.schema.json"
OUTPUT_SCHEMA = SCHEMA_DIR / "entity.v1.schema.json"

# --- Entity → Schema path mapping ---
# Maps (entity_id, sub_entity_id_or_None) to the schema path they constrain.
ENTITY_SCHEMA_MAP = {
    ("ENT", None): "$.entity",
    ("ENT", "ENTUQID"): "$.entity.id",
    ("RUL", None): "$.rules[]",
    ("RUL", "RULST"): "$.rules[].state",
    ("RST", None): "$.rule_set",
    ("RST", "RSTVRS"): "$.rule_set.version",
    ("RST", "RSTHSH"): "$.rule_set.hash",
    ("NTE", None): "$.notes[]",
}

# --- Constraint extraction patterns ---

# "MUST have a length of at least N and at most M characters"
RE_LENGTH = re.compile(r"MUST have a length of at least (\d+) and at most (\d+) characters")

# "IS a string of letters or numbers only"
RE_ALPHANUMERIC = re.compile(r"IS a string of letters or numbers only")

# "MAY have a state: X (C), Y (C), ..."
RE_STATE_ENUM = re.compile(r"MAY have a state:\s*(.+)")

# "MUST be in the semantic versioning format"
RE_SEMVER = re.compile(r"MUST be in the semantic versioning format")

# "MUST be a Blake3 hash"
RE_BLAKE3 = re.compile(r"MUST be a Blake3 hash")

# Semver regex (simplified but covers standard semver)
SEMVER_PATTERN = (
    "^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)"
    "(-[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?"
    "(\\+[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?$"
)


def load_bootstrap_schema() -> dict:
    return json.loads(BOOTSTRAP_SCHEMA.read_text(encoding="utf-8"))


def load_core_files() -> list[tuple[Path, dict]]:
    files = sorted(CORE_DIR.glob("*.json"))
    if not files:
        print("ERROR: No JSON files found in rules/core/", file=sys.stderr)
        sys.exit(1)
    result = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        result.append((f, data))
    return result


def validate_bootstrap(files: list[tuple[Path, dict]], schema: dict) -> None:
    validator = Draft202012Validator(schema)
    errors = []
    for path, data in files:
        for err in validator.iter_errors(data):
            errors.append(f"  {path.name}: {err.message}")
    if errors:
        print("Bootstrap validation failed:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print(f"  Bootstrap: {len(files)} files pass structural validation")


def collect_rules_by_entity(
    files: list[tuple[Path, dict]],
) -> dict[tuple[str, str | None], list[dict]]:
    """Collect rules grouped by (entity_id, sub_entity_id_or_None)."""
    result: dict[tuple[str, str | None], list[dict]] = {}

    for _path, data in files:
        eid = data["entity"]["id"]
        result.setdefault((eid, None), []).extend(data.get("rules", []))

        for sub in data.get("sub_entities", []):
            sid = sub["entity"]["id"]
            result.setdefault((eid, sid), []).extend(sub.get("rules", []))
            # Handle nested sub-entities (depth 2)
            for subsub in sub.get("sub_entities", []):
                ssid = subsub["entity"]["id"]
                result.setdefault((eid, ssid), []).extend(subsub.get("rules", []))

    return result


def extract_constraints(rules: list[dict], schema_path: str) -> dict:
    """Extract JSON Schema constraints from rule bodies."""
    constraints: dict = {}
    warnings: list[str] = []

    for rule in rules:
        body = rule["body"]
        rule_id = rule["id"]

        # Length constraints
        m = RE_LENGTH.search(body)
        if m:
            constraints["minLength"] = int(m.group(1))
            constraints["maxLength"] = int(m.group(2))

        # Alphanumeric pattern
        if RE_ALPHANUMERIC.search(body):
            constraints["pattern"] = "^[a-zA-Z0-9]+$"

        # State enum
        m = RE_STATE_ENUM.search(body)
        if m:
            # Parse "Draft (D), Abandoned (A), ..." → ["D", "A", ...]
            states = re.findall(r"\(([A-Z])\)", m.group(1))
            if states:
                constraints["enum"] = states

        # Semver
        if RE_SEMVER.search(body):
            constraints["pattern"] = SEMVER_PATTERN

        # Blake3
        if RE_BLAKE3.search(body):
            constraints["pattern"] = "^blake3:[a-f0-9]{64}$"

        # Rules that define required fields (HAS, IS associated) or
        # optional fields (MAY) are handled structurally, not via
        # pattern extraction. Log unmatched for visibility.
        if not any(kw in body for kw in ["HAS", "IS ", "DEFINES", "MUST", "MAY", "Once"]):
            warnings.append(f"  WARNING: {rule_id} → no constraint extracted: {body[:60]}...")

    for w in warnings:
        print(w)

    return constraints


def build_note_type_enum(
    files: list[tuple[Path, dict]],
) -> list[str]:
    """Extract note type enum from the spec. Hardcoded from Issue #4 §2.6."""
    return [
        "rationale",
        "example",
        "counter_example",
        "reference",
        "applies_to",
        "changelog",
        "clarification",
        "deprecation_notice",
        "supersedes",
        "extends",
        "related",
    ]


def build_schema(
    rules_by_entity: dict[tuple[str, str | None], list[dict]],
    files: list[tuple[Path, dict]],
) -> dict:
    """Assemble the full JSON Schema from extracted constraints."""

    # Extract constraints for mapped entities
    euid_constraints = {}
    state_constraints = {}
    version_constraints = {}
    hash_constraints = {}

    for key, schema_path in ENTITY_SCHEMA_MAP.items():
        rules = rules_by_entity.get(key, [])
        if not rules:
            print(f"  INFO: No rules found for {key} → {schema_path}")
            continue

        extracted = extract_constraints(rules, schema_path)
        if key == ("ENT", "ENTUQID"):
            euid_constraints = extracted
        elif key == ("RUL", "RULST"):
            state_constraints = extracted
        elif key == ("RST", "RSTVRS"):
            version_constraints = extracted
        elif key == ("RST", "RSTHSH"):
            hash_constraints = extracted

    note_types = build_note_type_enum(files)

    # Log unmapped entities
    for key in rules_by_entity:
        if key not in ENTITY_SCHEMA_MAP:
            eid, sid = key
            label = f"{eid}.{sid}" if sid else eid
            print(f"  INFO: Entity {label} has no schema mapping (informational)")

    # Build the schema
    entity_id_schema: dict = {"type": "string"}
    entity_id_schema.update(euid_constraints)

    state_schema: dict = {"type": "string"}
    state_schema.update(state_constraints)

    version_schema: dict = {"type": "string"}
    version_schema.update(version_constraints)

    hash_schema: dict = {
        "oneOf": [
            {"type": "string"},
            {"type": "null"},
        ]
    }
    if hash_constraints.get("pattern"):
        hash_schema = {
            "oneOf": [
                {"type": "string", "pattern": hash_constraints["pattern"]},
                {"type": "null"},
            ]
        }

    note_type_schema: dict = {"type": "string", "enum": note_types}

    # Rule object schema
    rule_schema = {
        "type": "object",
        "required": ["id", "revision", "state", "body", "added_by", "added_at"],
        "properties": {
            "id": {"type": "string", "pattern": "^[A-Z0-9]+-\\d{3}$"},
            "revision": {"type": "integer", "minimum": 0},
            "state": state_schema,
            "body": {"type": "string", "minLength": 1},
            "added_by": {"type": "string", "minLength": 1},
            "added_at": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "supersedes": {
                "oneOf": [
                    {"type": "string", "pattern": "^[A-Z0-9]+-\\d{3}$"},
                    {"type": "null"},
                ]
            },
        },
        "additionalProperties": False,
    }

    # Note object schema
    note_schema = {
        "type": "object",
        "required": [
            "id",
            "rule_ref",
            "type",
            "content",
            "added_by",
            "added_at",
            "revision",
        ],
        "properties": {
            "id": {"type": "string", "pattern": "^[A-Z0-9]+-\\d{3}/\\d{2}$"},
            "rule_ref": {"type": "string", "pattern": "^[A-Z0-9]+-\\d{3}$"},
            "type": note_type_schema,
            "content": {"type": "string", "minLength": 1},
            "added_by": {"type": "string", "minLength": 1},
            "added_at": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "revision": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }

    # Entity file schema (recursive for sub_entities)
    entity_file_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://steerspec.dev/schemas/entity/v1.json",
        "title": "SteerSpec Entity File Schema",
        "description": (
            "Full schema for SteerSpec entity files. Generated from core rule "
            "JSON files by tools/build-schema.py. Do not edit manually."
        ),
        "type": "object",
        "required": ["$schema", "entity", "rule_set", "rules", "notes"],
        "properties": {
            "$schema": {"type": "string"},
            "entity": {
                "type": "object",
                "required": ["id", "title"],
                "properties": {
                    "id": entity_id_schema,
                    "title": {"type": "string", "minLength": 1},
                    "description": {"type": "string"},
                    "parent": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "rule_set": {
                "type": "object",
                "required": ["version", "timestamp", "hash"],
                "properties": {
                    "version": version_schema,
                    "timestamp": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}",
                    },
                    "hash": hash_schema,
                },
                "additionalProperties": False,
            },
            "rules": {"type": "array", "items": rule_schema},
            "sub_entities": {"type": "array", "items": {"$ref": "#"}},
            "notes": {"type": "array", "items": note_schema},
        },
        "additionalProperties": False,
    }

    return entity_file_schema


def validate_full(files: list[tuple[Path, dict]], schema: dict) -> bool:
    """Validate all core JSON files against the generated schema.

    NOTE: This validation is circular by design — the schema is derived from
    the same files it validates. It catches structural inconsistencies (e.g.,
    a rule body claiming 6 states but a file using a 7th), but it cannot
    detect constraint *regression* (e.g., reducing allowed states from 6 to 2).
    Regression detection belongs in the PR validator (rule-diff, spec §7.2).
    """
    validator = Draft202012Validator(schema)
    all_ok = True

    for path, data in files:
        errors = list(validator.iter_errors(data))
        if errors:
            all_ok = False
            print(f"  FAIL: {path.name}", file=sys.stderr)
            for err in errors:
                print(f"    {err.json_path}: {err.message}", file=sys.stderr)
        else:
            print(f"  PASS: {path.name}")

    return all_ok


def main() -> int:
    check_mode = "--check" in sys.argv

    print("Phase 1: Loading and bootstrap validation")
    bootstrap_schema = load_bootstrap_schema()
    files = load_core_files()
    validate_bootstrap(files, bootstrap_schema)

    print("\nPhase 2: Extracting constraints and building schema")
    rules_by_entity = collect_rules_by_entity(files)
    schema = build_schema(rules_by_entity, files)

    print(f"\nPhase 3: Self-validation ({len(files)} files)")
    if not validate_full(files, schema):
        print(
            "\nERROR: Generated schema rejects core files. This indicates an incoherent rule change.",
            file=sys.stderr,
        )
        return 1

    generated_json = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"

    if check_mode:
        if OUTPUT_SCHEMA.exists():
            committed = OUTPUT_SCHEMA.read_text(encoding="utf-8")
            if committed == generated_json:
                print("\nSchema is up to date.")
                return 0
            else:
                print(
                    "\nERROR: Committed schema is stale. Run 'python3 tools/build-schema.py' and commit the result.",
                    file=sys.stderr,
                )
                return 1
        else:
            print(
                "\nERROR: Schema file does not exist. Run 'python3 tools/build-schema.py' to generate it.",
                file=sys.stderr,
            )
            return 1

    OUTPUT_SCHEMA.write_text(generated_json, encoding="utf-8")
    print(f"\nSchema written to {OUTPUT_SCHEMA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
