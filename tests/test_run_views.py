from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omnipanel.domain.contracts import (
    CandidateIdentityRecord,
    CandidateRecord,
    CandidateStatus,
    GateOutcome,
    GateResult,
    ProjectRecord,
    RacePolicy,
    RunRecord,
    RunStatus,
    RunStrategy,
    TaskRecord,
)
from omnipanel.run_views import RunFreshness, RunObservation, render_run_detail
from omnipanel.services import ApplicationSnapshot, ResourceSummary

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _candidate(candidate_id: str, status: CandidateStatus) -> CandidateRecord:
    return CandidateRecord(
        candidate=CandidateIdentityRecord(
            candidate_id=candidate_id,
            task_id="OP-002",
            worker_id=f"worker-{candidate_id}",
        ),
        status=status,
    )


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
    candidates: tuple[CandidateRecord, ...],
    task: TaskRecord | None = None,
) -> ApplicationSnapshot:
    evidence = ()
    if "evidence" in _fixture():
        from omnipanel.domain.contracts import EvidenceDescriptorRecord

        evidence = (EvidenceDescriptorRecord.model_validate(_fixture()["evidence"]),)
    return ApplicationSnapshot(
        projects=(ProjectRecord.model_validate(_fixture()["project"]),),
        metaissues=(),
        tasks=((task or _task()),),
        dag_edges=(),
        runs=(run,),
        candidates=candidates,
        evidence=evidence,
        model_identities=(),
        models=(),
        policies=(),
        resources=_resources(),
    )


def test_race_selection_is_provisional_until_completed() -> None:
    candidates = (
        _candidate("candidate-a", CandidateStatus.ELIGIBLE),
        _candidate("candidate-b", CandidateStatus.RUNNING),
    )
    running = RunRecord(
        run_id="run-race",
        task_id="OP-002",
        master_id="master-test",
        strategy=RunStrategy.RACE,
        candidate_ids=("candidate-a", "candidate-b"),
        status=RunStatus.RUNNING,
        race_policy=RacePolicy.FIRST_VALID_FREE,
        selected_candidate_id="candidate-a",
    )
    text = render_run_detail(_snapshot(running, candidates=candidates))
    assert "selection=provisional:candidate-a NOT-ACCEPTED" in text
    assert "[INDETERMINATE]" in text

    completed = running.model_copy(update={"status": RunStatus.COMPLETED})
    text = render_run_detail(_snapshot(completed, candidates=candidates))
    assert "selection=accepted:candidate-a" in text
    assert "NOT-ACCEPTED" not in text
    assert "[HISTORICAL]" in text


def test_gate_and_evidence_drill_down_preserves_provenance() -> None:
    evidence_id = "evidence-junit-001"
    candidate = _candidate("candidate-a", CandidateStatus.ELIGIBLE).model_copy(
        update={
            "gate_results": (
                GateResult(
                    gate_id="schema-roundtrip",
                    outcome=GateOutcome.PASS,
                    evidence_ids=(evidence_id,),
                ),
            ),
            "evidence_ids": (evidence_id,),
        }
    )
    run = RunRecord(
        run_id="run-single",
        task_id="OP-002",
        master_id="master-test",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=RunStatus.COMPLETED,
        selected_candidate_id="candidate-a",
        evidence_ids=(evidence_id,),
    )
    text = render_run_detail(_snapshot(run, candidates=(candidate,)))
    assert "schema-roundtrip: type=public-test" in text
    assert "outcome=pass" in text
    assert evidence_id in text
    assert "github://techrote/omnipanel/actions/runs/123/artifacts/456" in text
    assert "tests=64/67 pass" in text
    assert "implementation:1" in text
    assert "verification:1" in text


def test_live_observations_use_canonical_provider_and_model_ids() -> None:
    run = RunRecord(
        run_id="run-observed",
        task_id="OP-002",
        master_id="master-test",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=RunStatus.RUNNING,
    )
    now = datetime(2026, 9, 14, 0, 30, tzinfo=UTC)
    observations = (
        RunObservation(
            run_id=run.run_id,
            state=RunFreshness.STALE,
            observed_at=now,
            started_at=now - timedelta(minutes=4, seconds=9),
            last_event_at=now - timedelta(seconds=31),
            provider_id="exec-provider-1",
        ),
        RunObservation(
            run_id=run.run_id,
            candidate_id="candidate-a",
            state=RunFreshness.DISCONNECTED,
            observed_at=now,
            provider_id="exec-provider-1",
            model_provider_id="openai",
            model_id="gpt-5.6-sol",
        ),
    )
    text = render_run_detail(
        _snapshot(run, candidates=(_candidate("candidate-a", CandidateStatus.RUNNING),)),
        observations=observations,
    )
    assert "[STALE]" in text
    assert "elapsed=4m09s" in text
    assert "provider=exec-provider-1" in text
    assert "model=openai/gpt-5.6-sol" in text
    assert "freshness=disconnected" in text


def test_missing_candidate_state_is_explicitly_indeterminate() -> None:
    run = RunRecord(
        run_id="run-missing-state",
        task_id="OP-002",
        master_id="master-test",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=RunStatus.RUNNING,
    )
    text = render_run_detail(_snapshot(run, candidates=()))
    assert "status=indeterminate:no-durable-candidate-record" in text
    assert "durable candidate state is missing" in text


def test_observation_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="observed_at must include a timezone"):
        RunObservation(
            run_id="run-naive",
            state=RunFreshness.LIVE,
            observed_at=datetime(2026, 9, 14, 1, 0),
        )
