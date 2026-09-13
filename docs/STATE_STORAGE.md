# OP-003 durable local state

Status: implementation contract for state schema generation 1.

`src/omnipanel/storage.py` provides the first durable Omnipanel truth store. It is a local
SQLite database under the configured `AppConfig.data_dir`; it is not stored inside project
worktrees and it does not execute provider effects.

## Location and retention

Default paths continue to come from `omnipanel.config`:

- Windows: `%LOCALAPPDATA%\Omnipanel\state.sqlite3`;
- POSIX: `$XDG_STATE_HOME/omnipanel/state.sqlite3`, or `~/.local/state/omnipanel/state.sqlite3`.

Custom data directories must be absolute native paths. Unicode and spaces are supported.
The store creates the configured data directory only when durable state is explicitly
opened; bootstrap/status behavior remains read-only.

The database is operator-retained state. It is not a cache and is not deleted automatically.
Backups are explicit SQLite snapshots created with `StateStore.backup_to()`.

## Durable truth versus ephemeral state

Generation 1 persists:

- OP-002 project, metaissue, task, DAG-edge, run/candidate, evidence, component-contract,
  model-identity and model-assessment records;
- resolved/user policy choices needed after restart;
- component observations needed for compatibility/recovery decisions;
- resource reservations whose ownership must be reconciled after restart;
- effect-journal entries that make interrupted side effects visible.

Generation 1 deliberately does **not** persist:

- Textual widget/view state;
- transient progress animation or selection state;
- live process/socket/provider handles;
- provider credentials, tokens or secret values;
- speculative success for effects whose outcome is unknown.

## SQLite durability profile

Connections enable foreign keys, WAL journaling, `synchronous=FULL`, a bounded busy timeout
and explicit `BEGIN IMMEDIATE` transactions. Mutation helpers either commit a complete state
change or roll it back.

A single Omnipanel owner is enforced above SQLite with an atomic lock file next to the
database. A second instance fails with a visible `StateLockError`; it does not silently
share write ownership. Hard process termination may leave a stale lock. Recovery is an
explicit operator action via `StateStore.recover_stale_lock()` after confirming no owner is
live. Normal shutdown removes only a lock whose random token proves ownership.

## Schema generations and migrations

| From | To | Behavior |
|---:|---:|---|
| 0 / empty SQLite | 1 | Create generation-1 tables and indexes transactionally, preserving unrelated existing tables |
| 1 | 1 | Open without mutation beyond recovery reconciliation |
| >1 | unsupported | Fail closed with `StateMigrationError`; never downgrade automatically |

Migration statements execute individually inside the same explicit transaction. The
implementation intentionally avoids `sqlite3.executescript()` because it can commit an
existing transaction implicitly.

`PRAGMA user_version` is the durable state schema-generation marker. OP-002 record-level
`schema_version` remains independently validated when records are read.

## Restart and failure semantics

SQLite atomicity protects local writes. External effects need a stronger semantic boundary,
so the effect journal separates intent from known outcome:

| Persisted state before restart | State after restart | Interpretation |
|---|---|---|
| `prepared` effect | `indeterminate` | effect may or may not have happened; reconcile before retry/success |
| `committed` effect | `committed` | success was durably recorded |
| `aborted` effect | `aborted` | known non-success |
| `reserved` / `active` resource reservation | `indeterminate` | provider ownership must be re-qualified |
| `released` reservation | `released` | no live ownership is asserted |

This prevents a crash between a remote side effect and local acknowledgement from becoming
invented success. OP-004 and later provider services can build recovery workflows on this
journal without redefining the storage truth model.

## Model safety and policy

Model assessments persist canonical OP-002 safety states. `quarantined` and `Verboten`
assessments round-trip across restart and remain non-schedulable according to the OP-002
contract. User policy decisions are stored as validated `TaskPolicy` snapshots, including
the explicit decision evidence required by high-consequence policy.

## Credential boundary

There is no credential table. Provider requests persist only OP-002 capability handles and
resource/path/network requirements. Generic durable detail objects are also scanned and
reject credential-like field names such as `api_key`, access/refresh tokens, passwords,
private keys and secrets before insertion.

That scan is defense in depth, not a credential vault. Callers must not rename a secret into
an innocuous field. Actual credentials remain in the component/provider credential system
outside Omnipanel durable state.

## Corruption, integrity and backup

- invalid/non-SQLite files fail with `StateCorruptionError` and do not strand an acquired
  lock;
- `StateStore.integrity_check()` exposes SQLite `PRAGMA integrity_check` results;
- `StateStore.backup_to()` uses SQLite's online backup API and requires an absolute native
  destination path;
- schema generations newer than the running code fail closed rather than being rewritten;
- typed records are revalidated on load, so invalid stored JSON is surfaced as corruption.

Recovery never silently recreates or truncates a corrupt database. An operator can preserve
the original file, restore a known-good backup or move it aside before intentionally creating
new state.

## Windows behavior

The implementation uses `pathlib` and SQLite native paths, and the automated tests exercise
spaces and Unicode in state paths on Windows. Windows access control inherits from the data
directory; the code does not pretend POSIX mode bits are meaningful there. On POSIX the main
database and explicit backups are tightened to mode `0600` after creation.

Errors include the relevant path but not stored payloads or credentials. File ownership is
single-instance and deterministic on both platforms.

## Scope boundary

OP-003 is storage infrastructure only. It does not implement the OP-004 application-service
layer, readiness evaluation, provider scheduling, GitHub synchronization, component contract
negotiation, credential acquisition or production TUI behavior.
