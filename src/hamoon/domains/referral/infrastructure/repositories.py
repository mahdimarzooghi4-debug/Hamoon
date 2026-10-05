from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.referral.domain.entities import (
    IntegrationProcessingStatus,
    ProviderCallbackMessage,
    Referral,
    ReferralDataItem,
    ReferralDispatch,
    ReferralEvent,
)
from hamoon.domains.referral.domain.errors import ReferralVersionConflictError
from hamoon.domains.referral.infrastructure.models import (
    IntegrationMessageModel,
    ReferralDataItemModel,
    ReferralDispatchModel,
    ReferralEventModel,
    ReferralModel,
)


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


def _event(model: ReferralEventModel) -> ReferralEvent:
    return ReferralEvent(
        id=model.id,
        referral_id=model.referral_id,
        referral_version=model.referral_version,
        from_status=model.from_status,
        to_status=model.to_status,
        occurred_at=model.occurred_at,
        recorded_at=model.recorded_at,
        actor_id=model.actor_id,
        source=model.source,
        reason_code=model.reason_code,
        external_event_id=model.external_event_id,
    )


def _dispatch(model: ReferralDispatchModel) -> ReferralDispatch:
    return ReferralDispatch(
        id=model.id,
        referral_id=model.referral_id,
        provider_id=model.provider_id,
        idempotency_key=model.idempotency_key,
        request_hash=model.request_hash,
        payload=model.payload_json,
        status=model.status,
        created_at=model.created_at,
        sent_at=model.sent_at,
    )


def _message(model: IntegrationMessageModel) -> ProviderCallbackMessage:
    return ProviderCallbackMessage(
        id=model.id,
        provider_id=model.provider_id,
        source_system=model.source_system,
        external_event_id=model.external_event_id,
        external_record_id=model.external_record_id,
        message_type=model.message_type,
        payload_hash=model.payload_hash,
        schema_version=model.schema_version,
        received_at=model.received_at,
        processing_status=model.processing_status,
        processed_at=model.processed_at,
        error_code=model.error_code,
        correlation_id=model.correlation_id,
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
                subject_reference=referral.subject_reference,
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

    async def _hydrate(self, model: ReferralModel) -> Referral:
        result = await self._session.execute(
            select(ReferralDataItemModel)
            .where(ReferralDataItemModel.referral_id == model.id)
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
            subject_reference=model.subject_reference,
            created_by=model.created_by,
            created_at=model.created_at,
            data_items=tuple(_data_item(item) for item in result.scalars().all()),
        )

    async def get(self, referral_id: UUID) -> Referral | None:
        model = await self._session.get(ReferralModel, referral_id)
        return None if model is None else await self._hydrate(model)

    async def get_latest_for_intervention(
        self,
        intervention_id: UUID,
    ) -> Referral | None:
        result = await self._session.execute(
            select(ReferralModel)
            .where(ReferralModel.intervention_id == intervention_id)
            .order_by(
                ReferralModel.created_at.desc(),
                ReferralModel.id.desc(),
            )
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else await self._hydrate(model)

    async def get_by_provider_reference(
        self,
        *,
        provider_id: UUID,
        external_referral_id: str,
    ) -> Referral | None:
        result = await self._session.execute(
            select(ReferralModel).where(
                ReferralModel.provider_id == provider_id,
                ReferralModel.external_referral_id == external_referral_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else await self._hydrate(model)

    async def update(
        self,
        referral: Referral,
        *,
        expected_version: int,
    ) -> None:
        result = await self._session.execute(
            select(ReferralModel)
            .where(ReferralModel.id == referral.id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("REFERRAL_NOT_FOUND")
        if model.version != expected_version:
            raise ReferralVersionConflictError("Referral version changed.")

        model.status = referral.status
        model.version = referral.version
        model.response_due_at = referral.response_due_at
        model.sent_at = referral.sent_at
        model.accepted_at = referral.accepted_at
        model.completed_at = referral.completed_at
        model.cancelled_at = referral.cancelled_at
        model.external_referral_id = referral.external_referral_id
        model.subject_reference = referral.subject_reference

    async def add_event(self, event: ReferralEvent) -> None:
        self._session.add(
            ReferralEventModel(
                id=event.id,
                referral_id=event.referral_id,
                referral_version=event.referral_version,
                from_status=event.from_status,
                to_status=event.to_status,
                occurred_at=event.occurred_at,
                recorded_at=event.recorded_at,
                actor_id=event.actor_id,
                source=event.source,
                reason_code=event.reason_code,
                external_event_id=event.external_event_id,
            )
        )

    async def list_events(self, referral_id: UUID) -> list[ReferralEvent]:
        result = await self._session.execute(
            select(ReferralEventModel)
            .where(ReferralEventModel.referral_id == referral_id)
            .order_by(ReferralEventModel.referral_version)
        )
        return [_event(item) for item in result.scalars().all()]

    async def mark_data_items_shared(
        self,
        *,
        referral_id: UUID,
        shared_at: datetime,
        authorization_basis: str,
    ) -> None:
        result = await self._session.execute(
            select(ReferralDataItemModel)
            .where(ReferralDataItemModel.referral_id == referral_id)
            .with_for_update()
        )
        for item in result.scalars().all():
            item.shared_at = shared_at
            item.authorization_basis = authorization_basis


class SqlAlchemyReferralDispatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, dispatch_id: UUID) -> ReferralDispatch | None:
        model = await self._session.get(ReferralDispatchModel, dispatch_id)
        return None if model is None else _dispatch(model)

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ReferralDispatch | None:
        result = await self._session.execute(
            select(ReferralDispatchModel).where(
                ReferralDispatchModel.idempotency_key == idempotency_key
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _dispatch(model)

    async def get_latest_for_referral(
        self,
        referral_id: UUID,
    ) -> ReferralDispatch | None:
        result = await self._session.execute(
            select(ReferralDispatchModel)
            .where(ReferralDispatchModel.referral_id == referral_id)
            .order_by(
                ReferralDispatchModel.created_at.desc(),
                ReferralDispatchModel.id.desc(),
            )
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else _dispatch(model)

    async def list_pending(self, *, limit: int) -> list[ReferralDispatch]:
        result = await self._session.execute(
            select(ReferralDispatchModel)
            .where(ReferralDispatchModel.status == "PENDING")
            .order_by(
                ReferralDispatchModel.created_at,
                ReferralDispatchModel.id,
            )
            .limit(limit)
        )
        return [_dispatch(model) for model in result.scalars().all()]

    async def add(self, dispatch: ReferralDispatch) -> None:
        self._session.add(
            ReferralDispatchModel(
                id=dispatch.id,
                referral_id=dispatch.referral_id,
                provider_id=dispatch.provider_id,
                idempotency_key=dispatch.idempotency_key,
                request_hash=dispatch.request_hash,
                payload_json=dispatch.payload,
                status=dispatch.status,
                created_at=dispatch.created_at,
                sent_at=dispatch.sent_at,
            )
        )

    async def mark_sent(
        self,
        *,
        dispatch_id: UUID,
        sent_at: datetime,
    ) -> None:
        model = await self._session.get(ReferralDispatchModel, dispatch_id)
        if model is None:
            raise LookupError("REFERRAL_DISPATCH_NOT_FOUND")
        if model.status == "SENT":
            return
        model.status = "SENT"
        model.sent_at = sent_at

    async def mark_failed(self, *, dispatch_id: UUID) -> None:
        model = await self._session.get(ReferralDispatchModel, dispatch_id)
        if model is None:
            raise LookupError("REFERRAL_DISPATCH_NOT_FOUND")
        if model.status == "SENT":
            return
        model.status = "FAILED"


class SqlAlchemyProviderCallbackInboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        *,
        provider_id: UUID,
        external_event_id: str,
    ) -> ProviderCallbackMessage | None:
        result = await self._session.execute(
            select(IntegrationMessageModel).where(
                IntegrationMessageModel.provider_id == provider_id,
                IntegrationMessageModel.external_event_id == external_event_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _message(model)

    async def add(self, message: ProviderCallbackMessage) -> None:
        self._session.add(
            IntegrationMessageModel(
                id=message.id,
                provider_id=message.provider_id,
                source_system=message.source_system,
                external_event_id=message.external_event_id,
                external_record_id=message.external_record_id,
                message_type=message.message_type,
                payload_hash=message.payload_hash,
                schema_version=message.schema_version,
                received_at=message.received_at,
                processing_status=message.processing_status,
                processed_at=message.processed_at,
                error_code=message.error_code,
                correlation_id=message.correlation_id,
            )
        )

    async def mark_processed(
        self,
        *,
        message_id: UUID,
        processed_at: datetime,
    ) -> None:
        model = await self._session.get(IntegrationMessageModel, message_id)
        if model is None:
            raise RuntimeError("Integration message disappeared.")
        model.processing_status = IntegrationProcessingStatus.PROCESSED
        model.processed_at = processed_at
        model.error_code = None
