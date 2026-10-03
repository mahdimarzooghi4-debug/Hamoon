from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, getcontext
from enum import StrEnum
from uuid import UUID

from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.errors import (
    InvalidFormulaVersionError,
    InvalidPGORInputError,
)

getcontext().prec = 28

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
COEFFICIENT_TOLERANCE = Decimal("0.000000001")
BOTTLENECK_TOLERANCE = Decimal("0.000000001")


class FormulaStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class PGORSnapshotStatus(StrEnum):
    DRAFT_PREVIEW = "DRAFT_PREVIEW"
    OFFICIAL = "OFFICIAL"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class EBand(StrEnum):
    SEVERE_CRISIS = "SEVERE_CRISIS"
    VULNERABLE = "VULNERABLE"
    SUPPORTED_EMPOWERMENT = "SUPPORTED_EMPOWERMENT"
    ECONOMIC_SOCIAL_INDEPENDENCE = "ECONOMIC_SOCIAL_INDEPENDENCE"


class PBand(StrEnum):
    VERY_HIGH_RISK = "VERY_HIGH_RISK"
    MEDIUM = "MEDIUM"
    DESIRABLE = "DESIRABLE"


class RBand(StrEnum):
    FRAGILE = "FRAGILE"
    ACCEPTABLE = "ACCEPTABLE"
    STABLE = "STABLE"


@dataclass(frozen=True, slots=True)
class FormulaVersion:
    id: UUID
    code: str
    version: str
    status: FormulaStatus
    alpha: Decimal
    beta: Decimal
    gamma: Decimal
    approved_at: datetime | None
    effective_from: datetime | None
    production_eligible: bool

    def validate_coefficients(self) -> None:
        for coefficient in (self.alpha, self.beta, self.gamma):
            if coefficient < ZERO or coefficient > ONE:
                raise InvalidFormulaVersionError(
                    "PGOR coefficients must be within 0..1."
                )

        total = self.alpha + self.beta + self.gamma
        if abs(total - ONE) > COEFFICIENT_TOLERANCE:
            raise InvalidFormulaVersionError(
                "PGOR coefficients alpha + beta + gamma must equal 1."
            )


@dataclass(frozen=True, slots=True)
class AcceptedIndicatorInput:
    observation_id: UUID
    observation_version: int
    indicator_definition_id: UUID
    dimension_definition_id: UUID
    dimension_code: str
    variable_code: PGORVariableCode
    raw_score_0_100: Decimal


@dataclass(frozen=True, slots=True)
class NormalizedIndicatorInput:
    observation_id: UUID
    observation_version: int
    indicator_definition_id: UUID
    dimension_definition_id: UUID
    dimension_code: str
    variable_code: PGORVariableCode
    raw_score_0_100: Decimal
    normalized_score: Decimal


@dataclass(frozen=True, slots=True)
class PGORCalculationResult:
    p: Decimal
    g: Decimal
    o: Decimal
    r: Decimal
    e: Decimal
    dimension_scores: dict[str, Decimal]
    normalized_inputs: tuple[NormalizedIndicatorInput, ...]
    bottleneck_variables: tuple[PGORVariableCode, ...]
    e_band: EBand
    p_band: PBand
    r_band: RBand
    input_fingerprint: str


def normalize(raw_score_0_100: Decimal) -> Decimal:
    if raw_score_0_100 < ZERO or raw_score_0_100 > HUNDRED:
        raise InvalidPGORInputError("Indicator raw score must be within 0..100.")
    return raw_score_0_100 / HUNDRED


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        raise InvalidPGORInputError("Cannot aggregate an empty PGOR group.")
    return sum(values, ZERO) / Decimal(len(values))


def _e_band(value: Decimal) -> EBand:
    if value < Decimal("0.2"):
        return EBand.SEVERE_CRISIS
    if value < Decimal("0.4"):
        return EBand.VULNERABLE
    if value < Decimal("0.7"):
        return EBand.SUPPORTED_EMPOWERMENT
    return EBand.ECONOMIC_SOCIAL_INDEPENDENCE


def _p_band(value: Decimal) -> PBand:
    if value < Decimal("0.3"):
        return PBand.VERY_HIGH_RISK
    if value <= Decimal("0.6"):
        return PBand.MEDIUM
    return PBand.DESIRABLE


def _r_band(value: Decimal) -> RBand:
    if value < Decimal("0.4"):
        return RBand.FRAGILE
    if value <= Decimal("0.7"):
        return RBand.ACCEPTABLE
    return RBand.STABLE


def _fingerprint(
    *,
    inputs: tuple[NormalizedIndicatorInput, ...],
    definition_version_id: UUID,
    formula_version_id: UUID,
    engine_version: str,
) -> str:
    canonical = {
        "definition_version_id": str(definition_version_id),
        "formula_version_id": str(formula_version_id),
        "engine_version": engine_version,
        "inputs": [
            {
                "indicator_definition_id": str(item.indicator_definition_id),
                "observation_id": str(item.observation_id),
                "observation_version": item.observation_version,
                "raw_score_0_100": str(item.raw_score_0_100),
                "normalized_score": str(item.normalized_score),
                "dimension_definition_id": str(item.dimension_definition_id),
                "variable_code": item.variable_code.value,
            }
            for item in sorted(
                inputs,
                key=lambda current: (
                    str(current.indicator_definition_id),
                    str(current.observation_id),
                ),
            )
        ],
    }
    serialized = json.dumps(
        canonical,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def calculate_pgor(
    *,
    accepted_inputs: tuple[AcceptedIndicatorInput, ...],
    definition_version_id: UUID,
    formula: FormulaVersion,
    engine_version: str,
) -> PGORCalculationResult:
    if not accepted_inputs:
        raise InvalidPGORInputError("PGOR calculation requires accepted indicators.")

    formula.validate_coefficients()

    normalized = tuple(
        NormalizedIndicatorInput(
            observation_id=item.observation_id,
            observation_version=item.observation_version,
            indicator_definition_id=item.indicator_definition_id,
            dimension_definition_id=item.dimension_definition_id,
            dimension_code=item.dimension_code,
            variable_code=item.variable_code,
            raw_score_0_100=item.raw_score_0_100,
            normalized_score=normalize(item.raw_score_0_100),
        )
        for item in accepted_inputs
    )

    dimension_values: dict[UUID, list[Decimal]] = {}
    dimension_codes: dict[UUID, str] = {}
    dimension_variables: dict[UUID, PGORVariableCode] = {}

    for item in normalized:
        dimension_values.setdefault(item.dimension_definition_id, []).append(
            item.normalized_score
        )
        dimension_codes[item.dimension_definition_id] = item.dimension_code
        dimension_variables[item.dimension_definition_id] = item.variable_code

    dimension_scores_by_id = {
        dimension_id: _mean(values)
        for dimension_id, values in dimension_values.items()
    }
    dimension_scores = {
        dimension_codes[dimension_id]: score
        for dimension_id, score in dimension_scores_by_id.items()
    }

    variable_dimensions: dict[PGORVariableCode, list[Decimal]] = {
        code: [] for code in PGORVariableCode
    }
    for dimension_id, score in dimension_scores_by_id.items():
        variable_dimensions[dimension_variables[dimension_id]].append(score)

    missing_variables = [
        code.value for code, values in variable_dimensions.items() if not values
    ]
    if missing_variables:
        raise InvalidPGORInputError(
            "PGOR calculation is missing dimensions for variables: "
            + ",".join(missing_variables)
        )

    p = _mean(variable_dimensions[PGORVariableCode.P])
    g = _mean(variable_dimensions[PGORVariableCode.G])
    o = _mean(variable_dimensions[PGORVariableCode.O])
    r = _mean(variable_dimensions[PGORVariableCode.R])

    growth = (
        formula.alpha * (p**3)
        + formula.beta * (g**2)
        + formula.gamma * o
    )
    resilience_multiplier = Decimal("0.5") + Decimal("0.5") * r
    e = growth * resilience_multiplier

    values = {
        PGORVariableCode.P: p,
        PGORVariableCode.G: g,
        PGORVariableCode.O: o,
        PGORVariableCode.R: r,
    }
    minimum = min(values.values())
    bottlenecks = tuple(
        code
        for code, value in values.items()
        if abs(value - minimum) <= BOTTLENECK_TOLERANCE
    )

    return PGORCalculationResult(
        p=p,
        g=g,
        o=o,
        r=r,
        e=e,
        dimension_scores=dimension_scores,
        normalized_inputs=normalized,
        bottleneck_variables=bottlenecks,
        e_band=_e_band(e),
        p_band=_p_band(p),
        r_band=_r_band(r),
        input_fingerprint=_fingerprint(
            inputs=normalized,
            definition_version_id=definition_version_id,
            formula_version_id=formula.id,
            engine_version=engine_version,
        ),
    )
