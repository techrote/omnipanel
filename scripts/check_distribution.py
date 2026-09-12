"""Install a built wheel into a clean environment outside the source tree.

Run after ``python -m build``. Unlike a --no-deps smoke check, this installs actual
runtime dependencies and exercises the real Textual startup path. Network access
may be required by pip. It never invokes an execution provider.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, timeout=180)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        parser.error("supply an existing built wheel")
    with tempfile.TemporaryDirectory(prefix="omnipanel package 東京 ") as temporary:
        root = Path(temporary)
        environment = root / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        binaries = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binaries / ("python.exe" if os.name == "nt" else "python")
        console = binaries / ("omnipanel.exe" if os.name == "nt" else "omnipanel")
        run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheel)], root)
        run([str(python), "-m", "pip", "check"], root)
        run([str(python), "-I", "-m", "omnipanel", "--version"], root)
        run([str(console), "--version"], root)
        run([str(console), "status"], root)
        probe = r"""
import asyncio
from importlib.metadata import version
from pathlib import Path

import omnipanel
from omnipanel.config import AppConfig
from omnipanel.ui.app import BootstrapApp

assert omnipanel.__version__ == version("omnipanel")
location = Path(omnipanel.__file__)
assert "site-packages" in location.parts, location
assert (location.parent / "py.typed").is_file()
target = Path.cwd() / "state not created"

async def check():
    app = BootstrapApp(AppConfig(data_dir=target))
    async with app.run_test(size=(80, 24)) as pilot:
        assert await pilot.click("#close-dashboard")
    assert not target.exists()

asyncio.run(check())
print("Clean wheel: import, metadata, console/module entry points and Textual PASS")
"""
        run([str(python), "-I", "-c", probe], root)


if __name__ == "__main__":
    main()
