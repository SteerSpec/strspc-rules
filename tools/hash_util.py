"""Shared Blake3 hashing utilities for SteerSpec entity JSON files."""

import json

import blake3 as _blake3


def _null_rule_hash(entity: dict) -> None:
    """Recursively null out rule_set.hash on an entity and all sub_entities."""
    rule_set = entity.get("rule_set")
    if isinstance(rule_set, dict) and "hash" in rule_set:
        rule_set["hash"] = None
    for sub in entity.get("sub_entities", []):
        if isinstance(sub, dict):
            _null_rule_hash(sub)


def canonical_json(data: dict) -> bytes:
    """Serialize to canonical JSON: sorted keys, no whitespace, hash nulled."""
    obj = json.loads(json.dumps(data, sort_keys=True))
    _null_rule_hash(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_hash(data: dict) -> str:
    """Compute Blake3 hash of canonical JSON."""
    return "blake3:" + _blake3.blake3(canonical_json(data)).hexdigest()
