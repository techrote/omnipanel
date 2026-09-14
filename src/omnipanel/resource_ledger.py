"""Durable host/provider resource accounting and reconciliation for OP-032.

Providers retain authority over hard enforcement. The ledger mirrors successful provider
reservations into durable Omnipanel state, binds them to candidates, and reports any
provider/ledger disagreement rather than silently rewriting either side.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from omnipanel.domain.contracts import (
    ContractModel,
    OpaqueId,
    ProviderRequest,
    ResourceRequest,
)
from omnipanel.execution_provider import (
    ExecutionProvider,
    ExecutionProviderError,
    ProviderAvailability,
    ProviderDescription,
    ProviderFailureCode,
    ProviderIdentity,
    ProviderReservation,
    ProviderReservationState,
)
from omnipanel.services import ApplicationServices
from omnipanel.storage import (
    RecordNotFoundError,
    ReservationState,
    ResourceReservation,
)

_RESOURCE_BINDING_COMPONENT = "op032-resource-ledger"
_RESOURCE_RECONCILIATION_COMPONENT = "op032-resource-reconciliation"


class ResourceLedgerError(RuntimeError):
    """Base error for resource-ledger invariants and unsupported reconciliation."""


class ResourceAccountingState(StrEnum):
    CONSISTENT = "consistent"
    PROVIDER_REPORTS_MORE_AVAILABLE = "provider-reports-more-available"
    PROVIDER_REPORTS_LESS_AVAILABLE = "provider-reports-less-available"
    MIXED_DISAGREEMENT = "mixed-disagreement"
    INDETERMINATE = "indeterminate"


class ResourceIssueCode(StrEnum):
    MISSING_BINDING = "missing-binding"
    PROVIDER_IDENTITY_MISMATCH = "provider-identity-mismatch"
    DURABLE_OVERCOMMIT = "durable-overcommit"
    PROVIDER_MORE_AVAILABLE = "provider-more-available"
    PROVIDER_LESS_AVAILABLE = "provider-less-available"
    PROVIDER_INDETERMINATE = "provider-indeterminate"


class ReconciliationStatus(StrEnum):
    RECONCILED = "reconciled"
    PROVIDER_MISSING = "provider-missing"
    IDENTITY_MISMATCH = "identity-mismatch"
    PAYLOAD_MISMATCH = "payload-mismatch"
    MISSING_BINDING = "missing-binding"
    EXTERNAL_RELEASE_CONFIRMED = "external-release-confirmed"


class ResourceDelta(ContractModel):
    """Provider-reported available minus ledger-expected available."""

    cpu_millicores: int = Field(strict=True)
    memory_mib: int = Field(strict=True)
    storage_mib: int = Field(strict=True)
    wall_time_seconds: int = Field(strict=True)
    gpu_count: int = Field(strict=True)

    def values(self) -> tuple[int, ...]:
        return (
            self.cpu_millicores,
            self.memory_mib,
            self.storage_mib,
            self.wall_time_seconds,
            self.gpu_count,
        )


class ResourceAccountingIssue(ContractModel):
    code: ResourceIssueCode
    detail: str = Field(min_length=1, max_length=1024)
    reservation_id: OpaqueId | None = None


class ResourceReservationBinding(ContractModel):
    """Durable candidate/provenance metadata stored beside OP-003 reservations."""

    reservation_id: OpaqueId
    provider_reservation_id: OpaqueId
    run_id: OpaqueId
    candidate_id: OpaqueId
    provider: ProviderIdentity
    provider_request: ProviderRequest
    created_at: datetime
    last_reconciled_at: datetime | None = None
    last_reconciled_by: OpaqueId | None = None
    reconciliation_note: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("created_at", "last_reconciled_at")
    @classmethod
    def _aware_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("resource binding timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def _ordered_timestamps(self) -> Self:
        if self.last_reconciled_at is not None and self.last_reconciled_at < self.created_at:
            raise ValueError("last_reconciled_at must not precede created_at")
        return self


class ExternalReleaseConfirmation(ContractModel):
    reservation_id: OpaqueId
    confirmed_by: OpaqueId
    reason: str = Field(min_length=1, max_length=1024)
    confirmed_at: datetime

    @field_validator("confirmed_at")
    @classmethod
    def _aware_confirmed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at must include a timezone")
        return value


class ResourceReservationView(ContractModel):
    reservation_id: OpaqueId
    provider_reservation_id: OpaqueId | None = None
    run_id: OpaqueId
    provider_id: OpaqueId
    candidate_id: OpaqueId | None = None
    provider: ProviderIdentity | None = None
    provider_request: ProviderRequest | None = None
    request: ResourceRequest
    state: ReservationState
    updated_at: datetime
    binding_present: bool = Field(strict=True)

    @field_validator("updated_at")
    @classmethod
    def _aware_updated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return value


class ProviderResourceView(ContractModel):
    description: ProviderDescription
    availability: ProviderAvailability
    total: ResourceRequest
    reported_available: ResourceRequest
    ledger_reserved: ResourceRequest
    ledger_expected_available: ResourceRequest
    delta: ResourceDelta
    accounting_state: ResourceAccountingState
    issues: tuple[ResourceAccountingIssue, ...]
    reservations: tuple[ResourceReservationView, ...]
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class ResourceLedgerSnapshot(ContractModel):
    providers: tuple[ProviderResourceView, ...]
    reservations: tuple[ResourceReservationView, ...]


class ReservationReconciliation(ContractModel):
    reservation_id: OpaqueId
    provider_reservation_id: OpaqueId | None = None
    status: ReconciliationStatus
    durable_state: ReservationState
    provider_state: ProviderReservationState | None = None
    detail: str = Field(min_length=1, max_length=1024)


class DurableResourceLedger:
    """UI-independent durable mirror over qualified Execution Providers."""

    def __init__(
        self,
        services: ApplicationServices,
        providers: Mapping[str, ExecutionProvider],
    ) -> None:
        self.services = services
        checked: dict[str, ExecutionProvider] = {}
        for key, provider in providers.items():
            identity = provider.describe().identity
            if key != identity.provider_id:
                raise ResourceLedgerError(
                    f"provider mapping key {key!r} does not match identity {identity.provider_id!r}"
                )
            checked[key] = provider
        self._providers = checked

    def reserve_candidate(
        self,
        *,
        provider_id: str,
        run_id: str,
        candidate_id: str,
        request: ProviderRequest,
    ) -> ResourceReservationView:
        provider = self._provider(provider_id)
        provider_reservation = provider.reserve(run_id=run_id, request=request)
        identity = provider.describe().identity
        if provider_reservation.provider != identity:
            raise ResourceLedgerError("provider reservation identity changed during reservation")
        if provider_reservation.run_id != run_id:
            raise ResourceLedgerError("provider reservation returned a different run_id")
        if provider_reservation.request != request:
            raise ResourceLedgerError("provider reservation returned a different provider request")

        durable_id = f"resource-{uuid.uuid4().hex}"
        durable = ResourceReservation(
            reservation_id=durable_id,
            run_id=run_id,
            provider_id=provider_id,
            request=request.resources,
            state=_durable_state(provider_reservation.state),
            updated_at=provider_reservation.updated_at,
        )
        self.services.save_reservation(durable)
        binding = ResourceReservationBinding(
            reservation_id=durable.reservation_id,
            provider_reservation_id=provider_reservation.reservation_id,
            run_id=run_id,
            candidate_id=candidate_id,
            provider=identity,
            provider_request=request,
            created_at=provider_reservation.created_at,
        )
        self._save_binding(binding)
        return self._reservation_view(durable)

    def release(self, *, provider_id: str, reservation_id: str) -> ResourceReservationView:
        provider = self._provider(provider_id)
        durable = self.services.store.load_reservation(reservation_id)
        self._require_provider_match(durable, provider_id)
        binding = self._require_binding_for_provider(durable, provider)
        observed = provider.reservation(binding.provider_reservation_id)
        self._require_same_provider_reservation(durable, binding, observed)
        provider_reservation = provider.release(binding.provider_reservation_id)
        self._require_same_provider_reservation(durable, binding, provider_reservation)
        if provider_reservation.state is not ProviderReservationState.RELEASED:
            raise ResourceLedgerError("provider release did not settle reservation as released")
        updated = durable.model_copy(
            update={
                "state": ReservationState.RELEASED,
                "updated_at": max(durable.updated_at, provider_reservation.updated_at),
            }
        )
        self.services.save_reservation(updated)
        return self._reservation_view(updated)

    def reconcile_reservation(
        self,
        *,
        provider_id: str,
        reservation_id: str,
        reconciled_by: str = "system:provider-reconcile",
    ) -> ReservationReconciliation:
        provider = self._provider(provider_id)
        durable = self.services.store.load_reservation(reservation_id)
        self._require_provider_match(durable, provider_id)
        binding = self._load_binding_or_none(reservation_id)
        if binding is None:
            held = self._hold_indeterminate(durable, provider.inventory().observed_at)
            return ReservationReconciliation(
                reservation_id=reservation_id,
                status=ReconciliationStatus.MISSING_BINDING,
                durable_state=held.state,
                detail="candidate/provider binding is missing; reservation held indeterminate",
            )

        identity = provider.describe().identity
        if binding.provider != identity:
            held = self._hold_indeterminate(durable, provider.inventory().observed_at)
            return ReservationReconciliation(
                reservation_id=reservation_id,
                provider_reservation_id=binding.provider_reservation_id,
                status=ReconciliationStatus.IDENTITY_MISMATCH,
                durable_state=held.state,
                detail="provider identity/version no longer matches durable reservation binding",
            )

        try:
            observed = provider.reservation(binding.provider_reservation_id)
        except ExecutionProviderError as exc:
            if exc.diagnostic.code is not ProviderFailureCode.RESERVATION_NOT_FOUND:
                raise
            now = max(durable.updated_at, provider.inventory().observed_at)
            held = self._hold_indeterminate(durable, now)
            self._save_binding(
                binding.model_copy(
                    update={
                        "last_reconciled_at": _binding_time(binding, now),
                        "last_reconciled_by": reconciled_by,
                        "reconciliation_note": "provider reports reservation missing",
                    }
                )
            )
            return ReservationReconciliation(
                reservation_id=reservation_id,
                provider_reservation_id=binding.provider_reservation_id,
                status=ReconciliationStatus.PROVIDER_MISSING,
                durable_state=held.state,
                detail="provider no longer reports reservation; explicit resolution required",
            )

        if not _same_provider_reservation(durable, binding, observed):
            held = self._hold_indeterminate(durable, observed.updated_at)
            reconcile_time = _binding_time(binding, held.updated_at)
            self._save_binding(
                binding.model_copy(
                    update={
                        "last_reconciled_at": reconcile_time,
                        "last_reconciled_by": reconciled_by,
                        "reconciliation_note": "provider reservation payload/incarnation mismatch",
                    }
                )
            )
            return ReservationReconciliation(
                reservation_id=reservation_id,
                provider_reservation_id=binding.provider_reservation_id,
                status=ReconciliationStatus.PAYLOAD_MISMATCH,
                durable_state=held.state,
                provider_state=observed.state,
                detail="provider reservation identity/run/request/incarnation disagrees with durable state",
            )

        mapped = _durable_state(observed.state)
        updated_at = max(durable.updated_at, observed.updated_at)
        updated = durable.model_copy(update={"state": mapped, "updated_at": updated_at})
        self.services.save_reservation(updated)
        self._save_binding(
            binding.model_copy(
                update={
                    "last_reconciled_at": _binding_time(binding, updated_at),
                    "last_reconciled_by": reconciled_by,
                    "reconciliation_note": "provider reservation reconciled",
                }
            )
        )
        return ReservationReconciliation(
            reservation_id=reservation_id,
            provider_reservation_id=binding.provider_reservation_id,
            status=ReconciliationStatus.RECONCILED,
            durable_state=updated.state,
            provider_state=observed.state,
            detail="durable reservation reconciled to provider state",
        )

    def confirm_external_release(
        self,
        *,
        reservation_id: str,
        confirmed_by: str,
        reason: str,
        confirmed_at: datetime,
    ) -> ReservationReconciliation:
        if not confirmed_by.strip() or not reason.strip():
            raise ValueError("external release confirmation requires actor and reason")
        if confirmed_at.tzinfo is None or confirmed_at.utcoffset() is None:
            raise ValueError("confirmed_at must include a timezone")
        durable = self.services.store.load_reservation(reservation_id)
        if durable.state is not ReservationState.INDETERMINATE:
            raise ResourceLedgerError(
                "external release confirmation is allowed only for indeterminate reservations"
            )
        if confirmed_at < durable.updated_at:
            raise ValueError("confirmed_at must not precede the durable reservation timestamp")
        binding = self._load_binding_or_none(reservation_id)
        released = durable.model_copy(
            update={"state": ReservationState.RELEASED, "updated_at": confirmed_at}
        )
        self.services.save_reservation(released)
        confirmation = ExternalReleaseConfirmation(
            reservation_id=reservation_id,
            confirmed_by=confirmed_by,
            reason=reason,
            confirmed_at=confirmed_at,
        )
        self.services.store.save_component_observation(
            _RESOURCE_RECONCILIATION_COMPONENT,
            reservation_id,
            confirmation.model_dump(mode="json"),
        )
        if binding is not None:
            self._save_binding(
                binding.model_copy(
                    update={
                        "last_reconciled_at": _binding_time(binding, confirmed_at),
                        "last_reconciled_by": confirmed_by,
                        "reconciliation_note": reason,
                    }
                )
            )
        return ReservationReconciliation(
            reservation_id=reservation_id,
            provider_reservation_id=(
                None if binding is None else binding.provider_reservation_id
            ),
            status=ReconciliationStatus.EXTERNAL_RELEASE_CONFIRMED,
            durable_state=ReservationState.RELEASED,
            detail="indeterminate reservation explicitly confirmed released out of band",
        )

    def provider_view(self, provider_id: str) -> ProviderResourceView:
        provider = self._provider(provider_id)
        description = provider.describe()
        inventory = provider.inventory()
        durable = tuple(
            item
            for item in self.services.resource_reservations()
            if item.provider_id == provider_id
        )
        reservation_views = tuple(self._reservation_view(item) for item in durable)
        live = tuple(item for item in durable if item.state is not ReservationState.RELEASED)
        ledger_reserved = _sum_reserved(tuple(item.request for item in live))
        expected, overcommitted = _expected_available(inventory.total, ledger_reserved)
        delta = _delta(inventory.available, expected)
        issues: list[ResourceAccountingIssue] = []

        for item in live:
            binding = self._load_binding_or_none(item.reservation_id)
            if binding is None:
                issues.append(
                    ResourceAccountingIssue(
                        code=ResourceIssueCode.MISSING_BINDING,
                        detail="durable reservation lacks candidate/provider binding",
                        reservation_id=item.reservation_id,
                    )
                )
            elif binding.provider != inventory.provider:
                issues.append(
                    ResourceAccountingIssue(
                        code=ResourceIssueCode.PROVIDER_IDENTITY_MISMATCH,
                        detail="reservation was created by a different provider identity/version",
                        reservation_id=item.reservation_id,
                    )
                )

        if overcommitted:
            issues.append(
                ResourceAccountingIssue(
                    code=ResourceIssueCode.DURABLE_OVERCOMMIT,
                    detail="durable live reservations exceed provider-reported total capacity",
                )
            )
        if inventory.availability is ProviderAvailability.INDETERMINATE:
            issues.append(
                ResourceAccountingIssue(
                    code=ResourceIssueCode.PROVIDER_INDETERMINATE,
                    detail="provider inventory availability is indeterminate",
                )
            )

        state = _accounting_state(delta)
        if state is ResourceAccountingState.PROVIDER_REPORTS_MORE_AVAILABLE:
            issues.append(
                ResourceAccountingIssue(
                    code=ResourceIssueCode.PROVIDER_MORE_AVAILABLE,
                    detail="provider reports more free capacity than durable reservations imply",
                )
            )
        elif state is ResourceAccountingState.PROVIDER_REPORTS_LESS_AVAILABLE:
            issues.append(
                ResourceAccountingIssue(
                    code=ResourceIssueCode.PROVIDER_LESS_AVAILABLE,
                    detail="provider reports less free capacity than durable reservations imply",
                )
            )
        elif state is ResourceAccountingState.MIXED_DISAGREEMENT:
            issues.extend(
                (
                    ResourceAccountingIssue(
                        code=ResourceIssueCode.PROVIDER_MORE_AVAILABLE,
                        detail="provider reports more free capacity on at least one dimension",
                    ),
                    ResourceAccountingIssue(
                        code=ResourceIssueCode.PROVIDER_LESS_AVAILABLE,
                        detail="provider reports less free capacity on at least one dimension",
                    ),
                )
            )

        if any(
            issue.code
            in {
                ResourceIssueCode.MISSING_BINDING,
                ResourceIssueCode.PROVIDER_IDENTITY_MISMATCH,
                ResourceIssueCode.DURABLE_OVERCOMMIT,
                ResourceIssueCode.PROVIDER_INDETERMINATE,
            }
            for issue in issues
        ):
            state = ResourceAccountingState.INDETERMINATE

        return ProviderResourceView(
            description=description,
            availability=inventory.availability,
            total=inventory.total,
            reported_available=inventory.available,
            ledger_reserved=ledger_reserved,
            ledger_expected_available=expected,
            delta=delta,
            accounting_state=state,
            issues=tuple(issues),
            reservations=reservation_views,
            observed_at=inventory.observed_at,
        )

    def snapshot(self) -> ResourceLedgerSnapshot:
        providers = tuple(self.provider_view(provider_id) for provider_id in sorted(self._providers))
        reservations = tuple(
            self._reservation_view(item) for item in self.services.resource_reservations()
        )
        return ResourceLedgerSnapshot(providers=providers, reservations=reservations)

    def _provider(self, provider_id: str) -> ExecutionProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ResourceLedgerError(f"unknown execution provider: {provider_id}") from exc

    def _save_binding(self, binding: ResourceReservationBinding) -> None:
        self.services.store.save_component_observation(
            _RESOURCE_BINDING_COMPONENT,
            binding.reservation_id,
            binding.model_dump(mode="json"),
        )

    def _load_binding_or_none(self, reservation_id: str) -> ResourceReservationBinding | None:
        try:
            payload = self.services.store.load_component_observation(
                _RESOURCE_BINDING_COMPONENT,
                reservation_id,
            )
        except RecordNotFoundError:
            return None
        return ResourceReservationBinding.model_validate(payload)

    def _reservation_view(self, reservation: ResourceReservation) -> ResourceReservationView:
        binding = self._load_binding_or_none(reservation.reservation_id)
        return ResourceReservationView(
            reservation_id=reservation.reservation_id,
            provider_reservation_id=(
                None if binding is None else binding.provider_reservation_id
            ),
            run_id=reservation.run_id,
            provider_id=reservation.provider_id,
            candidate_id=None if binding is None else binding.candidate_id,
            provider=None if binding is None else binding.provider,
            provider_request=None if binding is None else binding.provider_request,
            request=reservation.request,
            state=reservation.state,
            updated_at=reservation.updated_at,
            binding_present=binding is not None,
        )

    def _require_binding_for_provider(
        self,
        reservation: ResourceReservation,
        provider: ExecutionProvider,
    ) -> ResourceReservationBinding:
        binding = self._load_binding_or_none(reservation.reservation_id)
        if binding is None:
            raise ResourceLedgerError("reservation candidate/provider binding is missing")
        if binding.provider != provider.describe().identity:
            raise ResourceLedgerError(
                "reservation provider identity/version does not match current provider"
            )
        return binding

    def _require_same_provider_reservation(
        self,
        durable: ResourceReservation,
        binding: ResourceReservationBinding,
        observed: ProviderReservation,
    ) -> None:
        if not _same_provider_reservation(durable, binding, observed):
            raise ResourceLedgerError(
                "provider reservation ID was reused or no longer matches durable provenance"
            )

    def _require_provider_match(self, reservation: ResourceReservation, provider_id: str) -> None:
        if reservation.provider_id != provider_id:
            raise ResourceLedgerError(
                f"reservation belongs to provider {reservation.provider_id!r}, not {provider_id!r}"
            )

    def _hold_indeterminate(
        self,
        reservation: ResourceReservation,
        updated_at: datetime,
    ) -> ResourceReservation:
        held = reservation.model_copy(
            update={
                "state": ReservationState.INDETERMINATE,
                "updated_at": max(reservation.updated_at, updated_at),
            }
        )
        self.services.save_reservation(held)
        return held


def _same_provider_reservation(
    durable: ResourceReservation,
    binding: ResourceReservationBinding,
    observed: ProviderReservation,
) -> bool:
    return (
        observed.provider == binding.provider
        and observed.reservation_id == binding.provider_reservation_id
        and observed.run_id == durable.run_id == binding.run_id
        and observed.request == binding.provider_request
        and observed.request.resources == durable.request
        and observed.created_at == binding.created_at
    )


def _binding_time(binding: ResourceReservationBinding, candidate: datetime) -> datetime:
    previous = binding.last_reconciled_at or binding.created_at
    return max(previous, candidate)


def _durable_state(state: ProviderReservationState) -> ReservationState:
    return ReservationState(state.value)


def _sum_reserved(requests: tuple[ResourceRequest, ...]) -> ResourceRequest:
    return ResourceRequest(
        cpu_millicores=sum(item.cpu_millicores for item in requests),
        memory_mib=sum(item.memory_mib for item in requests),
        storage_mib=sum(item.storage_mib for item in requests),
        wall_time_seconds=max((item.wall_time_seconds for item in requests), default=0),
        gpu_count=sum(item.gpu_count for item in requests),
    )


def _expected_available(
    total: ResourceRequest,
    reserved: ResourceRequest,
) -> tuple[ResourceRequest, bool]:
    overcommitted = any(
        reserved_value > total_value
        for reserved_value, total_value in (
            (reserved.cpu_millicores, total.cpu_millicores),
            (reserved.memory_mib, total.memory_mib),
            (reserved.storage_mib, total.storage_mib),
            (reserved.gpu_count, total.gpu_count),
        )
    )
    return (
        ResourceRequest(
            cpu_millicores=max(0, total.cpu_millicores - reserved.cpu_millicores),
            memory_mib=max(0, total.memory_mib - reserved.memory_mib),
            storage_mib=max(0, total.storage_mib - reserved.storage_mib),
            wall_time_seconds=total.wall_time_seconds,
            gpu_count=max(0, total.gpu_count - reserved.gpu_count),
        ),
        overcommitted,
    )


def _delta(reported: ResourceRequest, expected: ResourceRequest) -> ResourceDelta:
    return ResourceDelta(
        cpu_millicores=reported.cpu_millicores - expected.cpu_millicores,
        memory_mib=reported.memory_mib - expected.memory_mib,
        storage_mib=reported.storage_mib - expected.storage_mib,
        wall_time_seconds=reported.wall_time_seconds - expected.wall_time_seconds,
        gpu_count=reported.gpu_count - expected.gpu_count,
    )


def _accounting_state(delta: ResourceDelta) -> ResourceAccountingState:
    values = delta.values()
    if all(value == 0 for value in values):
        return ResourceAccountingState.CONSISTENT
    if all(value >= 0 for value in values):
        return ResourceAccountingState.PROVIDER_REPORTS_MORE_AVAILABLE
    if all(value <= 0 for value in values):
        return ResourceAccountingState.PROVIDER_REPORTS_LESS_AVAILABLE
    return ResourceAccountingState.MIXED_DISAGREEMENT


__all__ = [
    "DurableResourceLedger",
    "ExternalReleaseConfirmation",
    "ProviderResourceView",
    "ReconciliationStatus",
    "ReservationReconciliation",
    "ResourceAccountingIssue",
    "ResourceAccountingState",
    "ResourceDelta",
    "ResourceIssueCode",
    "ResourceLedgerError",
    "ResourceLedgerSnapshot",
    "ResourceReservationBinding",
    "ResourceReservationView",
]
