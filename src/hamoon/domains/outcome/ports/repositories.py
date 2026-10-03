from typing import Protocol
from uuid import UUID

from hamoon.domains.outcome.domain.entities import (
    HamoonOutcome,
    OutcomeInterpretationProposal,
)


class OutcomeRepository(Protocol):
    async def add(self, outcome: HamoonOutcome) -> None: ...

    async def get(self, outcome_id: UUID) -> HamoonOutcome | None: ...

    async def update(
        self,
        outcome: HamoonOutcome,
        *,
        expected_version: int,
    ) -> None: ...



class OutcomeInterpretationProposalRepository(Protocol):
    async def add(self, proposal: OutcomeInterpretationProposal) -> None: ...

    async def get(self, proposal_id: UUID) -> OutcomeInterpretationProposal | None: ...

    async def get_by_outcome(
        self,
        outcome_id: UUID,
    ) -> OutcomeInterpretationProposal | None: ...
