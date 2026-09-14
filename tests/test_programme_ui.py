from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.content import Content
from textual.widgets import Static

from omnipanel.config import AppConfig
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
from omnipanel.services import ApplicationServices
from omnipanel.storage import RecordNotFoundError, StateStore
from omnipanel.ui.app import OperatorApp
from omnipanel.workflow import TaskEvidence, WorkflowEngine

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _plain(app: OperatorApp, selector: str) -> str:
    visual = app.query_one(selector, Static).visual
    assert isinstance(visual, Content)
    return visual.plain


@pytest.mark.asyncio
async def test_policy_editor_persists_explicit_mandatory_choice(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "policy-ui").absolute())
    with StateStore(config) as store:
        services = ApplicationServices(store)
        services.put_record(_task())
        app = OperatorApp(config, services)
        async with app.run_test(size=(180, 30)) as pilot:
            assert await pilot.click("#nav-tasks")
            assert await pilot.click("#policy-expected-value")
            assert "value=priceless" in _plain(app, "#panel-body")
            assert "USER DECISION REQUIRED" in _plain(app, "#panel-body")
            assert await pilot.click("#policy-apply")
            await pilot.pause()
            saved = services.snapshot().policies
            assert len(saved) == 1
            assert saved[0].policy.economics.expected_value is ExpectedValue.PRICELESS
            assert saved[0].policy.user_decision is not None

    with StateStore(config) as reopened:
        saved = reopened.load_policy("OP-002")
        assert saved.economics.expected_value is ExpectedValue.PRICELESS
        assert saved.user_decision is not None


@pytest.mark.asyncio
async def test_bulk_defaults_skip_mandatory_tasks(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "bulk-ui").absolute())
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
        update={"task_id": "OP-003", "display_name": "Optional task", "policy": optional_policy}
    )
    with StateStore(config) as store:
        services = ApplicationServices(store)
        services.put_record(mandatory)
        services.put_record(optional)
        app = OperatorApp(config, services)
        async with app.run_test(size=(220, 30)) as pilot:
            assert await pilot.click("#nav-tasks")
            assert await pilot.click("#policy-bulk-defaults")
            body = _plain(app, "#panel-body")
            assert "mandatory decisions skipped: OP-002" in body
            assert services.store.load_policy("OP-003") == optional_policy
            with pytest.raises(RecordNotFoundError):
                services.store.load_policy("OP-002")


@pytest.mark.asyncio
async def test_project_and_metaissue_navigation_moves_task_scope(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "navigation-ui").absolute())
    base = _task()
    tasks = (
        base.model_copy(
            update={
                "task_id": "OP-101",
                "project_id": "proj-a",
                "parent_metaissue_id": "OP-M101",
                "display_name": "Project A / Metaissue A",
            }
        ),
        base.model_copy(
            update={
                "task_id": "OP-102",
                "project_id": "proj-a",
                "parent_metaissue_id": "OP-M102",
                "display_name": "Project A / Metaissue B",
            }
        ),
        base.model_copy(
            update={
                "task_id": "OP-103",
                "project_id": "proj-b",
                "parent_metaissue_id": "OP-M103",
                "display_name": "Project B / Metaissue C",
            }
        ),
    )
    with StateStore(config) as store:
        services = ApplicationServices(store)
        for task in tasks:
            services.put_record(task)
        app = OperatorApp(config, services)
        async with app.run_test(size=(260, 32)) as pilot:
            assert await pilot.click("#nav-tasks")
            assert "project=proj-a metaissue=OP-M101 task=OP-101" in _plain(app, "#panel-body")
            assert await pilot.click("#metaissue-next")
            assert "project=proj-a metaissue=OP-M102 task=OP-102" in _plain(app, "#panel-body")
            assert await pilot.click("#project-next")
            assert "project=proj-b metaissue=OP-M103 task=OP-103" in _plain(app, "#panel-body")


@pytest.mark.asyncio
async def test_workflow_readiness_is_visible_without_becoming_ui_authority(
    tmp_path: Path,
) -> None:
    config = AppConfig(data_dir=(tmp_path / "readiness-ui").absolute())
    engine = WorkflowEngine.from_paths(
        ROOT / "docs" / "workflow.json", ROOT / "docs" / "issue-bindings.json"
    )
    with StateStore(config) as store:
        app = OperatorApp(
            config,
            ApplicationServices(store),
            workflow=engine,
            task_evidence=(TaskEvidence(task_id="OP-008", issue_closed=True),),
        )
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.press("2")
            body = _plain(app, "#panel-body")
            assert "OP-008" in body
            assert "github=CLOSED evidence=UNPROVEN" in body
            assert "prerequisite lacks reconciled terminal evidence" in body
