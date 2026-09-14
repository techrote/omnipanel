from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from omnipanel.config import AppConfig
from omnipanel.domain.contracts import (
    ComponentContractRef,
    ProviderRequest,
    ResourceRequest,
    TaskRecord,
)
from omnipanel.execution_provider import (
    FakeExecutionProvider,
    ProviderAvailability,
    ProviderDescription,
    ProviderGuarantees,
    ProviderIdentity,
    ProviderMetadataItem,
    ProviderWorkPurpose,
)
from omnipanel.resource_ledger import DurableResourceLedger
from omnipanel.resource_views import (
    PlacementState,
    ResourceDashboardObservations,
    assess_task_placement,
    render_resource_dashboard,
)
from omnipanel.services import ApplicationServices
from omnipanel.storage import StateStore

ROOT = Path(__file__).parents[1]
OP002 = ROOT / "tests" / "fixtures" / "op002_examples.json"
OP010 = ROOT / "tests" / "fixtures" / "op010_resource_dashboard.json"
CLOCK = datetime(2026, 9, 14, 7, 45, tzinfo=UTC)
TOTAL = ResourceRequest(
    cpu_millicores=4000,
    memory_mib=8192,
    storage_mib=32768,
    wall_time_seconds=900,
)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _observations() -> ResourceDashboardObservations:
    return ResourceDashboardObservations.model_validate(_json(OP010))


def _task() -> TaskRecord:
    raw = _json(OP002)["task"]
    task = TaskRecord.model_validate(raw)
    return task.model_copy(
        update={
            "task_id": "OP-010",
            "display_name": "Fixture placement task",
            "provider_request": ProviderRequest(
                provider_class="general-worker",
                required_capability_handles=("build.python",),
                resources=ResourceRequest(
                    cpu_millicores=1000,
                    memory_mib=1024,
                    storage_mib=2048,
                    wall_time_seconds=180,
                ),
                writable_paths=("worktree",),
                network_access=False,
                isolation_required=True,
            ),
        }
    )


def _description(
    provider_id: str,
    *,
    provider_class: str,
    capabilities: tuple[str, ...],
    purposes: tuple[ProviderWorkPurpose, ...],
) -> ProviderDescription:
    metadata = [
        ProviderMetadataItem(key="host.id", value=f"host-{provider_id}"),
        ProviderMetadataItem(key="placement.kind", value="synthetic"),
    ]
    if provider_id == "provider-dev":
        metadata.append(ProviderMetadataItem(key="credential.token", value="SENTINEL_SECRET"))
    return ProviderDescription(
        identity=ProviderIdentity(
            provider_id=provider_id,
            provider_class=provider_class,
            implementation_version="fixture-1.0",
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


def _providers() -> dict[str, FakeExecutionProvider]:
    return {
        "provider-dev": FakeExecutionProvider(
            _description(
                "provider-dev",
                provider_class="general-worker",
                capabilities=("build.python",),
                purposes=(ProviderWorkPurpose.EXECUTION,),
            ),
            TOTAL,
            clock_start=CLOCK,
        ),
        "provider-validation": FakeExecutionProvider(
            _description(
                "provider-validation",
                provider_class="validation-worker",
                capabilities=("test.windows",),
                purposes=(ProviderWorkPurpose.VALIDATION,),
            ),
            ResourceRequest(
                cpu_millicores=2000,
                memory_mib=4096,
                storage_mib=16384,
                wall_time_seconds=600,
            ),
            clock_start=CLOCK,
        ),
        "provider-down": FakeExecutionProvider(
            _description(
                "provider-down",
                provider_class="general-worker",
                capabilities=("build.python",),
                purposes=(ProviderWorkPurpose.EXECUTION,),
            ),
            ResourceRequest(
                cpu_millicores=1000,
                memory_mib=2048,
                storage_mib=8192,
                wall_time_seconds=300,
            ),
            availability=ProviderAvailability.UNAVAILABLE,
            clock_start=CLOCK,
        ),
    }


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(data_dir=(tmp_path / "resource-dashboard").absolute())


def test_dashboard_renders_multiple_providers_pools_surplus_and_safe_metadata(
    tmp_path: Path,
) -> None:
    providers = _providers()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        task = _task()
        services.put_record(task)
        ledger = DurableResourceLedger(services, providers)
        reservation = ledger.reserve_candidate(
            provider_id="provider-dev",
            run_id="run-dashboard",
            candidate_id="candidate-dashboard",
            request=task.provider_request,
        )
        application = services.snapshot()
        resources = ledger.snapshot()
        text = render_resource_dashboard(
            application,
            resources,
            observations=_observations(),
            selected_provider="provider-dev",
            selected_reservation=reservation.reservation_id,
            selected_task=task.task_id,
        )

        assert "provider-dev" in text
        assert "provider-validation" in text
        assert "provider-down" in text
        assert "compatibility=qualified" in text
        assert "availability=unavailable" in text
        assert "development-pool" in text
        assert "validation-pool" in text
        assert "Surplus compute" in text
        assert "state=idle" in text
        assert "provider-dev: ELIGIBLE" in text
        assert "provider-validation: BLOCKED" in text
        assert "provider-down: BLOCKED" in text
        assert "host.id=host-provider-dev" in text
        assert "credential.token" not in text
        assert "SENTINEL_SECRET" not in text


def test_release_refresh_removes_allocation_without_stale_double_count(tmp_path: Path) -> None:
    providers = _providers()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        task = _task()
        services.put_record(task)
        ledger = DurableResourceLedger(services, providers)
        reservation = ledger.reserve_candidate(
            provider_id="provider-dev",
            run_id="run-release",
            candidate_id="candidate-release",
            request=task.provider_request,
        )
        before = ledger.provider_view("provider-dev")
        assert before.ledger_reserved.cpu_millicores == 1000
        assert before.reported_available.cpu_millicores == 3000

        ledger.release(
            provider_id="provider-dev",
            reservation_id=reservation.reservation_id,
        )
        after = ledger.provider_view("provider-dev")
        assert after.ledger_reserved.cpu_millicores == 0
        assert after.reported_available.cpu_millicores == 4000
        assert services.snapshot().resources.cpu_millicores == 0

        text = render_resource_dashboard(
            services.snapshot(),
            ledger.snapshot(),
            observations=_observations(),
            selected_provider="provider-dev",
            selected_reservation=reservation.reservation_id,
            selected_task=task.task_id,
        )
        assert "cpu=4000/4000m free" in text
        assert "state=released" in text


def test_provider_ledger_disagreement_makes_placement_indeterminate(tmp_path: Path) -> None:
    providers = _providers()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        task = _task()
        services.put_record(task)
        first = DurableResourceLedger(services, providers)
        first.reserve_candidate(
            provider_id="provider-dev",
            run_id="run-stale",
            candidate_id="candidate-stale",
            request=task.provider_request,
        )

        fresh_dev = FakeExecutionProvider(
            providers["provider-dev"].describe(),
            TOTAL,
            clock_start=CLOCK,
        )
        second = DurableResourceLedger(
            services,
            {
                "provider-dev": fresh_dev,
                "provider-validation": providers["provider-validation"],
                "provider-down": providers["provider-down"],
            },
        )
        provider_view = second.provider_view("provider-dev")
        qualification = next(
            item
            for item in _observations().qualifications
            if item.provider_id == "provider-dev"
        )
        assessment = assess_task_placement(task, provider_view, qualification)
        assert assessment.state is PlacementState.INDETERMINATE
        assert any("accounting" in reason for reason in assessment.reasons)

        text = render_resource_dashboard(
            services.snapshot(),
            second.snapshot(),
            observations=_observations(),
            selected_provider="provider-dev",
            selected_task=task.task_id,
        )
        assert "accounting=provider-reports-more-available" in text
        assert "provider-dev: INDETERMINATE" in text


def test_missing_qualification_is_not_inferred_compatible(tmp_path: Path) -> None:
    providers = _providers()
    with StateStore(_config(tmp_path)) as store:
        services = ApplicationServices(store)
        task = _task()
        services.put_record(task)
        ledger = DurableResourceLedger(services, providers)
        provider_view = ledger.provider_view("provider-dev")
        assessment = assess_task_placement(task, provider_view, None)
        assert assessment.state is PlacementState.INDETERMINATE
        assert "qualification unavailable" in assessment.reasons[0]
