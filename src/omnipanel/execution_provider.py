"""Provider-neutral execution capacity contract and deterministic fake for OP-014.

The provider boundary requests and observes execution. It does not emulate guarantees
that a provider does not enforce, and provider completion is deliberately distinct from
Omnipanel candidate acceptance/adjudication.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Never, Protocol, Self

from pydantic import Field, field_validator, model_validator

from omnipanel.domain.contracts import (
    CapabilityHandle,
    ComponentContractRef,
    ContractModel,
    ContractVersion,
    DisplayText,
    EvidenceDescriptorRecord,
    EvidenceKind,
    EvidenceProducer,
    EvidenceProducerType,
    OpaqueId,
    ProviderRequest,
    ResourceRequest,
    RunRecord,
    TaskId,
)


class ProviderAvailability(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INDETERMINATE = "indeterminate"


class ProviderWorkPurpose(StrEnum):
    EXECUTION = "execution"
    VALIDATION = "validation"


class ProviderReservationState(StrEnum):
    RESERVED = "reserved"
    ACTIVE = "active"
    RELEASED = "released"
    INDETERMINATE = "indeterminate"


class ProviderCandidateLifecycle(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INDETERMINATE = "indeterminate"


class ProviderFailureCode(StrEnum):
    PROVIDER_UNAVAILABLE = "provider-unavailable"
    PROVIDER_CLASS_MISMATCH = "provider-class-mismatch"
    CAPABILITY_UNSUPPORTED = "capability-unsupported"
    PURPOSE_UNSUPPORTED = "purpose-unsupported"
    ISOLATION_UNSUPPORTED = "isolation-unsupported"
    NETWORK_POLICY_UNSUPPORTED = "network-policy-unsupported"
    FILESYSTEM_POLICY_UNSUPPORTED = "filesystem-policy-unsupported"
    RESOURCE_ENFORCEMENT_UNSUPPORTED = "resource-enforcement-unsupported"
    RESOURCES_UNAVAILABLE = "resources-unavailable"
    RESERVATION_NOT_FOUND = "reservation-not-found"
    RESERVATION_STATE_INVALID = "reservation-state-invalid"
    CANDIDATE_NOT_FOUND = "candidate-not-found"
    CANDIDATE_STATE_INVALID = "candidate-state-invalid"
    REQUEST_MISMATCH = "request-mismatch"
    PROVIDER_IDENTITY_MISMATCH = "provider-identity-mismatch"


class ProviderIdentity(ContractModel):
    provider_id: OpaqueId
    provider_class: OpaqueId
    implementation_version: ContractVersion
    interface_contract: ComponentContractRef


class ProviderMetadataItem(ContractModel):
    key: OpaqueId
    value: DisplayText


class ProviderGuarantees(ContractModel):
    isolation: bool = Field(strict=True)
    resource_limits: bool = Field(strict=True)
    network_policy: bool = Field(strict=True)
    filesystem_policy: bool = Field(strict=True)


class ProviderDescription(ContractModel):
    identity: ProviderIdentity
    capabilities: tuple[CapabilityHandle, ...] = Field(max_length=128)
    supported_purposes: tuple[ProviderWorkPurpose, ...] = Field(min_length=1, max_length=8)
    guarantees: ProviderGuarantees
    metadata: tuple[ProviderMetadataItem, ...] = Field(max_length=64)

    @model_validator(mode="after")
    def _unique_fields(self) -> Self:
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("capabilities must not contain duplicates")
        if len(self.supported_purposes) != len(set(self.supported_purposes)):
            raise ValueError("supported_purposes must not contain duplicates")
        keys = tuple(item.key for item in self.metadata)
        if len(keys) != len(set(keys)):
            raise ValueError("metadata keys must not contain duplicates")
        return self


class ProviderInventory(ContractModel):
    provider: ProviderIdentity
    availability: ProviderAvailability
    total: ResourceRequest
    available: ResourceRequest
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def _available_within_total(self) -> Self:
        for field_name in (
            "cpu_millicores",
            "memory_mib",
            "storage_mib",
            "wall_time_seconds",
            "gpu_count",
        ):
            if getattr(self.available, field_name) > getattr(self.total, field_name):
                raise ValueError(f"available {field_name} cannot exceed total")
        return self


class ProviderReservation(ContractModel):
    reservation_id: OpaqueId
    provider: ProviderIdentity
    run_id: OpaqueId
    request: ProviderRequest
    state: ProviderReservationState
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reservation timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def _ordered_timestamps(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class ProviderCandidateRequest(ContractModel):
    run_id: OpaqueId
    candidate_id: OpaqueId
    task_id: TaskId
    purpose: ProviderWorkPurpose
    reservation_id: OpaqueId
    payload_ref: OpaqueId


class ProviderCandidateHandle(ContractModel):
    provider: ProviderIdentity
    provider_job_id: OpaqueId
    run_id: OpaqueId
    candidate_id: OpaqueId
    task_id: TaskId
    purpose: ProviderWorkPurpose
    reservation_id: OpaqueId


class ProviderCandidateObservation(ContractModel):
    handle: ProviderCandidateHandle
    sequence: int = Field(strict=True, ge=0, le=2_147_483_647)
    lifecycle: ProviderCandidateLifecycle
    observed_at: datetime
    evidence_ids: tuple[OpaqueId, ...] = Field(max_length=128)

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def _unique_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("evidence_ids must not contain duplicates")
        return value


class ProviderEvidenceReceipt(ContractModel):
    provider: ProviderIdentity
    provider_job_id: OpaqueId
    run_id: OpaqueId
    candidate_id: OpaqueId | None = None
    descriptor: EvidenceDescriptorRecord

    @model_validator(mode="after")
    def _provider_provenance_matches(self) -> Self:
        producer = self.descriptor.producer
        if producer.producer_type is not EvidenceProducerType.PROVIDER:
            raise ValueError("provider evidence must use producer_type='provider'")
        if producer.producer_id != self.provider.provider_id:
            raise ValueError("provider evidence producer_id must match provider identity")
        return self


class ProviderDiagnostic(ContractModel):
    code: ProviderFailureCode
    summary: DisplayText
    provider_id: OpaqueId
    reservation_id: OpaqueId | None = None
    candidate_id: OpaqueId | None = None
    missing_capability_handles: tuple[CapabilityHandle, ...] = Field(max_length=64)

    @field_validator("missing_capability_handles")
    @classmethod
    def _unique_missing(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("missing_capability_handles must not contain duplicates")
        return value


class ExecutionProviderError(RuntimeError):
    def __init__(self, diagnostic: ProviderDiagnostic) -> None:
        super().__init__(diagnostic.summary)
        self.diagnostic = diagnostic


class ExecutionProvider(Protocol):
    """Provider-neutral request/observation interface.

    Provider implementations own enforcement. Omnipanel must not fill in missing
    isolation, quota, network or filesystem guarantees above this boundary.
    """

    def describe(self) -> ProviderDescription: ...

    def inventory(self) -> ProviderInventory: ...

    def reserve(self, *, run_id: str, request: ProviderRequest) -> ProviderReservation: ...

    def start(self, request: ProviderCandidateRequest) -> ProviderCandidateHandle: ...

    def observe(self, handle: ProviderCandidateHandle) -> ProviderCandidateObservation: ...

    def cancel(
        self, handle: ProviderCandidateHandle, *, reason: str
    ) -> ProviderCandidateObservation: ...

    def collect_evidence(
        self, handle: ProviderCandidateHandle
    ) -> tuple[ProviderEvidenceReceipt, ...]: ...

    def release(self, reservation_id: str) -> ProviderReservation: ...


def attach_provider_evidence(
    run: RunRecord, receipts: tuple[ProviderEvidenceReceipt, ...]
) -> RunRecord:
    """Attach provider evidence references without converting execution success to acceptance."""

    evidence_ids = list(run.evidence_ids)
    for receipt in receipts:
        if receipt.run_id != run.run_id:
            raise ValueError("provider evidence receipt refers to a different run")
        if receipt.candidate_id is not None and receipt.candidate_id not in run.candidate_ids:
            raise ValueError("provider evidence receipt refers to a candidate outside the run")
        if receipt.descriptor.evidence_id not in evidence_ids:
            evidence_ids.append(receipt.descriptor.evidence_id)
    return run.model_copy(update={"evidence_ids": tuple(evidence_ids)})


class FakeExecutionProvider:
    """Deterministic in-memory provider for lifecycle/resource/error tests.

    ``finish`` is a test control surface, not part of ``ExecutionProvider``. It lets tests
    deterministically advance a provider job to a terminal execution lifecycle without
    granting Omnipanel candidate eligibility or acceptance.
    """

    def __init__(
        self,
        description: ProviderDescription,
        total: ResourceRequest,
        *,
        availability: ProviderAvailability = ProviderAvailability.AVAILABLE,
        clock_start: datetime,
    ) -> None:
        if clock_start.tzinfo is None or clock_start.utcoffset() is None:
            raise ValueError("clock_start must include a timezone")
        self._description = description
        self._total = total
        self._availability = availability
        self._clock_start = clock_start
        self._ticks = 0
        self._reservation_counter = 0
        self._job_counter = 0
        self._evidence_counter = 0
        self._reservations: dict[str, ProviderReservation] = {}
        self._handles: dict[str, ProviderCandidateHandle] = {}
        self._observations: dict[str, ProviderCandidateObservation] = {}
        self._evidence: dict[str, tuple[ProviderEvidenceReceipt, ...]] = {}
        self._reservation_jobs: dict[str, str] = {}

    def describe(self) -> ProviderDescription:
        return self._description

    def inventory(self) -> ProviderInventory:
        return ProviderInventory(
            provider=self._description.identity,
            availability=self._availability,
            total=self._total,
            available=self._available_resources(),
            observed_at=self._now(),
        )

    def set_availability(self, availability: ProviderAvailability) -> None:
        self._availability = availability

    def reserve(self, *, run_id: str, request: ProviderRequest) -> ProviderReservation:
        self._require_available()
        self._validate_provider_request(request)
        available = self._available_resources()
        if not _resource_request_fits(request.resources, available):
            self._raise(
                ProviderFailureCode.RESOURCES_UNAVAILABLE,
                "requested provider resources are unavailable",
            )
        self._reservation_counter += 1
        reservation_id = f"reservation-{self._reservation_counter:04d}"
        timestamp = self._tick()
        reservation = ProviderReservation(
            reservation_id=reservation_id,
            provider=self._description.identity,
            run_id=run_id,
            request=request,
            state=ProviderReservationState.RESERVED,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._reservations[reservation_id] = reservation
        return reservation

    def start(self, request: ProviderCandidateRequest) -> ProviderCandidateHandle:
        self._require_available()
        if request.purpose not in self._description.supported_purposes:
            self._raise(
                ProviderFailureCode.PURPOSE_UNSUPPORTED,
                "provider does not support the requested work purpose",
                reservation_id=request.reservation_id,
                candidate_id=request.candidate_id,
            )
        reservation = self._reservations.get(request.reservation_id)
        if reservation is None:
            self._raise(
                ProviderFailureCode.RESERVATION_NOT_FOUND,
                "provider reservation does not exist",
                reservation_id=request.reservation_id,
                candidate_id=request.candidate_id,
            )
        if reservation.state is not ProviderReservationState.RESERVED:
            self._raise(
                ProviderFailureCode.RESERVATION_STATE_INVALID,
                "provider reservation is not startable",
                reservation_id=request.reservation_id,
                candidate_id=request.candidate_id,
            )
        if reservation.run_id != request.run_id:
            self._raise(
                ProviderFailureCode.REQUEST_MISMATCH,
                "candidate request run_id does not match reservation",
                reservation_id=request.reservation_id,
                candidate_id=request.candidate_id,
            )
        if request.reservation_id in self._reservation_jobs:
            self._raise(
                ProviderFailureCode.RESERVATION_STATE_INVALID,
                "provider reservation already has a candidate job",
                reservation_id=request.reservation_id,
                candidate_id=request.candidate_id,
            )

        self._job_counter += 1
        provider_job_id = f"job-{self._job_counter:04d}"
        handle = ProviderCandidateHandle(
            provider=self._description.identity,
            provider_job_id=provider_job_id,
            run_id=request.run_id,
            candidate_id=request.candidate_id,
            task_id=request.task_id,
            purpose=request.purpose,
            reservation_id=request.reservation_id,
        )
        timestamp = self._tick()
        self._handles[provider_job_id] = handle
        self._observations[provider_job_id] = ProviderCandidateObservation(
            handle=handle,
            sequence=1,
            lifecycle=ProviderCandidateLifecycle.RUNNING,
            observed_at=timestamp,
            evidence_ids=(),
        )
        self._reservation_jobs[request.reservation_id] = provider_job_id
        self._reservations[request.reservation_id] = reservation.model_copy(
            update={"state": ProviderReservationState.ACTIVE, "updated_at": timestamp}
        )
        return handle

    def observe(self, handle: ProviderCandidateHandle) -> ProviderCandidateObservation:
        self._validate_handle(handle)
        return self._observations[handle.provider_job_id]

    def cancel(
        self, handle: ProviderCandidateHandle, *, reason: str
    ) -> ProviderCandidateObservation:
        if not reason.strip():
            raise ValueError("cancel reason must not be empty")
        current = self.observe(handle)
        if _terminal_lifecycle(current.lifecycle):
            self._raise(
                ProviderFailureCode.CANDIDATE_STATE_INVALID,
                "terminal provider candidate cannot be cancelled again",
                reservation_id=handle.reservation_id,
                candidate_id=handle.candidate_id,
            )
        return self._finish(handle, ProviderCandidateLifecycle.CANCELLED, detail=reason)

    def finish(
        self,
        handle: ProviderCandidateHandle,
        lifecycle: ProviderCandidateLifecycle,
        *,
        detail: str = "deterministic fake provider terminal result",
    ) -> ProviderCandidateObservation:
        if lifecycle not in {
            ProviderCandidateLifecycle.SUCCEEDED,
            ProviderCandidateLifecycle.FAILED,
            ProviderCandidateLifecycle.INDETERMINATE,
        }:
            raise ValueError("finish requires succeeded, failed or indeterminate lifecycle")
        current = self.observe(handle)
        if _terminal_lifecycle(current.lifecycle):
            self._raise(
                ProviderFailureCode.CANDIDATE_STATE_INVALID,
                "terminal provider candidate cannot transition again",
                reservation_id=handle.reservation_id,
                candidate_id=handle.candidate_id,
            )
        return self._finish(handle, lifecycle, detail=detail)

    def collect_evidence(
        self, handle: ProviderCandidateHandle
    ) -> tuple[ProviderEvidenceReceipt, ...]:
        self._validate_handle(handle)
        return self._evidence.get(handle.provider_job_id, ())

    def release(self, reservation_id: str) -> ProviderReservation:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            self._raise(
                ProviderFailureCode.RESERVATION_NOT_FOUND,
                "provider reservation does not exist",
                reservation_id=reservation_id,
            )
        if reservation.state is ProviderReservationState.RELEASED:
            return reservation
        job_id = self._reservation_jobs.get(reservation_id)
        if job_id is not None and not _terminal_lifecycle(self._observations[job_id].lifecycle):
            self._raise(
                ProviderFailureCode.RESERVATION_STATE_INVALID,
                "active provider reservation cannot be released before candidate termination",
                reservation_id=reservation_id,
                candidate_id=self._handles[job_id].candidate_id,
            )
        released = reservation.model_copy(
            update={"state": ProviderReservationState.RELEASED, "updated_at": self._tick()}
        )
        self._reservations[reservation_id] = released
        return released

    def _validate_provider_request(self, request: ProviderRequest) -> None:
        description = self._description
        if (
            request.provider_class is not None
            and request.provider_class != description.identity.provider_class
        ):
            self._raise(
                ProviderFailureCode.PROVIDER_CLASS_MISMATCH,
                "requested provider class does not match this provider",
            )
        missing = tuple(
            item
            for item in request.required_capability_handles
            if item not in description.capabilities
        )
        if missing:
            self._raise(
                ProviderFailureCode.CAPABILITY_UNSUPPORTED,
                "provider lacks one or more required capabilities",
                missing_capability_handles=missing,
            )
        guarantees = description.guarantees
        if request.isolation_required and not guarantees.isolation:
            self._raise(
                ProviderFailureCode.ISOLATION_UNSUPPORTED,
                "provider cannot enforce requested isolation",
            )
        if not guarantees.network_policy:
            self._raise(
                ProviderFailureCode.NETWORK_POLICY_UNSUPPORTED,
                "provider cannot enforce the request network policy",
            )
        if not guarantees.filesystem_policy:
            self._raise(
                ProviderFailureCode.FILESYSTEM_POLICY_UNSUPPORTED,
                "provider cannot enforce the request writable-path policy",
            )
        if _has_resource_limits(request.resources) and not guarantees.resource_limits:
            self._raise(
                ProviderFailureCode.RESOURCE_ENFORCEMENT_UNSUPPORTED,
                "provider cannot enforce requested resource limits",
            )

    def _require_available(self) -> None:
        if self._availability in {
            ProviderAvailability.UNAVAILABLE,
            ProviderAvailability.INDETERMINATE,
        }:
            self._raise(
                ProviderFailureCode.PROVIDER_UNAVAILABLE,
                "provider is unavailable or indeterminate",
            )

    def _validate_handle(self, handle: ProviderCandidateHandle) -> None:
        if handle.provider != self._description.identity:
            self._raise(
                ProviderFailureCode.PROVIDER_IDENTITY_MISMATCH,
                "candidate handle belongs to a different provider identity/version",
                reservation_id=handle.reservation_id,
                candidate_id=handle.candidate_id,
            )
        stored = self._handles.get(handle.provider_job_id)
        if stored is None:
            self._raise(
                ProviderFailureCode.CANDIDATE_NOT_FOUND,
                "provider candidate job does not exist",
                reservation_id=handle.reservation_id,
                candidate_id=handle.candidate_id,
            )
        if stored != handle:
            self._raise(
                ProviderFailureCode.REQUEST_MISMATCH,
                "candidate handle fields do not match provider state",
                reservation_id=handle.reservation_id,
                candidate_id=handle.candidate_id,
            )

    def _finish(
        self,
        handle: ProviderCandidateHandle,
        lifecycle: ProviderCandidateLifecycle,
        *,
        detail: str,
    ) -> ProviderCandidateObservation:
        self._evidence_counter += 1
        evidence_id = f"provider-evidence-{self._evidence_counter:04d}"
        timestamp = self._tick()
        descriptor = EvidenceDescriptorRecord(
            evidence_id=evidence_id,
            kind=EvidenceKind.PROVENANCE,
            producer=EvidenceProducer(
                producer_type=EvidenceProducerType.PROVIDER,
                producer_id=self._description.identity.provider_id,
            ),
            location=(
                f"provider://{self._description.identity.provider_id}/"
                f"{self._description.identity.implementation_version}/"
                f"{handle.provider_job_id}/{lifecycle.value}"
            ),
            created_at=timestamp,
        )
        receipt = ProviderEvidenceReceipt(
            provider=self._description.identity,
            provider_job_id=handle.provider_job_id,
            run_id=handle.run_id,
            candidate_id=handle.candidate_id,
            descriptor=descriptor,
        )
        self._evidence[handle.provider_job_id] = (receipt,)
        current = self._observations[handle.provider_job_id]
        observation = ProviderCandidateObservation(
            handle=handle,
            sequence=current.sequence + 1,
            lifecycle=lifecycle,
            observed_at=timestamp,
            evidence_ids=(evidence_id,),
        )
        self._observations[handle.provider_job_id] = observation
        if detail.strip():
            # The fake keeps the result detail out of durable/evidence contracts; the
            # deterministic evidence location and receipt carry the provider provenance.
            _ = detail
        return observation

    def _available_resources(self) -> ResourceRequest:
        active = tuple(
            reservation.request.resources
            for reservation in self._reservations.values()
            if reservation.state in {
                ProviderReservationState.RESERVED,
                ProviderReservationState.ACTIVE,
            }
        )
        return _subtract_resources(self._total, active)

    def _now(self) -> datetime:
        return self._clock_start + timedelta(microseconds=self._ticks)

    def _tick(self) -> datetime:
        self._ticks += 1
        return self._now()

    def _raise(
        self,
        code: ProviderFailureCode,
        summary: str,
        *,
        reservation_id: str | None = None,
        candidate_id: str | None = None,
        missing_capability_handles: tuple[str, ...] = (),
    ) -> Never:
        raise ExecutionProviderError(
            ProviderDiagnostic(
                code=code,
                summary=summary,
                provider_id=self._description.identity.provider_id,
                reservation_id=reservation_id,
                candidate_id=candidate_id,
                missing_capability_handles=missing_capability_handles,
            )
        )


def _has_resource_limits(request: ResourceRequest) -> bool:
    return any(
        (
            request.cpu_millicores,
            request.memory_mib,
            request.storage_mib,
            request.wall_time_seconds,
            request.gpu_count,
        )
    )


def _resource_request_fits(request: ResourceRequest, available: ResourceRequest) -> bool:
    return all(
        getattr(request, field_name) <= getattr(available, field_name)
        for field_name in (
            "cpu_millicores",
            "memory_mib",
            "storage_mib",
            "wall_time_seconds",
            "gpu_count",
        )
    )


def _subtract_resources(total: ResourceRequest, reservations: tuple[ResourceRequest, ...]) -> ResourceRequest:
    """Subtract fungible capacity; wall time remains a per-job maximum ceiling."""

    return ResourceRequest(
        cpu_millicores=max(0, total.cpu_millicores - sum(item.cpu_millicores for item in reservations)),
        memory_mib=max(0, total.memory_mib - sum(item.memory_mib for item in reservations)),
        storage_mib=max(0, total.storage_mib - sum(item.storage_mib for item in reservations)),
        wall_time_seconds=total.wall_time_seconds,
        gpu_count=max(0, total.gpu_count - sum(item.gpu_count for item in reservations)),
    )


def _terminal_lifecycle(lifecycle: ProviderCandidateLifecycle) -> bool:
    return lifecycle in {
        ProviderCandidateLifecycle.SUCCEEDED,
        ProviderCandidateLifecycle.FAILED,
        ProviderCandidateLifecycle.CANCELLED,
        ProviderCandidateLifecycle.INDETERMINATE,
    }


__all__ = [
    "ExecutionProvider",
    "ExecutionProviderError",
    "FakeExecutionProvider",
    "ProviderAvailability",
    "ProviderCandidateHandle",
    "ProviderCandidateLifecycle",
    "ProviderCandidateObservation",
    "ProviderCandidateRequest",
    "ProviderDescription",
    "ProviderDiagnostic",
    "ProviderEvidenceReceipt",
    "ProviderFailureCode",
    "ProviderGuarantees",
    "ProviderIdentity",
    "ProviderInventory",
    "ProviderMetadataItem",
    "ProviderReservation",
    "ProviderReservationState",
    "ProviderWorkPurpose",
    "attach_provider_evidence",
]
