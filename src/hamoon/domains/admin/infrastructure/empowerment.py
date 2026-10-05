from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.domains.household.infrastructure.models import HouseholdModel
from hamoon.domains.outcome.domain.entities import OutcomeClassification
from hamoon.domains.outcome.infrastructure.models import HamoonOutcomeModel
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.pgor.domain.engine import EBand, PGORSnapshotStatus
from hamoon.domains.pgor.infrastructure.models import PGORSnapshotModel


@dataclass(frozen=True, slots=True)
class VariableDistribution:
    mean: Decimal | None
    minimum: Decimal | None
    maximum: Decimal | None


@dataclass(frozen=True, slots=True)
class EmpowermentOverview:
    household_count: int
    households_with_official_pgor: int
    p: VariableDistribution
    g: VariableDistribution
    o: VariableDistribution
    r: VariableDistribution
    e: VariableDistribution
    e_band_counts: dict[EBand, int]
    bottleneck_counts: dict[PGORVariableCode, int]
    outcome_counts: dict[OutcomeClassification, int]
    unreviewed_outcomes: int


def _distribution(values: list[Decimal]) -> VariableDistribution:
    if not values:
        return VariableDistribution(mean=None, minimum=None, maximum=None)
    return VariableDistribution(
        mean=sum(values, Decimal("0")) / Decimal(len(values)),
        minimum=min(values),
        maximum=max(values),
    )


class SqlAlchemyEmpowermentOverviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_unit(self, *, unit_id: str) -> EmpowermentOverview:
        household_count = int(
            (
                await self._session.scalar(
                    select(func.count())
                    .select_from(HouseholdModel)
                    .where(HouseholdModel.organizational_unit_id == unit_id)
                )
            )
            or 0
        )

        ranked = (
            select(
                PGORSnapshotModel.household_id.label("household_id"),
                PGORSnapshotModel.p.label("p"),
                PGORSnapshotModel.g.label("g"),
                PGORSnapshotModel.o.label("o"),
                PGORSnapshotModel.r.label("r"),
                PGORSnapshotModel.e.label("e"),
                PGORSnapshotModel.e_band.label("e_band"),
                PGORSnapshotModel.bottleneck_variables.label(
                    "bottleneck_variables"
                ),
                func.row_number()
                .over(
                    partition_by=PGORSnapshotModel.household_id,
                    order_by=(
                        PGORSnapshotModel.calculated_at.desc(),
                        PGORSnapshotModel.id.desc(),
                    ),
                )
                .label("row_number"),
            )
            .join(
                HouseholdModel,
                HouseholdModel.id == PGORSnapshotModel.household_id,
            )
            .where(
                HouseholdModel.organizational_unit_id == unit_id,
                PGORSnapshotModel.status == PGORSnapshotStatus.OFFICIAL,
            )
            .subquery()
        )

        snapshot_rows = (
            await self._session.execute(
                select(ranked).where(ranked.c.row_number == 1)
            )
        ).mappings().all()

        p_values: list[Decimal] = []
        g_values: list[Decimal] = []
        o_values: list[Decimal] = []
        r_values: list[Decimal] = []
        e_values: list[Decimal] = []
        e_band_counts = {band: 0 for band in EBand}
        bottleneck_counts = {code: 0 for code in PGORVariableCode}

        for row in snapshot_rows:
            p_values.append(cast(Decimal, row["p"]))
            g_values.append(cast(Decimal, row["g"]))
            o_values.append(cast(Decimal, row["o"]))
            r_values.append(cast(Decimal, row["r"]))
            e_values.append(cast(Decimal, row["e"]))

            e_band = cast(EBand, row["e_band"])
            e_band_counts[e_band] += 1

            for value in cast(list[str], row["bottleneck_variables"]):
                variable = PGORVariableCode(value)
                bottleneck_counts[variable] += 1

        outcome_rows = (
            await self._session.execute(
                select(
                    HamoonOutcomeModel.classification,
                    func.count(HamoonOutcomeModel.id),
                )
                .join(
                    HouseholdModel,
                    HouseholdModel.id == HamoonOutcomeModel.household_id,
                )
                .where(
                    HouseholdModel.organizational_unit_id == unit_id,
                    HamoonOutcomeModel.classification.is_not(None),
                )
                .group_by(HamoonOutcomeModel.classification)
            )
        ).all()
        outcome_counts = {classification: 0 for classification in OutcomeClassification}
        for classification, count in outcome_rows:
            if classification is not None:
                outcome_counts[cast(OutcomeClassification, classification)] = int(
                    count
                )

        unreviewed_outcomes = int(
            (
                await self._session.scalar(
                    select(func.count())
                    .select_from(HamoonOutcomeModel)
                    .join(
                        HouseholdModel,
                        HouseholdModel.id == HamoonOutcomeModel.household_id,
                    )
                    .where(
                        HouseholdModel.organizational_unit_id == unit_id,
                        HamoonOutcomeModel.classification.is_(None),
                    )
                )
            )
            or 0
        )

        return EmpowermentOverview(
            household_count=household_count,
            households_with_official_pgor=len(snapshot_rows),
            p=_distribution(p_values),
            g=_distribution(g_values),
            o=_distribution(o_values),
            r=_distribution(r_values),
            e=_distribution(e_values),
            e_band_counts=e_band_counts,
            bottleneck_counts=bottleneck_counts,
            outcome_counts=outcome_counts,
            unreviewed_outcomes=unreviewed_outcomes,
        )
