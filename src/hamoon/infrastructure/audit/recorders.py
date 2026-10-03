from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.infrastructure.audit.models import AuditEntryModel
from hamoon.shared.contracts.records import AuditRecord


class SqlAlchemyAuditRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, audit: AuditRecord) -> None:
        self._session.add(
            AuditEntryModel(
                id=audit.id,
                actor_id=audit.actor_id,
                action=audit.action,
                resource_type=audit.resource_type,
                resource_id=audit.resource_id,
                request_id=audit.request_id,
                correlation_id=audit.correlation_id,
                purpose=audit.purpose,
                metadata_json=audit.metadata,
                created_at=audit.created_at,
            )
        )
