from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import ComponentContractRef, ProviderRequest, ResourceRequest
from omnipanel.execution_provider import (
    ExecutionProviderError,
    FakeExecutionProvider,
    ProviderAvailability,
    ProviderCandidateRequest,
    ProviderDescription,
    ProviderFailureCode,
    ProviderGuarantees,
    ProviderIdentity,
    ProviderMetadataItem,
    ProviderWorkPurpose,
)
from omnipanel.resource_ledger import (
    DurableResourceLedger,
    ReconciliationStatus,
    ResourceAccountingState,
    ResourceIssueCode,
    ResourceLedgerError,
)
from omnipanel.services import ApplicationServices
from omnipanel.storage import ReservationState, ResourceReservation, StateStore

CLOCK = datetime(2026, 9, 14, 7, 0, tzinfo=UTC)
TOTAL = ResourceRequest(
    cpu_millicores=4000,
    memory_mib=8192,
    storage_mib=32768,
    wall_time_seconds=900,
    gpu_count=1,
)


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(data_dir=(tmp_path / "resource-ledger-state").absolute())


def _description(
    *,
    provider_id: str = "provider-a",
    version: str = "1.0",
) -> ProviderDescription:
    return ProviderDescription(
        identity=ProviderIdentity(
            provider_id=provider_id,
            provider_class="general-worker",
            implementation_version=version,
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
        metadata=(
            ProviderMetadataItem(key="host.id", value="host-fixture-a"),
            ProviderMetadataItem(key="placement.kind", value="local-virtualized"),
        ),
    )


def _provider(
    *,
    description: ProviderDescription | None = None,
    total: ResourceRequest = TOTAL,
) -> FakeExecutionProvider:
    return FakeExecutionProvider(
        description or _description(),
        total,
        availability=ProviderAvailability.AVAILABLE,
        clock_start=CLOCK,
    )


def _request(
    *,
    cpu: int = 1000,
    memory: int = 2048,
    storage: int = 4096,
    wall: int = 300,
    gpu: int = 0,
) -> ProviderRequest:
    return ProviderRequest(
        provider_class="general-worker",
        required_capability_handles=(),
        resources=ResourceRequest(
            cpu_millicores=cpu,
            memory_mib=memory,
            storage_mib=storage,
            wall_time_seconds=wall,
            gpu_count=gpu,
        ),
        writable_paths=(),
        network_access=False,
        isolation_required=True,
    )


def test_candidate_reservation_round_trip_and_release_use_one_durable_source(
    tmp_path: Path,
) -> None:
    provider = _provider()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        ledger = DurableResourceLedger(services, {"provider-a": provider})
        request = _request(cpu=1500)
        view = ledger.reserve_candidate(
            provider_id="provider-a",
            run_id="run-a",
            candidate_id="candidate-a",
            request=request,
        )
        assert view.candidate_id == "candidate-a"
        assert view.binding_present
        assert view.state is ReservationState.RESERVED
        assert view.provider == provider.describe().identity
        assert view.provider_request == request
        assert view.provider_reservation_id == "reservation-0001"
        assert view.reservation_id != view.provider_reservation_id

        snapshot = services.snapshot()
        assert snapshot.resource_reservations == services.resource_reservations()
        assert len(snapshot.resource_reservations) == 1
        assert snapshot.resources.reserved == 1
        assert snapshot.resources.cpu_millicores == 1500

        provider_view = ledger.provider_view("provider-a")
        assert provider_view.accounting_state is ResourceAccountingState.CONSISTENT
        assert provider_view.ledger_reserved.cpu_millicores == 1500
        assert provider_view.reported_available.cpu_millicores == 2500
        assert provider_view.ledger_expected_available.cpu_millicores == 2500

        released = ledger.release(
            provider_id="provider-a",
            reservation_id=view.reservation_id,
        )
        assert released.state is ReservationState.RELEASED
        after = services.snapshot()
        assert after.resources.released == 1
        assert after.resources.cpu_millicores == 0


def test_provider_hard_ceiling_rejects_overcommit_without_durable_ghost(tmp_path: Path) -> None:
    provider = _provider(
        total=ResourceRequest(
            cpu_millicores=2000,
            memory_mib=4096,
            storage_mib=8192,
            wall_time_seconds=600,
        )
    )
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        ledger = DurableResourceLedger(services, {"provider-a": provider})
        ledger.reserve_candidate(
            provider_id="provider-a",
            run_id="run-a",
            candidate_id="candidate-a",
            request=_request(cpu=1500, memory=2048, storage=2048),
        )
        with pytest.raises(ExecutionProviderError) as exc:
            ledger.reserve_candidate(
                provider_id="provider-a",
                run_id="run-b",
                candidate_id="candidate-b",
                request=_request(cpu=1000, memory=1024, storage=1024),
            )
        assert exc.value.diagnostic.code is ProviderFailureCode.RESOURCES_UNAVAILABLE
        assert len(services.resource_reservations()) == 1
        assert services.snapshot().resources.cpu_millicores == 1500


def test_restart_marks_active_reservation_indeterminate_then_provider_reconciles_it(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    provider = _provider()
    reservation_id: str
    with StateStore(config) as store:
        services = ApplicationServices(store)
        ledger = DurableResourceLedger(services, {"provider-a": provider})
        reserved = ledger.reserve_candidate(
            provider_id="provider-a",
            run_id="run-restart",
            candidate_id="candidate-restart",
            request=_request(),
        )
        reservation_id = reserved.reservation_id
        provider_reservation_id = reserved.provider_reservation_id
        assert provider_reservation_id is not None
        provider.start(
            ProviderCandidateRequest(
                run_id="run-restart",
                candidate_id="candidate-restart",
                task_id="OP-032",
                purpose=ProviderWorkPurpose.EXECUTION,
                reservation_id=provider_reservation_id,
                payload_ref="payload-restart",
            )
        )
        reconciled = ledger.reconcile_reservation(
            provider_id="provider-a",
            reservation_id=reservation_id,
        )
        assert reconciled.durable_state is ReservationState.ACTIVE
        assert reconciled.provider_reservation_id == provider_reservation_id

    with StateStore(config) as reopened:
        services = ApplicationServices(reopened)
        assert reopened.load_reservation(reservation_id).state is ReservationState.INDETERMINATE
        ledger = DurableResourceLedger(services, {"provider-a": provider})
        result = ledger.reconcile_reservation(
            provider_id="provider-a",
            reservation_id=reservation_id,
        )
        assert result.status is ReconciliationStatus.RECONCILED
        assert result.durable_state is ReservationState.ACTIVE
        assert services.snapshot().resources.active == 1


def test_missing_provider_reservation_stays_indeterminate_until_explicit_release(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    original = _provider()
    reservation_id: str
    with StateStore(config) as store:
        services = ApplicationServices(store)
        ledger = DurableResourceLedger(services, {"provider-a": original})
        reservation_id = ledger.reserve_candidate(
            provider_id="provider-a",
            run_id="run-stale",
            candidate_id="candidate-stale",
            request=_request(),
        ).reservation_id

    replacement = _provider(description=original.describe())
    with StateStore(config) as reopened:
        services = ApplicationServices(reopened)
        ledger = DurableResourceLedger(services, {"provider-a": replacement})
        result = ledger.reconcile_reservation(
            provider_id="provider-a",
            reservation_id=reservation_id,
        )
        assert result.status is ReconciliationStatus.PROVIDER_MISSING
        assert result.durable_state is ReservationState.INDETERMINATE
        durable = reopened.load_reservation(reservation_id)
        assert durable.state is ReservationState.INDETERMINATE

        released = ledger.confirm_external_release(
            reservation_id=reservation_id,
            confirmed_by="human:operator",
            reason="provider host inspected out of band; job absent",
            confirmed_at=durable.updated_at,
        )
        assert released.status is ReconciliationStatus.EXTERNAL_RELEASE_CONFIRMED
        assert reopened.load_reservation(reservation_id).state is ReservationState.RELEASED


def test_provider_reporting_less_free_capacity_is_surfaced_not_hidden(tmp_path: Path) -> None:
    provider = _provider()
    provider.reserve(
        run_id="external-run",
        request=_request(cpu=750, memory=512, storage=1024),
    )
    with StateStore(_config(tmp_path)) as store:
        ledger = DurableResourceLedger(
            ApplicationServices(store),
            {"provider-a": provider},
        )
        view = ledger.provider_view("provider-a")
        assert view.accounting_state is ResourceAccountingState.PROVIDER_REPORTS_LESS_AVAILABLE
        assert view.delta.cpu_millicores == -750
        assert ResourceIssueCode.PROVIDER_LESS_AVAILABLE in {item.code for item in view.issues}


def test_provider_reporting_more_free_capacity_surfaces_stale_durable_hold(tmp_path: Path) -> None:
    provider = _provider()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        first = DurableResourceLedger(services, {"provider-a": provider})
        first.reserve_candidate(
            provider_id="provider-a",
            run_id="run-ghost",
            candidate_id="candidate-ghost",
            request=_request(cpu=1250),
        )

        fresh_provider = _provider(description=provider.describe())
        second = DurableResourceLedger(services, {"provider-a": fresh_provider})
        view = second.provider_view("provider-a")
        assert view.accounting_state is ResourceAccountingState.PROVIDER_REPORTS_MORE_AVAILABLE
        assert view.delta.cpu_millicores == 1250
        assert ResourceIssueCode.PROVIDER_MORE_AVAILABLE in {item.code for item in view.issues}


def test_provider_version_change_makes_accounting_indeterminate(tmp_path: Path) -> None:
    first_provider = _provider(description=_description(version="1.0"))
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        first = DurableResourceLedger(services, {"provider-a": first_provider})
        first.reserve_candidate(
            provider_id="provider-a",
            run_id="run-version",
            candidate_id="candidate-version",
            request=_request(),
        )

        replacement = _provider(description=_description(version="2.0"))
        second = DurableResourceLedger(services, {"provider-a": replacement})
        view = second.provider_view("provider-a")
        assert view.accounting_state is ResourceAccountingState.INDETERMINATE
        assert ResourceIssueCode.PROVIDER_IDENTITY_MISMATCH in {item.code for item in view.issues}


def test_release_refuses_reused_provider_id_with_different_identity(tmp_path: Path) -> None:
    original = _provider(description=_description(version="1.0"))
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        first = DurableResourceLedger(services, {"provider-a": original})
        durable_id = first.reserve_candidate(
            provider_id="provider-a",
            run_id="run-release-version",
            candidate_id="candidate-release-version",
            request=_request(),
        ).reservation_id

        replacement = _provider(description=_description(version="2.0"))
        second = DurableResourceLedger(services, {"provider-a": replacement})
        with pytest.raises(ResourceLedgerError, match="identity/version"):
            second.release(provider_id="provider-a", reservation_id=durable_id)
        assert store.load_reservation(durable_id).state is ReservationState.RESERVED


def test_provider_local_reservation_id_collisions_do_not_overwrite_durable_history(
    tmp_path: Path,
) -> None:
    provider_a = _provider(description=_description(provider_id="provider-a"))
    provider_b = _provider(description=_description(provider_id="provider-b"))
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        ledger = DurableResourceLedger(
            services,
            {"provider-a": provider_a, "provider-b": provider_b},
        )
        left = ledger.reserve_candidate(
            provider_id="provider-a",
            run_id="run-left",
            candidate_id="candidate-left",
            request=_request(),
        )
        right = ledger.reserve_candidate(
            provider_id="provider-b",
            run_id="run-right",
            candidate_id="candidate-right",
            request=_request(),
        )
        assert left.provider_reservation_id == "reservation-0001"
        assert right.provider_reservation_id == "reservation-0001"
        assert left.reservation_id != right.reservation_id
        assert len(services.resource_reservations()) == 2
        assert {item.provider_id for item in services.resource_reservations()} == {
            "provider-a",
            "provider-b",
        }


def test_external_release_requires_indeterminate_state(tmp_path: Path) -> None:
    provider = _provider()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        ledger = DurableResourceLedger(services, {"provider-a": provider})
        reservation_id = ledger.reserve_candidate(
            provider_id="provider-a",
            run_id="run-safe",
            candidate_id="candidate-safe",
            request=_request(),
        ).reservation_id
        with pytest.raises(ResourceLedgerError, match="indeterminate"):
            ledger.confirm_external_release(
                reservation_id=reservation_id,
                confirmed_by="human:operator",
                reason="should not bypass live reservation state",
                confirmed_at=CLOCK,
            )


def test_explicit_release_can_recover_indeterminate_reservation_with_missing_binding(
    tmp_path: Path,
) -> None:
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        orphan = ResourceReservation(
            reservation_id="resource-orphan",
            run_id="run-orphan",
            provider_id="provider-a",
            request=_request().resources,
            state=ReservationState.INDETERMINATE,
            updated_at=CLOCK,
        )
        services.save_reservation(orphan)
        ledger = DurableResourceLedger(services, {"provider-a": _provider()})
        result = ledger.confirm_external_release(
            reservation_id=orphan.reservation_id,
            confirmed_by="human:operator",
            reason="half-write inspected out of band; provider has no live reservation",
            confirmed_at=CLOCK,
        )
        assert result.status is ReconciliationStatus.EXTERNAL_RELEASE_CONFIRMED
        assert result.provider_reservation_id is None
        assert store.load_reservation(orphan.reservation_id).state is ReservationState.RELEASED


def test_provider_snapshot_is_deterministic_across_multiple_providers(tmp_path: Path) -> None:
    provider_b = _provider(description=_description(provider_id="provider-b"))
    provider_a = _provider(description=_description(provider_id="provider-a"))
    with StateStore(_config(tmp_path)) as store:
        ledger = DurableResourceLedger(
            ApplicationServices(store),
            {"provider-b": provider_b, "provider-a": provider_a},
        )
        snapshot = ledger.snapshot()
        assert [item.description.identity.provider_id for item in snapshot.providers] == [
            "provider-a",
            "provider-b",
        ]
