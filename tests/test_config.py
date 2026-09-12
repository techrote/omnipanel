import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from omnipanel.config import (
    MAX_CONFIG_BYTES,
    AppConfig,
    ConfigError,
    LogLevel,
    default_data_dir,
    load_config,
)


def test_defaults_are_typed_inert_and_immutable() -> None:
    config = load_config()
    assert config.data_dir.is_absolute()
    assert config.log_level is LogLevel.INFO
    assert not config.data_dir.exists()
    with pytest.raises(FrozenInstanceError):
        config.log_level = LogLevel.ERROR


def test_unicode_and_spaces_are_relative_to_config_not_cwd(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config(config_file)
    assert config.data_dir == config_file.parent / "state with spaces 東京"
    assert config.log_level is LogLevel.WARNING
    assert not config.data_dir.exists()


def test_override_is_relative_to_cwd(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config(config_file, data_dir=Path("override"))
    assert config.data_dir == tmp_path / "override"
    assert not config.data_dir.exists()


@pytest.mark.parametrize("level", list(LogLevel))
def test_log_levels(tmp_path: Path, level: LogLevel) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(f'log_level = "{level.value}"\n', encoding="utf-8")
    assert load_config(path).log_level is level


@pytest.mark.parametrize(
    "contents",
    [
        "schema_version = true",
        "schema_version = 0",
        "schema_version = 2",
        "schema_version = 1.0",
        'schema_version = "1"',
        "schema_version = []",
        "log_level = 1",
        "log_level = false",
        'log_level = "info"',
        'log_level = "SENTINEL_SECRET"',
        "data_dir = 42",
        "data_dir = false",
        "data_dir = []",
        'data_dir = ""',
        'data_dir = "   "',
        'data_dir = "bad\\npath"',
        'data_dir = "bad\\u0000path"',
        'data_dir = "bad\\u007fpath"',
        'token = "SENTINEL_SECRET"',
        '[provider]\ntoken = "SENTINEL_SECRET"',
        'log_level = "INFO"\nlog_level = "WARNING"',
        'broken = ["SENTINEL_SECRET"',
    ],
)
def test_invalid_config_rejected_without_echoing_values(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "invalid.toml"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ConfigError) as error:
        load_config(path)
    assert "SENTINEL_SECRET" not in str(error.value)


def test_invalid_config_cannot_be_hidden_by_override(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("schema_version = 2", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path, data_dir=tmp_path / "override")


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_windows_editor_utf8_bom_is_supported(tmp_path: Path, encoding: str) -> None:
    path = tmp_path / "settings.toml"
    path.write_text('data_dir = "東京"', encoding=encoding)
    assert load_config(path).data_dir == tmp_path / "東京"


def test_utf16_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text("schema_version = 1", encoding="utf-16")
    with pytest.raises(ConfigError, match="UTF-8"):
        load_config(path)


def test_missing_file_and_directory_rejected(tmp_path: Path) -> None:
    for path in [tmp_path / "missing.toml", tmp_path]:
        with pytest.raises(ConfigError, match="regular file"):
            load_config(path)


def test_size_limit(tmp_path: Path) -> None:
    path = tmp_path / "huge.toml"
    path.write_bytes(b"#" * MAX_CONFIG_BYTES)
    assert load_config(path).log_level is LogLevel.INFO
    path.write_bytes(b"#" * (MAX_CONFIG_BYTES + 1))
    with pytest.raises(ConfigError, match="64 KiB"):
        load_config(path)


def test_relative_environment_path_is_not_cwd_dependent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", "relative-local")
    monkeypatch.setenv("XDG_STATE_HOME", "relative-state")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    expected = (
        tmp_path / "AppData" / "Local" / "Omnipanel"
        if sys.platform == "win32"
        else tmp_path / ".local" / "state" / "omnipanel"
    )
    assert default_data_dir() == expected


def test_absolute_environment_path_is_used(tmp_path: Path) -> None:
    expected = (
        tmp_path / "local-app-data" / "Omnipanel"
        if sys.platform == "win32"
        else tmp_path / "xdg-state" / "omnipanel"
    )
    assert default_data_dir() == expected


def test_configuration_is_not_discovered_from_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "omnipanel.toml").write_text('token = "must not load"', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert load_config().log_level is LogLevel.INFO


def test_environment_tokens_are_not_interpolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OMNIPANEL_TOKEN", "SENTINEL_SECRET")
    path = tmp_path / "settings.toml"
    path.write_text('data_dir = "%OMNIPANEL_TOKEN%"', encoding="utf-8")
    assert load_config(path).data_dir.name == "%OMNIPANEL_TOKEN%"


def test_model_constructor_rejects_unvalidated_settings(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        AppConfig(data_dir=Path("relative"))
    with pytest.raises(ConfigError):
        AppConfig(data_dir=tmp_path, log_level="INFO")


@pytest.mark.skipif(sys.platform == "win32", reason="foreign Windows paths on POSIX")
@pytest.mark.parametrize("value", [r"C:\state", r"C:state", r"\\server\share\state"])
def test_windows_paths_are_not_silently_reinterpreted_on_posix(tmp_path: Path, value: str) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(f"data_dir = '{value}'", encoding="utf-8")
    with pytest.raises(ConfigError, match="Windows"):
        load_config(path)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows path semantics")
@pytest.mark.parametrize("value", [r"C:state", r"\state"])
def test_windows_drive_relative_paths_rejected(tmp_path: Path, value: str) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(f"data_dir = '{value}'", encoding="utf-8")
    with pytest.raises(ConfigError, match="ambiguous"):
        load_config(path)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows path semantics")
def test_native_windows_absolute_path(tmp_path: Path) -> None:
    target = tmp_path / "東京 with spaces"
    path = tmp_path / "settings.toml"
    path.write_text(f"data_dir = '{target}'", encoding="utf-8")
    assert load_config(path).data_dir == target
