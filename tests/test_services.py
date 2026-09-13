from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import DagEdge, ModelIdentityRecord, ProjectRecord, TaskRecord
from omnipanel.services import (
    ApplicationServices,
    BoundedUpdateStream,
    ServiceConfigurationError,
    UpdateTopic,
)
from omnipanel.storage import ReservationState, ResourceReservation, StateStore

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op002_examples.json"


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(data_dir=(tmp_path / "service state 東京").absolute())


def _project() -> ProjectRecord:
    return ProjectRecord.model_validate(_fixture()["project"])


def _task() -> TaskRecord:
    return TaskRecord.model_validate(_fixture()["task"])


def _model_identity() -> ModelIdentityRecord:
    return ModelIdentityRecord.model_validate(_fixture()["model_identity"])


def test_services_require_open_store(tmp_path: Path) -> None:
    with pytest.raises(ServiceConfigurationError, match="must be open"):
        ApplicationServices(StateStore(_config(tmp_path)))


def test_initial_connect_returns_durable_snapshot(tmp_path: Path) -> None:
    with StateStore(_config(tmp_path)) as store:
        store.put_record(_project())
        store.put_record(_task())
        store.save_policy(_task().task_id, _task().policy)
        services = ApplicationServices(store)
        sync = services.connect()

    assert sync.snapshot is not None
    assert sync.updates == ()
    assert sync.snapshot.projects == (_project(),)
    assert sync.snapshot.tasks == (_task(),)
    assert sync.snapshot.policies[0].policy == _task().policy


def test_disconnect_reconnect_replays_bounded_updates(tmp_path: Path) -> None:
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store, update_capacity=4)
        cursor = services.connect().cursor
        services.put_record(_project())
        services.put_record(_task())
        sync = services.connect(cursor)

    assert sync.snapshot is None
    assert [update.entity_type for update in sync.updates] == ["project", "task"]
    assert [update.sequence for update in sync.updates] == [1, 2]


def test_topology_and_canonical_model_views_are_present(tmp_path: Path) -> None:
    edge = DagEdge(predecessor_task_id="OP-003", successor_task_id="OP-004")
    model = _model_identity()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        start = services.connect().cursor
        edge_key = services.put_record(edge)
        services.put_record(model)
        sync = services.connect(start)
        snapshot = services.snapshot()

    assert edge_key == "OP-003->OP-004"
    assert sync.updates[0].entity_id == edge_key
    assert snapshot.dag_edges == (edge,)
    assert snapshot.model_identities == (model,)


def test_overflowed_cursor_falls_back_to_snapshot(tmp_path: Path) -> None:
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store, update_capacity=1)
        old_cursor = services.connect().cursor
        services.put_record(_project())
        services.put_record(_task())
        sync = services.connect(old_cursor)

    assert sync.snapshot is not None
    assert sync.updates == ()
    assert sync.snapshot.projects == (_project(),)
    assert sync.snapshot.tasks == (_task(),)


def test_service_restart_uses_durable_state_not_old_event_buffer(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with StateStore(config) as store:
        first = ApplicationServices(store)
        old_cursor = first.connect().cursor
        first.put_record(_project())

    with StateStore(config) as reopened:
        second = ApplicationServices(reopened)
        sync = second.connect(old_cursor)

    assert sync.snapshot is not None
    assert sync.snapshot.projects == (_project(),)
    assert sync.cursor.epoch != old_cursor.epoch


def test_policy_and_resource_mutations_emit_typed_updates(tmp_path: Path) -> None:
    reservation = ResourceReservation(
        reservation_id="reservation-service-001",
        run_id="run-single-001",
        provider_id="local",
        request={"cpu_millicores": 1000, "memory_mib": 2048, "gpu_count": 1},
        state=ReservationState.ACTIVE,
        updated_at=datetime.now(UTC),
    )
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        start = services.connect().cursor
        services.save_policy("OP-004", _task().policy)
        services.save_reservation(reservation)
        sync = services.connect(start)
        snapshot = services.snapshot()

    assert [update.topic for update in sync.updates] == [
        UpdateTopic.POLICY,
        UpdateTopic.RESOURCE,
    ]
    assert snapshot.resources.total == 1
    assert snapshot.resources.active == 1
    assert snapshot.resources.cpu_millicores == 1000
    assert snapshot.resources.memory_mib == 2048
    assert snapshot.resources.gpu_count == 1


def test_update_stream_capacity_is_strict_and_bounded() -> None:
    with pytest.raises(ServiceConfigurationError):
        BoundedUpdateStream(0)
    stream = BoundedUpdateStream(2)
    cursor = stream.cursor
    stream.publish(UpdateTopic.RECORD, "task", "OP-004")
    stream.publish(UpdateTopic.RECORD, "task", "OP-005")
    stream.publish(UpdateTopic.RECORD, "task", "OP-006")
    assert stream.replay(cursor) is None


def test_core_service_module_has_no_textual_dependency() -> None:
    source = (ROOT / "src" / "omnipanel" / "services.py").read_text(encoding="utf-8")
    assert "import textual" not in source
    assert "from textual" not in source
