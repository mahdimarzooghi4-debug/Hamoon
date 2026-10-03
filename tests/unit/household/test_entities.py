from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from hamoon.domains.household.domain.entities import (
    CaseAssignment,
    CaseAssignmentType,
    Household,
    HouseholdStatus,
)


def test_draft_household_can_activate() -> None:
    household = Household(
        id=uuid4(),
        case_code="H-TEST-001",
        lifecycle_status=HouseholdStatus.DRAFT,
        created_at=datetime.now(UTC),
        created_by=uuid4(),
    )

    activated = household.activate()

    assert activated.lifecycle_status is HouseholdStatus.ACTIVE
    assert activated.version == 2
    assert household.lifecycle_status is HouseholdStatus.DRAFT


def test_non_draft_household_cannot_activate() -> None:
    household = Household(
        id=uuid4(),
        case_code="H-TEST-002",
        lifecycle_status=HouseholdStatus.ACTIVE,
        created_at=datetime.now(UTC),
        created_by=uuid4(),
    )

    with pytest.raises(ValueError, match="Only a DRAFT"):
        household.activate()


def test_case_assignment_active_window() -> None:
    now = datetime.now(UTC)
    assignment = CaseAssignment(
        id=uuid4(),
        household_id=uuid4(),
        actor_id=uuid4(),
        assignment_type=CaseAssignmentType.DELEGATED,
        valid_from=now - timedelta(hours=1),
        valid_to=now + timedelta(hours=1),
        assigned_by=uuid4(),
        created_at=now - timedelta(hours=1),
    )

    assert assignment.is_active_at(now)
    assert not assignment.is_active_at(now + timedelta(hours=2))
