# Development and startup

OP-001 provides the Python package and inert startup proof. OP-002 adds UI-independent,
versioned domain contracts only; it does not implement orchestration effects, durable
state, component negotiation or the OP-007 operator shell. Read `AGENT_CONTEXT.md`,
the assigned issue and `SCHEMA_CONTRACTS.md` before extending these boundaries.

## Windows 11 / Windows Terminal

Use an installed Python 3.12, 3.13 or 3.14. From the repository root, paste each
complete block into PowerShell. Activation is unnecessary; every command names the
virtual environment interpreter explicitly.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m omnipanel --version
.\.venv\Scripts\python.exe -m omnipanel status
.\.venv\Scripts\python.exe -m omnipanel tui
```

The installed console command is `.\.venv\Scripts\omnipanel.exe`. For an ordinary
non-editable installation, use `python -m pip install .` with the intended interpreter
instead. A release has not been published to PyPI; do not substitute `pip install omnipanel`.

## Linux

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m omnipanel --version
.venv/bin/python -m omnipanel status
.venv/bin/python -m omnipanel tui
```

The console command is `.venv/bin/omnipanel`. `tui` requires an interactive terminal;
`status` is safe to redirect. No arguments print help. Global options precede the
subcommand. Close the dashboard with its mouse button or `q`.

## Explicit configuration

```powershell
.\.venv\Scripts\python.exe -m omnipanel --config examples/omnipanel.toml status
.\.venv\Scripts\python.exe -m omnipanel --data-dir "C:\Omnipanel state" status
```

The only supported startup TOML fields are `schema_version = 1`, `data_dir` and
`log_level`. This startup configuration schema is separate from the OP-002 domain-record
schemas. Unknown fields, unsupported versions, incorrect types, malformed input and
files over 64 KiB are errors. UTF-8, including an optional BOM, is accepted; UTF-16 is
not. `log_level` is an inert typed setting, not an activated logging subsystem.

A configuration file is loaded only when explicitly named. There is no current-directory
or home-directory discovery. A file-relative `data_dir` is relative to that file's parent;
a CLI override is relative to the working directory. `~` expands to the home directory;
other environment-variable tokens are not expanded. An override does not excuse a
malformed configuration file. Windows drive-relative and root-relative paths are
rejected as ambiguous. Windows drive/UNC paths are rejected on a non-Windows host.

The default state path is `%LOCALAPPDATA%/Omnipanel` on Windows, with a home/AppData/Local
fallback, or `$XDG_STATE_HOME/omnipanel` on Linux, with a home/.local/state fallback.
Relative environment values are ignored. Choosing or displaying a path creates no
state directory or database. This host-side configuration is not an execution-provider
contract, credential store, permission policy or capability grant.

JSON status uses ASCII escapes that round-trip Unicode paths, including when redirected
to a legacy Windows console. TUI path text is rendered literally, not as markup.
Exit codes: 0 for success/help, 2 for argument/configuration/noninteractive-TUI errors,
3 if Textual is missing from an incorrectly installed environment.

## Domain schema development

OP-002 contracts live in `src/omnipanel/domain/contracts.py`; their identity, versioning,
policy and scope invariants are documented in `docs/SCHEMA_CONTRACTS.md`. Synthetic
representative records live in `tests/fixtures/op002_examples.json` and are exercised by
`tests/test_domain_contracts.py`.

Top-level domain records use explicit `schema_version = 1` and reject future/unknown
versions rather than coercing them. Models are immutable and reject unknown fields.
Provider/resource defaults are fail-closed: no network, writable paths or capability
handles are granted by default and isolation remains required. These are data contracts,
not durable storage or authority activation.

## Verification commands

Run from the repository root after the editable development installation:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m build
$wheel = Get-ChildItem dist/omnipanel-*.whl | Select-Object -Last 1
.\.venv\Scripts\python.exe scripts/check_distribution.py $wheel.FullName
```

On Linux replace the interpreter with `.venv/bin/python`; the final command is
`.venv/bin/python scripts/check_distribution.py dist/omnipanel-*.whl`.
Start from a clean `dist` directory when comparing releases. Formatting repairs use
`python -m ruff format .`; inspect the resulting diff before committing.

The distribution probe creates a temporary clean virtual environment outside the
checkout, installs the wheel **with dependencies**, runs `pip check`, validates metadata,
module/console entry points and `py.typed`, and exercises the actual Textual UI through
`App.run_test`. It needs package-index access. No live component is contacted by Omnipanel.
The UI suite deliberately fails collection if Textual is absent; it does not silently skip.

Foundation CI covers Windows and Linux on Python 3.12/3.13/3.14. Its JUnit reports,
resolved dependency lists and built distributions are retained as GitHub Actions
artifacts for 14 days. Preserve significant acceptance evidence in `docs/evidence/`;
CI artifacts are not the permanent evidence store. Synthetic UI reopen tests do not
prove durable execution/recovery, which belongs to later issues.

## Dependency rationale and update policy

Runtime dependencies are intentionally small and direct:

- Pydantic 2.13.5 provides strict typed validation, immutable/closed models and JSON
  schema/serialization for the OP-002 domain-contract boundary.
- Textual 8.2.8 remains the selected presentation framework from OP-001 and is not
  imported by the domain contracts.

Configuration/CLI otherwise use the standard library. OP-002 does not add a database,
HTTP client, worker framework, component adapter or credential library.
`setuptools==82.0.1` provides the conventional PEP 517/518/621 build. Development tools
are pytest 9.0.2, pytest-asyncio 1.3.0, Ruff 0.16.7, mypy 2.3.1 and build 1.6.1.

Direct dependency pins and SHA-pinned GitHub Actions make update choices explicit;
this is **not a complete transitive lockfile or an offline reproducibility claim**.
CI retains the actual resolved dependency set per platform. Review dependency updates
and rerun the full matrix before changing pins. Do not bypass a failing check by
weakening assertions, skipping tests or silently broadening supported contracts.

## Completion boundary

OP-001 has completed its required automated acceptance, independent Stone review,
merge and post-merge reconciliation. The OP-001 evidence set remains in
`docs/evidence/` and issue #10.

OP-002 / issue #11 is now in implementation/self-verification in draft PR #57. Its
current candidate has passed the full automated Windows/Linux × Python 3.12/3.13/3.14
matrix at the tested implementation head. Because OP-002 is **Steel**, automated green
checks and implementer evidence are not completion: separate independent implementation
review, independent verification review and explicit user adjudication before
consequential promotion/merge remain mandatory. Do not start OP-003 or weaken
`workflow.json`, issue bindings or load-bearing policy to bypass those gates.
