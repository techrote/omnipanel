from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import omnipanel.execution_provider as execution_provider_module
from omnipanel.domain.contracts import ComponentContractRef, ProviderRequest, ResourceRequest
from omnipanel.execution_provider import (
    ExecutionProviderError,
    FakeExecutionProvider,
    ProviderCandidateRequest,
    ProviderDescription,
    ProviderFailureCode,
    ProviderGuarantees,
    ProviderIdentity,
    ProviderMetadataItem,
    ProviderWorkPurpose,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op014_provider_matrix.json"
CLOCK = datetime(2026, 9, 14, 2, 0, tzinfo=UTC)


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _provider(entry: dict[str, object]) -> FakeExecutionProvider:
    guarantees_raw = entry["guarantees"]
    metadata_raw = entry["metadata"]
    total_raw = entry["total"]
    capabilities_raw = entry["capabilities"]
    purposes_raw = entry["purposes"]
    assert isinstance(guarantees_raw, dict)
    assert isinstance(metadata_raw, dict)
    assert isinstance(total_raw, dict)
    assert isinstance(capabilities_raw, list)
    assert isinstance(purposes_raw, list)

    description = ProviderDescription(
        identity=ProviderIdentity(
            provider_id=str(entry["provider_id"]),
            provider_class=str(entry["provider_class"]),
            implementation_version=str(entry["implementation_version"]),
            interface_contract=ComponentContractRef(
                component_id="fixture-provider",
                contract_id="execution-provider",
                contract_version="1.0",
            ),
        ),
        capabilities=tuple(str(item) for item in capabilities_raw),
        supported_purposes=tuple(ProviderWorkPurpose(str(item)) for item in purposes_raw),
        guarantees=ProviderGuarantees.model_validate(guarantees_raw),
        metadata=tuple(
            ProviderMetadataItem(key=str(key), value=str(value))
            for key, value in metadata_raw.items()
        ),
    )
    return FakeExecutionProvider(
        description,
        ResourceRequest.model_validate(total_raw),
        clock_start=CLOCK,
    )


PROVIDERS = _fixture()["providers"]
assert isinstance(PROVIDERS, list)


@pytest.mark.parametrize("entry", PROVIDERS, ids=lambda entry: str(entry["name"]))
def test_fixture_provider_inventory_and_identity_are_generic(entry: dict[str, object]) -> None:
    provider = _provider(entry)
    description = provider.describe()
    inventory = provider.inventory()
    assert inventory.provider == description.identity
    assert inventory.available == inventory.total
    assert description.identity.provider_id == entry["provider_id"]
    assert description.identity.provider_class == entry["provider_class"]

    metadata = {item.key: item.value for item in description.metadata}
    assert "os.family" in metadata
    assert "placement.kind" in metadata


def test_validation_only_fixture_is_representable_without_separate_scheduler_shape() -> None:
    raw = next(item for item in PROVIDERS if item["name"] == "validation-only")
    assert isinstance(raw, dict)
    provider = _provider(raw)
    request = ProviderRequest(
        provider_class="validation-worker",
        required_capability_handles=("test.windows",),
        resources=ResourceRequest(
            cpu_millicores=1000,
            memory_mib=1024,
            storage_mib=2048,
            wall_time_seconds=120,
        ),
        writable_paths=("validation-output",),
        isolation_required=True,
    )
    reservation = provider.reserve(run_id="run-validation-matrix", request=request)

    with pytest.raises(ExecutionProviderError) as exc:
        provider.start(
            ProviderCandidateRequest(
                run_id="run-validation-matrix",
                candidate_id="candidate-validation",
                task_id="OP-014",
                purpose=ProviderWorkPurpose.EXECUTION,
                reservation_id=reservation.reservation_id,
                payload_ref="payload-validation",
            )
        )
    assert exc.value.diagnostic.code is ProviderFailureCode.PURPOSE_UNSUPPORTED

    handle = provider.start(
        ProviderCandidateRequest(
            run_id="run-validation-matrix",
            candidate_id="candidate-validation",
            task_id="OP-014",
            purpose=ProviderWorkPurpose.VALIDATION,
            reservation_id=reservation.reservation_id,
            payload_ref="payload-validation",
        )
    )
    assert handle.purpose is ProviderWorkPurpose.VALIDATION


def test_remote_shaped_fixture_uses_same_provider_contract() -> None:
    raw = next(item for item in PROVIDERS if item["name"] == "remote-shaped")
    assert isinstance(raw, dict)
    provider = _provider(raw)
    metadata = {item.key: item.value for item in provider.describe().metadata}
    assert metadata["placement.kind"] == "remote"
    assert type(provider) is FakeExecutionProvider


def test_generic_provider_module_contains_no_reference_platform_scheduler_semantics() -> None:
    source = inspect.getsource(execution_provider_module).lower()
    assert "ubuntu" not in source
    assert "hyper-v" not in source
    assert "windows-latest" not in source
