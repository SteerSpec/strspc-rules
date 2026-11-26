"""Tests for the config schema of tools/build-schema.py.

Needs the packages of requirements.txt, as build-schema.py does.
Run: python3 -m unittest discover -s tools/tests -t tools
"""

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

TOOLS = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("build_schema", TOOLS / "build-schema.py")
build_schema = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_schema)


def rules(prefix: str, *bodies: str) -> list[dict]:
    return [{"id": f"{prefix}-{n:03d}", "body": body} for n, body in enumerate(bodies, 1)]


COVERAGE = ("SPCFG", "SPCFGCOV")

COVERAGE_RULES = rules(
    "SPCFGCOV",
    "IS an entry in the `coverage` array of the `refs` object in config.yaml.",
    "MUST have an `entities` property holding an array of at least one Entity Unique Identifier.",
    "MUST have a `files` property holding an array of at least one file pattern.",
    "MAY have a `states` property holding an array of rule lifecycle state codes.",
    "Each Rule of an Entity in `entities` whose state `states` names MUST be cited in at least one file that a "
    "pattern in `files` matches.",
)


def base_rules() -> dict:
    return {
        ("SPCFG", None): rules(
            "SPCFG",
            "MAY declare an `evaluate_on` array of rule lifecycle state codes restricting which rules are evaluated.",
        ),
        ("SPCFG", "SPCFGSRC"): rules(
            "SPCFGSRC",
            "MUST have a `source` property of type string.",
            "MUST have a `scope` property with allowed values: global, local.",
        ),
        ("SPCFG", "SPCFGFAIL"): rules(
            "SPCFGFAIL",
            "Each item MUST be a valid rule lifecycle state code: Draft (D), Abandoned (A), Published (P), "
            "Implemented (I), Retired (R), Terminated (T).",
        ),
        ("ENT", "ENTUQID"): rules(
            "ENTUQID",
            "MUST have a length of at least 3 and at most 18 characters.",
            "IS a string of letters or numbers only.",
        ),
    }


def build(rules_by_entity: dict) -> dict:
    with contextlib.redirect_stdout(io.StringIO()):
        return build_schema.build_config_schema(rules_by_entity)


def with_coverage(coverage_rules: list[dict] = COVERAGE_RULES) -> dict:
    return build({**base_rules(), COVERAGE: coverage_rules})


def config(**sections) -> dict:
    return {"rules": [{"source": "./rules", "scope": "global"}], **sections}


def entry(**overrides) -> dict:
    item = {"entities": ["README", "CLAIM", "BRAND"], "files": [".claude/agents/*.md"]}
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not None}


def refs(*entries: dict) -> dict:
    return config(refs={"coverage": list(entries)})


class CoverageSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = with_coverage()
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def accepts(self, instance: dict) -> None:
        self.assertEqual([e.message for e in self.validator.iter_errors(instance)], [])

    def rejects(self, instance: dict) -> None:
        self.assertNotEqual(list(self.validator.iter_errors(instance)), [])

    def test_accepts_the_example_of_the_issue(self):
        self.accepts(refs(entry()))

    def test_accepts_states(self):
        self.accepts(refs(entry(states=["D", "P", "I"])))

    def test_accepts_several_entries(self):
        self.accepts(refs(entry(), entry(entities=["SPCFG"], files=["docs/**"])))

    def test_accepts_a_config_with_no_refs(self):
        self.accepts(config())

    def test_refs_is_not_required(self):
        self.assertEqual(self.schema["required"], ["rules"])

    def test_rejects_an_unknown_key_in_refs(self):
        self.rejects(config(refs={"coverage": [entry()], "strict": True}))

    def test_rejects_an_unknown_key_in_an_entry(self):
        self.rejects(refs(entry(exclude=["x.md"])))

    def test_rejects_an_entry_with_no_entities(self):
        self.rejects(refs(entry(entities=None)))

    def test_rejects_an_entry_with_no_files(self):
        self.rejects(refs(entry(files=None)))

    def test_rejects_empty_entities(self):
        self.rejects(refs(entry(entities=[])))

    def test_rejects_empty_files(self):
        self.rejects(refs(entry(files=[])))

    def test_rejects_an_empty_coverage(self):
        self.rejects(config(refs={"coverage": []}))

    def test_rejects_an_unknown_state_code(self):
        self.rejects(refs(entry(states=["X"])))

    def test_rejects_an_entity_id_the_entity_schema_rejects(self):
        for bad in ("AB", "CLAIM-009", "A" * 19):
            with self.subTest(bad=bad):
                self.rejects(refs(entry(entities=[bad])))

    def test_rejects_a_file_pattern_that_is_not_a_string(self):
        self.rejects(refs(entry(files=[1])))

    def test_entry_shape(self):
        item = self.schema["properties"]["refs"]["properties"]["coverage"]["items"]
        self.assertEqual(item["required"], ["entities", "files"])
        self.assertEqual(sorted(item["properties"]), ["entities", "files", "states"])
        self.assertIs(item["additionalProperties"], False)
        self.assertIs(self.schema["properties"]["refs"]["additionalProperties"], False)

    def test_states_share_the_items_of_fail_on(self):
        item = self.schema["properties"]["refs"]["properties"]["coverage"]["items"]
        self.assertEqual(item["properties"]["states"]["items"], self.schema["properties"]["fail_on"]["items"])

    def test_entities_take_the_entity_id_constraints(self):
        item = self.schema["properties"]["refs"]["properties"]["coverage"]["items"]
        self.assertEqual(
            item["properties"]["entities"]["items"],
            {"type": "string", "minLength": 3, "maxLength": 18, "pattern": "^[a-zA-Z0-9]+$"},
        )


class CoverageGenerationTest(unittest.TestCase):
    def test_no_coverage_rules_means_no_refs_section(self):
        schema = build(base_rules())
        self.assertNotIn("refs", schema["properties"])
        self.assertNotEqual(list(Draft202012Validator(schema).iter_errors(refs(entry()))), [])

    def test_coverage_rules_with_no_property_fail(self):
        with self.assertRaises(RuntimeError):
            with_coverage(COVERAGE_RULES[:1])

    def test_an_unknown_kind_of_array_item_fails(self):
        unknown = rules("SPCFGCOV", "MUST have a `files` property holding an array of at least one widget.")
        with self.assertRaises(RuntimeError):
            with_coverage(unknown)

    def test_entity_ids_with_no_constraints_fail(self):
        rules_by_entity = {**base_rules(), COVERAGE: COVERAGE_RULES}
        del rules_by_entity[("ENT", "ENTUQID")]
        with self.assertRaises(RuntimeError):
            build(rules_by_entity)

    def test_a_string_property_keeps_its_type(self):
        schema = build(base_rules())
        self.assertEqual(schema["properties"]["rules"]["items"]["properties"]["source"], {"type": "string"})


class CoreConfigSchemaTest(unittest.TestCase):
    """The schema built from the rules of dev.steerspec.core themselves."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            files = build_schema.load_core_files()
            cls.schema = build_schema.build_config_schema(build_schema.collect_rules_by_entity(files))
        cls.validator = Draft202012Validator(cls.schema)

    def test_accepts_the_example_of_the_issue(self):
        self.assertEqual([e.message for e in self.validator.iter_errors(refs(entry(states=["D", "P", "I"])))], [])

    def test_rejects_an_unknown_key_in_an_entry(self):
        self.assertNotEqual(list(self.validator.iter_errors(refs(entry(exclude=["x.md"])))), [])

    def test_keeps_the_sections_it_had(self):
        self.assertLessEqual({"rules", "evaluator", "cache", "fail_on", "evaluate_on"}, set(self.schema["properties"]))


if __name__ == "__main__":
    unittest.main()
