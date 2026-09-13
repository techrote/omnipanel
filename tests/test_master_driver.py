from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omnipanel.domain.contracts import (
    MasterIdentityRecord,
    ProviderRequest,
    RunStrategy,
    TaskRecord,
    WorkerIdentityRecord,
)
from omnipanel.master_driver import (
    FakeMasterDriver,
    MasterAdjudication,
    MasterAvailability,
    MasterLifecycle,
    MasterLifecycleError,
    MasterLifecycleErrorCode,
    MasterProposal,
    MasterProvenance,
    ProposedSubtask,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _master(
    master_id: str = "master-local", driver_id: str = "fake-master"
) -> MasterIdentityRecord:
    payload = dict(_fixture()["master"])
    payload["master_id"] = master_id
    payload["driver_id"] = driver_id
    return MasterIdentityRecord.model_validate(payload)


def _proposal(**updates: object) -> MasterProposal:
    payload: dict[str, object] = {
        "proposal_id": "proposal-op017-001",
        "task_id": "OP-002",
        "strategy": "single",
        "candidate_count": 1,
        "provider_request": {
            "required_capability_handles": [],
            "resources": {
                "cpu_millicores": 1000,
                "memory_mib": 2048,
                "wall_time_seconds": 1800,
            },
            "writable_paths": ["tests"],
            "network_access": False,
            "isolation_required": True,
        },
        "decomposition": [
            {"step_id": "inspect", "display_name": "Inspect contract", "depends_on": []},
            {
                "step_id": "implement",
                "display_name": "Implement change",
                "depends_on": ["inspect"],
            },
        ],
        "rationale": "Use one bounded candidate under the authoritative task policy",
    }
    payload.update(updates)
    return MasterProposal.model_validate(payload)


def _adjudication(**updates: object) -> MasterAdjudication:
    payload: dict[str, object] = {
        "contract_id": "derive-from-request",
        "recommendation": "select",
        "selected_candidate_id": "candidate-a",
        "evidence_ids": ["evidence-junit-001"],
        "rationale": "Candidate cleared the supplied evidence gate",
    }
    payload.update(updates)
    return MasterAdjudication.model_validate(payload)


def _driver(
    proposal: MasterProposal | None = None,
    adjudication: MasterAdjudication | None = None,
    *,
    identity: MasterIdentityRecord | None = None,
    availability: MasterAvailability = MasterAvailability.AVAILABLE,
) -> FakeMasterDriver:
    return FakeMasterDriver(
        identity or _master(),
        proposal or _proposal(),
        adjudication or _adjudication(),
        availability=availability,
    )


def test_fake_master_drives_complete_task_contract_lifecycle() -> None:
    task = _task()
    result = MasterLifecycle(_driver()).run(
        task,
        context="large conversation content is represented only by digest",
        conversation_ref="chat://op017/example",
        candidate_ids=("candidate-a",),
        evidence_ids=("evidence-junit-001",),
    )

    assert result.contract.task_id == task.task_id
    assert result.contract.master.master_id == "master-local"
    assert result.contract.strategy is RunStrategy.SINGLE
    assert result.contract.provider_request.writable_paths == ("tests",)
    assert result.contract.acceptance_gate_ids == tuple(
        gate.gate_id for gate in task.acceptance_gates
    )
    assert (
        result.intake.provenance.context_sha256
        != "large conversation content is represented only by digest"
    )
    assert result.adjudication.selected_candidate_id == "candidate-a"
    assert result.adjudication_request.promotion_requires_user


def test_master_identity_remains_distinct_from_worker_identity() -> None:
    master = _master()
    workers = _fixture()["workers"]
    assert isinstance(workers, list)
    worker = WorkerIdentityRecord.model_validate(workers[0])
    assert isinstance(master, MasterIdentityRecord)
    assert isinstance(worker, WorkerIdentityRecord)
    assert master.master_id != worker.worker_id
    assert master.driver_id == "fake-master"


def test_driver_replacement_preserves_normalized_domain_shape() -> None:
    task = _task()
    first = MasterLifecycle(_driver(identity=_master("master-a", "driver-a"))).run(
        task,
        context="same task context",
        candidate_ids=("candidate-a",),
        evidence_ids=("evidence-junit-001",),
    )
    second = MasterLifecycle(_driver(identity=_master("master-b", "driver-b"))).run(
        task,
        context="same task context",
        candidate_ids=("candidate-a",),
        evidence_ids=("evidence-junit-001",),
    )
    assert type(first.contract) is type(second.contract)
    assert first.contract.task_id == second.contract.task_id == task.task_id
    assert first.contract.strategy == second.contract.strategy == task.policy.strategy
    assert first.contract.provider_request == second.contract.provider_request
    assert first.contract.master.master_id != second.contract.master.master_id


def test_normalize_rejects_provenance_for_another_driver() -> None:
    lifecycle = MasterLifecycle(_driver(identity=_master("master-a", "driver-a")))
    foreign_provenance = MasterProvenance(
        driver_id="driver-b",
        context_sha256="0" * 64,
    )

    with pytest.raises(MasterLifecycleError) as caught:
        lifecycle.normalize(_task(), _proposal(), foreign_provenance)

    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.PROVENANCE_MISMATCH


def test_master_cannot_target_another_task() -> None:
    proposal = _proposal(task_id="OP-017")
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(proposal)).run(
            _task(),
            context="ctx",
            candidate_ids=("candidate-a",),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.TASK_MISMATCH


def test_master_cannot_override_authoritative_strategy() -> None:
    proposal = _proposal(strategy="race", candidate_count=2)
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(proposal)).run(
            _task(),
            context="ctx",
            candidate_ids=("candidate-a", "candidate-b"),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.STRATEGY_CONFLICT


def test_explicit_user_policy_remains_authoritative() -> None:
    task = _task()
    task = task.model_copy(
        update={"policy": task.policy.model_copy(update={"user_decision": None})}
    )
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver()).run(
            task,
            context="ctx",
            candidate_ids=("candidate-a",),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.USER_POLICY_REQUIRED


@pytest.mark.parametrize(
    ("provider_request", "expected"),
    [
        (
            ProviderRequest(
                required_capability_handles=("network.admin",), writable_paths=("tests",)
            ),
            MasterLifecycleErrorCode.CAPABILITY_BROADENED,
        ),
        (
            ProviderRequest(writable_paths=("src",), resources={"cpu_millicores": 1000}),
            MasterLifecycleErrorCode.WRITE_SCOPE_BROADENED,
        ),
        (
            ProviderRequest(writable_paths=("tests",), network_access=True),
            MasterLifecycleErrorCode.NETWORK_BROADENED,
        ),
        (
            ProviderRequest(writable_paths=("tests",), isolation_required=False),
            MasterLifecycleErrorCode.ISOLATION_WEAKENED,
        ),
        (
            ProviderRequest(
                writable_paths=("tests",),
                resources={"cpu_millicores": 3000, "memory_mib": 2048},
            ),
            MasterLifecycleErrorCode.RESOURCE_BROADENED,
        ),
    ],
)
def test_master_cannot_broaden_task_provider_boundary(
    provider_request: ProviderRequest, expected: MasterLifecycleErrorCode
) -> None:
    proposal = _proposal(provider_request=provider_request.model_dump(mode="json"))
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(proposal)).run(
            _task(),
            context="ctx",
            candidate_ids=("candidate-a",),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is expected


def test_master_cannot_relax_specific_provider_class() -> None:
    task = _task()
    task = task.model_copy(
        update={
            "provider_request": task.provider_request.model_copy(
                update={"provider_class": "trusted-local"}
            )
        }
    )
    proposal = _proposal()
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(proposal)).run(
            task,
            context="ctx",
            candidate_ids=("candidate-a",),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.PROVIDER_CLASS_BROADENED


def test_unavailable_master_fails_before_proposal_use() -> None:
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(availability=MasterAvailability.UNAVAILABLE)).run(
            _task(),
            context="ctx",
            candidate_ids=("candidate-a",),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.MASTER_UNAVAILABLE


def test_actual_candidate_count_must_match_normalized_proposal() -> None:
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver()).run(
            _task(),
            context="ctx",
            candidate_ids=("candidate-a", "candidate-b"),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.CANDIDATE_COUNT_INVALID


def test_candidate_set_must_be_unique_before_adjudication() -> None:
    proposal = _proposal(strategy="single", candidate_count=2)
    task = _task()
    task = task.model_copy(
        update={"policy": task.policy.model_copy(update={"strategy": RunStrategy.RACE})}
    )
    proposal = proposal.model_copy(update={"strategy": RunStrategy.RACE})
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(proposal)).run(
            task,
            context="ctx",
            candidate_ids=("candidate-a", "candidate-a"),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.CANDIDATE_SET_INVALID


def test_adjudication_cannot_select_unknown_candidate() -> None:
    adjudication = _adjudication(selected_candidate_id="candidate-z")
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(adjudication=adjudication)).run(
            _task(),
            context="ctx",
            candidate_ids=("candidate-a",),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.UNKNOWN_CANDIDATE


def test_adjudication_cannot_invent_evidence() -> None:
    adjudication = _adjudication(evidence_ids=["evidence-not-supplied"])
    with pytest.raises(MasterLifecycleError) as caught:
        MasterLifecycle(_driver(adjudication=adjudication)).run(
            _task(),
            context="ctx",
            candidate_ids=("candidate-a",),
            evidence_ids=("evidence-junit-001",),
        )
    assert caught.value.diagnostic.code is MasterLifecycleErrorCode.EVIDENCE_MISMATCH


def test_decomposition_rejects_cycles_and_unknown_dependencies() -> None:
    with pytest.raises(ValidationError, match="unknown step"):
        MasterProposal(
            proposal_id="bad-unknown",
            task_id="OP-002",
            strategy="single",
            candidate_count=1,
            provider_request=_task().provider_request,
            decomposition=(
                ProposedSubtask(step_id="a", display_name="A", depends_on=("missing",)),
            ),
            rationale="invalid dependency",
        )
    with pytest.raises(ValidationError, match="acyclic"):
        MasterProposal(
            proposal_id="bad-cycle",
            task_id="OP-002",
            strategy="single",
            candidate_count=1,
            provider_request=_task().provider_request,
            decomposition=(
                ProposedSubtask(step_id="a", display_name="A", depends_on=("b",)),
                ProposedSubtask(step_id="b", display_name="B", depends_on=("a",)),
            ),
            rationale="cycle",
        )
