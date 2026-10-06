from datetime import datetime
import re
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    AIDecision,
    AIDecisionType,
    DecisionTrace,
    Diagnosis,
    HumanDecision,
    LearningSignal,
)
from hamoon.domains.intelligence.domain.entities import (
    FeaturePackage,
    FeatureValue,
    SensitivityClass,
)
from hamoon.domains.intelligence.domain.registry import (
    AIModelVersionStatus,
    AIProviderStatus,
    EvaluationStatus,
    AIModelVersionCatalogItem,
    EvaluationRunState,
    PromptPolicyVersionCatalogItem,
    RoutingPolicyCatalogItem,
    PromptPolicyVersionStatus,
    ResolvedAIRoute,
    RoutingPolicyDraft,
    RoutingPolicyStatus,
    RoutingPromotionResult,
    HAMOON_NATIVE_PROVIDER_CODE,
)
from hamoon.domains.intelligence.infrastructure.models import (
    AIDecisionModel,
    DecisionTraceModel,
    DiagnosisModel,
    FeaturePackageModel,
    FeatureValueModel,
    HumanDecisionModel,
    LearningSignalModel,
    EvaluationMetricModel,
    AIModelModel,
    AIModelVersionModel,
    AIProviderModel,
    EvaluationRunModel,
    ModelRoutingPolicyModel,
    PromptPolicyModel,
    PromptPolicyVersionModel,
)
from hamoon.infrastructure.ai.contracts import AIRoutingPolicy, AITaskClass

class SqlAlchemyFeaturePackageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, package: FeaturePackage) -> None:
        self._session.add(
            FeaturePackageModel(
                id=package.id,
                household_id=package.household_id,
                assessment_id=package.assessment_id,
                pgor_snapshot_id=package.pgor_snapshot_id,
                package_type=package.package_type,
                schema_version=package.schema_version,
                source_fingerprint=package.source_fingerprint,
                data_quality_flags=list(package.data_quality_flags),
                created_at=package.created_at,
                created_by=package.created_by,
            )
        )
        for order, value in enumerate(package.values, start=1):
            self._session.add(
                FeatureValueModel(
                    id=uuid4(),
                    feature_package_id=package.id,
                    feature_key=value.key,
                    value_json=value.value,
                    source_refs=list(value.source_refs),
                    sensitivity_class=value.sensitivity_class,
                    sort_order=order,
                )
            )

    async def _hydrate(self, model: FeaturePackageModel) -> FeaturePackage:
        result = await self._session.execute(
            select(FeatureValueModel)
            .where(FeatureValueModel.feature_package_id == model.id)
            .order_by(FeatureValueModel.sort_order)
        )
        values = tuple(
            FeatureValue(
                key=value.feature_key,
                value=value.value_json,
                source_refs=tuple(value.source_refs),
                sensitivity_class=SensitivityClass(value.sensitivity_class),
            )
            for value in result.scalars().all()
        )
        return FeaturePackage(
            id=model.id,
            household_id=model.household_id,
            assessment_id=model.assessment_id,
            pgor_snapshot_id=model.pgor_snapshot_id,
            package_type=model.package_type,
            schema_version=model.schema_version,
            source_fingerprint=model.source_fingerprint,
            data_quality_flags=tuple(model.data_quality_flags),
            values=values,
            created_at=model.created_at,
            created_by=model.created_by,
        )

    async def get(self, package_id: UUID) -> FeaturePackage | None:
        model = await self._session.get(FeaturePackageModel, package_id)
        return None if model is None else await self._hydrate(model)

    async def get_by_snapshot(
        self,
        *,
        snapshot_id: UUID,
        schema_version: str,
    ) -> FeaturePackage | None:
        result = await self._session.execute(
            select(FeaturePackageModel).where(
                FeaturePackageModel.pgor_snapshot_id == snapshot_id,
                FeaturePackageModel.schema_version == schema_version,
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else await self._hydrate(model)

def _ai_decision(model: AIDecisionModel) -> AIDecision:
    return AIDecision(
        id=model.id,
        household_id=model.household_id,
        assessment_id=model.assessment_id,
        feature_package_id=model.feature_package_id,
        pgor_snapshot_id=model.pgor_snapshot_id,
        decision_type=model.decision_type,
        status=model.status,
        provider_code=model.provider_code,
        model_id=model.model_id,
        model_artifact_sha256=model.model_artifact_sha256,
        model_alias=model.model_alias,
        routing_policy_id=model.routing_policy_id,
        routing_policy_version=model.routing_policy_version,
        prompt_policy_version=model.prompt_policy_version,
        output_schema_version=model.output_schema_version,
        structured_output=model.structured_output,
        trace_id=model.trace_id,
        generated_at=model.generated_at,
    )

def _diagnosis(model: DiagnosisModel) -> Diagnosis:
    return Diagnosis(
        id=model.id,
        household_id=model.household_id,
        ai_decision_id=model.ai_decision_id,
        status=model.status,
        version=model.version,
        accepted_payload=model.accepted_payload,
        created_at=model.created_at,
        latest_human_decision_id=model.latest_human_decision_id,
        reviewed_at=model.reviewed_at,
        reviewed_by=model.reviewed_by,
    )

def _human_decision(model: HumanDecisionModel) -> HumanDecision:
    return HumanDecision(
        id=model.id,
        household_id=model.household_id,
        ai_decision_id=model.ai_decision_id,
        actor_id=model.actor_id,
        action=model.action,
        reason_code=model.reason_code,
        reason_text=model.reason_text,
        accepted_payload=model.accepted_payload,
        modified_payload=model.modified_payload,
        decided_at=model.decided_at,
        decision_context=model.decision_context,
        diagnosis_id=model.diagnosis_id,
        prescription_id=model.prescription_id,
        provider_match_id=model.provider_match_id,
        outcome_id=model.outcome_id,
    )

def _trace(model: DecisionTraceModel) -> DecisionTrace:
    return DecisionTrace(
        id=model.id,
        household_id=model.household_id,
        trace_type=model.trace_type,
        state_fingerprint=model.state_fingerprint,
        household_context_version=model.household_context_version,
        pgor_snapshot_id=model.pgor_snapshot_id,
        feature_package_id=model.feature_package_id,
        ai_decision_id=model.ai_decision_id,
        human_decision_id=model.human_decision_id,
        opened_at=model.opened_at,
        closed_at=model.closed_at,
        prescription_id=model.prescription_id,
        intervention_id=model.intervention_id,
        referral_id=model.referral_id,
        provider_result_id=model.provider_result_id,
        outcome_id=model.outcome_id,
        learning_signal_id=model.learning_signal_id,
    )

class SqlAlchemyAIDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, decision: AIDecision) -> None:
        self._session.add(
            AIDecisionModel(
                id=decision.id,
                household_id=decision.household_id,
                assessment_id=decision.assessment_id,
                feature_package_id=decision.feature_package_id,
                pgor_snapshot_id=decision.pgor_snapshot_id,
                decision_type=decision.decision_type,
                status=decision.status,
                provider_code=decision.provider_code,
                model_id=decision.model_id,
                model_artifact_sha256=decision.model_artifact_sha256,
                model_alias=decision.model_alias,
                routing_policy_id=decision.routing_policy_id,
                routing_policy_version=decision.routing_policy_version,
                prompt_policy_version=decision.prompt_policy_version,
                output_schema_version=decision.output_schema_version,
                structured_output=decision.structured_output,
                trace_id=decision.trace_id,
                generated_at=decision.generated_at,
            )
        )

    async def get(self, decision_id: UUID) -> AIDecision | None:
        model = await self._session.get(AIDecisionModel, decision_id)
        return None if model is None else _ai_decision(model)


    async def list_by_ids(
        self,
        decision_ids: list[UUID],
    ) -> dict[UUID, AIDecision]:
        if not decision_ids:
            return {}
        result = await self._session.execute(
            select(AIDecisionModel).where(AIDecisionModel.id.in_(decision_ids))
        )
        return {
            model.id: _ai_decision(model)
            for model in result.scalars().all()
        }

class SqlAlchemyDiagnosisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, diagnosis: Diagnosis) -> None:
        self._session.add(
            DiagnosisModel(
                id=diagnosis.id,
                household_id=diagnosis.household_id,
                ai_decision_id=diagnosis.ai_decision_id,
                status=diagnosis.status,
                version=diagnosis.version,
                accepted_payload=diagnosis.accepted_payload,
                created_at=diagnosis.created_at,
                latest_human_decision_id=diagnosis.latest_human_decision_id,
                reviewed_at=diagnosis.reviewed_at,
                reviewed_by=diagnosis.reviewed_by,
            )
        )

    async def get(self, diagnosis_id: UUID) -> Diagnosis | None:
        model = await self._session.get(DiagnosisModel, diagnosis_id)
        return None if model is None else _diagnosis(model)


    async def list_for_household(
        self,
        household_id: UUID,
        *,
        limit: int,
    ) -> list[Diagnosis]:
        result = await self._session.execute(
            select(DiagnosisModel)
            .where(DiagnosisModel.household_id == household_id)
            .order_by(DiagnosisModel.created_at.desc())
            .limit(limit)
        )
        return [_diagnosis(model) for model in result.scalars().all()]

    async def update(
        self,
        diagnosis: Diagnosis,
        *,
        expected_version: int,
    ) -> None:
        result = await self._session.execute(
            select(DiagnosisModel)
            .where(DiagnosisModel.id == diagnosis.id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise RuntimeError("Diagnosis disappeared during update.")
        if model.version != expected_version:
            from hamoon.domains.intelligence.domain.errors import (
                DiagnosisVersionConflictError,
            )

            raise DiagnosisVersionConflictError("Diagnosis version changed.")

        model.status = diagnosis.status
        model.version = diagnosis.version
        model.accepted_payload = diagnosis.accepted_payload
        model.latest_human_decision_id = diagnosis.latest_human_decision_id
        model.reviewed_at = diagnosis.reviewed_at
        model.reviewed_by = diagnosis.reviewed_by

class SqlAlchemyHumanDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, decision: HumanDecision) -> None:
        self._session.add(
            HumanDecisionModel(
                id=decision.id,
                household_id=decision.household_id,
                ai_decision_id=decision.ai_decision_id,
                diagnosis_id=decision.diagnosis_id,
                prescription_id=decision.prescription_id,
                provider_match_id=decision.provider_match_id,
                outcome_id=decision.outcome_id,
                decision_context=decision.decision_context,
                actor_id=decision.actor_id,
                action=decision.action,
                reason_code=decision.reason_code,
                reason_text=decision.reason_text,
                accepted_payload=decision.accepted_payload,
                modified_payload=decision.modified_payload,
                decided_at=decision.decided_at,
            )
        )

    async def get(self, decision_id: UUID) -> HumanDecision | None:
        model = await self._session.get(HumanDecisionModel, decision_id)
        return None if model is None else _human_decision(model)


    async def list_for_diagnoses(
        self,
        diagnosis_ids: list[UUID],
    ) -> dict[UUID, list[HumanDecision]]:
        if not diagnosis_ids:
            return {}
        result = await self._session.execute(
            select(HumanDecisionModel)
            .where(HumanDecisionModel.diagnosis_id.in_(diagnosis_ids))
            .order_by(HumanDecisionModel.decided_at.desc())
        )
        grouped: dict[UUID, list[HumanDecision]] = {}
        for model in result.scalars().all():
            if model.diagnosis_id is None:
                continue
            grouped.setdefault(model.diagnosis_id, []).append(
                _human_decision(model)
            )
        return grouped


    async def list_for_prescriptions(
        self,
        prescription_ids: list[UUID],
    ) -> dict[UUID, list[HumanDecision]]:
        if not prescription_ids:
            return {}
        result = await self._session.execute(
            select(HumanDecisionModel)
            .where(HumanDecisionModel.prescription_id.in_(prescription_ids))
            .order_by(HumanDecisionModel.decided_at.desc())
        )
        grouped: dict[UUID, list[HumanDecision]] = {}
        for model in result.scalars().all():
            if model.prescription_id is None:
                continue
            grouped.setdefault(model.prescription_id, []).append(
                _human_decision(model)
            )
        return grouped

class SqlAlchemyDecisionTraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, trace: DecisionTrace) -> None:
        self._session.add(
            DecisionTraceModel(
                id=trace.id,
                household_id=trace.household_id,
                trace_type=trace.trace_type,
                state_fingerprint=trace.state_fingerprint,
                household_context_version=trace.household_context_version,
                pgor_snapshot_id=trace.pgor_snapshot_id,
                feature_package_id=trace.feature_package_id,
                ai_decision_id=trace.ai_decision_id,
                human_decision_id=trace.human_decision_id,
                prescription_id=trace.prescription_id,
                intervention_id=trace.intervention_id,
                referral_id=trace.referral_id,
                provider_result_id=trace.provider_result_id,
                outcome_id=trace.outcome_id,
                learning_signal_id=trace.learning_signal_id,
                opened_at=trace.opened_at,
                closed_at=trace.closed_at,
            )
        )

    async def get_by_ai_decision(
        self,
        ai_decision_id: UUID,
    ) -> DecisionTrace | None:
        result = await self._session.execute(
            select(DecisionTraceModel).where(
                DecisionTraceModel.ai_decision_id == ai_decision_id
            )
        )
        model = result.scalar_one_or_none()
        return None if model is None else _trace(model)

    async def attach_human_decision(
        self,
        *,
        ai_decision_id: UUID,
        human_decision_id: UUID,
        learning_signal_id: UUID | None = None,
        closed_at: datetime | None,
    ) -> None:
        result = await self._session.execute(
            select(DecisionTraceModel)
            .where(DecisionTraceModel.ai_decision_id == ai_decision_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise RuntimeError("Decision trace is missing.")
        model.human_decision_id = human_decision_id
        if learning_signal_id is not None:
            model.learning_signal_id = learning_signal_id
        model.closed_at = closed_at

    async def attach_intervention(
        self,
        *,
        ai_decision_id: UUID,
        intervention_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(DecisionTraceModel)
            .where(DecisionTraceModel.ai_decision_id == ai_decision_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise RuntimeError("Decision trace is missing.")
        model.intervention_id = intervention_id

    async def attach_referral(
        self,
        *,
        intervention_id: UUID,
        referral_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(DecisionTraceModel)
            .where(
                DecisionTraceModel.trace_type == AIDecisionType.PRESCRIPTION,
                DecisionTraceModel.intervention_id == intervention_id,
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise RuntimeError("Prescription decision trace is missing.")
        model.referral_id = referral_id

    async def attach_provider_result(
        self,
        *,
        referral_id: UUID,
        provider_result_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(DecisionTraceModel)
            .where(
                DecisionTraceModel.trace_type == AIDecisionType.PRESCRIPTION,
                DecisionTraceModel.referral_id == referral_id,
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise RuntimeError("Prescription decision trace is missing.")
        model.provider_result_id = provider_result_id

    async def attach_outcome(
        self,
        *,
        intervention_id: UUID,
        outcome_id: UUID,
    ) -> None:
        result = await self._session.execute(
            select(DecisionTraceModel)
            .where(
                DecisionTraceModel.trace_type == AIDecisionType.PRESCRIPTION,
                DecisionTraceModel.intervention_id == intervention_id,
            )
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise RuntimeError("Prescription decision trace is missing.")
        model.outcome_id = outcome_id


class SqlAlchemyLearningSignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, signal: LearningSignal) -> None:
        self._session.add(
            LearningSignalModel(
                id=signal.id,
                household_id=signal.household_id,
                signal_type=signal.signal_type,
                ai_decision_id=signal.ai_decision_id,
                human_decision_id=signal.human_decision_id,
                diagnosis_id=signal.diagnosis_id,
                prescription_id=signal.prescription_id,
                intervention_id=signal.intervention_id,
                provider_match_id=signal.provider_match_id,
                provider_id=signal.provider_id,
                provider_result_id=signal.provider_result_id,
                outcome_id=signal.outcome_id,
                signal_label=signal.signal_label,
                quality_status=signal.quality_status,
                created_at=signal.created_at,
                created_by=signal.created_by,
            )
        )

    @staticmethod
    def _hydrate(model: LearningSignalModel) -> LearningSignal:
        return LearningSignal(
            id=model.id,
            household_id=model.household_id,
            signal_type=model.signal_type,
            ai_decision_id=model.ai_decision_id,
            human_decision_id=model.human_decision_id,
            diagnosis_id=model.diagnosis_id,
            signal_label=model.signal_label,
            quality_status=model.quality_status,
            created_at=model.created_at,
            created_by=model.created_by,
            prescription_id=model.prescription_id,
            intervention_id=model.intervention_id,
            provider_match_id=model.provider_match_id,
            provider_id=model.provider_id,
            provider_result_id=model.provider_result_id,
            outcome_id=model.outcome_id,
        )

    async def get(self, signal_id: UUID) -> LearningSignal | None:
        model = await self._session.get(LearningSignalModel, signal_id)
        return None if model is None else self._hydrate(model)

    async def list(
        self,
        *,
        quality_status: object | None,
        signal_type: object | None,
        limit: int,
    ) -> list[LearningSignal]:
        statement = select(LearningSignalModel)
        if quality_status is not None:
            statement = statement.where(
                LearningSignalModel.quality_status == quality_status
            )
        if signal_type is not None:
            statement = statement.where(
                LearningSignalModel.signal_type == signal_type
            )
        result = await self._session.execute(
            statement.order_by(LearningSignalModel.created_at.desc()).limit(limit)
        )
        return [self._hydrate(model) for model in result.scalars().all()]

    async def change_quality(
        self,
        *,
        signal_id: UUID,
        expected_quality: object,
        new_quality: object,
    ) -> LearningSignal:
        result = await self._session.execute(
            select(LearningSignalModel)
            .where(LearningSignalModel.id == signal_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("LEARNING_SIGNAL_NOT_FOUND")
        if model.quality_status != expected_quality:
            raise ValueError("LEARNING_SIGNAL_QUALITY_CONFLICT")
        model.quality_status = new_quality  # type: ignore[assignment]
        return self._hydrate(model)

class SqlAlchemyAIRuntimeRegistryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_active_route(
        self,
        task_class: AITaskClass,
    ) -> ResolvedAIRoute | None:
        result = await self._session.execute(
            select(
                ModelRoutingPolicyModel,
                AIModelVersionModel,
                AIModelModel,
                AIProviderModel,
                PromptPolicyVersionModel,
                EvaluationRunModel,
            )
            .join(
                AIModelVersionModel,
                AIModelVersionModel.id
                == ModelRoutingPolicyModel.model_version_id,
            )
            .join(
                AIModelModel,
                AIModelModel.id == AIModelVersionModel.ai_model_id,
            )
            .join(
                AIProviderModel,
                AIProviderModel.id == AIModelModel.provider_id,
            )
            .join(
                PromptPolicyVersionModel,
                PromptPolicyVersionModel.id
                == ModelRoutingPolicyModel.prompt_policy_version_id,
            )
            .join(
                EvaluationRunModel,
                EvaluationRunModel.id
                == ModelRoutingPolicyModel.evaluation_run_id,
            )
            .where(
                ModelRoutingPolicyModel.task_class == task_class,
                ModelRoutingPolicyModel.status == RoutingPolicyStatus.ACTIVE,
                AIModelVersionModel.status == AIModelVersionStatus.PRODUCTION,
                AIProviderModel.status == AIProviderStatus.ACTIVE,
                AIProviderModel.code == HAMOON_NATIVE_PROVIDER_CODE,
                AIModelVersionModel.artifact_sha256.is_not(None),
                PromptPolicyVersionModel.status == PromptPolicyVersionStatus.ACTIVE,
                EvaluationRunModel.status == EvaluationStatus.PASSED,
                EvaluationRunModel.passed.is_(True),
                EvaluationRunModel.completed_at.is_not(None),
                EvaluationRunModel.dataset_manifest_digest.is_not(None),
                EvaluationRunModel.report_digest.is_not(None),
                ModelRoutingPolicyModel.approved_at.is_not(None),
            )
            .order_by(ModelRoutingPolicyModel.approved_at.desc())
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            return None

        routing, model_version, _model, provider, prompt, evaluation = row
        if evaluation.completed_at is None:
            return None
        return ResolvedAIRoute(
            routing_policy=AIRoutingPolicy(
                id=routing.id,
                version=routing.version,
                task_class=routing.task_class,
                provider_code=provider.code,
                model_alias=routing.model_alias,
                concrete_model_id=model_version.concrete_model_id,
                model_artifact_sha256=model_version.artifact_sha256,
                prompt_policy_version=prompt.version,
                output_schema_version=prompt.output_schema_version,
                structured_output_required=routing.structured_output_required,
            ),
            instructions=prompt.instructions,
            evaluation_run_id=evaluation.id,
            evaluation_completed_at=evaluation.completed_at,
        )

    async def list_model_versions(
        self,
    ) -> list[AIModelVersionCatalogItem]:
        result = await self._session.execute(
            select(
                AIModelVersionModel,
                AIModelModel,
                AIProviderModel,
            )
            .join(
                AIModelModel,
                AIModelModel.id == AIModelVersionModel.ai_model_id,
            )
            .join(
                AIProviderModel,
                AIProviderModel.id == AIModelModel.provider_id,
            )
            .order_by(
                AIModelModel.model_key,
                AIModelVersionModel.version,
            )
        )
        return [
            AIModelVersionCatalogItem(
                id=version.id,
                ai_model_id=model.id,
                model_key=model.model_key,
                purpose=model.purpose,
                provider_id=provider.id,
                provider_code=provider.code,
                provider_status=provider.status,
                version=version.version,
                concrete_model_id=version.concrete_model_id,
                artifact_sha256=version.artifact_sha256,
                parent_model_version_id=version.parent_model_version_id,
                status=version.status,
                limitations=version.limitations,
                approved_at=version.approved_at,
                deployed_at=version.deployed_at,
            )
            for version, model, provider in result.all()
        ]

    async def get_native_growth_base(
        self,
        *,
        model_version_id: UUID,
        task_class: AITaskClass,
        model_key: str,
        concrete_model_id: str,
    ) -> AIModelVersionCatalogItem:
        result = await self._session.execute(
            select(
                AIModelVersionModel,
                AIModelModel,
                AIProviderModel,
            )
            .join(
                AIModelModel,
                AIModelModel.id == AIModelVersionModel.ai_model_id,
            )
            .join(
                AIProviderModel,
                AIProviderModel.id == AIModelModel.provider_id,
            )
            .where(AIModelVersionModel.id == model_version_id)
        )
        row = result.one_or_none()
        if row is None:
            raise LookupError("BASE_MODEL_VERSION_NOT_FOUND")
        version, model, provider = row
        if (
            provider.code != HAMOON_NATIVE_PROVIDER_CODE
            or provider.status is not AIProviderStatus.ACTIVE
        ):
            raise ValueError("BASE_MODEL_MUST_BE_HAMOON_NATIVE")
        if model.model_key != model_key.strip():
            raise ValueError("BASE_MODEL_KEY_MISMATCH")
        if model.purpose != task_class.value:
            raise ValueError("BASE_MODEL_PURPOSE_MISMATCH")
        if version.concrete_model_id != concrete_model_id.strip():
            raise ValueError("BASE_MODEL_ID_MISMATCH")
        if version.status not in {
            AIModelVersionStatus.APPROVED,
            AIModelVersionStatus.PRODUCTION,
        }:
            raise ValueError("BASE_MODEL_VERSION_NOT_APPROVED")
        if (
            version.artifact_sha256 is None
            or re.fullmatch(r"[0-9a-f]{64}", version.artifact_sha256) is None
        ):
            raise ValueError("BASE_MODEL_ARTIFACT_REQUIRED")
        return AIModelVersionCatalogItem(
            id=version.id,
            ai_model_id=model.id,
            model_key=model.model_key,
            purpose=model.purpose,
            provider_id=provider.id,
            provider_code=provider.code,
            provider_status=provider.status,
            version=version.version,
            concrete_model_id=version.concrete_model_id,
            artifact_sha256=version.artifact_sha256,
            parent_model_version_id=version.parent_model_version_id,
            status=version.status,
            limitations=version.limitations,
            approved_at=version.approved_at,
            deployed_at=version.deployed_at,
        )

    async def register_native_model_candidate(
        self,
        *,
        task_class: AITaskClass,
        model_key: str,
        version: str,
        concrete_model_id: str,
        artifact_sha256: str,
        parent_model_version_id: UUID | None,
        limitations: str | None,
    ) -> AIModelVersionCatalogItem:
        clean_key = model_key.strip()
        clean_version = version.strip()
        clean_model_id = concrete_model_id.strip()
        clean_digest = artifact_sha256.strip().lower()
        if not clean_key or not clean_version or not clean_model_id:
            raise ValueError("MODEL_CANDIDATE_METADATA_REQUIRED")
        if re.fullmatch(r"[0-9a-f]{64}", clean_digest) is None:
            raise ValueError("MODEL_ARTIFACT_DIGEST_INVALID")

        provider_result = await self._session.execute(
            select(AIProviderModel).where(
                AIProviderModel.code == HAMOON_NATIVE_PROVIDER_CODE,
                AIProviderModel.status == AIProviderStatus.ACTIVE,
            )
        )
        provider = provider_result.scalar_one_or_none()
        if provider is None:
            raise ValueError("HAMOON_NATIVE_PROVIDER_NOT_ACTIVE")

        model_result = await self._session.execute(
            select(AIModelModel).where(AIModelModel.model_key == clean_key)
        )
        model = model_result.scalar_one_or_none()
        if model is None:
            model = AIModelModel(
                id=uuid4(),
                model_key=clean_key,
                provider_id=provider.id,
                purpose=task_class.value,
            )
            self._session.add(model)
        else:
            if model.provider_id != provider.id:
                raise ValueError("MODEL_KEY_PROVIDER_MISMATCH")
            if model.purpose != task_class.value:
                raise ValueError("MODEL_KEY_PURPOSE_MISMATCH")

        if parent_model_version_id is not None:
            await self.get_native_growth_base(
                model_version_id=parent_model_version_id,
                task_class=task_class,
                model_key=clean_key,
                concrete_model_id=clean_model_id,
            )

        duplicate = await self._session.execute(
            select(AIModelVersionModel.id).where(
                AIModelVersionModel.ai_model_id == model.id,
                AIModelVersionModel.version == clean_version,
            )
        )
        if duplicate.scalar_one_or_none() is not None:
            raise ValueError("MODEL_VERSION_EXISTS")

        candidate = AIModelVersionModel(
            id=uuid4(),
            ai_model_id=model.id,
            version=clean_version,
            concrete_model_id=clean_model_id,
            artifact_sha256=clean_digest,
            parent_model_version_id=parent_model_version_id,
            status=AIModelVersionStatus.CANDIDATE,
            limitations=limitations.strip() if limitations else None,
            approved_at=None,
            deployed_at=None,
        )
        self._session.add(candidate)

        return AIModelVersionCatalogItem(
            id=candidate.id,
            ai_model_id=model.id,
            model_key=model.model_key,
            purpose=model.purpose,
            provider_id=provider.id,
            provider_code=provider.code,
            provider_status=provider.status,
            version=candidate.version,
            concrete_model_id=candidate.concrete_model_id,
            artifact_sha256=candidate.artifact_sha256,
            parent_model_version_id=candidate.parent_model_version_id,
            status=candidate.status,
            limitations=candidate.limitations,
            approved_at=candidate.approved_at,
            deployed_at=candidate.deployed_at,
        )

    async def list_prompt_policy_versions(
        self,
    ) -> list[PromptPolicyVersionCatalogItem]:
        result = await self._session.execute(
            select(
                PromptPolicyVersionModel,
                PromptPolicyModel,
            )
            .join(
                PromptPolicyModel,
                PromptPolicyModel.id == PromptPolicyVersionModel.prompt_policy_id,
            )
            .order_by(
                PromptPolicyModel.name,
                PromptPolicyVersionModel.version,
            )
        )
        return [
            PromptPolicyVersionCatalogItem(
                id=version.id,
                prompt_policy_id=policy.id,
                policy_name=policy.name,
                purpose=policy.purpose,
                version=version.version,
                output_schema_version=version.output_schema_version,
                guardrail_version=version.guardrail_version,
                status=version.status,
                approved_at=version.approved_at,
            )
            for version, policy in result.all()
        ]

    async def list_evaluation_runs(
        self,
        *,
        task_class: AITaskClass | None = None,
        limit: int = 100,
    ) -> list[EvaluationRunState]:
        query = select(EvaluationRunModel)
        if task_class is not None:
            query = query.where(EvaluationRunModel.task_class == task_class)
        result = await self._session.execute(
            query.order_by(EvaluationRunModel.started_at.desc()).limit(limit)
        )
        return [_evaluation_run_state(model) for model in result.scalars().all()]

    async def list_routing_policies(
        self,
        *,
        task_class: AITaskClass | None = None,
        limit: int = 100,
    ) -> list[RoutingPolicyCatalogItem]:
        query = select(ModelRoutingPolicyModel)
        if task_class is not None:
            query = query.where(ModelRoutingPolicyModel.task_class == task_class)
        result = await self._session.execute(
            query.order_by(
                ModelRoutingPolicyModel.approved_at.desc(),
                ModelRoutingPolicyModel.version.desc(),
            ).limit(limit)
        )
        return [
            RoutingPolicyCatalogItem(
                id=model.id,
                task_class=model.task_class,
                version=model.version,
                model_alias=model.model_alias,
                model_version_id=model.model_version_id,
                prompt_policy_version_id=model.prompt_policy_version_id,
                evaluation_run_id=model.evaluation_run_id,
                structured_output_required=model.structured_output_required,
                status=model.status,
                approved_at=model.approved_at,
            )
            for model in result.scalars().all()
        ]

    async def create_evaluation_run(
        self,
        *,
        task_class: AITaskClass,
        model_version_id: UUID,
        prompt_policy_version_id: UUID,
        dataset_version_id: UUID,
        dataset_manifest_digest: str,
        evaluation_policy_version: str,
        started_at: datetime,
    ) -> EvaluationRunState:
        model_version = await self._session.get(AIModelVersionModel, model_version_id)
        if model_version is None:
            raise LookupError("AI_MODEL_VERSION_NOT_FOUND")
        model = await self._session.get(AIModelModel, model_version.ai_model_id)
        if model is None:
            raise LookupError("AI_MODEL_NOT_FOUND")
        provider = await self._session.get(AIProviderModel, model.provider_id)
        if provider is None:
            raise LookupError("AI_PROVIDER_NOT_FOUND")
        if (
            provider.status is not AIProviderStatus.ACTIVE
            or provider.code != HAMOON_NATIVE_PROVIDER_CODE
        ):
            raise ValueError("EVALUATION_REQUIRES_HAMOON_NATIVE_MODEL")
        if model.purpose != task_class.value:
            raise ValueError("EVALUATION_MODEL_PURPOSE_MISMATCH")
        if (
            model_version.artifact_sha256 is None
            or re.fullmatch(r"[0-9a-f]{64}", model_version.artifact_sha256) is None
        ):
            raise ValueError("EVALUATION_MODEL_ARTIFACT_REQUIRED")
        if model_version.status not in {
            AIModelVersionStatus.CANDIDATE,
            AIModelVersionStatus.APPROVED,
        }:
            raise ValueError("EVALUATION_MODEL_VERSION_NOT_ELIGIBLE")

        prompt_version = await self._session.get(
            PromptPolicyVersionModel,
            prompt_policy_version_id,
        )
        if prompt_version is None:
            raise LookupError("PROMPT_POLICY_VERSION_NOT_FOUND")
        prompt_policy = await self._session.get(
            PromptPolicyModel,
            prompt_version.prompt_policy_id,
        )
        if prompt_policy is None:
            raise LookupError("PROMPT_POLICY_NOT_FOUND")
        if prompt_version.status is not PromptPolicyVersionStatus.ACTIVE:
            raise ValueError("EVALUATION_PROMPT_NOT_ACTIVE")
        if prompt_policy.purpose != task_class.value:
            raise ValueError("EVALUATION_PROMPT_PURPOSE_MISMATCH")

        evaluation_model = EvaluationRunModel(
            id=uuid4(),
            task_class=task_class,
            model_version_id=model_version_id,
            prompt_policy_version_id=prompt_policy_version_id,
            evaluation_policy_version=evaluation_policy_version,
            dataset_version_id=dataset_version_id,
            dataset_manifest_digest=dataset_manifest_digest,
            report_digest=None,
            started_at=started_at,
            status=EvaluationStatus.PENDING,
            passed=False,
            summary_metrics={},
            completed_at=None,
        )
        self._session.add(evaluation_model)
        return _evaluation_run_state(evaluation_model)

    async def get_evaluation_run(
        self,
        evaluation_run_id: UUID,
    ) -> EvaluationRunState | None:
        model = await self._session.get(EvaluationRunModel, evaluation_run_id)
        return None if model is None else _evaluation_run_state(model)

    async def complete_evaluation_run(
        self,
        *,
        evaluation_run_id: UUID,
        dataset_manifest_digest: str,
        report_digest: str,
        passed: bool,
        summary_metrics: dict[str, JsonValue],
        completed_at: datetime,
    ) -> EvaluationRunState:
        result = await self._session.execute(
            select(EvaluationRunModel)
            .where(EvaluationRunModel.id == evaluation_run_id)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise LookupError("EVALUATION_RUN_NOT_FOUND")
        if model.status not in {
            EvaluationStatus.PENDING,
            EvaluationStatus.RUNNING,
        }:
            raise ValueError("EVALUATION_RUN_ALREADY_COMPLETED")
        if model.dataset_manifest_digest is None:
            raise ValueError("EVALUATION_DATASET_DIGEST_REQUIRED")
        if model.dataset_manifest_digest != dataset_manifest_digest:
            raise ValueError("EVALUATION_DATASET_DIGEST_MISMATCH")
        if len(report_digest) != 64:
            raise ValueError("EVALUATION_REPORT_DIGEST_INVALID")
        structural_gate = summary_metrics.get("structural_gate_passed")
        if passed and structural_gate is not True:
            raise ValueError("EVALUATION_STRUCTURAL_GATE_NOT_PASSED")

        model.status = EvaluationStatus.PASSED if passed else EvaluationStatus.FAILED
        model.passed = passed
        model.summary_metrics = summary_metrics
        model.report_digest = report_digest
        model.completed_at = completed_at
        for metric_key, metric_value in summary_metrics.items():
            if isinstance(metric_value, (str, int, float, bool)) or metric_value is None:
                self._session.add(
                    EvaluationMetricModel(
                        id=uuid4(),
                        evaluation_run_id=model.id,
                        metric_key=metric_key,
                        metric_value=metric_value,
                        segment=None,
                        threshold=None,
                        passed=(
                            bool(metric_value)
                            if metric_key == "structural_gate_passed"
                            and isinstance(metric_value, bool)
                            else None
                        ),
                    )
                )
        return _evaluation_run_state(model)

    async def create_routing_policy(
        self,
        *,
        task_class: AITaskClass,
        version: str,
        model_alias: str,
        model_version_id: UUID,
        prompt_policy_version_id: UUID,
        evaluation_run_id: UUID,
    ) -> RoutingPolicyDraft:
        evaluation = await self._session.get(EvaluationRunModel, evaluation_run_id)
        if evaluation is None:
            raise LookupError("EVALUATION_RUN_NOT_FOUND")
        if (
            evaluation.status != EvaluationStatus.PASSED
            or not evaluation.passed
            or evaluation.completed_at is None
        ):
            raise ValueError("EVALUATION_NOT_PASSED")
        if evaluation.dataset_version_id is None:
            raise ValueError("EVALUATION_DATASET_REQUIRED")
        if (
            evaluation.dataset_manifest_digest is None
            or evaluation.report_digest is None
        ):
            raise ValueError("EVALUATION_ATTESTATION_REQUIRED")
        if evaluation.summary_metrics.get("structural_gate_passed") is not True:
            raise ValueError("EVALUATION_STRUCTURAL_GATE_NOT_PASSED")
        if evaluation.task_class is not task_class:
            raise ValueError("EVALUATION_TASK_CLASS_MISMATCH")
        if evaluation.model_version_id != model_version_id:
            raise ValueError("EVALUATION_MODEL_VERSION_MISMATCH")
        if evaluation.prompt_policy_version_id != prompt_policy_version_id:
            raise ValueError("EVALUATION_PROMPT_VERSION_MISMATCH")

        model_version = await self._session.get(AIModelVersionModel, model_version_id)
        if model_version is None:
            raise LookupError("AI_MODEL_VERSION_NOT_FOUND")
        prompt_version = await self._session.get(
            PromptPolicyVersionModel,
            prompt_policy_version_id,
        )
        if prompt_version is None:
            raise LookupError("PROMPT_POLICY_VERSION_NOT_FOUND")
        if model_version.status not in {
            AIModelVersionStatus.CANDIDATE,
            AIModelVersionStatus.APPROVED,
        }:
            raise ValueError("MODEL_VERSION_NOT_PROMOTABLE")
        if prompt_version.status is not PromptPolicyVersionStatus.ACTIVE:
            raise ValueError("PROMPT_POLICY_NOT_ACTIVE")

        clean_version = version.strip()
        clean_alias = model_alias.strip()
        if not clean_version or not clean_alias:
            raise ValueError("ROUTING_POLICY_METADATA_REQUIRED")
        duplicate = await self._session.execute(
            select(ModelRoutingPolicyModel.id).where(
                ModelRoutingPolicyModel.task_class == task_class,
                ModelRoutingPolicyModel.version == clean_version,
            )
        )
        if duplicate.scalar_one_or_none() is not None:
            raise ValueError("ROUTING_POLICY_VERSION_EXISTS")

        routing = ModelRoutingPolicyModel(
            id=uuid4(),
            task_class=task_class,
            version=clean_version,
            model_alias=clean_alias,
            model_version_id=model_version_id,
            prompt_policy_version_id=prompt_policy_version_id,
            evaluation_run_id=evaluation_run_id,
            structured_output_required=True,
            status=RoutingPolicyStatus.DRAFT,
            approved_at=None,
        )
        self._session.add(routing)
        return RoutingPolicyDraft(
            id=routing.id,
            task_class=routing.task_class,
            version=routing.version,
            model_alias=routing.model_alias,
            model_version_id=routing.model_version_id,
            prompt_policy_version_id=routing.prompt_policy_version_id,
            evaluation_run_id=routing.evaluation_run_id,
            status=routing.status,
        )

    async def promote_routing_policy(
        self,
        *,
        routing_policy_id: UUID,
        activated_at: datetime,
    ) -> RoutingPromotionResult:
        result = await self._session.execute(
            select(
                ModelRoutingPolicyModel,
                AIModelVersionModel,
                AIProviderModel,
                PromptPolicyVersionModel,
                EvaluationRunModel,
            )
            .join(
                AIModelVersionModel,
                AIModelVersionModel.id
                == ModelRoutingPolicyModel.model_version_id,
            )
            .join(
                AIModelModel,
                AIModelModel.id == AIModelVersionModel.ai_model_id,
            )
            .join(
                AIProviderModel,
                AIProviderModel.id == AIModelModel.provider_id,
            )
            .join(
                PromptPolicyVersionModel,
                PromptPolicyVersionModel.id
                == ModelRoutingPolicyModel.prompt_policy_version_id,
            )
            .join(
                EvaluationRunModel,
                EvaluationRunModel.id
                == ModelRoutingPolicyModel.evaluation_run_id,
            )
            .where(ModelRoutingPolicyModel.id == routing_policy_id)
            .with_for_update()
        )
        row = result.one_or_none()
        if row is None:
            raise LookupError("ROUTING_POLICY_NOT_FOUND")

        routing, model_version, provider, prompt, evaluation = row
        if provider.status != AIProviderStatus.ACTIVE:
            raise ValueError("AI_PROVIDER_NOT_ACTIVE")
        if provider.code != HAMOON_NATIVE_PROVIDER_CODE:
            raise ValueError("EXTERNAL_AI_PROVIDER_PRODUCTION_FORBIDDEN")
        if (
            model_version.artifact_sha256 is None
            or re.fullmatch(r"[0-9a-f]{64}", model_version.artifact_sha256) is None
        ):
            raise ValueError("MODEL_ARTIFACT_DIGEST_REQUIRED")
        if prompt.status != PromptPolicyVersionStatus.ACTIVE:
            raise ValueError("PROMPT_POLICY_NOT_ACTIVE")
        if evaluation.status != EvaluationStatus.PASSED or not evaluation.passed:
            raise ValueError("EVALUATION_NOT_PASSED")
        if evaluation.completed_at is None:
            raise ValueError("EVALUATION_NOT_COMPLETED")
        if (
            evaluation.dataset_version_id is None
            or evaluation.dataset_manifest_digest is None
            or evaluation.report_digest is None
        ):
            raise ValueError("EVALUATION_ATTESTATION_REQUIRED")
        if evaluation.summary_metrics.get("structural_gate_passed") is not True:
            raise ValueError("EVALUATION_STRUCTURAL_GATE_NOT_PASSED")
        if evaluation.model_version_id != model_version.id:
            raise ValueError("EVALUATION_MODEL_VERSION_MISMATCH")
        if evaluation.prompt_policy_version_id != prompt.id:
            raise ValueError("EVALUATION_PROMPT_VERSION_MISMATCH")
        if model_version.status not in {
            AIModelVersionStatus.CANDIDATE,
            AIModelVersionStatus.APPROVED,
        }:
            raise ValueError("MODEL_VERSION_NOT_PROMOTABLE")
        if routing.status != RoutingPolicyStatus.DRAFT:
            raise ValueError("ROUTING_POLICY_NOT_DRAFT")

        await self._session.execute(
            update(ModelRoutingPolicyModel)
            .where(
                ModelRoutingPolicyModel.task_class == routing.task_class,
                ModelRoutingPolicyModel.status == RoutingPolicyStatus.ACTIVE,
                ModelRoutingPolicyModel.id != routing.id,
            )
            .values(status=RoutingPolicyStatus.RETIRED)
        )

        model_version.status = AIModelVersionStatus.PRODUCTION
        model_version.approved_at = activated_at
        model_version.deployed_at = activated_at
        routing.status = RoutingPolicyStatus.ACTIVE
        routing.approved_at = activated_at

        return RoutingPromotionResult(
            routing_policy_id=routing.id,
            model_version_id=model_version.id,
            task_class=routing.task_class,
            routing_version=routing.version,
            model_status=model_version.status,
            routing_status=routing.status,
            activated_at=activated_at,
        )

def _evaluation_run_state(model: EvaluationRunModel) -> EvaluationRunState:
    return EvaluationRunState(
        id=model.id,
        task_class=model.task_class,
        model_version_id=model.model_version_id,
        prompt_policy_version_id=model.prompt_policy_version_id,
        evaluation_policy_version=model.evaluation_policy_version,
        dataset_version_id=model.dataset_version_id,
        dataset_manifest_digest=model.dataset_manifest_digest,
        report_digest=model.report_digest,
        status=model.status,
        passed=model.passed,
        summary_metrics=model.summary_metrics,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )
