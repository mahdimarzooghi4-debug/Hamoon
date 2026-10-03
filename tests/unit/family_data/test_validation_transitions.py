from datetime import UTC, datetime
from uuid import uuid4

import pytest

from hamoon.domains.family_data.domain.entities import (
    FactValidationState,
    FactValidationStatus,
)
from hamoon.domains.family_data.domain.errors import InvalidValidationTransitionError


def test_pending_can_be_validated() -> None:
    state = FactValidationState(
        fact_id=uuid4(),
        status=FactValidationStatus.PENDING_VALIDATION,
        version=1,
        changed_at=datetime.now(UTC),
        changed_by=uuid4(),
        reason_code="FACT_RECORDED",
    )

    validated = state.transition(
        to_status=FactValidationStatus.VALIDATED,
        changed_at=datetime.now(UTC),
        changed_by=uuid4(),
        reason_code="SOURCE_REVIEWED",
        reason_text=None,
    )

    assert validated.status is FactValidationStatus.VALIDATED
    assert validated.version == 2


def test_rejected_is_terminal() -> None:
    state = FactValidationState(
        fact_id=uuid4(),
        status=FactValidationStatus.REJECTED,
        version=2,
        changed_at=datetime.now(UTC),
        changed_by=uuid4(),
        reason_code="INVALID_SOURCE",
    )

    with pytest.raises(InvalidValidationTransitionError):
        state.transition(
            to_status=FactValidationStatus.VALIDATED,
            changed_at=datetime.now(UTC),
            changed_by=uuid4(),
            reason_code="RETRY",
            reason_text=None,
        )
