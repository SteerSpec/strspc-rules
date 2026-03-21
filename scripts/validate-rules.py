#!/usr/bin/env python3
"""Validate SteerSpec rule files for format and logic consistency.

Checks performed:
  1. Rule ID format: - [ENTITY-NNN.N/STATE] <non-empty text>
  2. No duplicate rule IDs across all rule files
  3. Each file that contains rules also contains a Version(s): block

Exit 0 on success, exit 1 if any check fails (all errors printed before exit).
"""

import re
import sys
from pathlib import Path

# Regex for a valid rule line: - [ENTITY-digits.digits/LETTER] <text>
RULE_LINE_RE = re.compile(r"^- \[([A-Z]+-\d+\.\d+/[A-Z])\] (.+)$")


def find_rule_files(root: Path) -> list[Path]:
    return sorted(root.glob("rules/**/*.md"))


def validate_file(path: Path, seen_ids: dict[str, Path]) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    has_rules = False
    has_version_block = False

    for lineno, line in enumerate(lines, start=1):
        # Check for Version(s): block
        if line.strip().startswith("Version(s):"):
            has_version_block = True

        # Only process lines that look like rule entries
        if not line.startswith("- ["):
            continue

        m = RULE_LINE_RE.match(line)
        if not m:
            errors.append(f"{path}:{lineno}: malformed rule line: {line!r}")
            continue

        rule_id = m.group(1)
        has_rules = True

        # Duplicate ID check
        if rule_id in seen_ids:
            errors.append(
                f"{path}:{lineno}: duplicate rule ID [{rule_id}] "
                f"(first seen in {seen_ids[rule_id]})"
            )
        else:
            seen_ids[rule_id] = path

    # Version block check (only required for files that actually contain rules)
    if has_rules and not has_version_block:
        errors.append(f"{path}: contains rules but has no 'Version(s):' block")

    return errors


def main() -> int:
    root = Path(__file__).parent.parent
    rule_files = find_rule_files(root)

    if not rule_files:
        print("No rule files found under rules/", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    seen_ids: dict[str, Path] = {}

    for path in rule_files:
        all_errors.extend(validate_file(path, seen_ids))

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(f"\n{len(all_errors)} error(s) found.", file=sys.stderr)
        return 1

    print(f"OK: validated {len(rule_files)} file(s), {len(seen_ids)} rule(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
