"""Tests for tools/pin_core.py. Run: python3 -m unittest discover -s tools/tests -t tools"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pin_core
from pin_core import PinError

OLD_SOURCE = "github://SteerSpec/strspc-rules@v1.8.0/rules/core"
NEW_SOURCE = "github://SteerSpec/strspc-rules@v1.8.1/rules/core"


OLD_SCHEMA = '{"title": "old"}\n'
NEW_SCHEMA = '{"title": "new"}\n'
ENTITY_SCHEMA = "rules/_schema/entity.v1.schema.json"


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
            target.write_text(text, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)

    def read(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8")

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

    def test_realm_json_source_drift_fails(self):
        drifted = [
            {
                "realm_id": "dev.steerspec.core",
                "version": "1.8.0",
                "source": "github://SteerSpec/strspc-rules@v1.7.0/rules/core",
            }
        ]
        with self.assertRaisesRegex(PinError, "source"):
            pin_core.rewrite_realm_json(realm_json(deps=drifted), "1.8.0", "1.8.1")

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
            ENTITY_SCHEMA: NEW_SCHEMA,
        }
        files.update(extra or {})
        repo = Repo(files)
        self.addCleanup(repo.close)
        return repo

    def make_core(self, schemas: dict[str, str] | None = None) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        core = Path(tmp.name)
        defaults = {"entity.v1.schema.json": NEW_SCHEMA, "config.v1.schema.json": NEW_SCHEMA}
        for name, text in (defaults if schemas is None else schemas).items():
            (core / name).write_text(text, encoding="utf-8")
        return core

    def apply(self, repo: Repo, files, new: str, core: Path | None = None) -> tuple[str, bool]:
        return pin_core.apply(repo.root, files, new, self.make_core() if core is None else core)

    def test_apply_happy_path(self):
        repo = self.make_repo()
        self.assertEqual(self.apply(repo, self.FILES, "1.8.1"), ("1.8.0", True))
        for path in self.FILES:
            self.assertNotIn("1.8.0", repo.read(path), path)
            self.assertIn("1.8.1", repo.read(path), path)
        self.assertIn("pins `strspc-rules@v1.8.1`.", repo.read("README.md"))

    def test_apply_already_pinned(self):
        repo = self.make_repo()
        before = repo.snapshot()
        self.assertEqual(self.apply(repo, self.FILES, "1.8.0"), ("1.8.0", False))
        self.assertEqual(repo.snapshot(), before)

    def test_apply_already_pinned_with_stale_core_source_fails(self):
        platform_source = NEW_SOURCE.replace("core", "platform")
        deps = [
            {"realm_id": "dev.steerspec.core", "version": "1.8.1", "source": OLD_SOURCE},
            {"realm_id": "dev.steerspec.platform", "version": "0.1.0", "source": platform_source},
        ]
        new_pins = {
            ".strspc/config.yaml": f"rules:\n  - source: {NEW_SOURCE}\n",
            "README.md": f"  - source: {NEW_SOURCE}\n",
        }
        repo = self.make_repo({"rules/realm.json": realm_json(deps=deps), **new_pins})
        with self.assertRaisesRegex(PinError, "source"):
            self.apply(repo, self.FILES, "1.8.1")

    def test_apply_already_pinned_with_unlisted_pin_fails(self):
        repo = self.make_repo({"docs/x.md": "see strspc-rules@v1.8.0\n"})
        with self.assertRaisesRegex(PinError, "docs/x.md"):
            self.apply(repo, self.FILES, "1.8.0")

    def test_apply_already_pinned_with_stale_file_fails(self):
        stale = "  - source: github://SteerSpec/strspc-rules@v1.7.0/rules/core\n"
        repo = self.make_repo({"README.md": stale})
        with self.assertRaisesRegex(PinError, "README.md"):
            self.apply(repo, self.FILES, "1.8.0")
        self.assertEqual(repo.read("README.md"), stale)

    def test_apply_second_pin_in_realm_json_fails(self):
        platform = {
            "realm_id": "dev.steerspec.platform",
            "version": "0.1.0",
            "source": "github://SteerSpec/strspc-rules@v1.8.0/rules/platform",
        }
        core = {"realm_id": "dev.steerspec.core", "version": "1.8.0", "source": OLD_SOURCE}
        repo = self.make_repo({"rules/realm.json": realm_json(deps=[core, platform])})
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "rules/realm.json"):
            self.apply(repo, self.FILES, "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_apply_refuses_downgrade(self):
        repo = self.make_repo()
        with self.assertRaisesRegex(PinError, "downgrade"):
            self.apply(repo, self.FILES, "1.7.9")

    def test_apply_missing_file_fails(self):
        repo = self.make_repo()
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "docs/SPEC.md"):
            self.apply(repo, [*self.FILES, "docs/SPEC.md"], "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_apply_unchanged_file_fails(self):
        repo = self.make_repo({"docs/SPEC.md": "no pin here\n"})
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "docs/SPEC.md"):
            self.apply(repo, [*self.FILES, "docs/SPEC.md"], "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_apply_leftover_fails(self):
        repo = self.make_repo({"docs/x.md": "see strspc-rules@v1.8.0\n"})
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "docs/x.md"):
            self.apply(repo, self.FILES, "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_leftover_ignores_changelog_and_old_fixtures(self):
        repo = self.make_repo(
            {
                "CHANGELOG.md": "pinned dev.steerspec.core@1.8.0\n",
                "sub/CHANGELOG.md": "strspc-rules@v1.8.0\n",
                "src/x_test.go": '"github://SteerSpec/strspc-rules@v1.6.0/rules/core"\n',
            }
        )
        self.apply(repo, self.FILES, "1.8.1")
        self.assertEqual(pin_core.find_leftovers(repo.root, "1.8.0"), [])
        self.assertIn("1.8.0", repo.read("CHANGELOG.md"))

    def test_apply_syncs_schemas(self):
        repo = self.make_repo({ENTITY_SCHEMA: OLD_SCHEMA})
        self.assertEqual(self.apply(repo, self.FILES, "1.8.1"), ("1.8.0", True))
        self.assertEqual(repo.read(ENTITY_SCHEMA), NEW_SCHEMA)

    def test_apply_syncs_only_schemas_both_sides_hold(self):
        repo = self.make_repo({ENTITY_SCHEMA: OLD_SCHEMA, "rules/_schema/own.schema.json": OLD_SCHEMA})
        self.apply(repo, self.FILES, "1.8.1")
        self.assertEqual(repo.read("rules/_schema/own.schema.json"), OLD_SCHEMA)
        self.assertFalse((repo.root / "rules/_schema/config.v1.schema.json").exists())

    def test_apply_already_pinned_with_stale_schema_syncs(self):
        repo = self.make_repo({ENTITY_SCHEMA: OLD_SCHEMA})
        self.assertEqual(self.apply(repo, self.FILES, "1.8.0"), ("1.8.0", True))
        self.assertEqual(repo.read(ENTITY_SCHEMA), NEW_SCHEMA)

    def test_apply_ignores_formatting_only_schema_difference(self):
        reformatted = '{\n  "title": "new"\n}\n'
        repo = self.make_repo({ENTITY_SCHEMA: reformatted})
        self.assertEqual(self.apply(repo, self.FILES, "1.8.0"), ("1.8.0", False))
        self.assertEqual(repo.read(ENTITY_SCHEMA), reformatted)

    def test_apply_replaces_invalid_schema(self):
        repo = self.make_repo({ENTITY_SCHEMA: "{not json\n"})
        self.assertEqual(self.apply(repo, self.FILES, "1.8.0"), ("1.8.0", True))
        self.assertEqual(repo.read(ENTITY_SCHEMA), NEW_SCHEMA)

    def test_apply_no_shared_schema_fails(self):
        repo = self.make_repo({ENTITY_SCHEMA: OLD_SCHEMA})
        before = repo.snapshot()
        for version in ("1.8.1", "1.8.0"):
            with self.assertRaisesRegex(PinError, "rules/_schema"):
                self.apply(repo, self.FILES, version, self.make_core({}))
            self.assertEqual(repo.snapshot(), before)

    def test_apply_failure_writes_no_schema(self):
        repo = self.make_repo({ENTITY_SCHEMA: OLD_SCHEMA, "docs/x.md": "see strspc-rules@v1.8.0\n"})
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "docs/x.md"):
            self.apply(repo, self.FILES, "1.8.1")
        self.assertEqual(repo.snapshot(), before)

    def test_apply_refused_downgrade_writes_no_schema(self):
        repo = self.make_repo({ENTITY_SCHEMA: OLD_SCHEMA})
        before = repo.snapshot()
        with self.assertRaisesRegex(PinError, "downgrade"):
            self.apply(repo, self.FILES, "1.7.9")
        self.assertEqual(repo.snapshot(), before)


class EncodingTests(unittest.TestCase):
    def test_cli_reads_and_writes_utf8_explicitly(self):
        # A locale-dependent read could skip a UTF-8 file (docs/SPEC.md has
        # em-dashes) in the leftover check. Fail on any default-encoding use.
        repo = Repo(
            {
                "rules/realm.json": realm_json(),
                "docs/SPEC.md": f"Source — `{OLD_SOURCE}`\n",
                ENTITY_SCHEMA: '{"title": "ancien"}\n',
            }
        )
        self.addCleanup(repo.close)
        core = tempfile.TemporaryDirectory()
        self.addCleanup(core.cleanup)
        (Path(core.name) / "entity.v1.schema.json").write_text('{"title": "—"}\n', encoding="utf-8")
        script = Path(pin_core.__file__)
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "warn_default_encoding",
                "-W",
                "error::EncodingWarning",
                str(script),
                "apply",
                "--repo-dir",
                str(repo.root),
                "--new",
                "1.8.1",
                "--schema-dir",
                core.name,
                "rules/realm.json",
                "docs/SPEC.md",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Source — `" + NEW_SOURCE + "`", repo.read("docs/SPEC.md"))
        self.assertIn("—", repo.read(ENTITY_SCHEMA))


APP = "steerspec-sync[bot]"


class OpenPinTests(unittest.TestCase):
    def test_newer_open_pin_refused(self):
        for author in (APP, "pleberre"):
            with self.assertRaises(PinError, msg=author):
                pin_core.check_open_pins([("chore/core-1.9.0", author)], "1.8.1")

    def test_hand_made_pr_on_target_branch_refused(self):
        with self.assertRaisesRegex(PinError, "chore/core-1.8.1"):
            pin_core.check_open_pins([("chore/core-1.8.1", "pleberre")], "1.8.1")

    def test_superseded_selection(self):
        prs = [
            ("chore/core-1.8.0", APP),
            ("chore/core-1.7.0", "pleberre"),
            ("chore/core-1.8.1", APP),
            ("chore/core-x", APP),
            ("feat/y", APP),
        ]
        self.assertEqual(pin_core.check_open_pins(prs, "1.8.1"), ["chore/core-1.8.0"])

    def test_cli_superseded_reads_branch_and_author(self):
        result = subprocess.run(
            [sys.executable, str(Path(pin_core.__file__)), "superseded", "--new", "1.8.1"],
            input=f"chore/core-1.8.0\t{APP}\nchore/core-1.7.0\tpleberre\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "chore/core-1.8.0\n")


if __name__ == "__main__":
    unittest.main()
