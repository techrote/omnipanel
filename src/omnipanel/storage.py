"""Durable local SQLite state with explicit migrations and recovery semantics.

OP-003 owns durable truth only. UI caches, live provider handles, credentials and execution
side effects are intentionally outside this module.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import (
    CandidateRecord,
    ComponentContractIdentityRecord,
    DagEdge,
    EvidenceDescriptorRecord,
    MetaissueRecord,
    ModelAssessmentRecord,
    ModelIdentityRecord,
    ProjectRecord,
    ResourceRequest,
    RunRecord,
    TaskPolicy,
    TaskRecord,
    VersionedRecord,
)

CURRENT_STATE_SCHEMA_VERSION: Final[int] = 1
DEFAULT_DATABASE_NAME: Final[str] = "state.sqlite3"
MAX_JSON_BYTES: Final[int] = 1024 * 1024

_SECRET_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "bearer",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
)


class StateError(RuntimeError):
    """Base class for durable-state failures."""


class StatePathError(StateError):
    """The durable-state path cannot be used safely."""


class StateLockError(StateError):
    """Another Omnipanel instance may own the durable-state directory."""


class StateMigrationError(StateError):
    """The database schema cannot be migrated safely."""


class StateCorruptionError(StateError):
    """SQLite reported corruption or an invalid database boundary."""


class CredentialStorageError(StateError):
    """A write attempted to persist a raw credential-like field."""


class RecordNotFoundError(StateError):
    """A requested durable record does not exist."""


class StoreModel(BaseModel):
    """Closed immutable storage-side record."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class ReservationState(StrEnum):
    RESERVED = "reserved"
    ACTIVE = "active"
    RELEASED = "released"
    INDETERMINATE = "indeterminate"


class ResourceReservation(StoreModel):
    reservation_id: str = Field(
        min_length=1,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    run_id: str = Field(
        min_length=1,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    provider_id: str = Field(
        min_length=1,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    request: ResourceRequest
    state: ReservationState = ReservationState.RESERVED
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return value


class EffectState(StrEnum):
    PREPARED = "prepared"
    COMMITTED = "committed"
    ABORTED = "aborted"
    INDETERMINATE = "indeterminate"


class EffectJournalEntry(StoreModel):
    effect_id: str = Field(
        min_length=1,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    kind: str = Field(
        min_length=1,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    state: EffectState
    detail: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effect timestamps must include a timezone")
        return value


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class StorePaths:
    data_dir: Path
    database: Path
    lock: Path


_RECORD_MODELS: Final[dict[str, type[VersionedRecord]]] = {
    "project": ProjectRecord,
    "metaissue": MetaissueRecord,
    "dag-edge": DagEdge,
    "task": TaskRecord,
    "model-identity": ModelIdentityRecord,
    "model-assessment": ModelAssessmentRecord,
    "evidence": EvidenceDescriptorRecord,
    "component-contract": ComponentContractIdentityRecord,
    "candidate-state": CandidateRecord,
    "run": RunRecord,
}

TRecord = TypeVar("TRecord", bound=VersionedRecord)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _canonical_json(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise StateError("durable payload must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise StateError("durable payload exceeds the 1 MiB record limit")
    return encoded


def _scan_for_raw_credentials(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).strip().lower().replace("-", "_")
            if any(fragment in key_text for fragment in _SECRET_KEY_FRAGMENTS):
                raise CredentialStorageError(
                    f"raw credential-like field is forbidden in durable state at {path}.{key}"
                )
            _scan_for_raw_credentials(child, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _scan_for_raw_credentials(child, path=f"{path}[{index}]")


def _model_payload(model: BaseModel) -> dict[str, Any]:
    payload = model.model_dump(mode="json")
    _scan_for_raw_credentials(payload)
    return payload


def _record_key(record: VersionedRecord) -> str:
    if isinstance(record, ProjectRecord):
        return record.project_id
    if isinstance(record, MetaissueRecord):
        return record.metaissue_id
    if isinstance(record, TaskRecord):
        return record.task_id
    if isinstance(record, RunRecord):
        return record.run_id
    if isinstance(record, CandidateRecord):
        return record.candidate.candidate_id
    if isinstance(record, EvidenceDescriptorRecord):
        return record.evidence_id
    if isinstance(record, ModelIdentityRecord):
        return f"{record.ref.provider_id}:{record.ref.model_id}"
    if isinstance(record, ModelAssessmentRecord):
        return f"{record.model.provider_id}:{record.model.model_id}"
    if isinstance(record, ComponentContractIdentityRecord):
        ref = record.ref
        return f"{ref.component_id}:{ref.contract_id}:{ref.contract_version}"
    if isinstance(record, DagEdge):
        return f"{record.predecessor_task_id}->{record.successor_task_id}"
    raise StateError(f"unsupported durable record class: {type(record).__name__}")


def _safe_database_name(name: str) -> str:
    if not name or name in {".", ".."} or Path(name).name != name:
        raise StatePathError("database_name must be a simple file name")
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise StatePathError("database_name must not contain control characters")
    return name


class StateStore:
    """Single-owner durable state backed by SQLite generation 1."""

    def __init__(
        self,
        config: AppConfig,
        *,
        database_name: str = DEFAULT_DATABASE_NAME,
    ) -> None:
        data_dir = config.data_dir
        if not data_dir.is_absolute():
            raise StatePathError("durable data_dir must be an absolute native path")
        filename = _safe_database_name(database_name)
        database = data_dir / filename
        self.paths = StorePaths(
            data_dir=data_dir,
            database=database,
            lock=database.with_suffix(database.suffix + ".lock"),
        )
        self._connection: sqlite3.Connection | None = None
        self._lock_token: str | None = None

    @property
    def is_open(self) -> bool:
        return self._connection is not None

    def __enter__(self) -> StateStore:
        return self.open()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def open(self) -> StateStore:
        if self._connection is not None:
            return self
        self._prepare_data_dir()
        self._acquire_lock()
        try:
            connection = sqlite3.connect(
                self.paths.database,
                timeout=5.0,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            self._connection = connection
            self._configure_connection()
            self._migrate()
            self._mark_interrupted_effects_indeterminate()
            self._mark_interrupted_reservations_indeterminate()
            self._tighten_database_permissions()
            return self
        except sqlite3.DatabaseError as exc:
            self._close_after_failed_open()
            raise StateCorruptionError(
                f"durable state database is invalid or unreadable: {self.paths.database}"
            ) from exc
        except Exception:
            self._close_after_failed_open()
            raise

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()
        self._release_lock()

    def _prepare_data_dir(self) -> None:
        try:
            self.paths.data_dir.mkdir(parents=True, exist_ok=True)
            if not self.paths.data_dir.is_dir():
                raise StatePathError(f"durable data path is not a directory: {self.paths.data_dir}")
        except OSError as exc:
            raise StatePathError(
                f"durable data directory could not be created or opened: {self.paths.data_dir}"
            ) from exc

    def _acquire_lock(self) -> None:
        token = uuid.uuid4().hex
        payload = _canonical_json(
            {
                "pid": os.getpid(),
                "token": token,
                "created_at": _utc_now().isoformat(),
            }
        )
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            descriptor = os.open(self.paths.lock, flags, 0o600)
        except FileExistsError as exc:
            raise StateLockError(
                "durable state is already locked; confirm no Omnipanel instance is running "
                f"before recovering lock file: {self.paths.lock}"
            ) from exc
        except OSError as exc:
            raise StateLockError(
                f"durable state lock could not be acquired: {self.paths.lock}"
            ) from exc
        try:
            os.write(descriptor, payload.encode("utf-8"))
        finally:
            os.close(descriptor)
        self._lock_token = token

    def _release_lock(self) -> None:
        token, self._lock_token = self._lock_token, None
        if token is None:
            return
        try:
            payload = json.loads(self.paths.lock.read_text(encoding="utf-8"))
            if payload.get("token") == token:
                self.paths.lock.unlink(missing_ok=True)
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Never delete a lock that cannot be proven to belong to this instance.
            return

    @staticmethod
    def recover_stale_lock(
        config: AppConfig,
        *,
        database_name: str = DEFAULT_DATABASE_NAME,
    ) -> Path:
        """Remove a stale lock only after an operator has confirmed no owner is live."""

        filename = _safe_database_name(database_name)
        lock = (config.data_dir / filename).with_suffix(Path(filename).suffix + ".lock")
        try:
            lock.unlink()
        except FileNotFoundError:
            return lock
        except OSError as exc:
            raise StateLockError(f"stale durable-state lock could not be removed: {lock}") from exc
        return lock

    def _close_after_failed_open(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()
        self._release_lock()

    def _tighten_database_permissions(self) -> None:
        if os.name == "nt":
            return
        try:
            os.chmod(self.paths.database, 0o600)
        except OSError as exc:
            raise StatePathError(
                f"durable state database permissions could not be restricted: {self.paths.database}"
            ) from exc

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise StateError("durable state store is not open")
        return self._connection

    def _configure_connection(self) -> None:
        connection = self._require_connection()
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run an immediate transaction and roll it back completely on failure."""

        connection = self._require_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
        except Exception:
            connection.execute("ROLLBACK")
            raise
        else:
            connection.execute("COMMIT")

    def _migrate(self) -> None:
        connection = self._require_connection()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > CURRENT_STATE_SCHEMA_VERSION:
            raise StateMigrationError(
                f"database schema generation {version} is newer than supported "
                f"generation {CURRENT_STATE_SCHEMA_VERSION}"
            )
        while version < CURRENT_STATE_SCHEMA_VERSION:
            migration = _MIGRATIONS.get(version)
            if migration is None:
                raise StateMigrationError(
                    f"no migration path exists from schema generation {version}"
                )
            try:
                with self.transaction() as transaction:
                    migration(transaction)
                    transaction.execute(f"PRAGMA user_version = {version + 1}")
            except sqlite3.DatabaseError as exc:
                raise StateMigrationError(
                    f"database migration {version}->{version + 1} failed"
                ) from exc
            version += 1

    @property
    def schema_version(self) -> int:
        connection = self._require_connection()
        return int(connection.execute("PRAGMA user_version").fetchone()[0])

    def put_record(self, record: VersionedRecord) -> str:
        record_type = str(getattr(record, "record_type", ""))
        if record_type not in _RECORD_MODELS:
            raise StateError(f"unsupported durable record_type: {record_type}")
        record_key = _record_key(record)
        encoded = _canonical_json(_model_payload(record))
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO records(
                    record_type, record_key, schema_version, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(record_type, record_key) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    record_type,
                    record_key,
                    record.schema_version,
                    encoded,
                    _utc_now().isoformat(),
                ),
            )
        return record_key

    def get_record(self, record_type: str, record_key: str) -> VersionedRecord:
        model = _RECORD_MODELS.get(record_type)
        if model is None:
            raise StateError(f"unsupported durable record_type: {record_type}")
        row = (
            self._require_connection()
            .execute(
                "SELECT payload_json FROM records WHERE record_type=? AND record_key=?",
                (record_type, record_key),
            )
            .fetchone()
        )
        if row is None:
            raise RecordNotFoundError(f"durable record not found: {record_type}/{record_key}")
        try:
            return model.model_validate_json(str(row["payload_json"]))
        except ValidationError as exc:
            raise StateCorruptionError(
                f"durable record failed validation: {record_type}/{record_key}"
            ) from exc

    def get_typed_record(self, model: type[TRecord], record_key: str) -> TRecord:
        field = model.model_fields.get("record_type")
        if field is None or not isinstance(field.default, str):
            raise StateError(f"record model lacks a default record_type: {model.__name__}")
        record = self.get_record(field.default, record_key)
        if not isinstance(record, model):
            raise StateCorruptionError(
                f"durable record type mismatch for {field.default}/{record_key}"
            )
        return record

    def list_record_keys(self, record_type: str) -> tuple[str, ...]:
        if record_type not in _RECORD_MODELS:
            raise StateError(f"unsupported durable record_type: {record_type}")
        rows = self._require_connection().execute(
            "SELECT record_key FROM records WHERE record_type=? ORDER BY record_key",
            (record_type,),
        )
        return tuple(str(row[0]) for row in rows)

    def save_policy(self, task_id: str, policy: TaskPolicy) -> None:
        encoded = _canonical_json(_model_payload(policy))
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO policy_choices(task_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (task_id, encoded, _utc_now().isoformat()),
            )

    def load_policy(self, task_id: str) -> TaskPolicy:
        row = (
            self._require_connection()
            .execute(
                "SELECT payload_json FROM policy_choices WHERE task_id=?",
                (task_id,),
            )
            .fetchone()
        )
        if row is None:
            raise RecordNotFoundError(f"durable policy not found for task: {task_id}")
        try:
            return TaskPolicy.model_validate_json(str(row["payload_json"]))
        except ValidationError as exc:
            raise StateCorruptionError(f"durable task policy failed validation: {task_id}") from exc

    def save_component_observation(
        self,
        component_id: str,
        observation_id: str,
        detail: Mapping[str, object],
    ) -> None:
        payload = dict(detail)
        _scan_for_raw_credentials(payload)
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO component_observations(
                    component_id, observation_id, payload_json, observed_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(component_id, observation_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    observed_at=excluded.observed_at
                """,
                (
                    component_id,
                    observation_id,
                    _canonical_json(payload),
                    _utc_now().isoformat(),
                ),
            )

    def load_component_observation(
        self,
        component_id: str,
        observation_id: str,
    ) -> dict[str, Any]:
        row = (
            self._require_connection()
            .execute(
                """
            SELECT payload_json FROM component_observations
            WHERE component_id=? AND observation_id=?
            """,
                (component_id, observation_id),
            )
            .fetchone()
        )
        if row is None:
            raise RecordNotFoundError(
                f"component observation not found: {component_id}/{observation_id}"
            )
        try:
            value = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError as exc:
            raise StateCorruptionError("component observation contains invalid JSON") from exc
        if not isinstance(value, dict):
            raise StateCorruptionError("component observation must decode to an object")
        return cast(dict[str, Any], value)

    def save_reservation(self, reservation: ResourceReservation) -> None:
        encoded = _canonical_json(_model_payload(reservation))
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO resource_reservations(
                    reservation_id, run_id, provider_id, state, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(reservation_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    provider_id=excluded.provider_id,
                    state=excluded.state,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    reservation.reservation_id,
                    reservation.run_id,
                    reservation.provider_id,
                    reservation.state.value,
                    encoded,
                    reservation.updated_at.isoformat(),
                ),
            )

    def load_reservation(self, reservation_id: str) -> ResourceReservation:
        row = (
            self._require_connection()
            .execute(
                "SELECT payload_json FROM resource_reservations WHERE reservation_id=?",
                (reservation_id,),
            )
            .fetchone()
        )
        if row is None:
            raise RecordNotFoundError(f"resource reservation not found: {reservation_id}")
        try:
            return ResourceReservation.model_validate_json(str(row["payload_json"]))
        except ValidationError as exc:
            raise StateCorruptionError(
                f"resource reservation failed validation: {reservation_id}"
            ) from exc

    def prepare_effect(
        self,
        effect_id: str,
        kind: str,
        detail: Mapping[str, object] | None = None,
    ) -> EffectJournalEntry:
        now = _utc_now()
        entry = EffectJournalEntry(
            effect_id=effect_id,
            kind=kind,
            state=EffectState.PREPARED,
            detail={} if detail is None else dict(detail),
            created_at=now,
            updated_at=now,
        )
        encoded = _canonical_json(_model_payload(entry))
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO effect_journal(
                    effect_id, kind, state, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.effect_id,
                    entry.kind,
                    entry.state.value,
                    encoded,
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ),
            )
        return entry

    def settle_effect(
        self,
        effect_id: str,
        state: EffectState,
    ) -> EffectJournalEntry:
        if state not in {
            EffectState.COMMITTED,
            EffectState.ABORTED,
            EffectState.INDETERMINATE,
        }:
            raise StateError("effect settlement must be committed, aborted or indeterminate")
        current = self.load_effect(effect_id)
        if current.state is not EffectState.PREPARED and current.state is not state:
            raise StateError(
                f"effect {effect_id} is already terminal as {current.state.value}; refusing rewrite"
            )
        updated = current.model_copy(update={"state": state, "updated_at": _utc_now()})
        encoded = _canonical_json(_model_payload(updated))
        with self.transaction() as connection:
            connection.execute(
                """
                UPDATE effect_journal
                SET state=?, payload_json=?, updated_at=?
                WHERE effect_id=?
                """,
                (
                    state.value,
                    encoded,
                    updated.updated_at.isoformat(),
                    effect_id,
                ),
            )
        return updated

    def load_effect(self, effect_id: str) -> EffectJournalEntry:
        row = (
            self._require_connection()
            .execute(
                "SELECT payload_json FROM effect_journal WHERE effect_id=?",
                (effect_id,),
            )
            .fetchone()
        )
        if row is None:
            raise RecordNotFoundError(f"effect journal entry not found: {effect_id}")
        try:
            return EffectJournalEntry.model_validate_json(str(row["payload_json"]))
        except ValidationError as exc:
            raise StateCorruptionError(
                f"effect journal entry failed validation: {effect_id}"
            ) from exc

    def list_effects(
        self,
        state: EffectState | None = None,
    ) -> tuple[EffectJournalEntry, ...]:
        connection = self._require_connection()
        if state is None:
            rows = connection.execute(
                "SELECT payload_json FROM effect_journal ORDER BY created_at, effect_id"
            )
        else:
            rows = connection.execute(
                """
                SELECT payload_json FROM effect_journal
                WHERE state=? ORDER BY created_at, effect_id
                """,
                (state.value,),
            )
        entries: list[EffectJournalEntry] = []
        for row in rows:
            try:
                entries.append(EffectJournalEntry.model_validate_json(str(row["payload_json"])))
            except ValidationError as exc:
                raise StateCorruptionError("effect journal contains an invalid entry") from exc
        return tuple(entries)

    def _mark_interrupted_effects_indeterminate(self) -> None:
        rows = (
            self._require_connection()
            .execute(
                "SELECT effect_id, payload_json FROM effect_journal WHERE state=?",
                (EffectState.PREPARED.value,),
            )
            .fetchall()
        )
        if not rows:
            return
        with self.transaction() as connection:
            for row in rows:
                try:
                    entry = EffectJournalEntry.model_validate_json(str(row["payload_json"]))
                except ValidationError as exc:
                    raise StateCorruptionError(
                        "prepared effect failed recovery validation"
                    ) from exc
                updated = entry.model_copy(
                    update={
                        "state": EffectState.INDETERMINATE,
                        "updated_at": _utc_now(),
                    }
                )
                connection.execute(
                    """
                    UPDATE effect_journal
                    SET state=?, payload_json=?, updated_at=?
                    WHERE effect_id=?
                    """,
                    (
                        EffectState.INDETERMINATE.value,
                        _canonical_json(_model_payload(updated)),
                        updated.updated_at.isoformat(),
                        entry.effect_id,
                    ),
                )

    def _mark_interrupted_reservations_indeterminate(self) -> None:
        rows = (
            self._require_connection()
            .execute(
                """
            SELECT reservation_id, payload_json FROM resource_reservations
            WHERE state IN (?, ?)
            """,
                (ReservationState.RESERVED.value, ReservationState.ACTIVE.value),
            )
            .fetchall()
        )
        if not rows:
            return
        with self.transaction() as connection:
            for row in rows:
                try:
                    reservation = ResourceReservation.model_validate_json(str(row["payload_json"]))
                except ValidationError as exc:
                    raise StateCorruptionError(
                        "resource reservation failed recovery validation"
                    ) from exc
                updated = reservation.model_copy(
                    update={
                        "state": ReservationState.INDETERMINATE,
                        "updated_at": _utc_now(),
                    }
                )
                connection.execute(
                    """
                    UPDATE resource_reservations
                    SET state=?, payload_json=?, updated_at=?
                    WHERE reservation_id=?
                    """,
                    (
                        ReservationState.INDETERMINATE.value,
                        _canonical_json(_model_payload(updated)),
                        updated.updated_at.isoformat(),
                        updated.reservation_id,
                    ),
                )

    def integrity_check(self) -> IntegrityReport:
        try:
            rows = self._require_connection().execute("PRAGMA integrity_check").fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptionError("SQLite integrity check could not run") from exc
        detail = "; ".join(str(row[0]) for row in rows)
        return IntegrityReport(ok=detail == "ok", detail=detail)

    def backup_to(self, destination: Path) -> Path:
        if not destination.is_absolute():
            raise StatePathError("backup destination must be an absolute native path")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not destination.is_file():
                raise StatePathError(f"backup destination is not a regular file: {destination}")
            target = sqlite3.connect(destination, isolation_level=None)
            try:
                self._require_connection().backup(target)
            finally:
                target.close()
            if os.name != "nt":
                os.chmod(destination, 0o600)
        except sqlite3.DatabaseError as exc:
            raise StateCorruptionError(f"durable state backup failed: {destination}") from exc
        except OSError as exc:
            raise StatePathError(f"durable state backup path is unusable: {destination}") from exc
        return destination


def _migration_0_to_1(connection: sqlite3.Connection) -> None:
    """Create generation 1 without implicit commits inside the migration transaction."""

    statements = (
        """
        CREATE TABLE records(
            record_type TEXT NOT NULL,
            record_key TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(record_type, record_key)
        )
        """,
        "CREATE INDEX records_type_updated_idx ON records(record_type, updated_at)",
        """
        CREATE TABLE policy_choices(
            task_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE component_observations(
            component_id TEXT NOT NULL,
            observation_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            PRIMARY KEY(component_id, observation_id)
        )
        """,
        """
        CREATE INDEX component_observations_time_idx
        ON component_observations(component_id, observed_at)
        """,
        """
        CREATE TABLE resource_reservations(
            reservation_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            state TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX resource_reservations_run_idx
        ON resource_reservations(run_id, state)
        """,
        """
        CREATE TABLE effect_journal(
            effect_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            state TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX effect_journal_state_idx ON effect_journal(state, updated_at)",
    )
    for statement in statements:
        connection.execute(statement)


_MIGRATIONS: Final[dict[int, Callable[[sqlite3.Connection], None]]] = {
    0: _migration_0_to_1,
}


__all__ = [
    "CURRENT_STATE_SCHEMA_VERSION",
    "DEFAULT_DATABASE_NAME",
    "CredentialStorageError",
    "EffectJournalEntry",
    "EffectState",
    "IntegrityReport",
    "RecordNotFoundError",
    "ReservationState",
    "ResourceReservation",
    "StateCorruptionError",
    "StateError",
    "StateLockError",
    "StateMigrationError",
    "StatePathError",
    "StateStore",
    "StorePaths",
]
