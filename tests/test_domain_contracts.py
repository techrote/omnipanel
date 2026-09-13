from __future__ import annotations

import copy
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from omnipanel.domain import contracts as schema


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "op002_examples.json"


@pytest.fixture(scope="module")
def examples() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture_name,model_type",
    [
        ("project", schema.ProjectRecord),
        ("metaissue", schema.MetaissueRecord),
        ("task", schema.TaskRecord),
        ("model_identity", schema.ModelIdentityRecord),
        ("model_assessment", schema.ModelAssessmentRecord),
        ("master", schema.MasterIdentityRecord),
        ("candidate_identity", schema.CandidateIdentityRecord),
        ("evidence", schema.EvidenceDescriptorRecord),
        ("component_contract", schema.ComponentContractIdentityRecord),
        ("candidate_state", schema.CandidateRecord),
    ],
)
def test_checked_in_examples_round_trip(
    examples: dict[str, object],
    fixture_name: str,
    model_type: type[schema.VersionedRecord],
) -> None:
    instance = model_type.model_validate(examples[fixture_name])
    assert model_type.model_validate_json(instance.model_dump_json()) == instance


def test_collection_examples_round_trip(examples: dict[str, object]) -> None:
    edges = [schema.DagEdge.model_validate(item) for item in examples["dag_edges"]]
    workers = [schema.WorkerIdentityRecord.model_validate(item) for item in examples["workers"]]
    runs = [schema.RunRecord.model_validate(item) for item in examples["runs"]]
    cancellation = schema.CancellationOutcome.model_validate(examples["cancellation"])
    assert len(edges) == 4
    assert len(workers) == 2
    assert [run.strategy for run in runs] == [
        schema.RunStrategy.SINGLE,
        schema.RunStrategy.RACE,
        schema.RunStrategy.DIVERSITY,
    ]
    assert cancellation.salvage_level is schema.SalvageLevel.MINIMAL


@pytest.mark.parametrize("policy", list(schema.RacePolicy))
def test_all_named_race_policies_are_representable(policy: schema.RacePolicy) -> None:
    run = schema.RunRecord(
        run_id="run-policy",
        task_id="OP-021",
        master_id="master",
        strategy=schema.RunStrategy.RACE,
        race_policy=policy,
        candidate_ids=("candidate-a", "candidate-b"),
        status=schema.RunStatus.RUNNING,
    )
    assert run.race_policy is policy


@pytest.mark.parametrize("version", [2, "1", True, 1.0])
def test_unknown_or_coerced_schema_versions_fail(version: object) -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        schema.ProjectRecord.model_validate(
            {
                "schema_version": version,
                "record_type": "project",
                "project_id": "example",
                "display_name": "Example",
            }
        )


def test_extra_fields_fail_closed(examples: dict[str, object]) -> None:
    payload = copy.deepcopy(examples["task"])
    assert isinstance(payload, dict)
    payload["secret_token"] = "must-not-be-accepted"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        schema.TaskRecord.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cpu_millicores", "1000"),
        ("memory_mib", True),
        ("wall_time_seconds", 1.5),
    ],
)
def test_resource_units_are_strict(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        schema.ResourceRequest.model_validate({field: value})


def test_provider_defaults_are_fail_closed() -> None:
    request = schema.ProviderRequest()
    assert request.required_capability_handles == ()
    assert request.writable_paths == ()
    assert request.network_access is False
    assert request.isolation_required is True
    assert request.resources == schema.ResourceRequest()


def test_provider_paths_reject_controls_and_duplicates() -> None:
    with pytest.raises(ValidationError, match="control"):
        schema.ProviderRequest(writable_paths=("safe", "bad\x00path"))
    with pytest.raises(ValidationError, match="duplicates"):
        schema.ProviderRequest(writable_paths=("same", "same"))


@pytest.mark.parametrize(
    "visibility,independent",
    [
        (schema.GateVisibility.CANDIDATE_VISIBLE, True),
        (schema.GateVisibility.MASTER_ONLY, False),
    ],
)
def test_hidden_gate_is_always_separated_from_candidate(
    visibility: schema.GateVisibility,
    independent: bool,
) -> None:
    with pytest.raises(ValidationError):
        schema.AcceptanceGate(
            gate_id="hidden",
            gate_type=schema.GateType.HIDDEN_TEST,
            display_name="Hidden tests",
            visibility=visibility,
            independent_context_required=independent,
        )


def _policy(
    *,
    load_bearing: str = "tissue",
    value: str = "low",
    wall_time: str = "short",
    cost: str = "free",
    strategy: str = "single",
    race_policy: str | None = None,
    impl_reviews: int = 0,
    verification_reviews: int = 0,
    user_promotion: bool = True,
    user_decision: dict[str, object] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "load_bearing": load_bearing,
        "economics": {
            "expected_value": value,
            "expected_wall_time": wall_time,
            "marginal_cost": cost,
        },
        "strategy": strategy,
        "review": {
            "self_check_required": True,
            "independent_implementation_reviews": impl_reviews,
            "independent_verification_reviews": verification_reviews,
            "consequential_promotion_requires_user": user_promotion,
        },
    }
    if race_policy is not None:
        result["race_policy"] = race_policy
    if user_decision is not None:
        result["user_decision"] = user_decision
    return result


@pytest.mark.parametrize(
    "payload,match",
    [
        (_policy(load_bearing="stone"), "Stone"),
        (_policy(load_bearing="steel"), "Steel"),
        (_policy(load_bearing="steel", impl_reviews=1), "verification"),
        (
            _policy(
                load_bearing="steel",
                impl_reviews=1,
                verification_reviews=1,
                user_promotion=False,
            ),
            "user adjudication",
        ),
    ],
)
def test_load_bearing_review_floors(payload: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        schema.TaskPolicy.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        _policy(load_bearing="steel", impl_reviews=1, verification_reviews=1),
        _policy(value="priceless"),
        _policy(wall_time="days"),
        _policy(cost="paid"),
    ],
)
def test_mandatory_human_choices_remain_undecided_by_default(
    payload: dict[str, object],
) -> None:
    policy = schema.TaskPolicy.model_validate(payload)
    assert policy.requires_explicit_user_decision()
    assert not policy.is_execution_policy_decided()


def test_explicit_human_policy_decision_is_structured() -> None:
    policy = schema.TaskPolicy.model_validate(
        _policy(
            load_bearing="steel",
            impl_reviews=1,
            verification_reviews=1,
            user_decision={
                "decision_id": "decision-1",
                "confirmed_by": "human:operator",
                "confirmed_at": "2026-09-13T00:20:00+01:00",
            },
        )
    )
    assert policy.is_execution_policy_decided()


def test_human_policy_decision_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        schema.TaskPolicy.model_validate(
            _policy(
                user_decision={
                    "decision_id": "decision-1",
                    "confirmed_by": "human:operator",
                    "confirmed_at": "2026-09-13T00:20:00",
                }
            )
        )


@pytest.mark.parametrize(
    "payload",
    [
        _policy(strategy="race"),
        _policy(strategy="single", race_policy="ask"),
        _policy(strategy="diversity", race_policy="collect-all"),
    ],
)
def test_race_policy_cannot_be_inferred_or_leak_to_other_strategies(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        schema.TaskPolicy.model_validate(payload)


def test_metaissue_defaults_cannot_orphan_race_policy() -> None:
    with pytest.raises(ValidationError, match="race_policy"):
        schema.TaskPolicyDefaults(race_policy=schema.RacePolicy.ASK)


def test_display_text_is_not_authoritative_identity(examples: dict[str, object]) -> None:
    payload = copy.deepcopy(examples["task"])
    assert isinstance(payload, dict)
    payload["display_name"] = "OP-999 — unrelated display text"
    assert schema.TaskRecord.model_validate(payload).task_id == "OP-002"


@pytest.mark.parametrize(
    "prerequisites,match",
    [
        (["OP-002"], "itself"),
        (["OP-001", "OP-001"], "duplicates"),
    ],
)
def test_task_dependency_invariants(
    examples: dict[str, object],
    prerequisites: list[str],
    match: str,
) -> None:
    payload = copy.deepcopy(examples["task"])
    assert isinstance(payload, dict)
    payload["prerequisite_task_ids"] = prerequisites
    with pytest.raises(ValidationError, match=match):
        schema.TaskRecord.model_validate(payload)


def test_dag_self_edge_fails() -> None:
    with pytest.raises(ValidationError, match="itself"):
        schema.DagEdge(
            predecessor_task_id="OP-101",
            successor_task_id="OP-101",
        )


def test_metaissues_dag_example_is_representable(examples: dict[str, object]) -> None:
    edges = [schema.DagEdge.model_validate(item) for item in examples["dag_edges"]]
    assert {(edge.predecessor_task_id, edge.successor_task_id) for edge in edges} == {
        ("OP-101", "OP-105"),
        ("OP-102", "OP-105"),
        ("OP-103", "OP-105"),
        ("OP-104", "OP-105"),
    }


def test_model_policy_examples_are_structured(examples: dict[str, object]) -> None:
    identity = schema.ModelIdentityRecord.model_validate(examples["model_identity"])
    assessment = schema.ModelAssessmentRecord.model_validate(examples["model_assessment"])
    assert identity.ref.provider_id == "openai"
    assert identity.ref.model_id == "gpt-5.6-sol"
    assert identity.display_name == "GPT-5.6 Sol"
    assert assessment.maturity == 9
    assert any(tag.qualifiers == ("tempAvail",) for tag in assessment.tags)
    assert not hasattr(assessment, "global_rank")


@pytest.mark.parametrize(
    "state,expected",
    [
        (schema.SafetyState.ACTIVE, True),
        (schema.SafetyState.QUARANTINED, False),
        (schema.SafetyState.VERBOTEN, False),
    ],
)
def test_model_safety_state_has_fail_closed_scheduling_semantics(
    examples: dict[str, object],
    state: schema.SafetyState,
    expected: bool,
) -> None:
    payload = copy.deepcopy(examples["model_assessment"])
    assert isinstance(payload, dict)
    payload["safety_state"] = state.value
    assessment = schema.ModelAssessmentRecord.model_validate(payload)
    assert assessment.is_automatically_schedulable() is expected


def test_recent_model_window_is_bounded(examples: dict[str, object]) -> None:
    payload = copy.deepcopy(examples["model_assessment"])
    assert isinstance(payload, dict)
    payload["recent_evidence_ids"] = [f"evidence-{index}" for index in range(25)]
    with pytest.raises(ValidationError):
        schema.ModelAssessmentRecord.model_validate(payload)


def test_worker_identity_separates_authority_from_model() -> None:
    with pytest.raises(ValidationError, match="canonical"):
        schema.WorkerIdentityRecord(
            worker_id="worker-1",
            kind=schema.WorkerKind.MODEL,
            authority_class=schema.WorkerAuthorityClass.DISPOSABLE_WRITE,
        )
    with pytest.raises(ValidationError, match="must not"):
        schema.WorkerIdentityRecord(
            worker_id="worker-1",
            kind=schema.WorkerKind.DETERMINISTIC,
            authority_class=schema.WorkerAuthorityClass.TRUSTED_DETERMINISTIC,
            model=schema.ModelRef(provider_id="openai", model_id="gpt-5.6-sol"),
        )


def test_evidence_invariants(examples: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="add up"):
        schema.TestSummary(total=5, passed=4)
    payload = copy.deepcopy(examples["evidence"])
    assert isinstance(payload, dict)
    payload["created_at"] = "2026-09-13T00:20:00"
    with pytest.raises(ValidationError, match="timezone"):
        schema.EvidenceDescriptorRecord.model_validate(payload)


def test_component_contract_identity_is_structured(examples: dict[str, object]) -> None:
    identity = schema.ComponentContractIdentityRecord.model_validate(examples["component_contract"])
    assert identity.ref.component_id == "ansible"
    assert identity.ref.contract_version == "1.0"
    assert identity.source_commit == "c" * 40


@pytest.mark.parametrize(
    "kwargs,match",
    [
        (
            {"strategy": schema.RunStrategy.SINGLE, "candidate_ids": ("a", "b")},
            "exactly one",
        ),
        (
            {
                "strategy": schema.RunStrategy.RACE,
                "candidate_ids": ("a",),
                "race_policy": schema.RacePolicy.ASK,
            },
            "at least two",
        ),
        (
            {
                "strategy": schema.RunStrategy.DIVERSITY,
                "candidate_ids": ("a", "b"),
                "race_policy": schema.RacePolicy.FIRST_VALID_ALL,
            },
            "Diversity",
        ),
    ],
)
def test_run_strategy_invariants(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        schema.RunRecord(
            run_id="run-1",
            task_id="OP-101",
            master_id="master",
            status=schema.RunStatus.PLANNED,
            **kwargs,
        )


def test_selected_candidate_must_belong_to_run() -> None:
    with pytest.raises(ValidationError, match="selected"):
        schema.RunRecord(
            run_id="run-1",
            task_id="OP-101",
            master_id="master",
            strategy=schema.RunStrategy.SINGLE,
            candidate_ids=("a",),
            selected_candidate_id="b",
            status=schema.RunStatus.COMPLETED,
        )


def test_cancellation_salvage_is_explicit() -> None:
    with pytest.raises(ValidationError, match="why"):
        schema.CancellationOutcome(
            candidate_id="candidate-a",
            kind=schema.CancellationKind.POLICY,
            salvage_level=schema.SalvageLevel.NONE,
        )
    with pytest.raises(ValidationError, match="evidence"):
        schema.CancellationOutcome(
            candidate_id="candidate-a",
            kind=schema.CancellationKind.POLICY,
            salvage_level=schema.SalvageLevel.MINIMAL,
        )
    containment = schema.CancellationOutcome(
        candidate_id="candidate-a",
        kind=schema.CancellationKind.CONTAINMENT,
        salvage_level=schema.SalvageLevel.NONE,
    )
    assert containment.salvage_evidence_ids == ()


def test_contained_candidate_requires_containment_outcome() -> None:
    candidate = schema.CandidateIdentityRecord(
        candidate_id="candidate-a",
        task_id="OP-101",
        worker_id="worker",
    )
    with pytest.raises(ValidationError, match="containment"):
        schema.CandidateRecord(
            candidate=candidate,
            status=schema.CandidateStatus.CONTAINED,
            cancellation=schema.CancellationOutcome(
                candidate_id="candidate-a",
                kind=schema.CancellationKind.USER,
                salvage_level=schema.SalvageLevel.NONE,
                salvage_unavailable_reason="terminated immediately",
            ),
        )


def test_contracts_are_immutable_and_closed(examples: dict[str, object]) -> None:
    project = schema.ProjectRecord.model_validate(examples["project"])
    with pytest.raises(ValidationError, match="frozen"):
        project.display_name = "Changed"
    assert schema.TaskRecord.model_json_schema()["additionalProperties"] is False
