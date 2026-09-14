from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from textual.content import Content
from textual.widgets import Static

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import (
    CandidateIdentityRecord,
    CandidateRecord,
    CandidateStatus,
    EvidenceDescriptorRecord,
    GateOutcome,
    GateResult,
    RacePolicy,
    RunRecord,
    RunStatus,
    RunStrategy,
    TaskRecord,
)
from omnipanel.run_views import RunFreshness, RunObservation
from omnipanel.services import ApplicationServices
from omnipanel.storage import StateStore
from omnipanel.ui.app import OperatorApp

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _evidence() -> EvidenceDescriptorRecord:
    return EvidenceDescriptorRecord.model_validate(_fixture()["evidence"])


def _candidate(candidate_id: str, status: CandidateStatus) -> CandidateRecord:
    evidence_ids = ("evidence-junit-001",) if status is CandidateStatus.ELIGIBLE else ()
    gate_results = (
        (
            GateResult(
                gate_id="schema-roundtrip",
                outcome=GateOutcome.PASS,
                evidence_ids=evidence_ids,
            ),
        )
        if status is CandidateStatus.ELIGIBLE
        else ()
    )
    return CandidateRecord(
        candidate=CandidateIdentityRecord(
            candidate_id=candidate_id,
            task_id="OP-002",
            worker_id=f"worker-{candidate_id}",
        ),
        status=status,
        gate_results=gate_results,
        evidence_ids=evidence_ids,
    )


def _race() -> RunRecord:
    return RunRecord(
        run_id="run-race-ui",
        task_id="OP-002",
        master_id="master-ui",
        strategy=RunStrategy.RACE,
        candidate_ids=("candidate-a", "candidate-b"),
        status=RunStatus.RUNNING,
        race_policy=RacePolicy.FIRST_VALID_FREE,
        selected_candidate_id="candidate-a",
        evidence_ids=("evidence-junit-001",),
    )


def _single() -> RunRecord:
    return RunRecord(
        run_id="run-single-ui",
        task_id="OP-002",
        master_id="master-ui",
        strategy=RunStrategy.SINGLE,
        candidate_ids=("candidate-a",),
        status=RunStatus.COMPLETED,
        selected_candidate_id="candidate-a",
        evidence_ids=("evidence-junit-001",),
    )


def _plain(app: OperatorApp, selector: str) -> str:
    visual = app.query_one(selector, Static).visual
    assert isinstance(visual, Content)
    return visual.plain


def _seed(services: ApplicationServices) -> None:
    services.put_record(_task())
    services.put_record(_evidence())
    services.put_record(_candidate("candidate-a", CandidateStatus.ELIGIBLE))
    services.put_record(_candidate("candidate-b", CandidateStatus.RUNNING))
    services.put_record(_race())
    services.put_record(_single())


@pytest.mark.asyncio
async def test_mouse_run_and_candidate_navigation_exposes_adjudication_state(
    tmp_path: Path,
) -> None:
    config = AppConfig(data_dir=(tmp_path / "run-ui").absolute())
    observed = datetime(2026, 9, 14, 1, 0, tzinfo=UTC)
    observations = (
        RunObservation(
            run_id="run-race-ui",
            state=RunFreshness.STALE,
            observed_at=observed,
            started_at=observed - timedelta(minutes=3),
            last_event_at=observed - timedelta(seconds=45),
            provider_id="provider-test",
        ),
        RunObservation(
            run_id="run-race-ui",
            candidate_id="candidate-a",
            state=RunFreshness.LIVE,
            observed_at=observed,
            provider_id="provider-test",
            model_provider_id="openai",
            model_id="gpt-5.6-sol",
        ),
    )
    with StateStore(config) as store:
        services = ApplicationServices(store)
        _seed(services)
        app = OperatorApp(config, services, run_observations=observations)
        async with app.run_test(size=(160, 36)) as pilot:
            assert await pilot.click("#nav-runs")
            body = _plain(app, "#panel-body")
            assert "run=run-race-ui" in body
            assert "phase=running  [STALE]" in body
            assert "selection=provisional:candidate-a NOT-ACCEPTED" in body
            assert "model=openai/gpt-5.6-sol" in body
            assert "schema-roundtrip" in body
            assert "evidence-junit-001" in body

            assert await pilot.click("#candidate-next")
            body = _plain(app, "#panel-body")
            assert "Candidate detail: candidate-b" in body
            assert "> candidate-b" in body
            assert "provider=unknown" in body

            assert await pilot.click("#run-next")
            body = _plain(app, "#panel-body")
            assert "run=run-single-ui" in body
            assert "selection=accepted:candidate-a" in body
            assert "[HISTORICAL]" in body


@pytest.mark.asyncio
async def test_reopen_reconstructs_durable_run_and_marks_live_context_indeterminate(
    tmp_path: Path,
) -> None:
    config = AppConfig(data_dir=(tmp_path / "run-reconnect").absolute())
    with StateStore(config) as store:
        services = ApplicationServices(store)
        _seed(services)
        first = OperatorApp(config, services)
        async with first.run_test(size=(120, 30)) as pilot:
            await pilot.press("3")
            assert "run=run-race-ui" in _plain(first, "#panel-body")
            assert "[INDETERMINATE]" in _plain(first, "#panel-body")
            await pilot.press("q")

    with StateStore(config) as reopened_store:
        reopened_services = ApplicationServices(reopened_store)
        second = OperatorApp(config, reopened_services)
        async with second.run_test(size=(120, 30)) as pilot:
            await pilot.press("3")
            body = _plain(second, "#panel-body")
            assert "run=run-race-ui" in body
            assert "selection=provisional:candidate-a NOT-ACCEPTED" in body
            assert "live observation unavailable" in body
            assert "provider=unknown (not inferred from worker/model identity)" in body
