from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from hamoon.domains.intelligence.application.commands import (
    BuildDiagnosisFeaturePackageCommand,
)
from hamoon.domains.intelligence.application.handlers import (
    BuildDiagnosisFeaturePackageHandler,
)
from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionBundle,
    PGORDefinitionStatus,
    PGORDefinitionVersion,
    PGORDimensionDefinition,
    PGORIndicatorDefinition,
    PGORVariableCode,
    PGORVariableDefinition,
    RequirementPolicyStatus,
)
from hamoon.domains.pgor.domain.engine import (
    EBand,
    PBand,
    PGORSnapshotStatus,
    RBand,
)
from hamoon.domains.pgor.domain.snapshots import PGORSnapshot, PGORSnapshotInput
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord

ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
HOUSEHOLD_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
DEFINITION_ID = UUID("44444444-4444-4444-4444-444444444444")
SNAPSHOT_ID = UUID("55555555-5555-5555-5555-555555555555")
VARIABLE_ID = UUID("66666666-6666-6666-6666-666666666666")
DIMENSION_ID = UUID("77777777-7777-7777-7777-777777777777")
INDICATOR_ID = UUID("88888888-8888-8888-8888-888888888888")
OBSERVATION_ID = UUID("99999999-9999-9999-9999-999999999999")
FORMULA_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class SnapshotRepo:
    async def create(self, **kwargs):
        raise AssertionError("not used")

    async def get(self, snapshot_id: UUID):
        if snapshot_id != SNAPSHOT_ID:
            return None
        return PGORSnapshot(
            id=SNAPSHOT_ID,
            household_id=HOUSEHOLD_ID,
            assessment_id=ASSESSMENT_ID,
            definition_version_id=DEFINITION_ID,
            formula_version_id=FORMULA_ID,
            engine_version="1.0.0",
            scoring_version="raw-0-100-v1",
            status=PGORSnapshotStatus.OFFICIAL,
            p=Decimal("0.4"),
            g=Decimal("0.5"),
            o=Decimal("0.6"),
            r=Decimal("0.7"),
            e=Decimal("0.3"),
            bottleneck_variables=(PGORVariableCode.P,),
            e_band=EBand.VULNERABLE,
            p_band=PBand.MEDIUM,
            r_band=RBand.ACCEPTABLE,
            completeness_ratio=Decimal("1"),
            data_quality_flags=(),
            input_fingerprint="a" * 64,
            calculated_at=datetime.now(UTC),
            calculated_by=ACTOR_ID,
        )

    async def list_inputs(self, snapshot_id: UUID):
        return [
            PGORSnapshotInput(
                snapshot_id=SNAPSHOT_ID,
                observation_id=OBSERVATION_ID,
                observation_version=1,
                indicator_definition_id=INDICATOR_ID,
                dimension_definition_id=DIMENSION_ID,
                variable_code=PGORVariableCode.P,
                raw_score_0_100=Decimal("40"),
                normalized_score=Decimal("0.4"),
            )
        ]


class DefinitionRepo:
    async def get_active_bundle(self):
        return None

    async def get_bundle(self, definition_version_id: UUID):
        if definition_version_id != DEFINITION_ID:
            return None
        return PGORDefinitionBundle(
            version=PGORDefinitionVersion(
                id=DEFINITION_ID,
                code="pgor-v1",
                version="1",
                status=PGORDefinitionStatus.ACTIVE,
                requirement_policy_status=RequirementPolicyStatus.RESOLVED,
                source_reference="source",
            ),
            variables=(
                PGORVariableDefinition(
                    id=VARIABLE_ID,
                    definition_version_id=DEFINITION_ID,
                    code=PGORVariableCode.P,
                    name_fa="مشارکت",
                    sort_order=1,
                ),
            ),
            dimensions=(
                PGORDimensionDefinition(
                    id=DIMENSION_ID,
                    variable_definition_id=VARIABLE_ID,
                    code="motivation",
                    name_fa="انگیزه",
                    sort_order=1,
                ),
            ),
            indicators=(
                PGORIndicatorDefinition(
                    id=INDICATOR_ID,
                    dimension_definition_id=DIMENSION_ID,
                    code="willingness_to_change",
                    name_fa="تمایل به تغییر",
                    score_min=0,
                    score_max=100,
                    required_for_complete_assessment=True,
                    direct_dimension_measure=False,
                    sort_order=1,
                ),
            ),
        )

    async def get_version(self, definition_version_id: UUID):
        bundle = await self.get_bundle(definition_version_id)
        return None if bundle is None else bundle.version

    async def list_indicators(self, definition_version_id: UUID):
        bundle = await self.get_bundle(definition_version_id)
        return [] if bundle is None else list(bundle.indicators)

    async def get_indicator(self, *, definition_version_id: UUID, indicator_id: UUID):
        for indicator in await self.list_indicators(definition_version_id):
            if indicator.id == indicator_id:
                return indicator
        return None


class PackageRepo:
    def __init__(self) -> None:
        self.item: FeaturePackage | None = None

    async def add(self, package: FeaturePackage) -> None:
        self.item = package

    async def get(self, package_id: UUID):
        if self.item is not None and self.item.id == package_id:
            return self.item
        return None

    async def get_by_snapshot(self, *, snapshot_id: UUID, schema_version: str):
        if (
            self.item is not None
            and self.item.pgor_snapshot_id == snapshot_id
            and self.item.schema_version == schema_version
        ):
            return self.item
        return None


class EventRecorder:
    def __init__(self) -> None:
        self.items: list[DomainEventRecord] = []

    async def record(self, event: DomainEventRecord) -> None:
        self.items.append(event)


class AuditRecorder:
    def __init__(self) -> None:
        self.items: list[AuditRecord] = []

    async def record(self, audit: AuditRecord) -> None:
        self.items.append(audit)


@pytest.mark.asyncio
async def test_feature_package_is_grounded_in_official_pgor_snapshot() -> None:
    packages = PackageRepo()
    events = EventRecorder()
    audits = AuditRecorder()

    package = await BuildDiagnosisFeaturePackageHandler(
        snapshots=SnapshotRepo(),
        definitions=DefinitionRepo(),
        packages=packages,
        events=events,
        audits=audits,
    ).handle(
        BuildDiagnosisFeaturePackageCommand(
            snapshot_id=SNAPSHOT_ID,
            actor_id=ACTOR_ID,
            request_id="req-1",
            correlation_id="corr-1",
        )
    )

    payload = package.provider_payload()

    assert payload["pgor.P"] == "0.4"
    assert payload["pgor.E"] == "0.3"
    assert payload[
        "indicator.P.motivation.willingness_to_change.normalized"
    ] == "0.4"
    assert payload["trace.engine_version"] == "1.0.0"
    assert payload["trace.scoring_version"] == "raw-0-100-v1"
    assert "household.name" not in payload
    assert events.items[0].event_type == "FeaturePackageBuilt"
