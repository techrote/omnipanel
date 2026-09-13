"""UI-independent durable-state views and bounded update delivery."""

from __future__ import annotations

import uuid
from collections import deque
from enum import StrEnum
from typing import TypeVar

from pydantic import Field, ValidationError

from omnipanel.domain.contracts import (
    CandidateRecord,
    ContractModel,
    EvidenceDescriptorRecord,
    MetaissueRecord,
    ModelAssessmentRecord,
    OpaqueId,
    ProjectRecord,
    RunRecord,
    TaskPolicy,
    TaskRecord,
    VersionedRecord,
)
from omnipanel.storage import (
    RecordNotFoundError,
    ReservationState,
    ResourceReservation,
    StateCorruptionError,
    StateStore,
)

TRecord = TypeVar("TRecord", bound=VersionedRecord)


class ServiceConfigurationError(ValueError):
    pass


class UpdateTopic(StrEnum):
    RECORD = "record"
    POLICY = "policy"
    RESOURCE = "resource"


class ServiceCursor(ContractModel):
    epoch: OpaqueId
    sequence: int = Field(strict=True, ge=0)


class ServiceUpdate(ContractModel):
    epoch: OpaqueId
    sequence: int = Field(strict=True, ge=1)
    topic: UpdateTopic
    entity_type: OpaqueId
    entity_id: OpaqueId


class PolicyView(ContractModel):
    task_id: OpaqueId
    policy: TaskPolicy


class ResourceSummary(ContractModel):
    total: int = Field(strict=True, ge=0)
    reserved: int = Field(strict=True, ge=0)
    active: int = Field(strict=True, ge=0)
    released: int = Field(strict=True, ge=0)
    indeterminate: int = Field(strict=True, ge=0)
    cpu_millicores: int = Field(strict=True, ge=0)
    memory_mib: int = Field(strict=True, ge=0)
    storage_mib: int = Field(strict=True, ge=0)
    gpu_count: int = Field(strict=True, ge=0)


class ApplicationSnapshot(ContractModel):
    projects: tuple[ProjectRecord, ...]
    metaissues: tuple[MetaissueRecord, ...]
    tasks: tuple[TaskRecord, ...]
    runs: tuple[RunRecord, ...]
    candidates: tuple[CandidateRecord, ...]
    evidence: tuple[EvidenceDescriptorRecord, ...]
    models: tuple[ModelAssessmentRecord, ...]
    policies: tuple[PolicyView, ...]
    resources: ResourceSummary


class ServiceSync(ContractModel):
    cursor: ServiceCursor
    snapshot: ApplicationSnapshot | None = None
    updates: tuple[ServiceUpdate, ...] = ()


class BoundedUpdateStream:
    """Process-local replay buffer; stale/foreign cursors require a durable snapshot."""

    def __init__(self, capacity: int = 256) -> None:
        if type(capacity) is not int or not 1 <= capacity <= 4096:
            raise ServiceConfigurationError("update buffer capacity must be 1..4096")
        self._epoch = uuid.uuid4().hex
        self._sequence = 0
        self._updates: deque[ServiceUpdate] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        maxlen = self._updates.maxlen
        assert maxlen is not None
        return maxlen

    @property
    def cursor(self) -> ServiceCursor:
        return ServiceCursor(epoch=self._epoch, sequence=self._sequence)

    def publish(self, topic: UpdateTopic, entity_type: str, entity_id: str) -> ServiceUpdate:
        self._sequence += 1
        update = ServiceUpdate(
            epoch=self._epoch,
            sequence=self._sequence,
            topic=topic,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        self._updates.append(update)
        return update

    def replay(self, cursor: ServiceCursor) -> tuple[ServiceUpdate, ...] | None:
        if cursor.epoch != self._epoch or cursor.sequence > self._sequence:
            return None
        oldest = self._updates[0].sequence if self._updates else self._sequence + 1
        if cursor.sequence < oldest - 1:
            return None
        return tuple(update for update in self._updates if update.sequence > cursor.sequence)


class ApplicationServices:
    """Typed service boundary between durable state and presentation layers."""

    def __init__(self, store: StateStore, *, update_capacity: int = 256) -> None:
        if not store.is_open:
            raise ServiceConfigurationError("StateStore must be open before services start")
        self.store = store
        self.updates = BoundedUpdateStream(update_capacity)

    def connect(self, cursor: ServiceCursor | None = None) -> ServiceSync:
        if cursor is None:
            return ServiceSync(cursor=self.updates.cursor, snapshot=self.snapshot())
        replay = self.updates.replay(cursor)
        if replay is None:
            return ServiceSync(cursor=self.updates.cursor, snapshot=self.snapshot())
        return ServiceSync(cursor=self.updates.cursor, updates=replay)

    def put_record(self, record: VersionedRecord) -> str:
        key = self.store.put_record(record)
        record_type = getattr(record, "record_type", "record")
        self.updates.publish(UpdateTopic.RECORD, str(record_type), key)
        return key

    def save_policy(self, task_id: str, policy: TaskPolicy) -> None:
        self.store.save_policy(task_id, policy)
        self.updates.publish(UpdateTopic.POLICY, "task-policy", task_id)

    def save_reservation(self, reservation: ResourceReservation) -> None:
        self.store.save_reservation(reservation)
        self.updates.publish(
            UpdateTopic.RESOURCE,
            "resource-reservation",
            reservation.reservation_id,
        )

    def snapshot(self) -> ApplicationSnapshot:
        tasks = self._records(TaskRecord, "task")
        return ApplicationSnapshot(
            projects=self._records(ProjectRecord, "project"),
            metaissues=self._records(MetaissueRecord, "metaissue"),
            tasks=tasks,
            runs=self._records(RunRecord, "run"),
            candidates=self._records(CandidateRecord, "candidate-state"),
            evidence=self._records(EvidenceDescriptorRecord, "evidence"),
            models=self._records(ModelAssessmentRecord, "model-assessment"),
            policies=self._policies(tasks),
            resources=self._resource_summary(),
        )

    def _records(self, model: type[TRecord], record_type: str) -> tuple[TRecord, ...]:
        return tuple(
            self.store.get_typed_record(model, key)
            for key in self.store.list_record_keys(record_type)
        )

    def _policies(self, tasks: tuple[TaskRecord, ...]) -> tuple[PolicyView, ...]:
        views: list[PolicyView] = []
        for task in tasks:
            try:
                policy = self.store.load_policy(task.task_id)
            except RecordNotFoundError:
                continue
            views.append(PolicyView(task_id=task.task_id, policy=policy))
        return tuple(views)

    def _reservations(self) -> tuple[ResourceReservation, ...]:
        rows = self.store._require_connection().execute(
            "SELECT payload_json FROM resource_reservations ORDER BY reservation_id"
        )
        items: list[ResourceReservation] = []
        for row in rows:
            try:
                items.append(ResourceReservation.model_validate_json(str(row["payload_json"])))
            except ValidationError as exc:
                raise StateCorruptionError(
                    "resource reservation failed service validation"
                ) from exc
        return tuple(items)

    def _resource_summary(self) -> ResourceSummary:
        reservations = self._reservations()
        live = tuple(
            item for item in reservations if item.state is not ReservationState.RELEASED
        )
        return ResourceSummary(
            total=len(reservations),
            reserved=sum(item.state is ReservationState.RESERVED for item in reservations),
            active=sum(item.state is ReservationState.ACTIVE for item in reservations),
            released=sum(item.state is ReservationState.RELEASED for item in reservations),
            indeterminate=sum(
                item.state is ReservationState.INDETERMINATE for item in reservations
            ),
            cpu_millicores=sum(item.request.cpu_millicores for item in live),
            memory_mib=sum(item.request.memory_mib for item in live),
            storage_mib=sum(item.request.storage_mib for item in live),
            gpu_count=sum(item.request.gpu_count for item in live),
        )
