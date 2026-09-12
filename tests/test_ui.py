"""Headless Textual startup tests; these do not claim OP-007 completion."""

from pathlib import Path

import pytest
from textual.content import Content
from textual.widgets import Button, Static

from omnipanel.config import AppConfig
from omnipanel.ui.app import BootstrapApp


@pytest.mark.asyncio
async def test_mouse_close_is_available_and_creates_no_state(tmp_path: Path) -> None:
    target = tmp_path / "[bold]literal 東京[/bold]"
    app = BootstrapApp(AppConfig(data_dir=target))
    async with app.run_test(size=(80, 24)) as pilot:
        assert app.query_one("#close-dashboard", Button).label.plain == "Close dashboard"
        rendered = app.query_one("#settings", Static).visual
        assert isinstance(rendered, Content)
        expected = f"State path (not created): {target}\nConfigured log level: INFO"
        assert rendered.plain == expected
        assert not rendered.spans
        assert await pilot.click("#close-dashboard")
    assert not target.exists()
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (40, 12), (120, 40)])
async def test_keyboard_exit_at_different_terminal_sizes(
    tmp_path: Path, size: tuple[int, int]
) -> None:
    app = BootstrapApp(AppConfig(data_dir=tmp_path / "unused-state"))
    async with app.run_test(size=size) as pilot:
        await pilot.press("q")
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_reopening_dashboard_preserves_existing_synthetic_file(tmp_path: Path) -> None:
    sentinel = tmp_path / "synthetic-evidence.txt"
    sentinel.write_text("inert fixture, not a real run", encoding="utf-8")
    for _ in range(2):
        app = BootstrapApp(AppConfig(data_dir=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("q")
    assert sentinel.read_text(encoding="utf-8") == "inert fixture, not a real run"
    assert set(tmp_path.iterdir()) == {sentinel}
