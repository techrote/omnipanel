from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from omnipanel.domain.contracts import (
    EconomicDimensions,
    ExpectedValue,
    ExpectedWallTime,
    LoadBearing,
    MarginalCost,
    ReviewPolicy,
    RunStrategy,
    TaskPolicy,
    TaskRecord,
)
from omnipanel.programme import (
    build_bulk_optional_policy_plan,
    confirm_policy,
    cycle_policy,
    render_programme,
)
from omnipanel.services import ApplicationSnapshot, ResourceSummary
from omnipanel.workflow import TaskEvidence, WorkflowEngine

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _empty_snapshot(*, tasks: tuple[TaskRecord, ...] = ()) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        projects=(),
        metaissues=(),
        tasks=tasks,
        dag_edges=(),
        runs=(),
        candidates=(),
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


def test_policy_edit_invalidates_stale_decision_and_confirms_mandatory_choice() -> None:
    original = _task().policy
    assert original.economics.expected_value is ExpectedValue.HIGH
    assert original.user_decision is not None

    draft = cycle_policy(original, "expected-value")
    assert draft.economics.expected_value is ExpectedValue.PRICELESS
    assert draft.user_decision is None
    assert not draft.is_execution_policy_decided()

    confirmed = confirm_policy(
        "OP-002",
        draft,
        confirmed_by="human:operator",
        confirmed_at=datetime(2026, 9, 13, 22, 0, tzinfo=timezone.utc),
    )
    assert confirmed.user_decision is not None
    assert confirmed.is_execution_policy_decided()


def test_cycle_to_steel_enforces_minimum_review_topology() -> None:
    policy = TaskPolicy(
        load_bearing=LoadBearing.STONE,
        economics=EconomicDimensions(
            expected_value=ExpectedValue.MEDIUM,
            expected_wall_time=ExpectedWallTime.SHORT,
            marginal_cost=MarginalCost.LOCAL,
        ),
        strategy=RunStrategy.SINGLE,
        review=ReviewPolicy(independent_implementation_reviews=1),
    )
    updated = cycle_policy(policy, "load-bearing")
    assert updated.load_bearing is LoadBearing.STEEL
    assert updated.review.independent_implementation_reviews >= 1
    assert updated.review.independent_verification_reviews >= 1
    assert updated.review.consequential_promotion_requires_user
    assert updated.user_decision is None


def test_bulk_defaults_never_cross_mandatory_decision_boundary() -> None:
    mandatory = _task()
    optional_policy = TaskPolicy(
        load_bearing=LoadBearing.STONE,
        economics=EconomicDimensions(
            expected_value=ExpectedValue.HIGH,
            expected_wall_time=ExpectedWallTime.SHORT,
            marginal_cost=MarginalCost.LOCAL,
        ),
        strategy=RunStrategy.SINGLE,
        review=ReviewPolicy(independent_implementation_reviews=1),
    )
    optional = mandatory.model_copy(
        update={
            "task_id": "OP-003",
            "display_name": "Optional example",
            "policy": optional_policy,
        }
    )
    plan = build_bulk_optional_policy_plan(_empty_snapshot(tasks=(mandatory, optional)))
    assert tuple(task_id for task_id, _ in plan.updates) == ("OP-003",)
    assert plan.mandatory_task_ids == ("OP-002",)


def test_programme_projection_distinguishes_closed_from_reconciled_evidence() -> None:
    engine = WorkflowEngine.from_paths(
        ROOT / "docs" / "workflow.json", ROOT / "docs" / "issue-bindings.json"
    )
    text = render_programme(
        _empty_snapshot(),
        workflow=engine,
        evidence=(TaskEvidence(task_id="OP-008", issue_closed=True),),
    )
    op008 = next(line for line in text.splitlines() if "OP-008" in line and "github=" in line)
    assert "github=CLOSED evidence=UNPROVEN" in op008
    assert "[BLOCKED]" in op008


def test_large_durable_dag_projection_keeps_stable_ids_visible() -> None:
    base = _task()
    tasks = tuple(
        base.model_copy(
            update={
                "task_id": f"OP-{1000 + index}",
                "display_name": f"Synthetic task {index}",
                "prerequisite_task_ids": (),
            }
        )
        for index in range(250)
    )
    text = render_programme(
        _empty_snapshot(tasks=tasks),
        selected_task_id=tasks[-1].task_id,
    )
    assert "OP-1000" in text
    assert "OP-1249" in text
    assert f"selected={tasks[-1].task_id}" in text
