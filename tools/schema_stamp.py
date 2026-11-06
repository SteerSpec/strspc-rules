"""Release stamp for the core schemas in rules/core/_schema/.

Each schema carries a top-level "x-steerspec-core-version": "X.Y.Z" taken
from realm.version, so a copy vendored into another realm shows which core
release it came from. JSON Schema 2020-12 ignores unknown keywords for
validation, and the x- prefix marks an extension. build-schema.py writes and
checks the stamp; this module has no dependencies so the unit tests can
import it.
"""

import json
import re

STAMP_KEY = "x-steerspec-core-version"

# Top-level lines only: two-space indent, as every core schema is laid out.
_TOP_ID_LINE = re.compile(r'^  "\$id": .*,\n', re.MULTILINE)
_TOP_STAMP_LINE = re.compile(r'^  "' + re.escape(STAMP_KEY) + r'": .*,\n', re.MULTILINE)


def stamp_schema_text(text: str, version: str) -> str:
    """Set the top-level release stamp of a schema to version, right after $id.

    Edits the text rather than re-serializing it, so a hand-maintained
    schema keeps its own layout.
    """
    line = f'  "{STAMP_KEY}": {json.dumps(version)},\n'
    if _TOP_STAMP_LINE.search(text):
        return _TOP_STAMP_LINE.sub(lambda _: line, text, count=1)
    match = _TOP_ID_LINE.search(text)
    if not match:
        raise ValueError('no top-level "$id" line to place the release stamp after')
    return text[: match.end()] + line + text[match.end() :]
