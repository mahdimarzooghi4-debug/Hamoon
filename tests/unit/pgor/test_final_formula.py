from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from hamoon.domains.pgor.domain.engine import FormulaStatus, FormulaVersion


def test_final_pgor_v1_coefficients_are_valid() -> None:
    formula = FormulaVersion(
        id=UUID("00000000-0000-0000-0000-000000000501"),
        code="HAMOON_PGOR_V1_FINAL",
        version="1.0.0",
        status=FormulaStatus.ACTIVE,
        alpha=Decimal("0.40"),
        beta=Decimal("0.35"),
        gamma=Decimal("0.25"),
        approved_at=datetime(2026, 10, 3, tzinfo=UTC),
        effective_from=datetime(2026, 10, 3, tzinfo=UTC),
        production_eligible=True,
    )

    formula.validate_coefficients()

    assert formula.alpha + formula.beta + formula.gamma == Decimal("1.00")
    assert formula.production_eligible is True
