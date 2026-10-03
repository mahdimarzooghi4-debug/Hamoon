from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.prescription.domain.entities import Prescription
from hamoon.domains.prescription.infrastructure.models import PrescriptionModel


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
            )
        )

    async def get(self, prescription_id: UUID) -> Prescription | None:
        model = await self._session.get(PrescriptionModel, prescription_id)
        return None if model is None else _prescription(model)
