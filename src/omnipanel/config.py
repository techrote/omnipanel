"""Small, inert startup configuration; not an execution or authorization policy.

No configuration discovery, directory creation, logging setup, environment-variable
interpolation, provider connection or credential loading occurs in this module.
"""

from __future__ import annotations

import os
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath

MAX_CONFIG_BYTES = 64 * 1024
CONFIG_VERSION = 1


class ConfigError(ValueError):
    """An explicit startup configuration could not be used safely."""


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Host-side startup settings only; no raw secrets or execution controls."""

    data_dir: Path
    log_level: LogLevel = LogLevel.INFO

    def __post_init__(self) -> None:
        if not isinstance(self.data_dir, Path) or not self.data_dir.is_absolute():
            raise ConfigError("data_dir must be an absolute native path")
        if not isinstance(self.log_level, LogLevel):
            raise ConfigError("log_level must be a LogLevel")


def default_data_dir() -> Path:
    """Choose, but never create, the operator's native state location.

    Relative environment paths are ignored, not interpreted relative to the cwd.
    The provider/domain model does not depend on these operator-host conventions.
    """
    if sys.platform == "win32":
        fallback = Path.home() / "AppData" / "Local"
        raw = os.environ.get("LOCALAPPDATA", "")
        suffix = "Omnipanel"
    else:
        fallback = Path.home() / ".local" / "state"
        raw = os.environ.get("XDG_STATE_HOME", "")
        suffix = "omnipanel"
    base = Path(raw) if raw and Path(raw).is_absolute() else fallback
    return base / suffix


def _absolute_path(raw: str, base: Path) -> Path:
    if not raw.strip() or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise ConfigError("data_dir must be a nonempty path without control characters")
    windows = PureWindowsPath(raw)
    if sys.platform != "win32" and windows.drive:
        raise ConfigError("Windows drive/UNC data_dir requires a Windows operator host")
    if sys.platform == "win32" and (windows.drive or windows.root) and not windows.is_absolute():
        raise ConfigError("drive-relative and root-relative data_dir paths are ambiguous")
    try:
        path = Path(raw).expanduser()
        return (path if path.is_absolute() else base / path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        # Never echo the raw value: rejected input may accidentally contain a secret.
        raise ConfigError("data_dir could not be resolved") from exc


def _read_config(path: Path) -> Mapping[str, object]:
    try:
        if not path.is_file():
            raise ConfigError("configuration must be an existing regular file")
        with path.open("rb") as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
    except OSError as exc:
        raise ConfigError("configuration file could not be read") from exc
    if len(raw) > MAX_CONFIG_BYTES:
        raise ConfigError("configuration exceeds the 64 KiB limit")
    try:
        # Accept the UTF-8 BOM commonly written by Windows editors, not UTF-16.
        return tomllib.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("configuration must contain valid UTF-8 TOML") from exc


def load_config(path: Path | None = None, *, data_dir: Path | None = None) -> AppConfig:
    """Load only an explicitly named file, then apply the explicit path override.

    File-relative paths are anchored to the config file's directory. CLI overrides
    are anchored to the current directory. Invalid files fail even with overrides.
    Nothing is written and no policy is activated.
    """
    values: Mapping[str, object] = {} if path is None else _read_config(path)
    if set(values) - {"schema_version", "data_dir", "log_level"}:
        raise ConfigError("configuration contains unsupported fields")
    version = values.get("schema_version", CONFIG_VERSION)
    if type(version) is not int or version != CONFIG_VERSION:
        raise ConfigError("unsupported configuration schema_version; expected integer 1")
    level = values.get("log_level", "INFO")
    if not isinstance(level, str):
        raise ConfigError("log_level must be an uppercase level name")
    try:
        log_level = LogLevel(level)
    except ValueError as exc:
        raise ConfigError("log_level must be DEBUG, INFO, WARNING, ERROR or CRITICAL") from exc
    raw_dir = values.get("data_dir")
    if raw_dir is not None and not isinstance(raw_dir, str):
        raise ConfigError("data_dir must be a string")
    base = Path.cwd() if path is None else path.absolute().parent
    directory = (
        _absolute_path(str(default_data_dir()), Path.cwd())
        if raw_dir is None
        else _absolute_path(raw_dir, base)
    )
    if data_dir is not None:
        directory = _absolute_path(str(data_dir), Path.cwd())
    return AppConfig(data_dir=directory, log_level=log_level)
