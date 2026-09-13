# OP-003 independent Steel implementation review

Date: 2026-09-13
Issue: #12 / OP-003
Implementation PR: #60
Reviewed implementation head: `aece55c863e23ffacd5df40ee9b3be3b87cc4285`
Foundation CI: run `34753097853` — PASS

## Disposition

**PASS.** A separate implementation-review pass inspected the final OP-003 storage diff, OP-002 contracts, recovery semantics, platform boundaries and failure behavior. No blocking correctness, authority-broadening or storage-lifecycle defect remains.

This is a separate review lane performed after implementation; it is **not** represented as a different human reviewer.

## Review findings

### Durable truth and scope

The implementation remains a storage layer. It persists the OP-002 records that must survive restart, validated policy choices, component observations, resource reservations and an effect journal. It does not add OP-004 orchestration, provider execution, GitHub mutation, credential acquisition or production TUI behavior.

State is placed under the configured native `AppConfig.data_dir`, outside worktrees by default, and is created only when the durable store is explicitly opened. Existing bootstrap/status behavior remains read-only.

### Transaction and migration lifecycle

SQLite is configured with WAL, `synchronous=FULL`, foreign keys and explicit `BEGIN IMMEDIATE` transactions. Generation 0→1 migration executes individual DDL statements inside one transaction rather than `executescript()`, avoiding its implicit-commit hazard. Future schema generations fail closed rather than being downgraded.

During this review a verification gap was identified: atomic migration rollback had been designed but not directly forced in a test. The final reviewed head adds a synthetic failure after DDL and proves that both the partial table and `user_version` change are rolled back and the ownership lock is released.

### Crash and external-effect recovery

Prepared external effects reopen as `indeterminate`; active/reserved resource reservations also reopen as `indeterminate`. The store never invents success from an interrupted effect.

An earlier review pass found that an indeterminate effect could be detected but not subsequently reconciled through the public settlement API. That defect was fixed before this reviewed SHA: after an external recovery workflow determines the true outcome, an indeterminate effect can be explicitly settled to `committed` or `aborted`, while contradictory rewrites of already terminal outcomes remain prohibited. The final tests cover both reconciled outcomes across a second restart.

### Ownership and platform behavior

Single-instance ownership is enforced with an atomic exclusive lock file. A second writer fails visibly. Stale-lock removal is an explicit operator action; normal close removes only a lock whose random token proves ownership. Failure during open/migration does not strand the current instance's lock.

Native `pathlib` paths, spaces and Unicode are exercised on Windows. POSIX main database and backup files are tightened to mode `0600`; Windows uses directory/ACL inheritance rather than pretending POSIX mode bits apply.

### Model safety, policy and credentials

OP-002 model assessments and policies are revalidated on load. `quarantined` and `Verboten` model states survive restart and remain non-auto-schedulable.

There is no credential table. Generic durable detail objects reject common credential-like keys before insertion. The documentation correctly describes this as defense in depth rather than a secret-value detector and preserves the architectural rule that actual credentials remain outside Omnipanel durable state.

### Corruption and recovery

Invalid/non-SQLite input fails visibly without truncation or silent recreation. Typed records are revalidated on read, integrity checking is exposed, explicit SQLite backups are supported, and newer schema generations fail closed.

## Acceptance mapping

- clean store creation, reopen and generation migration: **PASS**
- transaction/restart invariants: **PASS**
- atomic failed migration rollback: **PASS**
- interrupted effects are not invented as success: **PASS**
- indeterminate effects can be explicitly reconciled after verification: **PASS**
- raw credential-like fields rejected / no credential table: **PASS**
- quarantine/Verboten + user policy survive restart: **PASS**
- explicit single-instance ownership semantics: **PASS**
- useful Windows native path/error behavior: **PASS**
- storage-only scope retained: **PASS**

OP-003 satisfies the Steel implementation-review lane on the exact reviewed head.