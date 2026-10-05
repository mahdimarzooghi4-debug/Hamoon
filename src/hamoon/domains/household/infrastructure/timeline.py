from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.assessment.infrastructure.models import AssessmentModel
from hamoon.domains.family_data.infrastructure.models import HouseholdFactModel
from hamoon.domains.intelligence.infrastructure.models import DiagnosisModel
from hamoon.domains.outcome.infrastructure.models import HamoonOutcomeModel
from hamoon.domains.pgor.infrastructure.models import PGORSnapshotModel
from hamoon.domains.prescription.infrastructure.models import PrescriptionModel
from hamoon.domains.provider_result.infrastructure.models import ProviderResultModel
from hamoon.domains.referral.infrastructure.models import ReferralModel


@dataclass(frozen=True, slots=True)
class HouseholdTimelineItem:
    kind: str
    entity_id: UUID
    occurred_at: datetime
    status: str
    detail: str | None = None


def _text(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


class SqlAlchemyHouseholdTimelineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_household(
        self,
        *,
        household_id: UUID,
        limit: int,
    ) -> list[HouseholdTimelineItem]:
        items: list[HouseholdTimelineItem] = []

        facts = await self._session.execute(
            select(HouseholdFactModel).where(
                HouseholdFactModel.household_id == household_id
            )
        )
        items.extend(
            HouseholdTimelineItem(
                kind="FACT",
                entity_id=model.id,
                occurred_at=model.recorded_at,
                status="RECORDED",
                detail=model.fact_type,
            )
            for model in facts.scalars().all()
        )

        assessments = await self._session.execute(
            select(AssessmentModel).where(
                AssessmentModel.household_id == household_id
            )
        )
        items.extend(
            HouseholdTimelineItem(
                kind="ASSESSMENT",
                entity_id=model.id,
                occurred_at=model.started_at,
                status=_text(model.status),
                detail=_text(model.assessment_type),
            )
            for model in assessments.scalars().all()
        )

        pgor_snapshots = await self._session.execute(
            select(PGORSnapshotModel).where(
                PGORSnapshotModel.household_id == household_id
            )
        )
        items.extend(
            HouseholdTimelineItem(
                kind="PGOR",
                entity_id=model.id,
                occurred_at=model.calculated_at,
                status=_text(model.status),
                detail=f"E_BAND:{_text(model.e_band)}",
            )
            for model in pgor_snapshots.scalars().all()
        )

        diagnoses = await self._session.execute(
            select(DiagnosisModel).where(
                DiagnosisModel.household_id == household_id
            )
        )
        items.extend(
            HouseholdTimelineItem(
                kind="DIAGNOSIS",
                entity_id=model.id,
                occurred_at=model.created_at,
                status=_text(model.status),
            )
            for model in diagnoses.scalars().all()
        )

        prescriptions = await self._session.execute(
            select(PrescriptionModel).where(
                PrescriptionModel.household_id == household_id
            )
        )
        items.extend(
            HouseholdTimelineItem(
                kind="PRESCRIPTION",
                entity_id=model.id,
                occurred_at=model.created_at,
                status=_text(model.status),
            )
            for model in prescriptions.scalars().all()
        )

        referrals = await self._session.execute(
            select(ReferralModel).where(
                ReferralModel.household_id == household_id
            )
        )
        items.extend(
            HouseholdTimelineItem(
                kind="REFERRAL",
                entity_id=model.id,
                occurred_at=model.created_at,
                status=_text(model.status),
            )
            for model in referrals.scalars().all()
        )

        provider_results = await self._session.execute(
            select(ProviderResultModel)
            .join(
                ReferralModel,
                ReferralModel.id == ProviderResultModel.referral_id,
            )
            .where(ReferralModel.household_id == household_id)
        )
        items.extend(
            HouseholdTimelineItem(
                kind="PROVIDER_RESULT",
                entity_id=model.id,
                occurred_at=model.submitted_at,
                status=model.result_status,
                detail=model.result_type,
            )
            for model in provider_results.scalars().all()
        )

        outcomes = await self._session.execute(
            select(HamoonOutcomeModel).where(
                HamoonOutcomeModel.household_id == household_id
            )
        )
        items.extend(
            HouseholdTimelineItem(
                kind="OUTCOME",
                entity_id=model.id,
                occurred_at=model.assessed_at,
                status=_text(model.status),
                detail=(
                    None
                    if model.classification is None
                    else _text(model.classification)
                ),
            )
            for model in outcomes.scalars().all()
        )

        items.sort(
            key=lambda item: (
                item.occurred_at,
                item.kind,
                str(item.entity_id),
            ),
            reverse=True,
        )
        return items[:limit]
