from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

import omnipanel.storage as storage_module
from omnipanel.config import AppConfig
from omnipanel.domain.contracts import (
    CandidateRecord,
    ComponentContractIdentityRecord,
    EvidenceDescriptorRecord,
    MetaissueRecord,
    ModelAssessmentRecord,
    ModelIdentityRecord,
    ProjectRecord,
    RunRecord,
    SafetyState,
    TaskPolicy,
    TaskRecord,
)
from omnipanel.storage import (
    CURRENT_STATE_SCHEMA_VERSION,
    CredentialStorageError,
    EffectState,
    ReservationState,
    ResourceReservation,
    StateCorruptionError,
    StateLockError,
    StateMigrationError,
    StatePathError,
    StateStore,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(data_dir=(tmp_path / "Omnipanel state 東京").absolute())


def _task_policy() -> TaskPolicy:
    payload = _fixture()["task"]
    assert isinstance(payload, dict)
    policy = payload["policy"]
    assert isinstance(policy, dict)
    return TaskPolicy.model_validate(policy)


def test_clean_create_reopen_and_integrity(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert not config.data_dir.exists()

    with StateStore(config) as store:
        assert store.schema_version == CURRENT_STATE_SCHEMA_VERSION
        assert store.paths.database.parent == config.data_dir
        assert store.paths.database.is_file()
        assert store.integrity_check().ok

    assert not (config.data_dir / "state.sqlite3.lock").exists()
    with StateStore(config) as reopened:
        assert reopened.schema_version == CURRENT_STATE_SCHEMA_VERSION
        assert reopened.integrity_check().detail == "ok"


def test_generation_zero_migrates_without_erasing_unrelated_legacy_data(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.data_dir.mkdir(parents=True)
    database = config.data_dir / "state.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE legacy_marker(value TEXT NOT NULL)")
        connection.execute("INSERT INTO legacy_marker(value) VALUES ('preserve-me')")
        connection.execute("PRAGMA user_version = 0")
        connection.commit()
    finally:
        connection.close()

    with StateStore(config) as store:
        assert store.schema_version == 1
        row = store._require_connection().execute("SELECT value FROM legacy_marker").fetchone()
        assert row is not None
        assert row[0] == "preserve-me"
        tables = {
            row[0]
            for row in store._require_connection().execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "records",
            "policy_choices",
            "component_observations",
            "resource_reservations",
            "effect_journal",
        } <= tables


def test_failed_migration_rolls_back_schema_and_releases_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)

    def fail_after_create(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE migration_should_rollback(value TEXT)")
        raise sqlite3.OperationalError("synthetic migration failure")

    monkeypatch.setitem(storage_module._MIGRATIONS, 0, fail_after_create)

    with pytest.raises(StateMigrationError, match="0->1"):
        StateStore(config).open()

    assert not (config.data_dir / "state.sqlite3.lock").exists()
    database = config.data_dir / "state.sqlite3"
    connection = sqlite3.connect(database)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        leaked_table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='migration_should_rollback'
            """
        ).fetchone()
    finally:
        connection.close()

    assert version == 0
    assert leaked_table is None


def test_newer_database_generation_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.data_dir.mkdir(parents=True)
    database = config.data_dir / "state.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA user_version = 99")
    finally:
        connection.close()

    with pytest.raises(StateMigrationError, match="newer than supported"):
        StateStore(config).open()
    assert not (config.data_dir / "state.sqlite3.lock").exists()


def test_corrupt_database_is_reported_without_leaking_lock(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.data_dir.mkdir(parents=True)
    (config.data_dir / "state.sqlite3").write_bytes(b"not a sqlite database\x00\xff")

    with pytest.raises(StateCorruptionError, match="invalid or unreadable"):
        StateStore(config).open()
    assert not (config.data_dir / "state.sqlite3.lock").exists()


def test_single_instance_lock_is_explicit(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = StateStore(config).open()
    try:
        with pytest.raises(StateLockError, match="already locked"):
            StateStore(config).open()
    finally:
        first.close()

    with StateStore(config) as second:
        assert second.is_open


def test_stale_lock_recovery_is_operator_explicit(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.data_dir.mkdir(parents=True)
    lock = config.data_dir / "state.sqlite3.lock"
    lock.write_text('{"pid":999999,"token":"stale"}', encoding="utf-8")

    with pytest.raises(StateLockError):
        StateStore(config).open()
    recovered = StateStore.recover_stale_lock(config)
    assert recovered == lock
    assert not lock.exists()

    with StateStore(config) as store:
        assert store.is_open


def test_durable_op002_records_round_trip(tmp_path: Path) -> None:
    fixture = _fixture()
    records = [
        ProjectRecord.model_validate(fixture["project"]),
        MetaissueRecord.model_validate(fixture["metaissue"]),
        TaskRecord.model_validate(fixture["task"]),
        ModelIdentityRecord.model_validate(fixture["model_identity"]),
        ModelAssessmentRecord.model_validate(fixture["model_assessment"]),
        EvidenceDescriptorRecord.model_validate(fixture["evidence"]),
        ComponentContractIdentityRecord.model_validate(fixture["component_contract"]),
        CandidateRecord.model_validate(fixture["candidate_state"]),
    ]
    runs = fixture["runs"]
    assert isinstance(runs, list)
    records.extend(RunRecord.model_validate(run) for run in runs)

    config = _config(tmp_path)
    with StateStore(config) as store:
        keys = [(record.record_type, store.put_record(record)) for record in records]

    with StateStore(config) as reopened:
        for original, (record_type, key) in zip(records, keys, strict=True):
            loaded = reopened.get_record(record_type, key)
            assert loaded == original
        assert reopened.list_record_keys("run") == (
            "run-div-001",
            "run-race-001",
            "run-single-001",
        )


def test_quarantine_verboten_and_policy_survive_restart(tmp_path: Path) -> None:
    fixture = _fixture()
    assessment_payload = fixture["model_assessment"]
    assert isinstance(assessment_payload, dict)
    assessment_payload = dict(assessment_payload)
    assessment_payload["safety_state"] = SafetyState.VERBOTEN.value
    assessment = ModelAssessmentRecord.model_validate(assessment_payload)
    policy = _task_policy()

    config = _config(tmp_path)
    with StateStore(config) as store:
        key = store.put_record(assessment)
        store.save_policy("OP-003", policy)

    with StateStore(config) as reopened:
        loaded = reopened.get_typed_record(ModelAssessmentRecord, key)
        assert loaded.safety_state is SafetyState.VERBOTEN
        assert not loaded.is_automatically_schedulable()
        assert reopened.load_policy("OP-003") == policy


def test_component_observation_persists_and_rejects_raw_credentials(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with StateStore(config) as store:
        store.save_component_observation(
            "ansible",
            "probe-001",
            {"contract": "execution/1.0", "qualified": True, "latency_ms": 12},
        )
        with pytest.raises(CredentialStorageError, match="raw credential-like field"):
            store.save_component_observation(
                "interloc",
                "bad-probe",
                {"api_key": "should-never-be-written"},
            )

    with StateStore(config) as reopened:
        assert reopened.load_component_observation("ansible", "probe-001") == {
            "contract": "execution/1.0",
            "qualified": True,
            "latency_ms": 12,
        }
        rows = (
            reopened._require_connection()
            .execute("SELECT count(*) FROM component_observations WHERE observation_id='bad-probe'")
            .fetchone()
        )
        assert rows is not None
        assert rows[0] == 0


def test_transaction_exception_rolls_back_completely(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with StateStore(config) as store:
        with pytest.raises(RuntimeError, match="synthetic interruption"):
            with store.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO component_observations(
                        component_id, observation_id, payload_json, observed_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    ("test", "rollback", "{}", datetime.now(UTC).isoformat()),
                )
                raise RuntimeError("synthetic interruption")

        count = (
            store._require_connection()
            .execute("SELECT count(*) FROM component_observations WHERE observation_id='rollback'")
            .fetchone()[0]
        )
        assert count == 0


def test_interrupted_effect_reopens_as_indeterminate_not_success(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with StateStore(config) as store:
        prepared = store.prepare_effect(
            "effect-001",
            "git-merge",
            {"repository": "techrote/omnipanel", "pr": 123},
        )
        assert prepared.state is EffectState.PREPARED

    with StateStore(config) as reopened:
        recovered = reopened.load_effect("effect-001")
        assert recovered.state is EffectState.INDETERMINATE
        assert reopened.list_effects(EffectState.COMMITTED) == ()
        assert reopened.list_effects(EffectState.INDETERMINATE) == (recovered,)


@pytest.mark.parametrize("outcome", [EffectState.COMMITTED, EffectState.ABORTED])
def test_indeterminate_effect_can_be_reconciled_after_restart(
    tmp_path: Path,
    outcome: EffectState,
) -> None:
    config = _config(tmp_path)
    with StateStore(config) as store:
        store.prepare_effect("effect-reconcile", "provider-call")

    with StateStore(config) as reopened:
        assert reopened.load_effect("effect-reconcile").state is EffectState.INDETERMINATE
        reconciled = reopened.settle_effect("effect-reconcile", outcome)
        assert reconciled.state is outcome

    with StateStore(config) as verified:
        assert verified.load_effect("effect-reconcile").state is outcome


def test_committed_effect_remains_committed_after_restart(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with StateStore(config) as store:
        store.prepare_effect("effect-002", "local-write")
        settled = store.settle_effect("effect-002", EffectState.COMMITTED)
        assert settled.state is EffectState.COMMITTED

    with StateStore(config) as reopened:
        assert reopened.load_effect("effect-002").state is EffectState.COMMITTED


def test_active_resource_reservation_requires_requalification_after_restart(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    reservation = ResourceReservation(
        reservation_id="reservation-001",
        run_id="run-single-001",
        provider_id="local",
        request={"cpu_millicores": 2000, "memory_mib": 4096},
        state=ReservationState.ACTIVE,
        updated_at=now,
    )
    config = _config(tmp_path)
    with StateStore(config) as store:
        store.save_reservation(reservation)
        assert store.load_reservation(reservation.reservation_id).state is ReservationState.ACTIVE

    with StateStore(config) as reopened:
        recovered = reopened.load_reservation(reservation.reservation_id)
        assert recovered.state is ReservationState.INDETERMINATE
        assert recovered.updated_at >= now


def test_settled_resource_reservation_survives_restart(tmp_path: Path) -> None:
    reservation = ResourceReservation(
        reservation_id="reservation-002",
        run_id="run-single-001",
        provider_id="local",
        request={"cpu_millicores": 500},
        state=ReservationState.RELEASED,
        updated_at=datetime.now(UTC),
    )
    config = _config(tmp_path)
    with StateStore(config) as store:
        store.save_reservation(reservation)

    with StateStore(config) as reopened:
        assert reopened.load_reservation("reservation-002") == reservation


def test_effect_detail_rejects_raw_credentials_before_insert(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with StateStore(config) as store:
        with pytest.raises(CredentialStorageError):
            store.prepare_effect(
                "effect-secret",
                "provider-call",
                {"refresh_token": "never persist this"},
            )
        assert store.list_effects() == ()


def test_backup_is_valid_reopenable_snapshot(tmp_path: Path) -> None:
    config = _config(tmp_path)
    backup = (tmp_path / "backup area" / "omnipanel.sqlite3").absolute()
    project = ProjectRecord.model_validate(_fixture()["project"])

    with StateStore(config) as store:
        store.put_record(project)
        assert store.backup_to(backup) == backup

    backup_config = AppConfig(data_dir=backup.parent)
    with StateStore(backup_config, database_name=backup.name) as reopened:
        assert reopened.integrity_check().ok
        assert reopened.get_typed_record(ProjectRecord, project.project_id) == project


def test_relative_backup_path_is_rejected(tmp_path: Path) -> None:
    with StateStore(_config(tmp_path)) as store:
        with pytest.raises(StatePathError, match="absolute"):
            store.backup_to(Path("relative.sqlite3"))


def test_data_path_that_is_a_file_has_useful_error(tmp_path: Path) -> None:
    target = (tmp_path / "not-a-directory").absolute()
    target.write_text("occupied", encoding="utf-8")
    config = AppConfig(data_dir=target)

    with pytest.raises(StatePathError, match="could not be created or opened"):
        StateStore(config).open()


def test_database_name_must_not_escape_data_dir(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(StatePathError, match="simple file name"):
        StateStore(config, database_name="../escape.sqlite3")
