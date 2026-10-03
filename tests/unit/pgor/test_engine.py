from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import (
    AcceptedIndicatorInput,
    EBand,
    FormulaStatus,
    FormulaVersion,
    PBand,
    RBand,
    calculate_pgor,
    normalize,
)
from hamoon.domains.pgor.domain.errors import (
    InvalidFormulaVersionError,
    InvalidPGORInputError,
)

DEFINITION_ID = UUID("10000000-0000-0000-0000-000000000001")
FORMULA_ID = UUID("10000000-0000-0000-0000-000000000002")


def fixture_formula() -> FormulaVersion:
    return FormulaVersion(
        id=FORMULA_ID,
        code="NON_PRODUCTION_TEST_ONLY",
        version="test-1",
        status=FormulaStatus.DRAFT,
        alpha=Decimal("0.3333333333333333333333333333"),
        beta=Decimal("0.3333333333333333333333333333"),
        gamma=Decimal("0.3333333333333333333333333334"),
        approved_at=None,
        effective_from=None,
        production_eligible=False,
    )


def item(
    *,
    seed: int,
    variable: PGORVariableCode,
    dimension: str,
    score: str,
) -> AcceptedIndicatorInput:
    return AcceptedIndicatorInput(
        observation_id=UUID(f"20000000-0000-0000-0000-{seed:012d}"),
        observation_version=1,
        indicator_definition_id=UUID(f"30000000-0000-0000-0000-{seed:012d}"),
        dimension_definition_id=UUID(f"40000000-0000-0000-0000-{seed:012d}"),
        dimension_code=dimension,
        variable_code=variable,
        raw_score_0_100=Decimal(score),
    )


def test_normalization_source_vectors() -> None:
    assert normalize(Decimal("0")) == Decimal("0")
    assert normalize(Decimal("50")) == Decimal("0.5")
    assert normalize(Decimal("100")) == Decimal("1")


def test_formula_requires_coefficients_sum_to_one() -> None:
    invalid = FormulaVersion(
        id=FORMULA_ID,
        code="bad",
        version="1",
        status=FormulaStatus.DRAFT,
        alpha=Decimal("0.4"),
        beta=Decimal("0.4"),
        gamma=Decimal("0.4"),
        approved_at=None,
        effective_from=None,
        production_eligible=False,
    )

    with pytest.raises(InvalidFormulaVersionError):
        invalid.validate_coefficients()


def test_calculation_matches_source_formula() -> None:
    inputs = (
        item(seed=1, variable=PGORVariableCode.P, dimension="p1", score="50"),
        item(seed=2, variable=PGORVariableCode.G, dimension="g1", score="50"),
        item(seed=3, variable=PGORVariableCode.O, dimension="o1", score="50"),
        item(seed=4, variable=PGORVariableCode.R, dimension="r1", score="50"),
    )

    result = calculate_pgor(
        accepted_inputs=inputs,
        definition_version_id=DEFINITION_ID,
        formula=fixture_formula(),
        scoring_version="raw-0-100-v1",
        engine_version="1.0.0",
    )

    assert result.p == Decimal("0.5")
    assert result.g == Decimal("0.5")
    assert result.o == Decimal("0.5")
    assert result.r == Decimal("0.5")
    assert abs(result.e - Decimal("0.21875")) < Decimal("0.0000000001")
    assert result.e_band is EBand.VULNERABLE
    assert result.p_band is PBand.MEDIUM
    assert result.r_band is RBand.ACCEPTABLE


def test_missing_variable_is_rejected() -> None:
    inputs = (
        item(seed=1, variable=PGORVariableCode.P, dimension="p1", score="50"),
        item(seed=2, variable=PGORVariableCode.G, dimension="g1", score="50"),
        item(seed=3, variable=PGORVariableCode.O, dimension="o1", score="50"),
    )

    with pytest.raises(InvalidPGORInputError):
        calculate_pgor(
            accepted_inputs=inputs,
            definition_version_id=DEFINITION_ID,
            formula=fixture_formula(),
            scoring_version="raw-0-100-v1",
            engine_version="1.0.0",
        )


def test_fingerprint_is_deterministic() -> None:
    inputs = (
        item(seed=1, variable=PGORVariableCode.P, dimension="p1", score="80"),
        item(seed=2, variable=PGORVariableCode.G, dimension="g1", score="60"),
        item(seed=3, variable=PGORVariableCode.O, dimension="o1", score="40"),
        item(seed=4, variable=PGORVariableCode.R, dimension="r1", score="50"),
    )

    first = calculate_pgor(
        accepted_inputs=inputs,
        definition_version_id=DEFINITION_ID,
        formula=fixture_formula(),
        scoring_version="raw-0-100-v1",
        engine_version="1.0.0",
    )
    second = calculate_pgor(
        accepted_inputs=tuple(reversed(inputs)),
        definition_version_id=DEFINITION_ID,
        formula=fixture_formula(),
        scoring_version="raw-0-100-v1",
        engine_version="1.0.0",
    )

    assert first.input_fingerprint == second.input_fingerprint
    assert abs(first.e - Decimal("0.318")) < Decimal("0.0000000001")
