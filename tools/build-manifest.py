#!/usr/bin/env python3
"""Generate a manifest (index.json) for published SteerSpec rules.

Usage:
  python3 tools/build-manifest.py --version 0.3.1 [--output path/to/index.json]

If --output is omitted, prints to stdout.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from hash_util import compute_hash


def build_manifest(version: str, rules_dir: Path, schema_dir: Path) -> dict:
    """Build manifest dict from rule and schema files."""
    rules = []
    for path in sorted(rules_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        stored_hash = data.get("rule_set", {}).get("hash")
        if stored_hash is None:
            raise ValueError(f"missing rule_set.hash in {path}")

        computed_hash = compute_hash(data)
        if stored_hash != computed_hash:
            raise ValueError(f"hash mismatch in {path}: stored={stored_hash} computed={computed_hash}")

        rules.append(
            {
                "file": path.name,
                "entity_id": data["entity"]["id"],
                "hash": computed_hash,
            }
        )

    schemas = {}
    expected_schemas = [
        ("entity.v1.schema.json", "entity.v1", "schemas/entity/v1.json"),
        ("bootstrap.schema.json", "bootstrap", "schemas/entity/bootstrap.json"),
    ]
    for filename, key, served_path in expected_schemas:
        if not (schema_dir / filename).exists():
            raise FileNotFoundError(f"missing expected schema file: {schema_dir / filename}")
        schemas[key] = served_path

    return {
        "version": version,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schemas": schemas,
        "rules": rules,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate rules manifest")
    parser.add_argument("--version", required=True, help="Release version (e.g. 0.3.1)")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument(
        "--rules-dir",
        default=Path(__file__).parent.parent / "rules" / "core",
        type=Path,
        help="Directory containing rule JSON files",
    )
    parser.add_argument(
        "--schema-dir",
        default=Path(__file__).parent.parent / "rules" / "core" / "_schema",
        type=Path,
        help="Directory containing schema files",
    )
    args = parser.parse_args()

    manifest = build_manifest(args.version, args.rules_dir, args.schema_dir)
    output = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Manifest written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
