from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from textual.content import Content
from textual.widgets import Static

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import (
    ComponentContractRef,
    ProviderRequest,
    ResourceRequest,
    TaskRecord,
)
from omnipanel.execution_provider import (
    FakeExecutionProvider,
    ProviderDescription,
    ProviderGuarantees,
    ProviderIdentity,
    ProviderMetadataItem,
    ProviderWorkPurpose,
)
from omnipanel.resource_ledger import DurableResourceLedger
from omnipanel.resource_views import ResourceDashboardObservations
from omnipanel.services import ApplicationServices
from omnipanel.storage import ReservationState, StateStore
from omnipanel.ui.resources import ResourceOperatorApp

ROOT = Path(__file__).parents[1]
OP002 = ROOT / "tests" / "fixtures" / "op002_examples.json"
OP010 = ROOT / "tests" / "fixtures" / "op010_resource_dashboard.json"
CLOCK = datetime(2026, 9, 14, 7, 45, tzinfo=UTC)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _task() -> TaskRecord:
    task = TaskRecord.model_validate(_json(OP002)["task"])
    return task.model_copy(
        update={
            "task_id": "OP-010",
            "display_name": "Resource UI fixture",
            "provider_request": ProviderRequest(
                provider_class="general-worker",
                required_capability_handles=("build.python",),
                resources=ResourceRequest(
                    cpu_millicores=1000,
                    memory_mib=1024,
                    storage_mib=2048,
                    wall_time_seconds=180,
                ),
                isolation_required=True,
            ),
        }
    )


def _description(
    provider_id: str,
    provider_class: str,
    capabilities: tuple[str, ...],
    purposes: tuple[ProviderWorkPurpose, ...],
) -> ProviderDescription:
    metadata = [ProviderMetadataItem(key="host.id", value=f"host-{provider_id}")]
    if provider_id == "provider-dev":
        metadata.append(ProviderMetadataItem(key="credential.secret", value="NEVER_RENDER_ME"))
    return ProviderDescription(
        identity=ProviderIdentity(
            provider_id=provider_id,
            provider_class=provider_class,
            implementation_version="fixture-ui-1.0",
            interface_contract=ComponentContractRef(
                component_id=f"{provider_id}-component",
                contract_id="execution-provider",
                contract_version="1.0",
            ),
        ),
        capabilities=capabilities,
        supported_purposes=purposes,
        guarantees=ProviderGuarantees(
            isolation=True,
            resource_limits=True,
            network_policy=True,
            filesystem_policy=True,
        ),
        metadata=tuple(metadata),
    )


def _provider(
    provider_id: str,
    provider_class: str,
    capabilities: tuple[str, ...],
    purposes: tuple[ProviderWorkPurpose, ...],
    *,
    cpu: int,
) -> FakeExecutionProvider:
    return FakeExecutionProvider(
        _description(provider_id, provider_class, capabilities, purposes),
        ResourceRequest(
            cpu_millicores=cpu,
            memory_mib=4096,
            storage_mib=16384,
            wall_time_seconds=600,
        ),
        clock_start=CLOCK,
    )


def _observations() -> ResourceDashboardObservations:
    return ResourceDashboardObservations.model_validate(_json(OP010))


def _plain(app: ResourceOperatorApp, selector: str) -> str:
    visual = app.query_one(selector, Static).visual
    assert isinstance(visual, Content)
    return visual.plain


@pytest.mark.asyncio
async def test_resource_panel_reconciles_refreshes_and_preserves_global_blocker(
    tmp_path: Path,
) -> None:
    config = AppConfig(data_dir=(tmp_path / "resource-ui").absolute())
    dev = _provider(
        "provider-dev",
        "general-worker",
        ("build.python",),
        (ProviderWorkPurpose.EXECUTION,),
        cpu=4000,
    )
    validation = _provider(
        "provider-validation",
        "validation-worker",
        ("test.windows",),
        (ProviderWorkPurpose.VALIDATION,),
        cpu=2000,
    )
    with StateStore(config) as store:
        services = ApplicationServices(store)
        task = _task()
        services.put_record(task)
        ledger = DurableResourceLedger(
            services,
            {"provider-dev": dev, "provider-validation": validation},
        )
        reservation = ledger.reserve_candidate(
            provider_id="provider-dev",
            run_id="run-ui-resource",
            candidate_id="candidate-ui-resource",
            request=task.provider_request,
        )
        app = ResourceOperatorApp(
            config,
            services,
            resource_ledger=ledger,
            resource_observations=_observations(),
        )
        async with app.run_test(size=(220, 42)) as pilot:
            assert await pilot.click("#nav-resources")
            body = _plain(app, "#panel-body")
            assert "Provider detail: provider-dev" in body
            assert "provider-dev: ELIGIBLE" in body
            assert "development-pool" in body
            assert "NEVER_RENDER_ME" not in body
            assert "BLOCKER: execution disabled" in _plain(app, "#status-banner")

            assert await pilot.click("#resource-reconcile")
            await pilot.pause()
            body = _plain(app, "#panel-body")
            assert "Notice: Reconcile reconciled" in body
            assert store.load_reservation(reservation.reservation_id).state is ReservationState.RESERVED

            ledger.release(
                provider_id="provider-dev",
                reservation_id=reservation.reservation_id,
            )
            assert await pilot.click("#resource-refresh")
            await pilot.pause()
            body = _plain(app, "#panel-body")
            assert "Notice: Provider inventory and durable reservations refreshed." in body
            assert "cpu=4000/4000m free" in body
            assert "state=released" in body

            assert await pilot.click("#resource-provider-next")
            body = _plain(app, "#panel-body")
            assert "Provider detail: provider-validation" in body
            assert "provider-validation: BLOCKED" in body
            assert "BLOCKER: execution disabled" in _plain(app, "#status-banner")


@pytest.mark.asyncio
async def test_resource_panel_works_without_configured_provider(tmp_path: Path) -> None:
    config = AppConfig(data_dir=(tmp_path / "resource-ui-empty").absolute())
    with StateStore(config) as store:
        services = ApplicationServices(store)
        app = ResourceOperatorApp(config, services)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.press("5")
            body = _plain(app, "#panel-body")
            assert "Providers: 0" in body
            assert "provider availability INDETERMINATE" in body
            assert "Surplus compute" in body
            assert "INDETERMINATE" in body
