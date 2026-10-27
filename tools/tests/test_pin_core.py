"""Tests for tools/pin_core.py. Run: python3 -m unittest discover -s tools/tests -t tools"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import pin_core
from pin_core import PinError

OLD_SOURCE = "github://SteerSpec/strspc-rules@v1.8.0/rules/core"
NEW_SOURCE = "github://SteerSpec/strspc-rules@v1.8.1/rules/core"


def realm_json(own_version: str = "0.1.0", deps: list[dict] | None = None) -> str:
    if deps is None:
        deps = [{"realm_id": "dev.steerspec.core", "version": "1.8.0", "source": OLD_SOURCE}]
    data = {
        "$schema": "./_schema/realm.v1.schema.json",
        "realm": {"id": "dev.steerspec.platform", "title": "SteerSpec Platform", "version": own_version},
        "dependencies": deps,
        "rule_identifier_format": None,
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


class Repo:
    """A throwaway git repository with tracked files."""

    def __init__(self, files: dict[str, str]):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for path, text in files.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)

    def read(self, path: str) -> str:
        return (self.root / path).read_text()

    def snapshot(self) -> dict[str, str]:
        return {
            str(p.relative_to(self.root)): p.read_text()
            for p in self.root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }

    def close(self) -> None:
        self._tmp.cleanup()


class PatternTests(unittest.TestCase):
    def test_pattern_boundaries(self):
        regex = pin_core.pin_regex("1.8.0")
        for text in [
            "strspc-rules@v1.8.0/rules",
            "strspc-rules@v1.8.0`",
            "pins strspc-rules@v1.8.0.",
            "dev.steerspec.core@1.8.0",
        ]:
            self.assertIsNotNone(regex.search(text), text)
        for text in [
            "strspc-rules@v1.8.01",
            "strspc-rules@v1.8.0-rc1",
            "strspc-rules@v1.8.0.1",
            "strspc-rules@v1.6.0/",
            "strspc-rules@v1/",
            "strspc-rules@latest/",
        ]:
            self.assertIsNone(regex.search(text), text)

    def test_rewrite_bare_pin_followed_by_backtick(self):
        self.assertEqual(
            pin_core.rewrite_text("pins `strspc-rules@v1.8.0`.", "1.8.0", "1.8.1"),
            "pins `strspc-rules@v1.8.1`.",
        )

    def test_rewrite_spec_readme_form(self):
        self.assertEqual(
            pin_core.rewrite_text("depends on dev.steerspec.core@1.8.0", "1.8.0", "1.8.1"),
            "depends on dev.steerspec.core@1.8.1",
        )

    def test_parse_version_rejects_non_release(self):
        self.assertEqual(pin_core.parse_version("1.8.10"), (1, 8, 10))
        for bad in ["v1.8.0", "1.8", "1.8.0-rc1", ""]:
            with self.assertRaises(PinError, msg=bad):
                pin_core.parse_version(bad)


class RealmJsonTests(unittest.TestCase):
    def test_realm_json_rewrites_version_and_source(self):
        before = realm_json()
        after = pin_core.rewrite_realm_json(before, "1.8.0", "1.8.1")
        dep = json.loads(after)["dependencies"][0]
        self.assertEqual(dep["version"], "1.8.1")
        self.assertEqual(dep["source"], NEW_SOURCE)
        changed = [a for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b]
        self.assertEqual(len(changed), 2)

    def test_realm_json_keeps_own_version(self):
        after = pin_core.rewrite_realm_json(realm_json(own_version="1.8.0"), "1.8.0", "1.8.1")
        self.assertEqual(json.loads(after)["realm"]["version"], "1.8.0")

    def test_realm_json_non_canonical_format_fails(self):
        text = json.dumps(json.loads(realm_json()), indent=4) + "\n"
        with self.assertRaises(PinError):
            pin_core.rewrite_realm_json(text, "1.8.0", "1.8.1")

    def test_read_core_version_requires_exactly_one(self):
        self.assertEqual(pin_core.read_core_version(realm_json()), "1.8.0")
        core = {"realm_id": "dev.steerspec.core", "version": "1.8.0", "source": OLD_SOURCE}
        for deps in ([], [core, core]):
            with self.assertRaises(PinError):
                pin_core.read_core_version(realm_json(deps=deps))


class ApplyTests(unittest.TestCase):
    FILES = ("rules/realm.json", ".strspc/config.yaml", "README.md")

    def make_repo(self, extra: dict[str, str] | None = None) -> Repo:
        files = {
            "rules/realm.json": realm_json(),
            ".strspc/config.yaml": f"rules:\n  - source: {OLD_SOURCE}\n    scope: global\n",
            "README.md": f"  - source: {OLD_SOURCE}   # bumped\n\nThe generated config pins `strspc-rules@v1.8.0`.\n",
        }
        files.update(extra or {})
        repo = Repo(files)
        self.addCleanup(repo.close)
        return repo

    def test_apply_happy_path(self):
        repo = self.make_repo()
        self.assertEqual(pin_core.apply(repo.root, self.FILES, "1.8.1"), ("1.8.0", True))
        for path in self.FILES:
            self.assertNotIn("1.8.0", repo.read(path), path)
            self.assertIn("1.8.1", repo.read(path), path)
        self.assertIn("pins `strspc-rules@v1.8.1`.", repo.read("README.md"))

    def test_apply_already_pinned(self):
        repo = self.make_repo()
        before = repo.snapshot()
        self.assertEqual(pin_core.apply(repo.root, self.FILES, "1.8.0"), ("1.8.0", False))
        self.assertEqual(repo.snapshot(), before)

    def test_apply_refuses_downgrade(self):
        repo = self.make_repo()
        with self.assertRaisesRegex(PinError, "downgrade"):
            pin_core.apply(repo.root, self.FILES, "1.7.9")

    def test_apply_missing_file_fails(self):
        repo = self.make_repo()
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "docs/SPEC.md"):
            pin_core.apply(repo.root, [*self.FILES, "docs/SPEC.md"], "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_apply_unchanged_file_fails(self):
        repo = self.make_repo({"docs/SPEC.md": "no pin here\n"})
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "docs/SPEC.md"):
            pin_core.apply(repo.root, [*self.FILES, "docs/SPEC.md"], "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_apply_leftover_fails(self):
        repo = self.make_repo({"docs/x.md": "see strspc-rules@v1.8.0\n"})
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "docs/x.md"):
            pin_core.apply(repo.root, self.FILES, "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_leftover_ignores_changelog_and_old_fixtures(self):
        repo = self.make_repo(
            {
                "CHANGELOG.md": "pinned dev.steerspec.core@1.8.0\n",
                "sub/CHANGELOG.md": "strspc-rules@v1.8.0\n",
                "src/x_test.go": '"github://SteerSpec/strspc-rules@v1.6.0/rules/core"\n',
            }
        )
        pin_core.apply(repo.root, self.FILES, "1.8.1")
        self.assertEqual(pin_core.find_leftovers(repo.root, "1.8.0"), [])
        self.assertIn("1.8.0", repo.read("CHANGELOG.md"))


class OpenPinTests(unittest.TestCase):
    def test_newer_open_pin_refused(self):
        with self.assertRaises(PinError):
            pin_core.check_open_pins(["chore/core-1.9.0"], "1.8.1")

    def test_superseded_selection(self):
        branches = ["chore/core-1.8.0", "chore/core-1.8.1", "chore/core-x", "feat/y"]
        self.assertEqual(pin_core.check_open_pins(branches, "1.8.1"), ["chore/core-1.8.0"])


if __name__ == "__main__":
    unittest.main()
