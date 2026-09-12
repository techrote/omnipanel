"""Executable import boundary checks, not a substitute for independent review."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import omnipanel


def test_core_entry_points_run_when_textual_import_is_blocked(tmp_path: Path) -> None:
    source = r"""
import importlib.abc
import json
import sys

class NoTextual(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "textual" or fullname.startswith("textual."):
            raise AssertionError("Core tried to import Textual")
        return None

sys.meta_path.insert(0, NoTextual())
import omnipanel
import omnipanel.domain
import omnipanel.config
import omnipanel.__main__
from omnipanel.cli import main
assert not any(name.startswith("textual") for name in sys.modules)
assert main(["status"]) == 0
"""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert '"execution_enabled": false' in result.stdout
    assert not list(tmp_path.iterdir())


def test_textual_imports_are_confined_to_presentation() -> None:
    root = Path(omnipanel.__file__).parent
    for path in root.rglob("*.py"):
        if "ui" in path.relative_to(root).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert all(not name.startswith("textual") for name in names), str(path)


def test_no_worker_or_live_network_operations_in_bootstrap() -> None:
    root = Path(omnipanel.__file__).parent
    forbidden = {"subprocess", "socket", "requests", "httpx", "ctypes", "multiprocessing"}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not (forbidden & {name.split(".")[0] for name in names}), str(path)
