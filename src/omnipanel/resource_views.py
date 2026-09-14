"""Fail-closed execution-provider/resource dashboard projections for OP-010."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from omnipanel.domain.contracts import ContractModel, ResourceRequest, TaskRecord
from omnipanel.execution_provider import ProviderAvailability, ProviderWorkPurpose
from omnipanel.resource_ledger import (
    ProviderResourceView,
    ResourceAccountingState,
    ResourceLedgerSnapshot,
)
from omnipanel.services import ApplicationSnapshot

_SAFE_METADATA_KEYS = (
    "host.id",
    "placement.kind",
    "os.family",
    "platform.id",
    "environment.kind",
    "image.id",
    "harness.id",
)


class ProviderQualificationState(StrEnum):
    QUALIFIED = "qualified"
    INCOMPATIBLE = "incompatible"
    INDETERMINATE = "indeterminate"


class ProviderPoolState(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    PAUSED = "paused"
    INDETERMINATE = "indeterminate"


class SurplusComputeState(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    PAUSED = "paused"
    INDETERMINATE = "indeterminate"


class PlacementState(StrEnum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    INDETERMINATE = "indeterminate"


class ProviderQualificationObservation(ContractModel):
    provider_id: str = Field(min_length=1, max_length=128)
    state: ProviderQualificationState
    observed_at: datetime
    reason: str = Field(min_length=1, max_length=1024)

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class ProviderPoolObservation(ContractModel):
    pool_id: str = Field(min_length=1, max_length=128)
    provider_ids: tuple[str, ...] = Field(min_length=1, max_length=64)
    state: ProviderPoolState
    observed_at: datetime
    note: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def _unique_providers(self) -> Self:
        if len(self.provider_ids) != len(set(self.provider_ids)):
            raise ValueError("provider_ids must not contain duplicates")
        return self


class SurplusComputeObservation(ContractModel):
    state: SurplusComputeState
    observed_at: datetime
    provider_id: str | None = Field(default=None, min_length=1, max_length=128)
    cpu_millicores: int = Field(default=0, strict=True, ge=0)
    reason: str = Field(min_length=1, max_length=1024)

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class ResourceDashboardObservations(ContractModel):
    qualifications: tuple[ProviderQualificationObservation, ...] = ()
    pools: tuple[ProviderPoolObservation, ...] = ()
    surplus: SurplusComputeObservation | None = None


class PlacementAssessment(ContractModel):
    provider_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=128)
    state: PlacementState
    reasons: tuple[str, ...] = Field(min_length=1, max_length=32)


def selected_provider_id(snapshot: ResourceLedgerSnapshot, current: str | None) -> str | None:
    ids = tuple(item.description.identity.provider_id for item in snapshot.providers)
    if not ids:
        return None
    return current if current in ids else ids[0]


def selected_reservation_id(
    snapshot: ResourceLedgerSnapshot,
    provider_id: str | None,
    current: str | None,
) -> str | None:
    if provider_id is None:
        return None
    provider = next(
        (
            item
            for item in snapshot.providers
            if item.description.identity.provider_id == provider_id
        ),
        None,
    )
    if provider is None:
        return None
    ids = tuple(item.reservation_id for item in provider.reservations)
    if not ids:
        return None
    return current if current in ids else ids[0]


def selected_resource_task_id(snapshot: ApplicationSnapshot, current: str | None) -> str | None:
    ids = tuple(item.task_id for item in snapshot.tasks)
    if not ids:
        return None
    return current if current in ids else ids[0]


def assess_task_placement(
    task: TaskRecord,
    provider: ProviderResourceView,
    qualification: ProviderQualificationObservation | None,
    *,
    purpose: ProviderWorkPurpose = ProviderWorkPurpose.EXECUTION,
) -> PlacementAssessment:
    provider_id = provider.description.identity.provider_id
    request = task.provider_request
    reasons: list[str] = []
    state = PlacementState.ELIGIBLE

    if qualification is None:
        state = PlacementState.INDETERMINATE
        reasons.append("provider compatibility qualification unavailable")
    elif qualification.state is ProviderQualificationState.INDETERMINATE:
        state = PlacementState.INDETERMINATE
        reasons.append(f"provider compatibility indeterminate: {qualification.reason}")
    elif qualification.state is ProviderQualificationState.INCOMPATIBLE:
        state = PlacementState.BLOCKED
        reasons.append(f"provider incompatible: {qualification.reason}")

    if provider.availability is ProviderAvailability.UNAVAILABLE:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append("provider unavailable")
    elif provider.availability is ProviderAvailability.INDETERMINATE:
        state = _combine_placement(state, PlacementState.INDETERMINATE)
        reasons.append("provider availability indeterminate")
    elif provider.availability is ProviderAvailability.DEGRADED:
        reasons.append("provider availability degraded")

    if provider.accounting_state is not ResourceAccountingState.CONSISTENT:
        state = _combine_placement(state, PlacementState.INDETERMINATE)
        reasons.append(f"resource accounting {provider.accounting_state.value}")

    description = provider.description
    if purpose not in description.supported_purposes:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append(f"work purpose {purpose.value} unsupported")
    if request.provider_class is not None:
        if request.provider_class != description.identity.provider_class:
            state = _combine_placement(state, PlacementState.BLOCKED)
            reasons.append(
                "provider class mismatch: "
                f"needs {request.provider_class}, has {description.identity.provider_class}"
            )

    missing = tuple(
        handle
        for handle in request.required_capability_handles
        if handle not in description.capabilities
    )
    if missing:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append("missing capabilities: " + ",".join(missing))

    guarantees = description.guarantees
    if request.isolation_required and not guarantees.isolation:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append("requested isolation cannot be enforced")
    if not guarantees.network_policy:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append("network policy cannot be enforced")
    if not guarantees.filesystem_policy:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append("filesystem policy cannot be enforced")
    if _has_resource_limits(request.resources) and not guarantees.resource_limits:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append("resource limits cannot be enforced")

    shortages = _resource_shortages(request.resources, provider.reported_available)
    if shortages:
        state = _combine_placement(state, PlacementState.BLOCKED)
        reasons.append("insufficient resources: " + ",".join(shortages))

    if not reasons:
        reasons.append("provider qualified, available and within accounted capacity")
    elif state is PlacementState.ELIGIBLE:
        reasons.append("placement remains eligible under degraded provider state")
    return PlacementAssessment(
        provider_id=provider_id,
        task_id=task.task_id,
        state=state,
        reasons=tuple(reasons),
    )


def render_resource_dashboard(
    application: ApplicationSnapshot,
    resources: ResourceLedgerSnapshot | None,
    *,
    observations: ResourceDashboardObservations = ResourceDashboardObservations(),
    selected_provider: str | None = None,
    selected_reservation: str | None = None,
    selected_task: str | None = None,
    notice: str | None = None,
) -> str:
    if resources is None:
        lines = [
            "Resource ledger: INDETERMINATE (no qualified provider ledger connected)",
            f"Durable reservations: {application.resources.total}",
            f"Durable indeterminate: {application.resources.indeterminate}",
        ]
        if notice:
            lines.insert(0, f"Notice: {notice}")
        return "\n".join(lines)

    provider_id = selected_provider_id(resources, selected_provider)
    reservation_id = selected_reservation_id(resources, provider_id, selected_reservation)
    task_id = selected_resource_task_id(application, selected_task)
    qualifications = _qualification_map(observations)
    lines: list[str] = []
    if notice:
        lines.append(f"Notice: {notice}")
    lines.extend(
        (
            f"Providers: {len(resources.providers)}  "
            f"Durable reservations: {len(resources.reservations)}",
            "Provider list",
        )
    )
    if not resources.providers:
        lines.append("- none; provider availability INDETERMINATE")
    for provider in resources.providers:
        identity = provider.description.identity
        marker = ">" if identity.provider_id == provider_id else " "
        qualification = qualifications.get(identity.provider_id)
        qualification_text = (
            qualification.state.value if qualification is not None else "indeterminate"
        )
        lines.append(
            f"{marker} {identity.provider_id} class={identity.provider_class} "
            f"version={identity.implementation_version} compatibility={qualification_text} "
            f"availability={provider.availability.value} accounting={provider.accounting_state.value}"
        )

    if provider_id is not None:
        provider = next(
            item
            for item in resources.providers
            if item.description.identity.provider_id == provider_id
        )
        lines.extend(("", _render_provider_detail(provider, reservation_id, qualifications)))

    lines.extend(("", _render_placement_matrix(application, resources, task_id, qualifications)))
    lines.extend(("", _render_pools(resources, observations)))
    lines.extend(("", _render_surplus(observations)))
    return "\n".join(lines)


def _render_provider_detail(
    provider: ProviderResourceView,
    reservation_id: str | None,
    qualifications: dict[str, ProviderQualificationObservation],
) -> str:
    description = provider.description
    identity = description.identity
    qualification = qualifications.get(identity.provider_id)
    compatibility = qualification.state.value if qualification else "indeterminate"
    compatibility_reason = (
        qualification.reason if qualification else "no qualification observation supplied"
    )
    lines = [
        f"Provider detail: {identity.provider_id}",
        f"interface={identity.interface_contract.component_id}/"
        f"{identity.interface_contract.contract_id}@"
        f"{identity.interface_contract.contract_version}",
        f"compatibility={compatibility} reason={compatibility_reason}",
        "purposes=" + ",".join(item.value for item in description.supported_purposes),
        "capabilities=" + (",".join(description.capabilities) or "none"),
        "capacity "
        f"cpu={provider.reported_available.cpu_millicores}/{provider.total.cpu_millicores}m free "
        f"memory={provider.reported_available.memory_mib}/{provider.total.memory_mib}MiB free "
        f"storage={provider.reported_available.storage_mib}/{provider.total.storage_mib}MiB free "
        f"gpu={provider.reported_available.gpu_count}/{provider.total.gpu_count} free "
        f"wall-ceiling={provider.total.wall_time_seconds}s",
        "ledger-reserved "
        f"cpu={provider.ledger_reserved.cpu_millicores}m "
        f"memory={provider.ledger_reserved.memory_mib}MiB "
        f"storage={provider.ledger_reserved.storage_mib}MiB "
        f"gpu={provider.ledger_reserved.gpu_count}",
        "delta(provider-ledger) "
        f"cpu={provider.delta.cpu_millicores:+d}m "
        f"memory={provider.delta.memory_mib:+d}MiB "
        f"storage={provider.delta.storage_mib:+d}MiB "
        f"gpu={provider.delta.gpu_count:+d}",
    ]
    safe_metadata = tuple(
        item
        for item in description.metadata
        if item.key in _SAFE_METADATA_KEYS
    )
    lines.append(
        "metadata="
        + (" ".join(f"{item.key}={item.value}" for item in safe_metadata) or "none")
    )
    if provider.issues:
        lines.append("issues=" + "; ".join(f"{item.code.value}:{item.detail}" for item in provider.issues))
    else:
        lines.append("issues=none")
    lines.append("Reservations")
    if not provider.reservations:
        lines.append("- none")
    for reservation in provider.reservations:
        marker = ">" if reservation.reservation_id == reservation_id else " "
        candidate = reservation.candidate_id or "unknown"
        provider_reservation = reservation.provider_reservation_id or "unknown"
        lines.append(
            f"{marker} {reservation.reservation_id} provider-id={provider_reservation} "
            f"run={reservation.run_id} candidate={candidate} state={reservation.state.value} "
            f"cpu={reservation.request.cpu_millicores}m "
            f"memory={reservation.request.memory_mib}MiB"
        )
    return "\n".join(lines)


def _render_placement_matrix(
    application: ApplicationSnapshot,
    resources: ResourceLedgerSnapshot,
    task_id: str | None,
    qualifications: dict[str, ProviderQualificationObservation],
) -> str:
    if task_id is None:
        return "Task placement\n- no durable task selected"
    task = next(item for item in application.tasks if item.task_id == task_id)
    lines = [f"Task placement: {task.task_id} {task.display_name}"]
    if not resources.providers:
        lines.append("- no providers; placement INDETERMINATE")
        return "\n".join(lines)
    for provider in resources.providers:
        assessment = assess_task_placement(
            task,
            provider,
            qualifications.get(provider.description.identity.provider_id),
        )
        lines.append(
            f"- {assessment.provider_id}: {assessment.state.value.upper()} — "
            + "; ".join(assessment.reasons)
        )
    return "\n".join(lines)


def _render_pools(
    resources: ResourceLedgerSnapshot,
    observations: ResourceDashboardObservations,
) -> str:
    lines = ["Worker pools"]
    if not observations.pools:
        lines.append("- topology INDETERMINATE (no pool observation supplied)")
        return "\n".join(lines)
    provider_map = {
        item.description.identity.provider_id: item for item in resources.providers
    }
    for pool in observations.pools:
        members = tuple(provider_map.get(provider_id) for provider_id in pool.provider_ids)
        missing = tuple(
            provider_id
            for provider_id, member in zip(pool.provider_ids, members, strict=True)
            if member is None
        )
        present = tuple(member for member in members if member is not None)
        total_cpu = sum(item.total.cpu_millicores for item in present)
        free_cpu = sum(item.reported_available.cpu_millicores for item in present)
        total_memory = sum(item.total.memory_mib for item in present)
        free_memory = sum(item.reported_available.memory_mib for item in present)
        state = pool.state.value if not missing else "indeterminate"
        suffix = f" missing={','.join(missing)}" if missing else ""
        note = f" note={pool.note}" if pool.note else ""
        lines.append(
            f"- {pool.pool_id}: state={state} providers={len(present)}/{len(pool.provider_ids)} "
            f"cpu={free_cpu}/{total_cpu}m free memory={free_memory}/{total_memory}MiB free"
            f"{suffix}{note}"
        )
    return "\n".join(lines)


def _render_surplus(observations: ResourceDashboardObservations) -> str:
    surplus = observations.surplus
    if surplus is None:
        return "Surplus compute\nstate=INDETERMINATE reason=no surplus-compute observation supplied"
    provider = surplus.provider_id or "none"
    return (
        "Surplus compute\n"
        f"state={surplus.state.value} provider={provider} "
        f"cpu={surplus.cpu_millicores}m reason={surplus.reason}"
    )


def _qualification_map(
    observations: ResourceDashboardObservations,
) -> dict[str, ProviderQualificationObservation]:
    result: dict[str, ProviderQualificationObservation] = {}
    for item in observations.qualifications:
        previous = result.get(item.provider_id)
        if previous is None or item.observed_at > previous.observed_at:
            result[item.provider_id] = item
    return result


def _combine_placement(current: PlacementState, new: PlacementState) -> PlacementState:
    if PlacementState.BLOCKED in {current, new}:
        return PlacementState.BLOCKED
    if PlacementState.INDETERMINATE in {current, new}:
        return PlacementState.INDETERMINATE
    return PlacementState.ELIGIBLE


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


def _resource_shortages(request: ResourceRequest, available: ResourceRequest) -> tuple[str, ...]:
    shortages: list[str] = []
    fields = (
        ("cpu", request.cpu_millicores, available.cpu_millicores),
        ("memory", request.memory_mib, available.memory_mib),
        ("storage", request.storage_mib, available.storage_mib),
        ("wall-time", request.wall_time_seconds, available.wall_time_seconds),
        ("gpu", request.gpu_count, available.gpu_count),
    )
    for label, required, free in fields:
        if required > free:
            shortages.append(f"{label}:{required}>{free}")
    return tuple(shortages)


__all__ = [
    "PlacementAssessment",
    "PlacementState",
    "ProviderPoolObservation",
    "ProviderPoolState",
    "ProviderQualificationObservation",
    "ProviderQualificationState",
    "ResourceDashboardObservations",
    "SurplusComputeObservation",
    "SurplusComputeState",
    "assess_task_placement",
    "render_resource_dashboard",
    "selected_provider_id",
    "selected_reservation_id",
    "selected_resource_task_id",
]
