"""YAML I/O + AIADRA YAML Profile spike-grade lint + atomic write.

Per ADR/0002 §1 AIADRA YAML Profile: YAML 1.2 only; no anchors/aliases/merge
keys/custom tags; duplicate-key rejection; quoted ambiguous scalars; JSON
Schema validation at every read.

Spike-grade implementation:
  * regex-over-raw-text pre-parse pass catches anchors/aliases/merge
    keys/custom tags/YAML 1.1 directive AND unquoted ambiguous scalars
    (UUID / Number / version / timestamp / bool-like)
  * ruamel.yaml typ='safe' for duplicate-key rejection
  * dump-side: every string serialised with explicit quoting style so
    output is always Profile conformant
  * atomic write via temp-file-then-rename of raw bytes (no platform
    newline translation)
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError


class ProfileViolationError(ValueError):
    """Raised when text violates the AIADRA YAML Profile."""


# ---------------- raw-text pre-parse pass ----------------

_RE_YAML_BAD_DIRECTIVE = re.compile(r"^%YAML\s+1\.1", re.MULTILINE)
_RE_ANCHOR = re.compile(r"(?<!['\"])\s&[A-Za-z0-9_-]+")
_RE_ALIAS = re.compile(r"(?<!['\"])\s\*[A-Za-z0-9_-]+")
_RE_MERGE_KEY = re.compile(r"^\s*<<\s*:", re.MULTILINE)
# Catch both single-bang `!localtag` and double-bang `!!secondaryhandle:type` —
# Codex3 N5 (arc 20260530-1) noted ADR/0002's examples focus on `!!...` but
# "custom tags" reads broadly. Spike-grade lints both.
_RE_CUSTOM_TAG = re.compile(r"(?<!['\"])\s!{1,2}[A-Za-z]")

# Patterns for ambiguous scalars that MUST be quoted per ADR/0002 §1.
_AMBIG = [
    (re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"), "UUID"),
    (re.compile(r"^[A-Z]+-[0-9]{6}$"), "Number"),
    # Three+ segment dotted strings (semver) are unambiguous strings, not floats; require quoting.
    # Two-segment forms (e.g., "7.0") parse as floats per YAML 1.2 and are NOT linted as
    # ambiguous strings — they're legitimate numeric scalars when used as parameter values.
    # FRICTION_LOG: spike accepts the gap for two-segment version strings; production lint
    # should consult the schema field type before deciding.
    (re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)+$"), "semver"),
    (re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"), "ISO 8601 timestamp"),
    (re.compile(r"^(y|Y|yes|Yes|YES|n|N|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF)$"), "bool-like"),
    (re.compile(r"^0[0-9]+$"), "leading-zero numeric"),
]


def _scalar_is_quoted_or_block(value: str) -> bool:
    """Return True if the value already has a quoting/block-scalar style."""
    if not value:
        return True  # empty value, nothing to misinterpret
    return value[0] in ('"', "'", "[", "{", "|", ">", "&", "*", "!")


def _scan_ambiguous_scalars(text: str) -> None:
    """Raise ProfileViolationError on any unquoted ambiguous scalar in value
    position (after `key:` or `- ` for list-item values).

    Spike-grade: line-by-line regex. False negatives possible for inline
    flow-style mappings/sequences; the Profile rejects flow style for
    sidecars anyway in practice. False positives possible for `#` inside
    unquoted scalars — see FRICTION_LOG.md.
    """
    for line_no, raw in enumerate(text.splitlines(), 1):
        # Strip an unquoted line-comment (naive: # preceded by whitespace or at line start)
        if "#" in raw:
            idx = raw.find("#")
            if idx == 0 or raw[idx - 1].isspace():
                raw = raw[:idx]
        line = raw.rstrip()
        if not line.strip():
            continue
        # mapping value: `key: value`
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
        # list-item scalar: `- value` (and not `- key: value`)
        m2 = re.match(r"^\s*-\s+(.+)$", line)
        if m2:
            v = m2.group(1).strip()
            # Skip sub-mappings (`- key: ...`) — the value position is the
            # rest of the line after `: ` and would be re-scanned by the
            # mapping-value branch above when ruamel parses sub-keys.
            if re.match(r"^[^\s:#'\"\[\{]+:\s*", v):
                continue
            if not _scalar_is_quoted_or_block(v):
                for pat, kind in _AMBIG:
                    if pat.match(v):
                        raise ProfileViolationError(
                            f"line {line_no}: unquoted {kind} list-item scalar {v!r}"
                        )


def validate_yaml_profile(text: str) -> None:
    """Raise ProfileViolationError if text violates the AIADRA YAML Profile."""
    if _RE_YAML_BAD_DIRECTIVE.search(text):
        raise ProfileViolationError("YAML 1.1 directive forbidden; Profile requires 1.2")
    if _RE_ANCHOR.search(text):
        raise ProfileViolationError("YAML anchors (&name) forbidden by AIADRA YAML Profile")
    if _RE_ALIAS.search(text):
        raise ProfileViolationError("YAML aliases (*name) forbidden by AIADRA YAML Profile")
    if _RE_MERGE_KEY.search(text):
        raise ProfileViolationError("YAML merge keys (<<:) forbidden by AIADRA YAML Profile")
    if _RE_CUSTOM_TAG.search(text):
        raise ProfileViolationError("YAML custom tags (! or !!) forbidden by AIADRA YAML Profile")
    _scan_ambiguous_scalars(text)


# ---------------- ruamel.yaml wrapper ----------------


def _str_representer(dumper, data):
    """Force every string scalar to be emitted double-quoted.

    Spike-grade: over-quotes (e.g., `type: "Part"` rather than `type: Part`),
    which is more than the Profile strictly requires but is always Profile
    conformant. Production-grade may be selective using ruamel scalarstring
    types — see FRICTION_LOG.md.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


def _yaml() -> YAML:
    y = YAML(typ="safe", pure=True)
    y.default_flow_style = False
    y.allow_duplicate_keys = False
    y.indent(mapping=2, sequence=4, offset=2)
    y.representer.add_representer(str, _str_representer)
    return y


def load_yaml(path: Path) -> Any:
    """Load YAML from path, Profile-validating raw text first."""
    text = path.read_text(encoding="utf-8")
    validate_yaml_profile(text)
    try:
        return _yaml().load(text)
    except DuplicateKeyError as e:
        raise ProfileViolationError(f"Duplicate mapping key (AIADRA YAML Profile violation): {e}") from e


def dump_yaml(data: Any) -> str:
    """Dump data to YAML string with all strings double-quoted (Profile)."""
    buf = io.StringIO()
    _yaml().dump(data, buf)
    return buf.getvalue()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Atomically write raw bytes via temp-file-then-rename (os.replace).

    Writes BYTES (not text) so Windows does not translate \n to \r\n and the
    on-disk hash matches the in-memory text's UTF-8 hash. See Codex2 B2 +
    FRICTION_LOG.md.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write text as UTF-8 bytes (no newline translation)."""
    atomic_write_bytes(path, text.encode("utf-8"))


def write_yaml_atomic(path: Path, data: Any) -> str:
    """Dump + atomic write. Returns the exact UTF-8 text written (for hashing)."""
    text = dump_yaml(data)
    atomic_write_text(path, text)
    return text
