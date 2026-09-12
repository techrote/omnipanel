"""Read-only bootstrap entry points; no live integrations or worker execution."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from omnipanel import __version__
from omnipanel.config import ConfigError, load_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnipanel",
        description="Omnipanel bootstrap. No orchestration or execution is enabled.",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=f"Omnipanel {__version__}")
    parser.add_argument("--config", type=Path, help="explicit UTF-8 TOML configuration file")
    parser.add_argument("--data-dir", type=Path, help="state path override (not created)")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("status", help="print inert startup status as JSON")
    commands.add_parser("tui", help="open the minimal, non-executing dashboard")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        config = load_config(args.config, data_dir=args.data_dir)
    except (ConfigError, OSError, RuntimeError) as exc:
        message = str(exc) if isinstance(exc, ConfigError) else "startup paths are unavailable"
        print(f"omnipanel: {message}", file=sys.stderr)
        return 2
    if args.command == "status":
        # ASCII JSON is lossless for Unicode paths, including redirected legacy consoles.
        print(
            json.dumps(
                {
                    "version": __version__,
                    "mode": "bootstrap",
                    "execution_enabled": False,
                    "data_dir": str(config.data_dir),
                    "log_level": config.log_level.value,
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "omnipanel: tui requires an interactive terminal; use status for JSON", file=sys.stderr
        )
        return 2
    try:
        from omnipanel.ui.app import BootstrapApp
    except ModuleNotFoundError as exc:
        if exc.name != "textual":
            raise
        print(
            "omnipanel: Textual is missing; reinstall Omnipanel with its dependencies",
            file=sys.stderr,
        )
        return 3
    BootstrapApp(config).run()
    return 0
