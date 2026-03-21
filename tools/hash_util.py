"""Shared Blake3 hashing utilities for SteerSpec entity JSON files."""

import json

import blake3 as _blake3


def canonical_json(data: dict) -> bytes:
    """Serialize to canonical JSON: sorted keys, no whitespace, hash nulled."""
    obj = json.loads(json.dumps(data, sort_keys=True))
    if "rule_set" in obj and "hash" in obj["rule_set"]:
        obj["rule_set"]["hash"] = None
    for sub in obj.get("sub_entities", []):
        if "rule_set" in sub and "hash" in sub["rule_set"]:
            sub["rule_set"]["hash"] = None
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_hash(data: dict) -> str:
    """Compute Blake3 hash of canonical JSON."""
    return "blake3:" + _blake3.blake3(canonical_json(data)).hexdigest()
