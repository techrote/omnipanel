from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omnipanel.domain.contracts import (
    CancellationKind,
    CancellationOutcome,
    CandidateIdentityRecord,
    CandidateRecord,
    CandidateStatus,
    RunRecord,
    RunStatus,
    RunStrategy,
    SalvageLevel,
    TaskRecord,
)
from omnipanel.run_views import RunFreshness, RunObservation, render_run_detail
from omnipanel.services import ApplicationSnapshot, ResourceSummary

ROOT = Path(__file__).parents[1]
OP002_FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"
MATRIX_FIXTURE = ROOT / "tests" / "fixtures" / "op009_run_view_matrix.json"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_load(OP002_FIXTURE)["task"])


def _candidate(candidate_status: CandidateStatus) -> CandidateRecord:
    cancellation = None
    if candidate_status is CandidateStatus.CANCELLED:
        cancellation = CancellationOutcome(
            candidate_id="candidate-a",
            kind=CancellationKind.POLICY,
            salvage_level=SalvageLevel.MINIMAL,
            salvage_evidence_ids=("evidence-junit-001",),
        )
    return CandidateRecord(
        candidate=CandidateIdentityRecord(
            candidate_id="candidate-a",
            task_id="OP-002",
            worker_id="worker-a",
        ),
        status=candidate_status,
        cancellation=cancellation,
    )


def _snapshot(run: RunRecord, candidate: CandidateRecord) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        projects=(),
        metaissues=(),
        tasks=(_task(),),
        dag_edges=(),
        runs=(run,),
        candidates=(candidate,),
        evidence=(),
        model_identities=(),
        models=(),
        policies=(),
        resources=ResourceSummary(
            total=0,
            reserved=0,
            active=0,
            released=0,
            indeterminate=0,
            cpu_millicores=0,
            memory_mib=0,
            storage_mib=0,
            gpu_count=0,
        ),
    )


SCENARIOS = _load(MATRIX_FIXTURE)["scenarios"]
assert isinstance(SCENARIOS, list)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: str(item["name"]))
def test_run_view_fixture_matrix(scenario: dict[str, object]) -> None:
    run_status = RunStatus(str(scenario["run_status"]))
    candidate_status = CandidateStatus(str(scenario["candidate_status"]))
    run = RunRecord(
        run_id=f"run-{scenario['name']}",
        task_id="OP-002",
        master_id="master-test",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=run_status,
    )
    freshness_value = scenario["freshness"]
    observations: tuple[RunObservation, ...] = ()
    if freshness_value is not None:
        freshness = RunFreshness(str(freshness_value))
        observed_at = datetime(2026, 9, 14, 1, 20, tzinfo=UTC)
        observations = (
            RunObservation(
                run_id=run.run_id,
                state=freshness,
                observed_at=observed_at,
            ),
            RunObservation(
                run_id=run.run_id,
                candidate_id="candidate-a",
                state=freshness,
                observed_at=observed_at,
            ),
        )

    text = render_run_detail(
        _snapshot(run, _candidate(candidate_status)),
        observations=observations,
    )

    assert str(scenario["expected_run_marker"]) in text
    assert str(scenario["expected_candidate_text"]) in text
    if candidate_status is CandidateStatus.CANCELLED:
        assert "Cancellation: kind=policy salvage=minimal" in text
        assert "evidence-junit-001: MISSING DESCRIPTOR" in text
