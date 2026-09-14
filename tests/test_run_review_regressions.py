from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omnipanel.domain.contracts import (
    AcceptanceGate,
    CandidateIdentityRecord,
    CandidateRecord,
    CandidateStatus,
    EconomicDimensions,
    ExpectedValue,
    ExpectedWallTime,
    GateType,
    GateVisibility,
    LoadBearing,
    MarginalCost,
    ReviewPolicy,
    RunRecord,
    RunStatus,
    RunStrategy,
    TaskPolicy,
    TaskRecord,
)
from omnipanel.run_views import RunFreshness, RunObservation, render_run_detail
from omnipanel.services import ApplicationSnapshot, PolicyView, ResourceSummary

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _resources() -> ResourceSummary:
    return ResourceSummary(
        total=0,
        reserved=0,
        active=0,
        released=0,
        indeterminate=0,
        cpu_millicores=0,
        memory_mib=0,
        storage_mib=0,
        gpu_count=0,
    )


def _snapshot(
    run: RunRecord,
    *,
    candidates: tuple[CandidateRecord, ...] = (),
    policies: tuple[PolicyView, ...] = (),
    task: TaskRecord | None = None,
) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        projects=(),
        metaissues=(),
        tasks=((task or _task()),),
        dag_edges=(),
        runs=(run,),
        candidates=candidates,
        evidence=(),
        model_identities=(),
        models=(),
        policies=policies,
        resources=_resources(),
    )


def _completed() -> RunRecord:
    return RunRecord(
        run_id="run-completed-review",
        task_id="OP-002",
        master_id="master-review",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=RunStatus.COMPLETED,
        selected_candidate_id="candidate-a",
    )


def _candidate(status: CandidateStatus, *, task_id: str = "OP-002") -> CandidateRecord:
    return CandidateRecord(
        candidate=CandidateIdentityRecord(
            candidate_id="candidate-a",
            task_id=task_id,
            worker_id="worker-review",
        ),
        status=status,
    )


def test_completed_selection_needs_matching_eligible_candidate_state() -> None:
    run = _completed()
    missing = render_run_detail(_snapshot(run))
    assert "ACCEPTANCE-INDETERMINATE candidate-state=missing" in missing
    assert "selection=accepted" not in missing

    failed = render_run_detail(_snapshot(run, candidates=(_candidate(CandidateStatus.FAILED),)))
    assert "ACCEPTANCE-INDETERMINATE candidate-status=failed" in failed
    assert "selection=accepted" not in failed

    eligible = render_run_detail(_snapshot(run, candidates=(_candidate(CandidateStatus.ELIGIBLE),)))
    assert "selection=accepted:candidate-a" in eligible


def test_terminal_noncompleted_selection_is_not_provisional() -> None:
    run = _completed().model_copy(update={"status": RunStatus.CANCELLED})
    text = render_run_detail(_snapshot(run, candidates=(_candidate(CandidateStatus.ELIGIBLE),)))
    assert "selection=recorded:candidate-a NOT-ACCEPTED run-status=cancelled" in text
    assert "selection=provisional" not in text


def test_candidate_task_mismatch_fails_closed() -> None:
    text = render_run_detail(
        _snapshot(
            _completed(),
            candidates=(_candidate(CandidateStatus.ELIGIBLE, task_id="OP-999"),),
        )
    )
    assert "ACCEPTANCE-INDETERMINATE candidate-task=OP-999" in text
    assert "status=indeterminate:task-mismatch:OP-999" in text
    assert "state=INDETERMINATE; candidate task mismatch" in text
    assert "selection=accepted" not in text


def test_review_requirements_use_durable_policy_override() -> None:
    override = TaskPolicy(
        load_bearing=LoadBearing.STONE,
        economics=EconomicDimensions(
            expected_value=ExpectedValue.HIGH,
            expected_wall_time=ExpectedWallTime.SHORT,
            marginal_cost=MarginalCost.LOCAL,
        ),
        strategy=RunStrategy.SINGLE,
        review=ReviewPolicy(
            independent_implementation_reviews=2,
            independent_verification_reviews=3,
            consequential_promotion_requires_user=False,
        ),
    )
    text = render_run_detail(
        _snapshot(
            _completed(),
            candidates=(_candidate(CandidateStatus.ELIGIBLE),),
            policies=(PolicyView(task_id="OP-002", policy=override),),
        )
    )
    assert "implementation:2" in text
    assert "verification:3" in text
    assert "user-promotion:no" in text


def test_optional_gate_is_rendered_as_optional_not_unknown() -> None:
    optional_gate = AcceptanceGate(
        gate_id="optional-review",
        gate_type=GateType.REVIEW,
        display_name="Optional review",
        visibility=GateVisibility.MASTER_ONLY,
        required=False,
    )
    task = _task().model_copy(update={"acceptance_gates": (optional_gate,)})
    text = render_run_detail(
        _snapshot(
            _completed(),
            candidates=(_candidate(CandidateStatus.ELIGIBLE),),
            task=task,
        )
    )
    assert "optional-review: type=review" in text
    assert "required=no outcome=UNRECORDED" in text


def test_observation_rejects_temporally_impossible_timestamps() -> None:
    observed_at = datetime(2026, 9, 14, 1, 30, tzinfo=UTC)
    with pytest.raises(ValueError, match="started_at must not be later"):
        RunObservation(
            run_id="run-time",
            state=RunFreshness.LIVE,
            observed_at=observed_at,
            started_at=observed_at + timedelta(seconds=1),
        )
    with pytest.raises(ValueError, match="last_event_at must not be later"):
        RunObservation(
            run_id="run-time",
            state=RunFreshness.LIVE,
            observed_at=observed_at,
            last_event_at=observed_at + timedelta(seconds=1),
        )
