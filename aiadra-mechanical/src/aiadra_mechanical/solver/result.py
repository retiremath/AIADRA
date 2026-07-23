"""The signed two-axis solve result (Codex16 B2).

ADR/0044 D4 and the skb-1 gate deliberately separate DoF/CLASSIFICATION
from SOLVE DIAGNOSTICS, and this surface preserves both axes:

- ``classification``: ``well | under | over | rejected`` — the rank/DoF
  verdict on the strong system;
- ``diagnostics``: ``redundant | conflicting | non-convergent |
  out-of-domain | completion-stuck`` — what happened while classifying,
  completing, and solving. A redundant-but-consistent over system SOLVES
  (classification ``over`` + a ``redundant`` diagnostic + solved
  coordinates); a conflicting one does not. Collapsing the axes was the
  exact compression Codex16 refused.

The hyphenated diagnostic kinds are the canonical skb-1 wire strings —
kept verbatim so :meth:`SolveResult.canonical_bytes` reproduces the
accepted corpus evidence byte-for-byte.

``solved_coordinates`` are DERIVED/ephemeral output — never Product Truth
(ADR/0044: solved coordinates are cache, the constrained model is the
fact). ``weak_completion`` records are the AIADRA-chosen skb-0 completion,
typed per fact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import canonical_result_bytes

CLASSIFICATIONS = ("well", "under", "over", "rejected")
DIAGNOSTIC_KINDS = ("redundant", "conflicting", "non-convergent",
                    "out-of-domain", "completion-stuck")


@dataclass(frozen=True)
class Diagnostic:
    """One typed solve diagnostic: what happened, naming which facts."""

    kind: str
    members: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in DIAGNOSTIC_KINDS:
            raise ValueError(f"unknown diagnostic kind {self.kind!r}")

    def to_record(self) -> dict[str, Any]:
        return {"kind": self.kind, "members": list(self.members)}


@dataclass(frozen=True)
class CompletionFact:
    """One skb-0 weak completion record, typed.

    ``raw`` is the canonical record dict (identity-bearing shape from the
    accepted evidence); the typed fields are views into it.
    """

    raw: Mapping[str, Any]

    @property
    def fact_id(self) -> str:
        return self.raw["id"]

    @property
    def target_entity(self) -> str:
        return self.raw["target"]["entity"]

    @property
    def target_parameter(self) -> str:
        return self.raw["target"]["parameter"]

    @property
    def magnitude(self) -> float:
        return self.raw["value"]["magnitude"]

    @property
    def unit(self) -> str:
        return self.raw["value"]["unit"]

    def to_record(self) -> dict[str, Any]:
        return _deep_copy(self.raw)


@dataclass(frozen=True)
class SolveTelemetry:
    """Evidence, never Truth: timing and native update-step accounting."""

    wall_ms: float | None = None
    update_steps: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SolveResult:
    """The two-axis result of solving one skb-1-shaped system."""

    classification: str
    dof_strong: int | None
    weak_completion: tuple[CompletionFact, ...]
    solved_coordinates: Mapping[str, float] | None
    residual_max: Mapping[str, float] | None
    diagnostics: tuple[Diagnostic, ...]
    branch_oracle_value: int | None
    case_id: str
    corpus_version: str
    solver_contract: str
    telemetry: SolveTelemetry = field(compare=False, default=SolveTelemetry())

    def __post_init__(self) -> None:
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(f"unknown classification {self.classification!r}")

    @property
    def solved(self) -> bool:
        return self.solved_coordinates is not None

    @classmethod
    def from_canonical(cls, result: Mapping[str, Any],
                       telemetry: SolveTelemetry = SolveTelemetry()) -> "SolveResult":
        """Type a canonical result dict (the accepted evidence DTO shape)."""
        solved = result["solved"]
        residual = result["residual_max"]
        return cls(
            classification=result["classification"],
            dof_strong=result["dof_strong"],
            weak_completion=tuple(
                CompletionFact(MappingProxyType(_deep_copy(w)))
                for w in result["weak_completion"]
            ),
            solved_coordinates=(MappingProxyType(dict(solved))
                                if solved is not None else None),
            residual_max=(MappingProxyType(dict(residual))
                          if residual is not None else None),
            diagnostics=tuple(
                Diagnostic(kind=d["kind"], members=tuple(d["members"]))
                for d in result["diagnostics"]
            ),
            branch_oracle_value=result["branch_oracle_value"],
            case_id=result["case_id"],
            corpus_version=result["corpus_version"],
            solver_contract=result["solver_contract"],
            telemetry=telemetry,
        )

    def canonical_dict(self) -> dict[str, Any]:
        """The exact accepted-evidence DTO shape (skb-1 SCHEMA section 5)."""
        return {
            "case_id": self.case_id,
            "corpus_version": self.corpus_version,
            "solver_contract": self.solver_contract,
            "classification": self.classification,
            "dof_strong": self.dof_strong,
            "weak_completion": [w.to_record() for w in self.weak_completion],
            "solved": (dict(self.solved_coordinates)
                       if self.solved_coordinates is not None else None),
            "residual_max": (dict(self.residual_max)
                             if self.residual_max is not None else None),
            "branch_oracle_value": self.branch_oracle_value,
            "diagnostics": [d.to_record() for d in self.diagnostics],
        }

    def canonical_bytes(self) -> bytes:
        """skb-canon-1 serialization — the repeatability/digest lane."""
        return canonical_result_bytes(self.canonical_dict())


def _deep_copy(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj
