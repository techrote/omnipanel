# OP-003 independent Steel verification review

Date: 2026-09-13
Issue: #12 / OP-003
Implementation PR: #60
Verified implementation head: `aece55c863e23ffacd5df40ee9b3be3b87cc4285`
Foundation CI: run `34753097853` — PASS

## Disposition

**PASS.** A separate verification-review pass inspected the final automated evidence and test intent against OP-003's acceptance criteria. This is a separate review lane, not a claim that a different human reviewer performed it.

## Matrix evidence

Foundation CI run `34753097853` completed successfully on the exact implementation head across all six required lanes:

- Windows / Python 3.12
- Windows / Python 3.13
- Windows / Python 3.14
- Ubuntu / Python 3.12
- Ubuntu / Python 3.13
- Ubuntu / Python 3.14

The Windows / Python 3.12 lane is particularly relevant to OP-003's platform contract. It reported:

- Ruff lint: **PASS**
- Ruff formatting check: **PASS** (`51 files already formatted`)
- strict mypy: **PASS** (`Success: no issues found in 11 source files`)
- pytest: **177 passed, 3 skipped** out of 180 collected
- sdist/wheel build: **PASS**
- clean dependency-complete wheel installation: **PASS**
- console/module entry points and headless Textual smoke from the clean wheel: **PASS**

The three skips are the pre-existing POSIX-only skips for foreign Windows path parsing; the Windows lane executes the Windows-specific path behavior instead.

## Storage verification reviewed

The final suite exercises:

- clean generation-1 create/reopen/integrity;
- generation-0 migration while preserving unrelated legacy data;
- forced migration failure after DDL with rollback of both partial schema and schema version;
- refusal to open a newer unsupported schema generation;
- corrupt/non-SQLite database failure without a stranded ownership lock;
- exclusive single-instance ownership plus explicit stale-lock recovery;
- round-trip persistence of representative OP-002 project, metaissue, task, model, evidence, component, candidate and run records;
- persistence of policy and restrictive model safety state;
- credential-like field rejection before durable insertion;
- transactional rollback after a synthetic interruption;
- prepared effect recovery to `indeterminate`, never success;
- explicit reconciliation of indeterminate effects to both `committed` and `aborted`, retained across another restart;
- active resource reservation recovery to `indeterminate` and released-reservation stability;
- SQLite backup/reopen/integrity behavior;
- relative/path-escape rejection and useful invalid data-path failure;
- spaces and Unicode in the native state path on Windows;
- separate parameterized `quarantined` and `Verboten` restart tests preserving non-auto-schedulability.

## Acceptance result

The automated evidence directly covers OP-003's required migration, restart, credential, safety-policy, ownership and Windows behavior. Packaging verification also confirms `storage.py` is included in the built wheel and works alongside the existing bootstrap boundary.

No verification-only blocker remains. OP-003 satisfies the Steel verification-review lane on the exact reviewed head.