import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.intelligence.application.commands import (
    BuildDiagnosisFeaturePackageCommand,
)
from hamoon.domains.intelligence.domain.entities import (
    FeaturePackage,
    FeaturePackageType,
    FeatureValue,
)
from hamoon.domains.intelligence.domain.errors import FeaturePackageBuildError
from hamoon.domains.intelligence.ports.repositories import FeaturePackageRepository
from hamoon.domains.pgor.domain.engine import PGORSnapshotStatus
from hamoon.domains.pgor.ports.repositories import (
    PGORDefinitionRepository,
    PGORSnapshotRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

DIAGNOSIS_FEATURE_SCHEMA_VERSION = "diagnosis-input-v1"


class BuildDiagnosisFeaturePackageHandler:
    def __init__(
        self,
        *,
        snapshots: PGORSnapshotRepository,
        definitions: PGORDefinitionRepository,
        packages: FeaturePackageRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._snapshots = snapshots
        self._definitions = definitions
        self._packages = packages
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: BuildDiagnosisFeaturePackageCommand,
    ) -> FeaturePackage:
        existing = await self._packages.get_by_snapshot(
            snapshot_id=command.snapshot_id,
            schema_version=DIAGNOSIS_FEATURE_SCHEMA_VERSION,
        )
        if existing is not None:
            return existing

        snapshot = await self._snapshots.get(command.snapshot_id)
        if snapshot is None:
            raise FeaturePackageBuildError("PGOR_SNAPSHOT_NOT_FOUND")
        if snapshot.status is not PGORSnapshotStatus.OFFICIAL:
            raise FeaturePackageBuildError("PGOR_SNAPSHOT_NOT_OFFICIAL")

        bundle = await self._definitions.get_bundle(snapshot.definition_version_id)
        if bundle is None:
            raise FeaturePackageBuildError("PGOR_DEFINITION_NOT_FOUND")

        snapshot_inputs = await self._snapshots.list_inputs(snapshot.id)
        indicators = {item.id: item for item in bundle.indicators}
        dimensions = {item.id: item for item in bundle.dimensions}

        values: list[FeatureValue] = [
            FeatureValue("pgor.P", str(snapshot.p), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.G", str(snapshot.g), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.O", str(snapshot.o), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.R", str(snapshot.r), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue("pgor.E", str(snapshot.e), (f"pgor_snapshot:{snapshot.id}",)),
            FeatureValue(
                "pgor.bottleneck_variables",
                [item.value for item in snapshot.bottleneck_variables],
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "pgor.e_band",
                snapshot.e_band.value,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "pgor.p_band",
                snapshot.p_band.value,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "pgor.r_band",
                snapshot.r_band.value,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "pgor.data_quality_flags",
                list(snapshot.data_quality_flags),
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "trace.engine_version",
                snapshot.engine_version,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "trace.scoring_version",
                snapshot.scoring_version,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "trace.definition_version_id",
                str(snapshot.definition_version_id),
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "trace.formula_version_id",
                str(snapshot.formula_version_id),
                (f"pgor_snapshot:{snapshot.id}",),
            ),
            FeatureValue(
                "trace.input_fingerprint",
                snapshot.input_fingerprint,
                (f"pgor_snapshot:{snapshot.id}",),
            ),
        ]

        if snapshot.completeness_ratio is not None:
            values.append(
                FeatureValue(
                    "pgor.completeness_ratio",
                    str(snapshot.completeness_ratio),
                    (f"pgor_snapshot:{snapshot.id}",),
                )
            )

        for item in snapshot_inputs:
            indicator = indicators.get(item.indicator_definition_id)
            dimension = dimensions.get(item.dimension_definition_id)
            if indicator is None or dimension is None:
                raise FeaturePackageBuildError("SNAPSHOT_INPUT_DEFINITION_MISMATCH")

            key = (
                f"indicator.{item.variable_code.value}."
                f"{dimension.code}.{indicator.code}.normalized"
            )
            values.append(
                FeatureValue(
                    key=key,
                    value=str(item.normalized_score),
                    source_refs=(f"observation:{item.observation_id}",),
                )
            )

        source_fingerprint = hashlib.sha256(
            (
                snapshot.input_fingerprint
                + "|"
                + DIAGNOSIS_FEATURE_SCHEMA_VERSION
            ).encode("utf-8")
        ).hexdigest()
        now = datetime.now(UTC)
        package = FeaturePackage(
            id=uuid4(),
            household_id=snapshot.household_id,
            assessment_id=snapshot.assessment_id,
            pgor_snapshot_id=snapshot.id,
            package_type=FeaturePackageType.DIAGNOSIS,
            schema_version=DIAGNOSIS_FEATURE_SCHEMA_VERSION,
            source_fingerprint=source_fingerprint,
            data_quality_flags=snapshot.data_quality_flags,
            values=tuple(values),
            created_at=now,
            created_by=command.actor_id,
        )
        await self._packages.add(package)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="FeaturePackageBuilt",
                event_version=1,
                aggregate_type="FEATURE_PACKAGE",
                aggregate_id=package.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "feature_package_id": str(package.id),
                    "household_id": str(package.household_id),
                    "assessment_id": str(package.assessment_id),
                    "pgor_snapshot_id": str(package.pgor_snapshot_id),
                    "package_type": package.package_type.value,
                    "schema_version": package.schema_version,
                    "source_fingerprint": package.source_fingerprint,
                    "feature_count": len(package.values),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="intelligence.feature_package.build",
                resource_type="FEATURE_PACKAGE",
                resource_id=package.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="AI_DIAGNOSIS",
                metadata={
                    "event_id": str(event_id),
                    "pgor_snapshot_id": str(package.pgor_snapshot_id),
                    "schema_version": package.schema_version,
                    "source_fingerprint": package.source_fingerprint,
                },
            )
        )
        return package
