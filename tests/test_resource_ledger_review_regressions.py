from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import ComponentContractRef, ProviderRequest, ResourceRequest
from omnipanel.execution_provider import (
    FakeExecutionProvider,
    ProviderAvailability,
    ProviderDescription,
    ProviderGuarantees,
    ProviderIdentity,
    ProviderWorkPurpose,
)
from omnipanel.resource_ledger import DurableResourceLedger, ResourceLedgerError
from omnipanel.services import ApplicationServices
from omnipanel.storage import ReservationState, ResourceReservation, StateStore

CLOCK = datetime(2026, 9, 14, 7, 30, tzinfo=UTC)
TOTAL = ResourceRequest(
    cpu_millicores=4000,
    memory_mib=8192,
    storage_mib=32768,
    wall_time_seconds=900,
)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(data_dir=(tmp_path / "resource-ledger-review").absolute())


def _description() -> ProviderDescription:
    return ProviderDescription(
        identity=ProviderIdentity(
            provider_id="provider-a",
            provider_class="general-worker",
            implementation_version="1.0",
            interface_contract=ComponentContractRef(
                component_id="fixture-provider",
                contract_id="execution-provider",
                contract_version="1.0",
            ),
        ),
        capabilities=(),
        supported_purposes=(ProviderWorkPurpose.EXECUTION,),
        guarantees=ProviderGuarantees(
            isolation=True,
            resource_limits=True,
            network_policy=True,
            filesystem_policy=True,
        ),
        metadata=(),
    )


def _provider() -> FakeExecutionProvider:
    return FakeExecutionProvider(
        _description(),
        TOTAL,
        availability=ProviderAvailability.AVAILABLE,
        clock_start=CLOCK,
    )


def _request() -> ProviderRequest:
    return ProviderRequest(
        provider_class="general-worker",
        resources=ResourceRequest(
            cpu_millicores=1000,
            memory_mib=1024,
            storage_mib=2048,
            wall_time_seconds=180,
        ),
        isolation_required=True,
    )


def test_reused_provider_local_id_cannot_release_an_older_durable_reservation(
    tmp_path: Path,
) -> None:
    original = _provider()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        first = DurableResourceLedger(services, {"provider-a": original})
        old = first.reserve_candidate(
            provider_id="provider-a",
            run_id="run-old",
            candidate_id="candidate-old",
            request=_request(),
        )
        assert old.provider_reservation_id == "reservation-0001"

        restarted = _provider()
        second = DurableResourceLedger(services, {"provider-a": restarted})
        new = second.reserve_candidate(
            provider_id="provider-a",
            run_id="run-new",
            candidate_id="candidate-new",
            request=_request(),
        )
        assert new.provider_reservation_id == "reservation-0001"
        assert new.reservation_id != old.reservation_id

        with pytest.raises(ResourceLedgerError, match="reused"):
            second.release(provider_id="provider-a", reservation_id=old.reservation_id)

        assert store.load_reservation(old.reservation_id).state is ReservationState.RESERVED
        assert restarted.reservation("reservation-0001").run_id == "run-new"


def test_external_release_confirmation_timestamp_cannot_move_state_backward(
    tmp_path: Path,
) -> None:
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        reservation = ResourceReservation(
            reservation_id="resource-stale-clock",
            run_id="run-stale-clock",
            provider_id="provider-a",
            request=_request().resources,
            state=ReservationState.INDETERMINATE,
            updated_at=CLOCK,
        )
        services.save_reservation(reservation)
        ledger = DurableResourceLedger(services, {"provider-a": _provider()})

        with pytest.raises(ValueError, match="must not precede"):
            ledger.confirm_external_release(
                reservation_id=reservation.reservation_id,
                confirmed_by="human:operator",
                reason="stale timestamp must fail",
                confirmed_at=CLOCK - timedelta(seconds=1),
            )
        assert (
            store.load_reservation(reservation.reservation_id).state
            is ReservationState.INDETERMINATE
        )
