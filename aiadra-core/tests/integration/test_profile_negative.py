"""Each of the 12 carried-from-Wedge-002 negative Profile fixtures must reject.

Acceptance criterion item 6 per Claude1 Decision §7 (arc 20260531-1). Verifies
the regex-grade Profile lint rejects every documented violation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aiadra_core.validation.profile import ProfileViolationError, load_yaml


_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "profile_negative"

# (filename, expected substring in error message)
# Uses load_yaml so the full Profile check runs (regex pre-parse lint + ruamel
# duplicate-key detection). Duplicate-key violations only surface during the
# YAML parse stage; lint_profile is regex-only by design.
_CASES = [
    ("alias.yaml",            "aliases"),
    ("anchor.yaml",           "anchors"),
    ("custom_tag.yaml",       "custom tags"),
    ("duplicate_key.yaml",    "Duplicate"),
    # merge_key triggers the alias check first because `*defaults` appears in the
    # raw text; rejection is correct (both are forbidden). See FRICTION_LOG §2.
    ("merge_key.yaml",        ""),
    ("single_bang_tag.yaml",  "custom tags"),
    ("unquoted_bool_like.yaml", "bool-like"),
    ("unquoted_number.yaml",  "Number"),
    ("unquoted_timestamp.yaml", "timestamp"),
    ("unquoted_uuid.yaml",    "UUID"),
    ("unquoted_version.yaml", "semver"),
    ("yaml_1_1.yaml",         "1.1"),
]


@pytest.mark.parametrize("filename,expected_substr", _CASES)
def test_negative_fixture_rejected(filename: str, expected_substr: str):
    fixture = _FIXTURES_DIR / filename
    with pytest.raises(ProfileViolationError) as exc_info:
        load_yaml(fixture)
    if expected_substr:
        assert expected_substr.lower() in str(exc_info.value).lower(), \
            f"{filename}: expected {expected_substr!r} in error {exc_info.value!r}"


def test_count_of_negative_fixtures():
    """Sanity: exactly 12 negative fixtures carried from Wedge-002."""
    yaml_files = sorted(_FIXTURES_DIR.glob("*.yaml"))
    assert len(yaml_files) == 12, [p.name for p in yaml_files]
