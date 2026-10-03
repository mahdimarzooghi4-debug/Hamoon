from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.referral.domain.entities import Referral, ReferralDataItem
from hamoon.domains.referral.infrastructure.models import ReferralDataItemModel, ReferralModel


def _data_item(model: ReferralDataItemModel) -> ReferralDataItem:
    return ReferralDataItem(
        id=model.id,
        referral_id=model.referral_id,
        data_category=model.data_category,
        source_fact_id=model.source_fact_id,
        snapshot_value=model.snapshot_value,
        purpose=model.purpose,
        authorization_basis=model.authorization_basis,
        shared_at=model.shared_at,
    )


class SqlAlchemyReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, referral: Referral) -> None:
        self._session.add(
            ReferralModel(
                id=referral.id,
                household_id=referral.household_id,
                intervention_id=referral.intervention_id,
                provider_match_id=referral.provider_match_id,
                provider_selection_id=referral.provider_selection_id,
                provider_id=referral.provider_id,
                provider_service_id=referral.provider_service_id,
                status=referral.status,
                priority=referral.priority,
                version=referral.version,
                response_due_at=referral.response_due_at,
                sent_at=referral.sent_at,
                accepted_at=referral.accepted_at,
                completed_at=referral.completed_at,
                cancelled_at=referral.cancelled_at,
                external_referral_id=referral.external_referral_id,
                created_by=referral.created_by,
                created_at=referral.created_at,
            )
        )
        for item in referral.data_items:
            self._session.add(
                ReferralDataItemModel(
                    id=item.id,
                    referral_id=referral.id,
                    data_category=item.data_category,
                    source_fact_id=item.source_fact_id,
                    snapshot_value=item.snapshot_value,
                    purpose=item.purpose,
                    authorization_basis=item.authorization_basis,
                    shared_at=item.shared_at,
                )
            )

    async def get(self, referral_id: UUID) -> Referral | None:
        model = await self._session.get(ReferralModel, referral_id)
        if model is None:
            return None
        result = await self._session.execute(
            select(ReferralDataItemModel)
            .where(ReferralDataItemModel.referral_id == referral_id)
            .order_by(ReferralDataItemModel.id)
        )
        return Referral(
            id=model.id,
            household_id=model.household_id,
            intervention_id=model.intervention_id,
            provider_match_id=model.provider_match_id,
            provider_selection_id=model.provider_selection_id,
            provider_id=model.provider_id,
            provider_service_id=model.provider_service_id,
            status=model.status,
            priority=model.priority,
            version=model.version,
            response_due_at=model.response_due_at,
            sent_at=model.sent_at,
            accepted_at=model.accepted_at,
            completed_at=model.completed_at,
            cancelled_at=model.cancelled_at,
            external_referral_id=model.external_referral_id,
            created_by=model.created_by,
            created_at=model.created_at,
            data_items=tuple(_data_item(item) for item in result.scalars().all()),
        )
