"""The I1 profile-authoring operations (ADR/0044 A4; Codex5 authorized).

Three operations, one semantic path:

- `mechanical.author_profile_sketch`  (write, creates)
- `mechanical.replace_sketch_graph`   (write, edits)
- `mechanical.preview_sketch_graph`   (READ, no draft/staging/audit)

Line, polyline, rectangle and circle are UI SUGAR over one fact graph —
there are deliberately no per-tool operations. That is what makes G-AI true:
an agent authors the identical graph with no renderer in the loop.

The reference grammar is closed (Codex4 B2): a client key `K` matches
`^[A-Za-z0-9_]{1,32}$` and is unique across the WHOLE call; a reference is
`{"key": K}` or `{"id": "skp_NNNN"}` and never a bare string, so a ref can
never be read two ways.

The SURVIVAL LAW (Codex4 B1) — `replace_sketch_graph` only:
  * a preserved `id` keeps its entity AND its structural references exactly
    (a segment's endpoints, a circle's centre, a fact's target may NOT
    change under a preserved id);
  * a `key` mints a new id;
  * an existing profile record ABSENT from the call is REMOVED — the
    skeleton case, which invalidates dependents fail-closed.
Only authored NOMINALS may change under a preserved id. This is what makes
I2's wall identity survive a drag for a reason rather than by luck.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from aiadra_core.transaction.boundary import TransactionError

_KEY_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
_ENTITY_ID_RE = re.compile(r"^skp_([0-9]{4})$")
_FACT_ID_RE = re.compile(r"^c([0-9]{2})$")
_ENTITY_ID_MAX = 9999
_FACT_ID_MAX = 99


def _fail(op: str, reason: str) -> None:
    raise TransactionError(f"{op}: {reason}")


def _mint(prefix: str, width: int, used: set, op: str, limit: int) -> str:
    """Typed id-capacity refusal BEFORE staging (Codex4 N2): a bounded id
    grammar never wraps, never widens silently, and never reuses."""
    n = 1
    while f"{prefix}{n:0{width}d}" in used:
        n += 1
    if n > limit:
        _fail(op, f"id space {prefix}{'N' * width} is exhausted "
                  f"({limit} records); refusing before staging rather than "
                  "wrapping, widening the grammar, or reusing an id")
    minted = f"{prefix}{n:0{width}d}"
    used.add(minted)
    return minted


def _check_ref(ref: Any, op: str, where: str) -> tuple:
    """Resolve the closed `{key}|{id}` union. Returns ('key'|'id', value)."""
    if not isinstance(ref, Mapping) or len(ref) != 1:
        _fail(op, f"{where} must be exactly one of {{'key': …}} or {{'id': …}} "
                  f"— a bare string is never accepted (got {ref!r})")
    if "key" in ref:
        if not (isinstance(ref["key"], str) and _KEY_RE.match(ref["key"])):
            _fail(op, f"{where} key {ref['key']!r} is not ^[A-Za-z0-9_]{{1,32}}$")
        return "key", ref["key"]
    if "id" in ref:
        if not (isinstance(ref["id"], str) and _ENTITY_ID_RE.match(ref["id"])):
            _fail(op, f"{where} id {ref['id']!r} is not ^skp_NNNN$")
        return "id", ref["id"]
    _fail(op, f"{where} carries neither 'key' nor 'id'")
    raise AssertionError  # unreachable


def resolve_profile(profile: Any, *, op: str,
                    existing: Mapping[str, Mapping[str, Any]] | None = None,
                    reserved_ids: Sequence[str] = ()) -> tuple:
    """Turn a client profile payload into engine entities + constraints.

    `existing` maps the target feature's CURRENT profile records by id (edit
    lane); `reserved_ids` are ids already in use in the whole feature (the
    reference block plus current profile) so minting never collides.

    Returns (entities, constraints, removed_ids).
    """
    if not isinstance(profile, Mapping):
        _fail(op, "profile must be an object")
    unknown = set(profile) - {"points", "segments", "circles", "facts"}
    if unknown:
        _fail(op, f"profile carries unknown keys {sorted(unknown)} "
                  "(the profile payload shape is closed)")

    existing = dict(existing or {})
    used_entity_ids = {i for i in reserved_ids if _ENTITY_ID_RE.match(i)}
    used_fact_ids: set = set()

    seen_keys: set = set()
    seen_ids: set = set()

    def _claim(rec: Any, kind: str, index: int) -> tuple:
        """Returns ('key'|'id', value) for a record's own identity slot."""
        if not isinstance(rec, Mapping):
            _fail(op, f"{kind}[{index}] must be an object")
        has_key, has_id = "key" in rec, "id" in rec
        if has_key == has_id:
            _fail(op, f"{kind}[{index}] must carry exactly one of 'key' "
                      "(mint a new record) or 'id' (preserve an existing one)")
        if has_key:
            k = rec["key"]
            if not (isinstance(k, str) and _KEY_RE.match(k)):
                _fail(op, f"{kind}[{index}] key {k!r} is not ^[A-Za-z0-9_]{{1,32}}$")
            if k in seen_keys:
                _fail(op, f"key {k!r} appears twice — keys are unique across "
                          "the whole call")
            seen_keys.add(k)
            return "key", k
        i = rec["id"]
        if not isinstance(i, str):
            _fail(op, f"{kind}[{index}] id must be a string")
        if i in seen_ids:
            _fail(op, f"id {i!r} appears twice in this call")
        seen_ids.add(i)
        if i not in existing:
            _fail(op, f"{kind}[{index}] preserves id {i!r}, which is not a "
                      "record of THIS sketch's current profile block "
                      "(cross-sketch, reference-block and unknown ids refuse)")
        return "id", i

    # ---- pass 1: identity for points, circles, segments, facts ----------
    key_to_id: dict = {}
    plan: list = []

    for kind, width, prefix, limit in (("points", 4, "skp_", _ENTITY_ID_MAX),
                                       ("segments", 4, "skp_", _ENTITY_ID_MAX),
                                       ("circles", 4, "skp_", _ENTITY_ID_MAX)):
        for index, rec in enumerate(profile.get(kind, []) or []):
            slot, value = _claim(rec, kind, index)
            if slot == "id":
                want = {"points": "point", "segments": "line",
                        "circles": "circle"}[kind]
                if existing[value]["type"] != want:
                    _fail(op, f"id {value!r} is a {existing[value]['type']!r} "
                              f"but appears under {kind!r} — same-id kind "
                              "mutation is never a shortcut between the value "
                              "and skeleton cases")
                eid = value
            else:
                eid = _mint(prefix, width, used_entity_ids, op, limit)
                key_to_id[value] = eid
            plan.append((kind, rec, eid))

    for index, rec in enumerate(profile.get("facts", []) or []):
        slot, value = _claim(rec, "facts", index)
        if slot == "id":
            if not _FACT_ID_RE.match(value):
                _fail(op, f"fact id {value!r} is not ^cNN$")
            fid = value
            used_fact_ids.add(fid)
        else:
            fid = None            # minted in pass 2 once the set is known
        plan.append(("facts", rec, fid))

    def _resolve(ref: Any, where: str) -> str:
        slot, value = _check_ref(ref, op, where)
        if slot == "id":
            if value not in existing:
                _fail(op, f"{where} references id {value!r}, which is not a "
                          "record of this sketch's current profile block")
            return value
        if value not in key_to_id:
            _fail(op, f"{where} references key {value!r}, which no record in "
                      "this call declares")
        return key_to_id[value]

    # ---- pass 2: build the engine records --------------------------------
    entities: list = []
    constraints: list = []
    for kind, rec, ident in plan:
        if kind == "points":
            nom = rec.get("nominal", {"x": rec.get("x"), "y": rec.get("y")})
            if not (isinstance(nom, Mapping) and set(nom) == {"x", "y"}):
                _fail(op, f"point {ident} needs nominal {{x, y}}")
            entities.append({"id": ident, "type": "point", "construction": False,
                             "nominal": {"x": float(nom["x"]), "y": float(nom["y"])}})
        elif kind == "segments":
            start = _resolve(rec.get("start"), f"segment {ident} start")
            end = _resolve(rec.get("end"), f"segment {ident} end")
            if "id" in rec:
                prev = existing[ident]
                if (prev["start"], prev["end"]) != (start, end):
                    _fail(op, f"segment {ident} preserves its id but changes "
                              "its endpoints — a structural change must omit "
                              "the id and supply a new key (survival law)")
            entities.append({"id": ident, "type": "line", "construction": False,
                             "start": start, "end": end})
        elif kind == "circles":
            center = _resolve(rec.get("center"), f"circle {ident} center")
            if "id" in rec:
                prev = existing[ident]
                if prev["center"] != center:
                    _fail(op, f"circle {ident} preserves its id but changes "
                              "its centre — a structural change must omit the "
                              "id and supply a new key (survival law)")
            radius = rec.get("radius_mm", rec.get("radius"))
            if not isinstance(radius, (int, float)) or isinstance(radius, bool):
                _fail(op, f"circle {ident} needs a numeric radius_mm")
            entities.append({"id": ident, "type": "circle", "construction": False,
                             "center": center,
                             "nominal": {"radius": float(radius)}})

    for kind, rec, ident in plan:
        if kind != "facts":
            continue
        if rec.get("kind") not in ("horizontal", "vertical"):
            _fail(op, f"fact kind {rec.get('kind')!r} is outside skb-b1 "
                      "(only horizontal/vertical on profile segments)")
        target = _resolve(rec.get("target"), "fact target")
        fid = ident or _mint("c", 2, used_fact_ids, op, _FACT_ID_MAX)
        if "id" in rec:
            prev = existing[rec["id"]]
            if prev.get("kind") != rec["kind"] or prev["args"][0] != target:
                _fail(op, f"fact {fid} preserves its id but changes its kind "
                          "or target — an H/V fact has no editable value, so "
                          "a different target is a DIFFERENT fact (survival "
                          "law): omit the id and supply a new key")
        constraints.append({"id": fid, "kind": rec["kind"], "args": [target]})

    kept = {e["id"] for e in entities} | {c["id"] for c in constraints}
    removed = sorted(i for i in existing if i not in kept)
    return entities, constraints, removed
