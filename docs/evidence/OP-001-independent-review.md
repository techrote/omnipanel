# OP-001 independent Stone implementation review

Review date: 2026-09-13 (Europe/London)
Repository: `techrote/omnipanel`
Stable task: `OP-001`
GitHub issue: #10
Pull request: #56
Reviewed base: `a27d37a2bf11508da45caa8d217fb504aa61f119`
Reviewed implementation commit: `977c968731721a86411c60fca51c42ec2c833fc5`
Reviewed evidence head: `4765a6bead8eb27b23598067f9664b1a2bc36f44`
Primary recorded implementation CI: run `34725770901`
Fresh evidence-head CI: run `34726012863`

This is the independent Stone implementation review required by OP-001. It is not a second implementation pass, an architectural redesign, a merge action, or authorization to begin OP-002. This report was added only after the implementation/evidence head above had been reviewed; the publication commit containing this file is review evidence, not a change to the reviewed implementation.

## Verdict

**PASS — OP-001 satisfies Stone independent review**

The implementation is a trustworthy minimal Python 3.12+ Omnipanel foundation within the scope of issue #10. I found no blocking or non-blocking implementation finding that should delay OP-001. The source, tests, packaging, CI and retained evidence are mutually consistent, and the implementation preserves the programme's architecture, trust, dependency and scope boundaries.

## Findings

No blocking findings.

No non-blocking findings requiring follow-up were identified. Several deliberately narrow verification techniques were treated only as supporting evidence rather than as proof by themselves; they were cross-checked against source structure, clean-distribution behavior, raw CI artifacts and the canonical programme documents.

The absence of a manual Windows 11 / Windows Terminal session is a verification limitation, not a defect in OP-001. The implementation explicitly describes hosted Windows CI and headless Textual checks as narrower evidence and does not claim manual terminal qualification.

## Repository-state reconciliation

- PR #56 was open, mergeable, not merged, and still targeted `main` at review time.
- `main` still pointed to the recorded base `a27d37a2bf11508da45caa8d217fb504aa61f119`; it had not independently acquired overlapping OP-001 implementation.
- PR #56's implementation/evidence head was the recorded `4765a6bead8eb27b23598067f9664b1a2bc36f44` before this review report was published.
- Issue #10 remained the OP-001 contract and remained open.
- Issue #11 remained OP-002 with prerequisite OP-001. No OP-002 implementation branch or separate OP-002 pull request was found.
- The PR changed 27 bounded OP-001 files before this review report. `docs/workflow.json`, stable-ID bindings, canonical architecture/trust/orchestration documents and downstream task contracts were not modified.
- Comparison of `977c968731721a86411c60fca51c42ec2c833fc5` to `4765a6bead8eb27b23598067f9664b1a2bc36f44` showed only `docs/evidence/OP-001.md` and `docs/evidence/OP-001-ci.json`; the recorded final implementation tree was therefore not altered by the evidence-only commit.

## Scope and diff assessment

The implementation is appropriately bounded to OP-001:

- conventional `src/omnipanel` package and package metadata;
- immutable typed startup configuration;
- minimal read-only CLI/status behavior;
- lazy-loaded minimal Textual bootstrap;
- test harness and boundary tests;
- Linux/Windows CI;
- clean-wheel verification;
- development/startup documentation and OP-001 evidence.

I found no premature implementation of OP-002 task/run/domain schemas, OP-003 durable state/migrations, OP-004 application services, OP-005 DAG/readiness, OP-006 compatibility machinery, OP-007 production TUI architecture, worker scheduling, provider execution, credential management or live component calls. `src/omnipanel/domain/__init__.py` remains intentionally empty apart from a boundary docstring identifying OP-002 as the owner of future core schemas.

## Packaging and dependency assessment

`pyproject.toml` is coherent with the OP-001 contract:

- build backend: `setuptools.build_meta` with direct build requirement `setuptools==82.0.1`;
- package discovery from `src`;
- `requires-python = ">=3.12"` and classifiers for 3.12/3.13/3.14;
- one runtime dependency, `textual==8.2.8`;
- development-only build/type/test/lint tools separated under the `dev` extra;
- console entry point `omnipanel = omnipanel.cli:main`;
- package version sourced from `omnipanel._version.__version__`;
- `py.typed` explicitly packaged.

The direct pins are intentionally not represented as a full transitive lockfile, which is consistent with the issue/programme rather than a missing requirement.

I independently inspected a built wheel retained from the Windows 3.12 job. Its contents were limited to the expected Omnipanel package modules, `py.typed` and distribution metadata; source-tree tests/docs were not required for import. Wheel metadata matched version `0.1.0.dev1`, Python `>=3.12`, the Textual runtime dependency and the console entry point.

`scripts/check_distribution.py` genuinely creates a temporary virtual environment outside the checkout, installs the wheel with runtime dependencies, runs `pip check`, uses isolated `-I` module startup, exercises the installed console command, checks metadata/`py.typed`, and runs a real Textual `App.run_test` mouse-close path. It does not accidentally validate an editable source checkout.

## Core/UI boundary assessment

The dependency direction is correct in both structure and behavior:

- package/core imports do not import Textual;
- `cli.py` imports only version/configuration at module import time;
- Textual is imported lazily only for the `tui` command;
- Textual imports are confined to `src/omnipanel/ui/app.py`;
- the domain package has no presentation dependency;
- the bootstrap UI displays inert configuration and has no execution/service ownership semantics.

The boundary subprocess test that blocks Textual imports is useful supporting evidence, but this conclusion is based on direct source inspection as well rather than treating that test as sufficient by itself.

## Configuration assessment

The startup configuration is deliberately small and typed. Review found:

- immutable/slotted `AppConfig` with an absolute native `Path` and strict `LogLevel` enum;
- explicit configuration-file loading only, with no implicit current-directory/home discovery;
- strict supported fields and schema version;
- deterministic precedence: defaults -> explicit file -> explicit CLI data-dir override;
- malformed/unsupported explicit configuration remains an error even when an override is supplied;
- UTF-8 and UTF-8 BOM accepted, UTF-16 rejected;
- 64 KiB size bound;
- file-relative and CLI-relative path semantics documented and tested;
- Windows drive/root-relative ambiguity rejected on Windows;
- Windows drive/UNC input rejected rather than reinterpreted on POSIX;
- Unicode/spaces tested;
- relative `LOCALAPPDATA` / `XDG_STATE_HOME` values ignored rather than made cwd-relative;
- no environment-variable interpolation inside configuration values;
- rejected input values are not echoed in configuration errors;
- configuration resolution performs no state-directory/database creation.

The module reads only the environment variables needed to choose the documented default host-side state location. It does not harvest credentials or activate authority.

## CLI and bootstrap UI assessment

The CLI behavior is suitable for OP-001:

- no command prints help and returns success without forcing configuration parsing;
- `--help` and `--version` do not load invalid explicit configuration;
- `status` returns read-only JSON with `execution_enabled: false`;
- invalid arguments/configuration use nonzero exit status without a traceback/secret echo;
- `tui` rejects non-interactive stdin/stdout;
- a missing Textual dependency is diagnosed separately from unrelated import failures;
- no status/default invocation creates state.

The Textual application is deliberately minimal. It has a mouse-close button and `q` keyboard exit, uses a scroll container for variable terminal sizes, renders dynamic path text with `markup=False`, and explicitly states that closing the view is not a stop-job action. There is no scheduler or durable execution object for the UI to own.

The earlier first-run `Static.markup` test defect was corrected appropriately. The current test checks public rendered `Content`, exact `.plain` text and absence of styling spans for a path containing both Rich-like markup syntax and Unicode. This validates the intended literal-rendering behavior rather than merely deleting the failing assertion.

## Windows and Unicode assessment

Windows 11 remains the programme's reference control-host direction, and OP-001 provides credible automated Windows evidence without overclaiming manual qualification.

The test suite has platform-specific cases for native Windows absolute paths, ambiguous drive/root-relative paths and POSIX rejection of foreign Windows drive/UNC input. Unicode names and spaces occur in both configuration and distribution-probe paths. Status JSON uses ASCII escapes while round-tripping Unicode values.

The recorded three skips in each matrix job are genuine opposite-platform path cases, not hidden missing functionality. Raw Windows 3.12 JUnit showed exactly the three POSIX-only foreign-Windows-path tests skipped; raw Linux 3.12 JUnit showed exactly the three native-Windows cases skipped. UI tests were not skipped.

Manual Windows 11 / Windows Terminal qualification: **NOT RUN**. That is explicitly not claimed as an OP-001 PASS condition by the implementation evidence.

## Side effects and trust-boundary assessment

Direct source inspection found no unexpected application-level:

- filesystem writes;
- network access;
- subprocess execution;
- credential loading/harvesting;
- privileged operations;
- Git mutations;
- live Ansible, Interloc, Ohmy or intrallm calls;
- provider discovery;
- scheduling behavior.

Build/distribution verification appropriately uses subprocesses in `scripts/`, not in Omnipanel runtime modules. CI checkout uses `persist-credentials: false` and workflow permissions are `contents: read`.

No credential or privilege expansion was introduced. No external component contract is assumed live or silently negotiated.

## Test-quality assessment

The tests are meaningful for the bounded OP-001 contract and include positive, negative and boundary cases rather than only happy-path assertions.

Notable strengths include:

- no-config informational CLI behavior;
- no state creation by status/TUI paths;
- configuration schema/type/error/size/encoding/path cases;
- secret-like rejected values not echoed;
- real subprocess import boundary checks;
- real Textual `run_test` mouse interaction and keyboard close at multiple terminal sizes;
- literal Unicode/markup-like path rendering;
- installed distribution metadata/entrypoint/typing-marker checks;
- clean-wheel testing outside the checkout.

The static AST checks for forbidden imports and Textual placement are intentionally limited heuristics. They could not establish the trust boundary alone; direct source review and the execution/packaging checks above were therefore used to adjudicate the requirement. I found no bypass in the actual implementation.

## CI integrity and retained-evidence reconciliation

`.github/workflows/ci.yml` genuinely defines six jobs:

- `ubuntu-latest` and `windows-latest`;
- Python 3.12, 3.13 and 3.14.

For each matrix job the workflow runs editable development installation, Ruff lint, Ruff format check, strict source mypy, pytest with JUnit, source/wheel build, clean dependency-complete wheel validation, dependency/interpreter capture and artifact retention. Failure-prone gates are not masked with `continue-on-error`, `|| true` or equivalent. The checkout/setup-python/upload-artifact actions use full commit SHA pins. Artifact retention does not determine test/build success.

Primary implementation run `34725770901` was independently read back from GitHub Actions. It had six completed successful jobs at implementation SHA `977c968731721a86411c60fca51c42ec2c833fc5`, and all acceptance steps were successful. Its six retained artifact IDs and GitHub-reported SHA-256 digests match `docs/evidence/OP-001-ci.json`.

I independently downloaded and inspected two opposite-platform artifacts from that run:

- Windows 3.12 artifact `10307513213`: ZIP SHA-256 `020a9779ea1ded0d06b6dd5ac0c326a93136d3cb8d961a2d8d24848e19b81881`; JUnit: 67 tests, 64 passed, 3 skipped, 0 failures/errors.
- Linux 3.12 artifact `10308016888`: ZIP SHA-256 `1995978b72e104e447d8edcd5a0f607fe2a8efcd4cac5ab099b0265e0b4de14b`; JUnit: 67 tests, 64 passed, 3 skipped, 0 failures/errors.

The Windows artifact's `pip freeze` naturally identified the GitHub Actions pull-request synthetic merge commit rather than the branch head. The synthetic merge commit `a9a2572d95be95c54e59111c2ba0efeab4b27a23` has parents `a27d37a...` and `977c968...` and tree `03faadf1c5c00775f5eb871d791e7be1ee884ee2`; the reviewed head `977c968...` has the same tree SHA. Thus the CI checkout tested the exact implementation tree while validating mergeability with the unchanged base. The checked-in evidence's normalized source identity does not conceal a different code tree.

The current evidence head `4765a6bead8eb27b23598067f9664b1a2bc36f44` also has a full successful six-job run, `34726012863`, with the same gates. This independently confirms that the evidence-only commit did not destabilize the foundation.

## Independent reproduction performed

Reviewer-side environment available for direct smoke verification: Linux x86_64, CPython 3.13.5.

Using the downloaded built wheel in a new temporary virtual environment, without source-checkout imports, I performed:

```text
python -m venv <temporary-venv>
<venv>/bin/python -m pip install --no-deps omnipanel-0.1.0.dev1-py3-none-any.whl
<venv>/bin/python -I -m omnipanel --version
<venv>/bin/omnipanel status
<venv>/bin/python -I -c "import omnipanel, omnipanel.domain, omnipanel.config; ..."
```

Result: **PASS** for wheel installation itself, isolated module/version startup, installed console `status`, package/domain/config imports, and read-only state-path behavior. A fresh temporary `XDG_STATE_HOME` target remained absent after status execution.

The following complete development gates were **NOT RUN locally by the independent reviewer** because the local review environment did not provide the required Textual/Ruff/mypy/build dependency set and was not used to download/reconstruct it:

```text
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check --diff .
python -m mypy
python -m pytest
python -m build
python scripts/check_distribution.py dist/omnipanel-*.whl
```

They are not converted into local PASS. Instead, their execution and results were independently established from the live GitHub Actions workflow/job records plus raw retained artifacts as described above. The reviewed issue does not require every matrix permutation to be reproduced locally when CI evidence is independently validated.

## Acceptance matrix

| OP-001 acceptance criterion | Result | Independent basis |
|---|---|---|
| 1. Clean install/dev install on supported Python | **PASS** | Six-job 3.12/3.13/3.14 Linux/Windows CI executes editable dev install; clean dependency-complete wheel installation runs outside checkout; downloaded built wheel independently inspected and smoke-installed. |
| 2. Package import and minimal entry point work | **PASS** | Module/console behavior covered by source tests and clean distribution probe; reviewer independently ran isolated module/version, console status and package/domain/config imports from the built wheel. |
| 3. Unit test/lint baseline green | **PASS** | Live run `34725770901` and current-head run `34726012863` each contain six successful jobs with Ruff lint/format, strict mypy and pytest; raw Windows/Linux JUnit independently reconciled. |
| 4. No Textual imports required by core domain modules | **PASS** | Direct source dependency inspection, lazy UI import in CLI, empty domain boundary, subprocess Textual import blocker and AST boundary test agree. |
| 5. README/development commands explicit and reproducible | **PASS** | README and `docs/DEVELOPMENT.md` give concrete Windows/Linux installation/startup/verification commands; CI uses the corresponding gates and distribution probe. |

No required acceptance criterion remains unresolved.

## Architecture/security assessment

- Premature downstream implementation: **not found**.
- Textual/domain coupling: **not found**.
- Unexpected application side effects: **not found**.
- Credential or privilege expansion: **not found**.
- Live external-component coupling: **not found**.
- Stable-ID/dependency changes: **not found**.
- OP-002 dependency bypass/start: **not found**.

The implementation is consistent with the canonical architecture: Textual is a presentation dependency, durable execution semantics remain future work, credential-bearing authority remains below Omnipanel, and task/domain schemas remain owned by OP-002.

## Verification limitations / NOT RUN

- Manual Windows 11 / Windows Terminal interactive qualification: **NOT RUN**.
- Independent local dependency-complete editable install/Ruff/mypy/full pytest/build: **NOT RUN**; independently validated in repository CI instead.
- Live Ansible/Interloc/Ohmy/intrallm integration: **NOT RUN** and intentionally outside OP-001 scope.
- Durable job/restart semantics: **NOT RUN** and intentionally outside OP-001 scope.

These limitations do not leave an OP-001 acceptance criterion unresolved and are not represented as PASS for capabilities not exercised.

## Merge recommendation

**RECOMMEND MERGE**

This is a recommendation only. This review does not merge PR #56, close issue #10, mark OP-002 complete/started, or bypass the programme's separate merge/reconciliation step.

After this review evidence is retained, OP-001 is ready for the separate merge/reconciliation step. OP-002 remains blocked until the programme's merged-evidence prerequisite is actually satisfied.
