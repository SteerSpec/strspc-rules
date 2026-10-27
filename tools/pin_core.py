#!/usr/bin/env python3
"""Move a consumer repository's dev.steerspec.core pin to a new release.

Consumers pin core literally (RR004 exact match, reproducible resolution
outside Actions), so a core release means editing files in every consumer.
The release workflow runs this in each consumer checkout:

    python3 tools/pin_core.py apply --repo-dir DIR --new X.Y.Z FILE...
        Rewrites every pin in FILE... from the consumer's current version
        (read from DIR/rules/realm.json) to X.Y.Z. Prints old=… and
        changed=true|false. Fails, writing nothing, on a downgrade, on a
        listed file that is missing or holds no pin, or on a pin left in
        any other tracked file (a layout drift the file list must follow).

    python3 tools/pin_core.py superseded --new X.Y.Z < branches
        Reads open pin PR head branches, prints those for older versions
        (to close). Fails if one is for a newer version.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CORE_REALM_ID = "dev.steerspec.core"
REALM_JSON = "rules/realm.json"
PIN_BRANCH = re.compile(r"^chore/core-(\d+\.\d+\.\d+)$")


class PinError(Exception):
    pass


def parse_version(v: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v)
    if not m:
        raise PinError(f"'{v}' is not a MAJOR.MINOR.PATCH version")
    return int(m[1]), int(m[2]), int(m[3])


def pin_regex(old: str) -> re.Pattern[str]:
    # Not followed by a digit, '-' or '.digit': 1.8.0 must not match inside
    # 1.8.01, 1.8.0-rc1 or 1.8.0.1. No trailing '/' required, so a bare
    # `strspc-rules@v1.8.0` in prose is a pin too.
    return re.compile(r"(strspc-rules@v|dev\.steerspec\.core@)" + re.escape(old) + r"(?![0-9]|-|\.[0-9])")


def rewrite_text(text: str, old: str, new: str) -> str:
    return pin_regex(old).sub(lambda m: m[1] + new, text)


def _dump(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _core_deps(data: dict) -> list[dict]:
    return [d for d in data.get("dependencies") or [] if d.get("realm_id") == CORE_REALM_ID]


def read_core_version(realm_text: str) -> str:
    deps = _core_deps(json.loads(realm_text))
    if len(deps) != 1:
        raise PinError(f"{REALM_JSON} has {len(deps)} {CORE_REALM_ID} dependencies; expected exactly one")
    return deps[0]["version"]


def rewrite_realm_json(text: str, old: str, new: str) -> str:
    data = json.loads(text)
    # Re-serialising must not reformat the manifest; refuse rather than
    # open a PR full of whitespace changes.
    if _dump(data) != text:
        raise PinError(f"{REALM_JSON} is not in canonical 2-space JSON form; refusing to reformat it")
    read_core_version(text)
    dep = _core_deps(data)[0]
    source = rewrite_text(dep["source"], old, new)
    # Version and source must move together; a source that does not pin the
    # same version is drift, not something to half-update.
    if source == dep["source"]:
        raise PinError(f"{REALM_JSON} core source {dep['source']!r} does not pin {old}")
    dep["version"] = new
    dep["source"] = source
    return _dump(data)


def find_leftovers(repo_dir: Path, old: str) -> list[str]:
    regex = pin_regex(old)
    tracked = subprocess.run(
        ["git", "-C", str(repo_dir), "ls-files", "-z"], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.split("\0")
    hits = []
    for path in filter(None, tracked):
        if Path(path).name == "CHANGELOG.md":
            continue
        try:
            text = (repo_dir / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        hits += [f"{path}:{n}" for n, line in enumerate(text.splitlines(), 1) if regex.search(line)]
    return hits


def apply(repo_dir: Path, files: list[str], new: str) -> tuple[str, bool]:
    old = read_core_version((repo_dir / REALM_JSON).read_text(encoding="utf-8"))
    if parse_version(old) == parse_version(new):
        # Already pinned only if every listed file says so: a hand bump that
        # missed a file must not read as done.
        current = pin_regex(new)
        for path in files:
            target = repo_dir / path
            if not target.is_file() or not current.search(target.read_text(encoding="utf-8")):
                raise PinError(f"{REALM_JSON} pins {new} but {path} does not; fix that file by hand")
        return old, False
    if parse_version(old) > parse_version(new):
        raise PinError(f"consumer pins {CORE_REALM_ID} {old}; refusing to downgrade to {new}")

    updated = {}
    for path in files:
        target = repo_dir / path
        if not target.is_file():
            raise PinError(f"{path} does not exist; update the file list for this repository")
        text = target.read_text(encoding="utf-8")
        result = rewrite_realm_json(text, old, new) if path == REALM_JSON else rewrite_text(text, old, new)
        if result == text:
            raise PinError(f"{path} holds no {old} pin; update the file list for this repository")
        updated[path] = result

    # Check what would be left behind before writing anything.
    remaining = [hit for hit in find_leftovers(repo_dir, old) if hit.split(":", 1)[0] not in updated]
    if remaining:
        raise PinError(f"{old} pins outside the file list: {', '.join(remaining)}")

    for path, text in updated.items():
        (repo_dir / path).write_text(text, encoding="utf-8")
    return old, True


def check_open_pins(branches: list[str], new: str) -> list[str]:
    superseded = []
    for branch in branches:
        m = PIN_BRANCH.match(branch)
        if not m:
            continue
        if parse_version(m[1]) > parse_version(new):
            raise PinError(f"open pin PR {branch} is newer than {new}; refusing to pin an older release")
        if parse_version(m[1]) < parse_version(new):
            superseded.append(branch)
    return superseded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--repo-dir", type=Path, required=True)
    p_apply.add_argument("--new", required=True)
    p_apply.add_argument("files", nargs="+")
    p_sup = sub.add_parser("superseded")
    p_sup.add_argument("--new", required=True)
    args = parser.parse_args()

    try:
        parse_version(args.new)
        if args.command == "apply":
            old, changed = apply(args.repo_dir, args.files, args.new)
            print(f"old={old}")
            print(f"changed={'true' if changed else 'false'}")
        else:
            branches = [line.strip() for line in sys.stdin if line.strip()]
            for branch in check_open_pins(branches, args.new):
                print(branch)
    except PinError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
