"""Synthetic-only fixtures. No home configuration or live components are used."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_state_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    folder = tmp_path / "operator settings 東京"
    folder.mkdir()
    path = folder / "omnipanel.toml"
    path.write_text(
        'schema_version = 1\ndata_dir = "state with spaces 東京"\nlog_level = "WARNING"\n',
        encoding="utf-8",
    )
    return path
