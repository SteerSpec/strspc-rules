#!/usr/bin/env python3
"""Compute and update Blake3 hashes for SteerSpec entity JSON files.

Usage:
  python3 tools/compute-hash.py [FILE...]

If no files are given, processes all rules/core/*.json files.
Sets rule_set.hash to "blake3:<hex>" computed over canonical JSON
(sorted keys, minified) with the hash field set to null.
"""

import json
import sys
from pathlib import Path

from hash_util import compute_hash


def process_file(path: Path) -> bool:
    """Compute and update hash in a single entity file. Returns True if changed."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if "rule_set" not in data:
        print(f"  {path.name}: skipped (no rule_set)")
        return False

    new_hash = compute_hash(data)
    old_hash = data.get("rule_set", {}).get("hash")

    if old_hash == new_hash:
        print(f"  {path.name}: unchanged ({new_hash[:20]}...)")
        return False

    data["rule_set"]["hash"] = new_hash
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  {path.name}: {new_hash[:20]}...")
    return True


def main() -> int:
    if len(sys.argv) > 1:
        files = [Path(p) for p in sys.argv[1:]]
    else:
        root = Path(__file__).parent.parent / "rules" / "core"
        files = sorted(f for f in root.glob("*.json") if f.name != "realm.json")

    if not files:
        print("No JSON files found.", file=sys.stderr)
        return 1

    changed = 0
    for path in files:
        if process_file(path):
            changed += 1

    print(f"\nProcessed {len(files)} file(s), {changed} updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
