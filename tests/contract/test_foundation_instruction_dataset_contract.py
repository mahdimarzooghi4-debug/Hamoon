from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("training/foundation/v1")


def _load(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_foundation_pack_is_draft_synthetic_and_not_runtime_eligible() -> None:
    manifest = _load("manifest.json")

    assert manifest["status"] == "APPROVED_SOURCE_ONLY"
    assert manifest["approval_state"] == "HUMAN_APPROVED_SOURCE"
    assert manifest["runtime_training_eligible"] is False
    assert manifest["human_review_required"] is False
    assert manifest["human_approval"]["status"] == "APPROVED"
    assert manifest["human_approval"]["scope"] == "FOUNDATION_SOURCE_CONTENT"
    assert manifest["contains_production_household_data"] is False
    assert manifest["contains_hidden_chain_of_thought"] is False

    governance = manifest["governance"]
    assert isinstance(governance, dict)
    assert governance["controlled_import_required_before_training"] is True
    assert governance["fabricate_learning_signal_ids"] is False
    assert governance["automatic_approval_forbidden"] is True
    assert governance["automatic_promotion_forbidden"] is True
    assert governance["evaluation_example_reuse_forbidden"] is True


def test_foundation_behavior_contract_preserves_hamoon_safety_boundaries() -> None:
    contract = _load("behavior_contract.json")
    rules = {
        item["id"]
        for item in contract["rules"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    assert {
        "USE_SUPPLIED_VERSIONED_FEATURES_ONLY",
        "NO_PGOR_RECALCULATION",
        "UNKNOWN_STAYS_UNKNOWN",
        "CONFLICT_DO_NOT_GUESS",
        "GROUND_OBSERVABLE_CLAIMS",
        "NO_CAUSAL_UPGRADE",
        "PROPOSAL_NOT_DECISION",
        "NO_PROVIDER_SELECTION_OR_DISPATCH",
        "STRUCTURED_OUTPUT_ONLY",
        "EVALUATION_SEPARATION",
    } <= rules


def test_foundation_diagnosis_examples_are_grounded_and_human_reviewed() -> None:
    dataset = _load("diagnosis.json")
    assert dataset["task_class"] == "DIAGNOSIS"
    assert dataset["status"] == "DRAFT_SOURCE_ONLY"
    assert dataset["contains_production_household_data"] is False
    assert dataset["contains_hidden_chain_of_thought"] is False

    examples = dataset["examples"]
    assert isinstance(examples, list)
    assert len(examples) == 12

    for example in examples:
        assert isinstance(example, dict)
        input_payload = example["input_payload"]
        target = example["target_payload"]
        assert isinstance(input_payload, dict)
        assert isinstance(target, dict)
        assert target["schema_version"] == "diagnosis-v1"
        assert target["review_flags"] == ["HUMAN_REVIEW_REQUIRED"]
        assert set(input_payload["pgor.data_quality_flags"]) <= {
            "HAS_UNRESOLVED_OBSERVATION"
        }

        for item in target["items"]:
            for ref in item["supporting_feature_refs"]:
                assert ref in input_payload


def test_foundation_outcome_examples_never_claim_causality() -> None:
    dataset = _load("outcome_interpretation.json")
    assert dataset["task_class"] == "OUTCOME_INTERPRETATION"
    assert dataset["status"] == "DRAFT_SOURCE_ONLY"
    assert dataset["contains_production_household_data"] is False
    assert dataset["contains_hidden_chain_of_thought"] is False

    examples = dataset["examples"]
    assert isinstance(examples, list)
    assert len(examples) == 12

    for example in examples:
        assert isinstance(example, dict)
        input_payload = example["input_payload"]
        target = example["target_payload"]
        assert isinstance(input_payload, dict)
        assert isinstance(target, dict)
        assert input_payload["policy.causal_claim_allowed"] is False
        assert target["schema_version"] == "outcome-interpretation-v1"
        assert target["causal_claim"] is False
        assert "HUMAN_REVIEW_REQUIRED" in target["review_flags"]
        for ref in target["supporting_feature_refs"]:
            assert ref in input_payload


def test_foundation_examples_do_not_reuse_current_evaluation_case_ids() -> None:
    diagnosis = _load("diagnosis.json")
    outcome = _load("outcome_interpretation.json")
    foundation_ids = {
        item["example_id"]
        for dataset in (diagnosis, outcome)
        for item in dataset["examples"]
    }

    eval_ids: set[str] = set()
    for path in (
        Path("evaluation/diagnosis/v1/dataset.json"),
        Path("evaluation/outcome/v1/dataset.json"),
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))
        eval_ids.update(item["case_id"] for item in payload["cases"])

    assert foundation_ids.isdisjoint(eval_ids)


def test_prescription_foundation_is_explicitly_deferred_not_fabricated() -> None:
    manifest = _load("manifest.json")
    deferred = {
        item["task_class"]: item["reason"]
        for item in manifest["deferred_tasks"]
    }
    assert "PRESCRIPTION" in deferred
    assert "review_schedule" in deferred["PRESCRIPTION"]
    assert "success_criteria" in deferred["PRESCRIPTION"]
