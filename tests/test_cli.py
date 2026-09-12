import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from omnipanel import __version__
from omnipanel.cli import main


def test_default_help_does_not_load_config(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--config", "missing.toml"]) == 0
    assert "bootstrap" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("flag", ["--help", "--version"])
def test_information_flags_do_not_load_config(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as result:
        main(["--config", "missing.toml", flag])
    assert result.value.code == 0
    assert "omnipanel" in capsys.readouterr().out.lower()


def test_status_json_is_lossless_and_does_not_create_state(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = set(config_file.parent.iterdir())
    assert main(["--config", str(config_file), "status"]) == 0
    output = capsys.readouterr()
    value = json.loads(output.out)
    assert output.out.isascii()
    assert output.err == ""
    assert value == {
        "version": __version__,
        "mode": "bootstrap",
        "execution_enabled": False,
        "data_dir": str(config_file.parent / "state with spaces 東京"),
        "log_level": "WARNING",
    }
    assert set(config_file.parent.iterdir()) == before


def test_cli_override(
    config_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "override 東京"
    assert main(["--config", str(config_file), "--data-dir", str(target), "status"]) == 0
    assert json.loads(capsys.readouterr().out)["data_dir"] == str(target)
    assert not target.exists()


def test_config_error_has_nonzero_exit_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "secret.toml"
    path.write_text('token = "SENTINEL_SECRET"', encoding="utf-8")
    assert main(["--config", str(path), "status"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "unsupported fields" in output.err
    assert "SENTINEL_SECRET" not in output.err
    assert "Traceback" not in output.err


def test_tui_requires_interactive_terminal(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["tui"]) == 2
    assert "interactive terminal" in capsys.readouterr().err


def test_unknown_command_rejected() -> None:
    with pytest.raises(SystemExit) as result:
        main(["run"])
    assert result.value.code == 2


def test_abbreviated_option_rejected() -> None:
    with pytest.raises(SystemExit) as result:
        main(["--data", "somewhere", "status"])
    assert result.value.code == 2


def test_module_entry_point_from_outside_checkout(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "omnipanel", "status"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(result.stdout)["execution_enabled"] is False
    assert not list(tmp_path.iterdir())
