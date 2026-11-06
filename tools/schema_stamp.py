"""Release stamp for the core schemas in rules/core/_schema/.

Each schema carries a top-level "$comment": "dev.steerspec.core vX.Y.Z" taken
from realm.version, so a copy vendored into another realm shows which core
release it came from. $comment is a JSON Schema keyword that validators
ignore. build-schema.py writes and checks the stamp; this module has no
dependencies so the unit tests can import it.
"""

import json
import re

# Top-level lines only: two-space indent, as every core schema is laid out.
_TOP_ID_LINE = re.compile(r'^  "\$id": .*,\n', re.MULTILINE)
_TOP_COMMENT_LINE = re.compile(r'^  "\$comment": .*,\n', re.MULTILINE)


def release_stamp(version: str) -> str:
    return f"dev.steerspec.core v{version}"


def stamp_schema_text(text: str, stamp: str) -> str:
    """Set the top-level $comment of a schema to stamp, right after $id.

    Edits the text rather than re-serializing it, so a hand-maintained
    schema keeps its own layout.
    """
    line = f'  "$comment": {json.dumps(stamp, ensure_ascii=False)},\n'
    if _TOP_COMMENT_LINE.search(text):
        return _TOP_COMMENT_LINE.sub(lambda _: line, text, count=1)
    match = _TOP_ID_LINE.search(text)
    if not match:
        raise ValueError('no top-level "$id" line to place the release stamp after')
    return text[: match.end()] + line + text[match.end() :]
