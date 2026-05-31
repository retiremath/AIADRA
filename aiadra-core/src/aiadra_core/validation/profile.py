"""AIADRA YAML Profile lint + Profile-conformant dumper.

Per ADR/0002 §1: YAML 1.2 only; no anchors/aliases/merge keys/custom tags;
duplicate-key rejection; quoted ambiguous scalars; JSON Schema validation at
every read (in the validation/schema.py layer).

Spike-grade implementation carried forward from Wedge-002. Known false positive:
two-segment version strings vs. floats (e.g., "1.0" matches both rules). The
production-grade token-stream-based linter is deferred per ADR/0025 §10.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError


class ProfileViolationError(ValueError):
    """Raised when text violates the AIADRA YAML Profile."""


_RE_YAML_BAD_DIRECTIVE = re.compile(r"^%YAML\s+1\.1", re.MULTILINE)
_RE_ANCHOR = re.compile(r"(?<!['\"])\s&[A-Za-z0-9_-]+")
_RE_ALIAS = re.compile(r"(?<!['\"])\s\*[A-Za-z0-9_-]+")
_RE_MERGE_KEY = re.compile(r"^\s*<<\s*:", re.MULTILINE)
_RE_CUSTOM_TAG = re.compile(r"(?<!['\"])\s!{1,2}[A-Za-z]")

_AMBIG = [
    (re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"), "UUID"),
    (re.compile(r"^[A-Z]+-[0-9]{6}$"), "Number"),
    (re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)+$"), "semver"),
    (re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"), "ISO 8601 timestamp"),
    (re.compile(r"^(y|Y|yes|Yes|YES|n|N|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$"), "bool-like"),
    (re.compile(r"^0[0-9]+$"), "leading-zero numeric"),
]


def _scalar_is_quoted_or_block(value: str) -> bool:
    if not value:
        return True
    return value[0] in ('"', "'", "[", "{", "|", ">", "&", "*", "!")


def _scan_ambiguous_scalars(text: str) -> None:
    for line_no, raw in enumerate(text.splitlines(), 1):
        if "#" in raw:
            idx = raw.find("#")
            if idx == 0 or raw[idx - 1].isspace():
                raw = raw[:idx]
        line = raw.rstrip()
        if not line.strip():
            continue
        m = re.match(r"^\s*[^\s:#\[\{]+:\s+(.+)$", line)
        if m:
            v = m.group(1).strip()
            if not _scalar_is_quoted_or_block(v):
                for pat, kind in _AMBIG:
                    if pat.match(v):
                        raise ProfileViolationError(
                            f"line {line_no}: unquoted {kind} scalar {v!r} "
                            f"(AIADRA YAML Profile requires quoting)"
                        )
        m2 = re.match(r"^\s*-\s+(.+)$", line)
        if m2:
            v = m2.group(1).strip()
            if re.match(r"^[^\s:#'\"\[\{]+:\s*", v):
                continue
            if not _scalar_is_quoted_or_block(v):
                for pat, kind in _AMBIG:
                    if pat.match(v):
                        raise ProfileViolationError(
                            f"line {line_no}: unquoted {kind} list-item scalar {v!r}"
                        )


def lint_profile(yaml_text: str) -> None:
    """Raise ProfileViolationError if text violates the AIADRA YAML Profile."""
    if _RE_YAML_BAD_DIRECTIVE.search(yaml_text):
        raise ProfileViolationError("YAML 1.1 directive forbidden; Profile requires 1.2")
    if _RE_ANCHOR.search(yaml_text):
        raise ProfileViolationError("YAML anchors (&name) forbidden by AIADRA YAML Profile")
    if _RE_ALIAS.search(yaml_text):
        raise ProfileViolationError("YAML aliases (*name) forbidden by AIADRA YAML Profile")
    if _RE_MERGE_KEY.search(yaml_text):
        raise ProfileViolationError("YAML merge keys (<<:) forbidden by AIADRA YAML Profile")
    if _RE_CUSTOM_TAG.search(yaml_text):
        raise ProfileViolationError("YAML custom tags (! or !!) forbidden by AIADRA YAML Profile")
    _scan_ambiguous_scalars(yaml_text)


def _str_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


def _yaml() -> YAML:
    y = YAML(typ="safe", pure=True)
    y.default_flow_style = False
    y.allow_duplicate_keys = False
    y.indent(mapping=2, sequence=4, offset=2)
    y.representer.add_representer(str, _str_representer)
    return y


def load_yaml(path: Path) -> Any:
    """Load YAML from path, Profile-linting raw text first.

    Raises ProfileViolationError on Profile violation (including duplicate keys
    surfaced by ruamel.yaml's DuplicateKeyError).
    """
    text = path.read_text(encoding="utf-8")
    lint_profile(text)
    try:
        return _yaml().load(text)
    except DuplicateKeyError as e:
        raise ProfileViolationError(
            f"Duplicate mapping key (AIADRA YAML Profile violation): {e}"
        ) from e


def dump_yaml(data: Any) -> str:
    """Dump data to YAML string with all strings double-quoted (Profile)."""
    buf = io.StringIO()
    _yaml().dump(data, buf)
    return buf.getvalue()
