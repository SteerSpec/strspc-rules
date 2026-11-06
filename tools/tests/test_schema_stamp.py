"""Tests for tools/schema_stamp.py. Run: python3 -m unittest discover -s tools/tests -t tools"""

import json
import unittest
from pathlib import Path

from schema_stamp import release_stamp, stamp_schema_text

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "rules" / "core" / "_schema"

UNSTAMPED = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://steerspec.dev/schemas/realm/v1.json",
  "title": "T",
  "properties": {
    "x": { "$comment": "nested, left alone", "type": "string" }
  }
}
"""


class ReleaseStampTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(release_stamp("1.19.0"), "dev.steerspec.core v1.19.0")


class StampSchemaTextTest(unittest.TestCase):
    def test_inserts_after_id(self):
        out = stamp_schema_text(UNSTAMPED, "dev.steerspec.core v1.19.0")
        lines = out.splitlines()
        self.assertEqual(lines[2], '  "$id": "https://steerspec.dev/schemas/realm/v1.json",')
        self.assertEqual(lines[3], '  "$comment": "dev.steerspec.core v1.19.0",')
        self.assertEqual(json.loads(out)["$comment"], "dev.steerspec.core v1.19.0")

    def test_replaces_existing_stamp(self):
        once = stamp_schema_text(UNSTAMPED, "dev.steerspec.core v1.19.0")
        twice = stamp_schema_text(once, "dev.steerspec.core v1.20.0")
        self.assertEqual(twice.count('"$comment": "dev.steerspec.core'), 1)
        self.assertEqual(json.loads(twice)["$comment"], "dev.steerspec.core v1.20.0")

    def test_idempotent(self):
        once = stamp_schema_text(UNSTAMPED, "dev.steerspec.core v1.19.0")
        self.assertEqual(stamp_schema_text(once, "dev.steerspec.core v1.19.0"), once)

    def test_leaves_nested_comment(self):
        out = stamp_schema_text(UNSTAMPED, "dev.steerspec.core v1.19.0")
        self.assertIn('"$comment": "nested, left alone"', out)
        self.assertEqual(json.loads(out)["properties"]["x"]["$comment"], "nested, left alone")

    def test_only_the_stamp_line_changes(self):
        out = stamp_schema_text(UNSTAMPED, "dev.steerspec.core v1.19.0")
        self.assertEqual(out.replace('  "$comment": "dev.steerspec.core v1.19.0",\n', ""), UNSTAMPED)

    def test_no_top_level_id(self):
        with self.assertRaises(ValueError):
            stamp_schema_text('{\n  "title": "T"\n}\n', "dev.steerspec.core v1.19.0")


class CommittedSchemasTest(unittest.TestCase):
    def test_every_core_schema_is_stamped_with_realm_version(self):
        version = json.loads((SCHEMA_DIR.parent / "realm.json").read_text(encoding="utf-8"))["realm"]["version"]
        schemas = sorted(SCHEMA_DIR.glob("*.schema.json"))
        self.assertTrue(schemas)
        for path in schemas:
            with self.subTest(schema=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(data.get("$comment"), release_stamp(version))


if __name__ == "__main__":
    unittest.main()
