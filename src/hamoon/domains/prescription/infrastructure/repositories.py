from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.prescription.domain.entities import (
    Prescription,
    PrescriptionItem,
    PrescriptionItemStatus,
)
from hamoon.domains.prescription.infrastructure.models import (
    PrescriptionItemModel,
    PrescriptionModel,
)


def _prescription(model: PrescriptionModel) -> Prescription:
    return Prescription(
        id=model.id,
        household_id=model.household_id,
        diagnosis_id=model.diagnosis_id,
        ai_decision_id=model.ai_decision_id,
        pgor_snapshot_id=model.pgor_snapshot_id,
        status=model.status,
        version=model.version,
        accepted_payload=model.accepted_payload,
        created_at=model.created_at,
        created_by=model.created_by,
        latest_human_decision_id=model.latest_human_decision_id,
        accepted_at=model.accepted_at,
        accepted_by=model.accepted_by,
    )


def _item(model: PrescriptionItemModel) -> PrescriptionItem:
    return PrescriptionItem(
        id=model.id,
        prescription_id=model.prescription_id,
        source_code=model.source_code,
        intervention_type=model.intervention_type,
        target_pgor_variable=model.target_pgor_variable,
        priority=model.priority,
        current_value=model.current_value,
        target_value=model.target_value,
        success_criteria=tuple(model.success_criteria),
        review_after_days=model.review_after_days,
        review_rationale=model.review_rationale,
        rationale=model.rationale,
        title=model.title,
        status=model.status,
        machine_proposed=model.machine_proposed,
    )


class SqlAlchemyPrescriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, prescription: Prescription) -> None:
        self._session.add(
            PrescriptionModel(
                id=prescription.id,
                household_id=prescription.household_id,
                diagnosis_id=prescription.diagnosis_id,
                ai_decision_id=prescription.ai_decision_id,
                pgor_snapshot_id=prescription.pgor_snapshot_id,
                status=prescription.status,
                version=prescription.version,
                accepted_payload=prescription.accepted_payload,
                created_at=prescription.created_at,
                created_by=prescription.created_by,
                latest_human_decision_id=prescription.latest_human_decision_id,
                accepted_at=prescription.accepted_at,
                accepted_by=prescription.accepted_by,
            )
        )

    async def get(self, prescription_id: UUID) -> Prescription | None:
        model = await self._session.get(PrescriptionModel, prescription_id)
        return None if model is None else _prescription(model)

    async def update(
        self,
        prescription: Prescription,
        *,
        expected_version: int,
    ) -> None:
        result = await self._session.execute(
            select(PrescriptionModel)
            .where(PrescriptionModel.id == prescription.id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("PRESCRIPTION_NOT_FOUND")
        if model.version != expected_version:
            raise ValueError("PRESCRIPTION_VERSION_CONFLICT")

        model.status = prescription.status
        model.version = prescription.version
        model.accepted_payload = prescription.accepted_payload
        model.latest_human_decision_id = prescription.latest_human_decision_id
        model.accepted_at = prescription.accepted_at
        model.accepted_by = prescription.accepted_by

    async def add_items(self, items: tuple[PrescriptionItem, ...]) -> None:
        for item in items:
            self._session.add(
                PrescriptionItemModel(
                    id=item.id,
                    prescription_id=item.prescription_id,
                    source_code=item.source_code,
                    intervention_type=item.intervention_type,
                    target_pgor_variable=item.target_pgor_variable,
                    priority=item.priority,
                    current_value=item.current_value,
                    target_value=item.target_value,
                    success_criteria=list(item.success_criteria),
                    review_after_days=item.review_after_days,
                    review_rationale=item.review_rationale,
                    rationale=item.rationale,
                    title=item.title,
                    status=item.status,
                    machine_proposed=item.machine_proposed,
                )
            )

    async def get_item(
        self,
        *,
        prescription_id: UUID,
        item_id: UUID,
    ) -> PrescriptionItem | None:
        result = await self._session.execute(
            select(PrescriptionItemModel).where(
                PrescriptionItemModel.id == item_id,
                PrescriptionItemModel.prescription_id == prescription_id,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _item(model)

    async def list_items(self, prescription_id: UUID) -> list[PrescriptionItem]:
        result = await self._session.execute(
            select(PrescriptionItemModel)
            .where(PrescriptionItemModel.prescription_id == prescription_id)
            .order_by(PrescriptionItemModel.priority)
        )
        return [_item(model) for model in result.scalars().all()]

    async def mark_item_activated(self, item_id: UUID) -> None:
        result = await self._session.execute(
            select(PrescriptionItemModel)
            .where(PrescriptionItemModel.id == item_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("PRESCRIPTION_ITEM_NOT_FOUND")
        if model.status is not PrescriptionItemStatus.ACCEPTED:
            raise ValueError("PRESCRIPTION_ITEM_NOT_ACCEPTED")
        model.status = PrescriptionItemStatus.ACTIVATED
