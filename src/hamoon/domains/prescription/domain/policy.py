from typing import cast
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.entities import FeaturePackage
from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.prescription.domain.entities import (
    PrescriptionItem,
    PrescriptionItemStatus,
)
from hamoon.domains.prescription.domain.errors import PrescriptionGenerationError

INTERVENTIONS_BY_TARGET: dict[PGORVariableCode, frozenset[InterventionType]] = {
    PGORVariableCode.P: frozenset(
        {
            InterventionType.COUNSELING,
            InterventionType.MOTIVATION,
            InterventionType.PSYCHOLOGICAL_EMPOWERMENT,
            InterventionType.COACHING,
        }
    ),
    PGORVariableCode.G: frozenset(
        {
            InterventionType.TRAINING,
            InterventionType.SKILLS_TRAINING,
            InterventionType.VOCATIONAL_TRAINING,
        }
    ),
    PGORVariableCode.O: frozenset(
        {
            InterventionType.MARKET_LINKAGE,
            InterventionType.EMPLOYMENT,
            InterventionType.FINANCING_FACILITIES,
            InterventionType.NETWORKING,
        }
    ),
    PGORVariableCode.R: frozenset(
        {
            InterventionType.SOCIAL_SUPPORT,
            InterventionType.TREATMENT,
            InterventionType.RISK_REDUCTION,
            InterventionType.STABILIZATION,
        }
    ),
}


def validate_prescription_output(
    *,
    output: dict[str, JsonValue],
    feature_package: FeaturePackage,
    diagnosis_id: UUID,
) -> None:
    payload = feature_package.provider_payload()
    bottlenecks_raw = payload.get("pgor.bottleneck_variables")
    if not isinstance(bottlenecks_raw, list):
        raise PrescriptionGenerationError("PRESCRIPTION_BOTTLENECKS_MISSING")

    bottlenecks: set[PGORVariableCode] = set()
    for raw in cast(list[object], bottlenecks_raw):
        if not isinstance(raw, str):
            continue
        try:
            bottlenecks.add(PGORVariableCode(raw))
        except ValueError:
            continue
    if not bottlenecks:
        raise PrescriptionGenerationError("PRESCRIPTION_BOTTLENECKS_INVALID")

    expected_intensity = payload.get("prescription.intensity_score")
    if not isinstance(expected_intensity, str):
        raise PrescriptionGenerationError("PRESCRIPTION_INTENSITY_MISSING")
    if output.get("intensity_score") != expected_intensity:
        raise PrescriptionGenerationError("PRESCRIPTION_INTENSITY_MISMATCH")

    available_feature_keys = set(payload)
    expected_diagnosis_ref = f"diagnosis:{diagnosis_id}"
    items = output.get("items")
    if not isinstance(items, list) or not items:
        raise PrescriptionGenerationError("PRESCRIPTION_ITEMS_INVALID")

    ranks: set[int] = set()
    for raw_item in cast(list[object], items):
        if not isinstance(raw_item, dict):
            raise PrescriptionGenerationError("PRESCRIPTION_ITEM_INVALID")
        item = cast(dict[str, object], raw_item)
        target_raw = item.get("target_variable")
        intervention_raw = item.get("intervention_type")
        rank = item.get("priority_rank")
        feature_refs = item.get("supporting_feature_refs")
        diagnosis_refs = item.get("diagnosis_refs")

        try:
            target = PGORVariableCode(target_raw) if isinstance(target_raw, str) else None
        except ValueError:
            target = None
        try:
            intervention = (
                InterventionType(intervention_raw)
                if isinstance(intervention_raw, str)
                else None
            )
        except ValueError:
            intervention = None

        if target is None or target not in bottlenecks:
            raise PrescriptionGenerationError("PRESCRIPTION_TARGET_NOT_BOTTLENECK")
        if intervention is None or intervention not in INTERVENTIONS_BY_TARGET[target]:
            raise PrescriptionGenerationError(
                "PRESCRIPTION_INTERVENTION_NOT_SOURCE_MATRIX"
            )
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            raise PrescriptionGenerationError("PRESCRIPTION_PRIORITY_INVALID")
        if rank in ranks:
            raise PrescriptionGenerationError("PRESCRIPTION_PRIORITY_DUPLICATE")
        ranks.add(rank)

        if not isinstance(feature_refs, list) or not feature_refs:
            raise PrescriptionGenerationError("PRESCRIPTION_GROUNDING_FAILED")
        for ref in cast(list[object], feature_refs):
            if not isinstance(ref, str) or ref not in available_feature_keys:
                raise PrescriptionGenerationError("PRESCRIPTION_GROUNDING_FAILED")

        if not isinstance(diagnosis_refs, list):
            raise PrescriptionGenerationError("PRESCRIPTION_DIAGNOSIS_REF_MISSING")
        if expected_diagnosis_ref not in cast(list[object], diagnosis_refs):
            raise PrescriptionGenerationError("PRESCRIPTION_DIAGNOSIS_REF_MISSING")


def materialize_prescription_items(
    *,
    prescription_id: UUID,
    output: dict[str, JsonValue],
    machine_proposed: bool,
    id_factory,
) -> tuple[PrescriptionItem, ...]:
    raw_items = output.get("items")
    if not isinstance(raw_items, list):
        raise PrescriptionGenerationError("PRESCRIPTION_ITEMS_INVALID")

    items: list[PrescriptionItem] = []
    for raw_item in cast(list[object], raw_items):
        if not isinstance(raw_item, dict):
            raise PrescriptionGenerationError("PRESCRIPTION_ITEM_INVALID")
        item = cast(dict[str, object], raw_item)

        code = item.get("code")
        title = item.get("title")
        rationale = item.get("rationale")
        target = item.get("target_variable")
        intervention = item.get("intervention_type")
        priority = item.get("priority_rank")
        criteria = item.get("success_criteria")
        schedule = item.get("review_schedule")
        if not all(isinstance(value, str) for value in (code, title, rationale, target, intervention)):
            raise PrescriptionGenerationError("PRESCRIPTION_ITEM_INVALID")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise PrescriptionGenerationError("PRESCRIPTION_PRIORITY_INVALID")
        if not isinstance(criteria, list) or not isinstance(schedule, dict):
            raise PrescriptionGenerationError("PRESCRIPTION_ITEM_INVALID")

        schedule_object = cast(dict[str, object], schedule)
        review_after_days = schedule_object.get("review_after_days")
        review_rationale = schedule_object.get("rationale")
        if (
            not isinstance(review_after_days, int)
            or isinstance(review_after_days, bool)
            or not isinstance(review_rationale, str)
        ):
            raise PrescriptionGenerationError("PRESCRIPTION_REVIEW_SCHEDULE_INVALID")

        criteria_values = tuple(
            value for value in cast(list[object], criteria) if isinstance(value, str)
        )
        if len(criteria_values) != len(criteria):
            raise PrescriptionGenerationError("PRESCRIPTION_SUCCESS_CRITERIA_INVALID")

        items.append(
            PrescriptionItem(
                id=id_factory(),
                prescription_id=prescription_id,
                source_code=cast(str, code),
                intervention_type=InterventionType(cast(str, intervention)),
                target_pgor_variable=PGORVariableCode(cast(str, target)),
                priority=priority,
                current_value=None,
                target_value=None,
                success_criteria=criteria_values,
                review_after_days=review_after_days,
                review_rationale=review_rationale,
                rationale=cast(str, rationale),
                title=cast(str, title),
                status=PrescriptionItemStatus.ACCEPTED,
                machine_proposed=machine_proposed,
            )
        )
    return tuple(items)
