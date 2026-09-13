from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.content import Content
from textual.widgets import Static

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import ProjectRecord, TaskRecord
from omnipanel.services import ApplicationServices
from omnipanel.storage import StateStore
from omnipanel.ui.app import OperatorApp

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _project() -> ProjectRecord:
    return ProjectRecord.model_validate(_fixture()["project"])


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _plain(app: OperatorApp, selector: str) -> str:
    visual = app.query_one(selector, Static).visual
    assert isinstance(visual, Content)
    return visual.plain


@pytest.mark.asyncio
async def test_mouse_navigation_reads_service_snapshot(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "operator 東京").absolute())
    with StateStore(config) as store:
        services = ApplicationServices(store)
        services.put_record(_project())
        services.put_record(_task())
        app = OperatorApp(config, services)
        async with app.run_test(size=(80, 24)) as pilot:
            assert await pilot.click("#nav-tasks")
            await pilot.pause()
            assert _plain(app, "#panel-title") == "Tasks"
            assert _task().task_id in _plain(app, "#panel-body")


@pytest.mark.asyncio
async def test_keyboard_navigation_refreshes_from_durable_services(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "keyboard-state").absolute())
    with StateStore(config) as store:
        services = ApplicationServices(store)
        app = OperatorApp(config, services)
        async with app.run_test(size=(80, 24)) as pilot:
            services.put_record(_task())
            await pilot.press("2")
            await pilot.pause()
            assert _plain(app, "#panel-title") == "Tasks"
            assert _task().display_name in _plain(app, "#panel-body")
            await pilot.press("6")
            assert _plain(app, "#panel-title") == "System"
            assert "Provider execution: disabled" in _plain(app, "#panel-body")


@pytest.mark.asyncio
async def test_blocker_remains_visible_across_panel_changes(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "blocker-state").absolute())
    with StateStore(config) as store:
        app = OperatorApp(config, ApplicationServices(store))
        async with app.run_test(size=(80, 24)) as pilot:
            app.show_blocker("Ansible contract is incompatible")
            assert _plain(app, "#status-banner") == "BLOCKER: Ansible contract is incompatible"
            await pilot.press("4")
            assert _plain(app, "#panel-title") == "Evidence"
            assert _plain(app, "#status-banner") == "BLOCKER: Ansible contract is incompatible"


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(40, 12), (50, 14), (120, 40)])
async def test_navigation_is_usable_at_small_and_large_terminal_sizes(
    tmp_path: Path, size: tuple[int, int]
) -> None:
    config = AppConfig(data_dir=(tmp_path / f"size-{size[0]}x{size[1]}").absolute())
    with StateStore(config) as store:
        app = OperatorApp(config, ApplicationServices(store))
        async with app.run_test(size=size) as pilot:
            await pilot.press("5")
            assert _plain(app, "#panel-title") == "Models"
            assert "No durable model records" in _plain(app, "#panel-body")
            assert _plain(app, "#status-banner").startswith("BLOCKER:")


@pytest.mark.asyncio
async def test_reopening_ui_preserves_underlying_application_state(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "reopen-state").absolute())
    with StateStore(config) as store:
        services = ApplicationServices(store)
        services.put_record(_project())
        for _ in range(2):
            app = OperatorApp(config, services)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.press("1")
                assert "Projects: 1" in _plain(app, "#panel-body")
                await pilot.press("q")
        assert services.snapshot().projects == (_project(),)
