#!/usr/bin/env python3
"""Generate entity.v1.schema.json and config.v1.schema.json from core rule JSON files.

The schemas are derived from the rules themselves, making the system
self-recursive: rules define the schema, the schema validates the rules.

Validation phases:
  1. Bootstrap schema validates structural shape (the axiom)
  2. This builder reads rules, extracts constraints, produces the full schemas
  3. The entity schema validates the core files (self-check)
  4. The config schema is generated from SPCFG rules (validates consumer config files)

Usage:
  python3 tools/build-schema.py [--check]

  --check  Verify the committed schemas match what would be generated.
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
OUTPUT_CONFIG_SCHEMA = SCHEMA_DIR / "config.v1.schema.json"

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

# --- Config schema mapping ---
# Maps SPCFG sub-entities to the config.yaml schema paths they constrain.
CONFIG_SCHEMA_MAP = {
    ("SPCFG", "SPCFGSRC"): "$.rules[]",
    ("SPCFG", "SPCFGEVAL"): "$.evaluator",
    ("SPCFG", "SPCFGCCH"): "$.cache",
    ("SPCFG", "SPCFGFAIL"): "$.fail_on",
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

# --- Config constraint extraction patterns ---

# "MUST have a `field` property of type string"
RE_REQUIRED_PROP = re.compile(r"MUST have a `(\w+)` property")

# "MAY have a `field` property of type string"  /  "MAY have an `field` property"
RE_OPTIONAL_PROP = re.compile(r"MAY have (?:a|an) `(\w+)` property")

# "of type string or null"
RE_TYPE_STRING_OR_NULL = re.compile(r"of type string or null")

# "with allowed values: X, Y"
RE_ALLOWED_VALUES = re.compile(r"with allowed values:\s*(.+?)\.?$")

# "state code: Draft (D), Abandoned (A), ..."  — reuses state enum extraction
RE_STATE_CODE_LIST = re.compile(r"state code:\s*(.+)")

# Semver regex (simplified but covers standard semver)
SEMVER_PATTERN = (
    "^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)"
    "(-[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?"
    "(\\+[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?$"
)


def load_bootstrap_schema() -> dict:
    return json.loads(BOOTSTRAP_SCHEMA.read_text(encoding="utf-8"))


def load_core_files() -> list[tuple[Path, dict]]:
    files = sorted(f for f in CORE_DIR.glob("*.json") if f.name != "realm.json")
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

    # Log unmapped entities (skip those mapped in CONFIG_SCHEMA_MAP)
    for key in rules_by_entity:
        if key not in ENTITY_SCHEMA_MAP and key not in CONFIG_SCHEMA_MAP:
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


def extract_config_constraints(rules: list[dict]) -> dict:
    """Extract config schema constraints from SPCFG sub-entity rule bodies.

    Returns a dict with 'required' (list), 'properties' (dict of field schemas),
    and optionally 'items_schema' for array item constraints.
    """
    required: list[str] = []
    properties: dict[str, dict] = {}
    items_schema: dict | None = None

    for rule in rules:
        body = rule["body"]

        # Required property: "MUST have a `field` property ..."
        m = RE_REQUIRED_PROP.search(body)
        if m:
            field = m.group(1)
            required.append(field)
            schema: dict = {"type": "string"}
            if RE_TYPE_STRING_OR_NULL.search(body):
                schema = {"oneOf": [{"type": "string"}, {"type": "null"}]}
            # Check for allowed values (enum)
            vm = RE_ALLOWED_VALUES.search(body)
            if vm:
                values = [v.strip() for v in vm.group(1).split(",")]
                schema["enum"] = values
            properties[field] = schema
            continue

        # Optional property: "MAY have a `field` property ..."
        m = RE_OPTIONAL_PROP.search(body)
        if m:
            field = m.group(1)
            schema = {"type": "string"}
            if RE_TYPE_STRING_OR_NULL.search(body):
                schema = {"oneOf": [{"type": "string"}, {"type": "null"}]}
            properties[field] = schema
            continue

        # State code list for array items: "state code: Draft (D), ..."
        m = RE_STATE_CODE_LIST.search(body)
        if m:
            codes = re.findall(r"\(([A-Z])\)", m.group(1))
            if codes:
                items_schema = {"type": "string", "enum": codes}

    result: dict = {}
    if required:
        result["required"] = required
    if properties:
        result["properties"] = properties
    if items_schema:
        result["items_schema"] = items_schema
    return result


def build_config_schema(
    rules_by_entity: dict[tuple[str, str | None], list[dict]],
) -> dict | None:
    """Build config.v1.schema.json from SPCFG sub-entity rules.

    Returns None if SPCFG entity is not found (no config schema to generate).
    Raises RuntimeError if SPCFG exists but required sub-entities are missing.
    """
    # Check if SPCFG exists
    if ("SPCFG", None) not in rules_by_entity:
        return None

    print("\n  Building config schema from SPCFG rules")

    # Extract constraints for each config section
    sections: dict[str, dict] = {}
    for key, schema_path in CONFIG_SCHEMA_MAP.items():
        rules = rules_by_entity.get(key, [])
        if not rules:
            print(f"  INFO: No rules found for {key} → {schema_path}")
            continue
        extracted = extract_config_constraints(rules)
        sections[schema_path] = extracted
        _eid, sid = key
        print(f"  {sid}: {len(rules)} rules → {len(extracted.get('properties', {}))} properties")

    # Guard: the config schema requires a "rules" array, so SPCFGSRC must be present.
    # Raise rather than returning None — SPCFG exists, so this is a broken state.
    if "$.rules[]" not in sections or not sections["$.rules[]"]:
        raise RuntimeError("SPCFG entity exists but SPCFGSRC rules not found — cannot generate config schema")

    # Assemble the config schema
    config_properties: dict = {}

    # $.rules[] → array of rule source objects
    src = sections["$.rules[]"]
    items_obj: dict = {"type": "object", "additionalProperties": False}
    if src.get("required"):
        items_obj["required"] = src["required"]
    if src.get("properties"):
        items_obj["properties"] = src["properties"]
    config_properties["rules"] = {
        "type": "array",
        # minItems: 1 mirrors SPCFG-004 ("MUST declare at least one rule source")
        "minItems": 1,
        "items": items_obj,
    }

    # $.evaluator → evaluator object
    evl = sections.get("$.evaluator", {})
    if evl:
        evl_obj: dict = {"type": "object", "additionalProperties": False}
        if evl.get("required"):
            evl_obj["required"] = evl["required"]
        if evl.get("properties"):
            evl_obj["properties"] = evl["properties"]
        config_properties["evaluator"] = evl_obj

    # $.cache → cache object
    cch = sections.get("$.cache", {})
    if cch:
        cch_obj: dict = {"type": "object", "additionalProperties": False}
        if cch.get("properties"):
            cch_obj["properties"] = cch["properties"]
        config_properties["cache"] = cch_obj

    # $.fail_on → array of state codes
    fail = sections.get("$.fail_on", {})
    if fail:
        fail_obj: dict = {"type": "array"}
        if fail.get("items_schema"):
            fail_obj["items"] = fail["items_schema"]
        config_properties["fail_on"] = fail_obj

    config_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://steerspec.dev/schemas/config/v1.json",
        "title": "SteerSpec Config Schema",
        "description": (
            "Schema for .strspc/config.yaml. Generated from SPCFG entity "
            "rules by tools/build-schema.py. Do not edit manually."
        ),
        "type": "object",
        "required": ["rules"],
        "properties": config_properties,
        "additionalProperties": False,
    }

    return config_schema


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

    print("\nPhase 2: Extracting constraints and building entity schema")
    rules_by_entity = collect_rules_by_entity(files)
    schema = build_schema(rules_by_entity, files)

    print(f"\nPhase 3: Self-validation ({len(files)} files)")
    if not validate_full(files, schema):
        print(
            "\nERROR: Generated schema rejects core files. This indicates an incoherent rule change.",
            file=sys.stderr,
        )
        return 1

    print("\nPhase 4: Building config schema from SPCFG rules")
    config_schema = build_config_schema(rules_by_entity)

    generated_json = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    generated_config_json = json.dumps(config_schema, indent=2, ensure_ascii=False) + "\n" if config_schema else None

    if check_mode:
        all_ok = True

        # Check entity schema
        if OUTPUT_SCHEMA.exists():
            committed = OUTPUT_SCHEMA.read_text(encoding="utf-8")
            if committed == generated_json:
                print("\nEntity schema is up to date.")
            else:
                print(
                    "\nERROR: Committed entity schema is stale."
                    " Run 'python3 tools/build-schema.py' and commit the result.",
                    file=sys.stderr,
                )
                all_ok = False
        else:
            print(
                "\nERROR: Entity schema file does not exist. Run 'python3 tools/build-schema.py' to generate it.",
                file=sys.stderr,
            )
            all_ok = False

        # Check config schema
        if generated_config_json:
            if OUTPUT_CONFIG_SCHEMA.exists():
                committed_config = OUTPUT_CONFIG_SCHEMA.read_text(encoding="utf-8")
                if committed_config == generated_config_json:
                    print("Config schema is up to date.")
                else:
                    print(
                        "\nERROR: Committed config schema is stale."
                        " Run 'python3 tools/build-schema.py' and commit the result.",
                        file=sys.stderr,
                    )
                    all_ok = False
            else:
                print(
                    "\nERROR: Config schema file does not exist. Run 'python3 tools/build-schema.py' to generate it.",
                    file=sys.stderr,
                )
                all_ok = False

        return 0 if all_ok else 1

    OUTPUT_SCHEMA.write_text(generated_json, encoding="utf-8")
    print(f"\nEntity schema written to {OUTPUT_SCHEMA.relative_to(ROOT)}")

    if generated_config_json:
        OUTPUT_CONFIG_SCHEMA.write_text(generated_config_json, encoding="utf-8")
        print(f"Config schema written to {OUTPUT_CONFIG_SCHEMA.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
