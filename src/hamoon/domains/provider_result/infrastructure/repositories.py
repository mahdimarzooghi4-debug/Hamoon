from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.provider_result.domain.entities import ProviderResult
from hamoon.domains.provider_result.infrastructure.models import (
    ProviderResultEvidenceModel,
    ProviderResultModel,
)


async def _hydrate(
    session: AsyncSession,
    model: ProviderResultModel,
) -> ProviderResult:
    evidence_result = await session.execute(
        select(ProviderResultEvidenceModel.evidence_id)
        .where(ProviderResultEvidenceModel.provider_result_id == model.id)
        .order_by(ProviderResultEvidenceModel.evidence_id)
    )
    return ProviderResult(
        id=model.id,
        referral_id=model.referral_id,
        provider_id=model.provider_id,
        result_status=model.result_status,
        result_type=model.result_type,
        result_summary=model.result_summary,
        result_payload=model.result_payload,
        service_started_at=model.service_started_at,
        service_completed_at=model.service_completed_at,
        submitted_at=model.submitted_at,
        external_result_id=model.external_result_id,
        provider_reference=model.provider_reference,
        request_hash=model.request_hash,
        evidence_ids=tuple(evidence_result.scalars().all()),
    )


class SqlAlchemyProviderResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, result: ProviderResult) -> None:
        self._session.add(
            ProviderResultModel(
                id=result.id,
                referral_id=result.referral_id,
                provider_id=result.provider_id,
                result_status=result.result_status,
                result_type=result.result_type,
                result_summary=result.result_summary,
                result_payload=result.result_payload,
                service_started_at=result.service_started_at,
                service_completed_at=result.service_completed_at,
                submitted_at=result.submitted_at,
                external_result_id=result.external_result_id,
                provider_reference=result.provider_reference,
                request_hash=result.request_hash,
            )
        )
        for evidence_id in result.evidence_ids:
            self._session.add(
                ProviderResultEvidenceModel(
                    id=uuid4(),
                    provider_result_id=result.id,
                    evidence_id=evidence_id,
                )
            )

    async def get(self, result_id: UUID) -> ProviderResult | None:
        model = await self._session.get(ProviderResultModel, result_id)
        return None if model is None else await _hydrate(self._session, model)

    async def get_by_external_result(
        self,
        *,
        provider_id: UUID,
        external_result_id: str,
    ) -> ProviderResult | None:
        result = await self._session.execute(
            select(ProviderResultModel).where(
                ProviderResultModel.provider_id == provider_id,
                ProviderResultModel.external_result_id == external_result_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else await _hydrate(self._session, model)

    async def list_for_referral(self, referral_id: UUID) -> list[ProviderResult]:
        result = await self._session.execute(
            select(ProviderResultModel)
            .where(ProviderResultModel.referral_id == referral_id)
            .order_by(ProviderResultModel.submitted_at)
        )
        return [
            await _hydrate(self._session, model)
            for model in result.scalars().all()
        ]
