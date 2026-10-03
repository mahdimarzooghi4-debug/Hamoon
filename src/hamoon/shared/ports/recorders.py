from typing import Protocol

from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord


class DomainEventRecorder(Protocol):
    async def record(self, event: DomainEventRecord) -> None: ...


class AuditRecorder(Protocol):
    async def record(self, audit: AuditRecord) -> None: ...
