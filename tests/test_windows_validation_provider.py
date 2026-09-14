from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omnipanel.domain.contracts import (
    ProviderRequest,
    ResourceRequest,
    TestSummary as ValidationTestSummary,
)
from omnipanel.execution_provider import (
    ExecutionProvider,
    ExecutionProviderError,
    ProviderAvailability,
    ProviderCandidateLifecycle,
    ProviderCandidateRequest,
    ProviderFailureCode,
    ProviderWorkPurpose,
)
from omnipanel.windows_validation_provider import (
    WINDOWS_VALIDATION_CAPABILITY,
    WINDOWS_VALIDATION_PROVIDER_CLASS,
    SyntheticWindowsValidationProvider,
    WindowsValidationOutcome,
    WindowsValidationPlatform,
    WindowsValidationQualification,
    WindowsValidationQualificationState,
    validation_not_run_result,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "op015_windows_validation.json"
CLOCK = datetime(2026, 9, 14, 6, 30, tzinfo=UTC)


def _fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _provider(
    *,
    availability: ProviderAvailability = ProviderAvailability.AVAILABLE,
) -> SyntheticWindowsValidationProvider:
    raw = _fixture()["synthetic"]
    assert isinstance(raw, dict)
    platform_raw = raw["platform"]
    total_raw = raw["total"]
    capabilities_raw = raw["capabilities"]
    assert isinstance(platform_raw, dict)
    assert isinstance(total_raw, dict)
    assert isinstance(capabilities_raw, list)
    return SyntheticWindowsValidationProvider(
        provider_id=str(raw["provider_id"]),
        implementation_version=str(raw["implementation_version"]),
        platform=WindowsValidationPlatform.model_validate(platform_raw),
        capabilities=tuple(str(item) for item in capabilities_raw),
        total=ResourceRequest.model_validate(total_raw),
        clock_start=CLOCK,
        availability=availability,
    )


def _request(*, cpu_millicores: int = 1000) -> ProviderRequest:
    return ProviderRequest(
        provider_class=WINDOWS_VALIDATION_PROVIDER_CLASS,
        required_capability_handles=(
            WINDOWS_VALIDATION_CAPABILITY,
            "test.pytest",
        ),
        resources=ResourceRequest(
            cpu_millicores=cpu_millicores,
            memory_mib=1024,
            storage_mib=2048,
            wall_time_seconds=180,
        ),
        writable_paths=("validation-output",),
        network_access=False,
        isolation_required=True,
    )


def _start(provider: SyntheticWindowsValidationProvider, *, payload_ref: str = "artifact-a"):
    reservation = provider.reserve(run_id="run-op015", request=_request())
    handle = provider.start(
        ProviderCandidateRequest(
            run_id="run-op015",
            candidate_id="candidate-a",
            task_id="OP-015",
            purpose=ProviderWorkPurpose.VALIDATION,
            reservation_id=reservation.reservation_id,
            payload_ref=payload_ref,
        )
    )
    return reservation, handle


def test_provider_is_validation_only_through_generic_contract() -> None:
    provider = _provider()
    generic: ExecutionProvider = provider
    description = generic.describe()
    assert description.identity.provider_class == WINDOWS_VALIDATION_PROVIDER_CLASS
    assert description.supported_purposes == (ProviderWorkPurpose.VALIDATION,)
    assert WINDOWS_VALIDATION_CAPABILITY in description.capabilities
    metadata = {item.key: item.value for item in description.metadata}
    assert metadata["os.family"] == "windows"
    assert metadata["platform.id"] == provider.platform.platform_id


def test_execution_work_is_rejected_before_backend_start() -> None:
    provider = _provider()
    reservation = provider.reserve(run_id="run-op015", request=_request())
    with pytest.raises(ExecutionProviderError) as exc:
        provider.start(
            ProviderCandidateRequest(
                run_id="run-op015",
                candidate_id="candidate-a",
                task_id="OP-015",
                purpose=ProviderWorkPurpose.EXECUTION,
                reservation_id=reservation.reservation_id,
                payload_ref="artifact-a",
            )
        )
    assert exc.value.diagnostic.code is ProviderFailureCode.PURPOSE_UNSUPPORTED


def test_pass_result_records_test_platform_and_provider_identity() -> None:
    provider = _provider()
    reservation, handle = _start(provider)
    summary = ValidationTestSummary(total=4, passed=4)
    result = provider.finish_validation(
        handle,
        WindowsValidationOutcome.PASS,
        test_summary=summary,
        detail="synthetic Windows acceptance suite passed",
    )

    assert provider.observe(handle).lifecycle is ProviderCandidateLifecycle.SUCCEEDED
    assert result.outcome is WindowsValidationOutcome.PASS
    assert result.test_summary == summary
    assert result.provider == provider.describe().identity
    assert result.platform == provider.platform
    receipts = provider.collect_evidence(handle)
    assert tuple(item.descriptor.evidence_id for item in receipts) == result.evidence_ids
    assert receipts[-1].descriptor.test_summary == summary
    assert provider.platform.platform_id in receipts[-1].descriptor.location
    assert provider.platform.image_id in receipts[-1].descriptor.location
    assert provider.platform.harness_id in receipts[-1].descriptor.location
    assert provider.describe().identity.provider_id in receipts[-1].descriptor.location
    assert provider.release(reservation.reservation_id).state.value == "released"


def test_validation_fail_is_not_provider_execution_failure_or_pass() -> None:
    provider = _provider()
    _, handle = _start(provider)
    summary = ValidationTestSummary(total=5, passed=4, failed=1)
    result = provider.finish_validation(
        handle,
        WindowsValidationOutcome.FAIL,
        test_summary=summary,
        detail="one Windows-specific assertion failed",
    )
    assert provider.observe(handle).lifecycle is ProviderCandidateLifecycle.SUCCEEDED
    assert result.outcome is WindowsValidationOutcome.FAIL
    assert result.test_summary.failed == 1
    assert result.outcome is not WindowsValidationOutcome.PASS


def test_candidate_payload_cannot_replace_platform_harness_identity() -> None:
    provider = _provider()
    _, handle = _start(provider, payload_ref="candidate-controlled-artifact")
    result = provider.finish_validation(
        handle,
        WindowsValidationOutcome.PASS,
        test_summary=ValidationTestSummary(total=1, passed=1),
    )
    receipt = provider.collect_evidence(handle)[-1]
    assert result.platform.harness_id == "validation-harness-v1"
    assert "candidate-controlled-artifact" not in receipt.descriptor.location
    assert result.platform.harness_id in receipt.descriptor.location


def test_unavailable_live_environment_normalizes_to_not_run() -> None:
    provider = _provider(availability=ProviderAvailability.UNAVAILABLE)
    with pytest.raises(ExecutionProviderError) as exc:
        provider.reserve(run_id="run-unavailable", request=_request())
    assert exc.value.diagnostic.code is ProviderFailureCode.PROVIDER_UNAVAILABLE

    live_raw = _fixture()["live_gate"]
    assert isinstance(live_raw, dict)
    qualification = WindowsValidationQualification(
        state=WindowsValidationQualificationState(str(live_raw["state"])),
        platform=provider.platform,
        reason=str(live_raw["reason"]),
        provider=None,
    )
    result = validation_not_run_result(
        qualification,
        run_id="run-unavailable",
        task_id="OP-015",
        candidate_id="candidate-a",
        observed_at=CLOCK,
    )
    assert result.outcome is WindowsValidationOutcome.NOT_RUN
    assert result.provider_job_id is None
    assert result.test_summary is None
    assert result.evidence_ids == ()
    assert result.outcome is not WindowsValidationOutcome.PASS


def test_over_capacity_request_fails_through_generic_resource_contract() -> None:
    provider = _provider()
    with pytest.raises(ExecutionProviderError) as exc:
        provider.reserve(run_id="run-over", request=_request(cpu_millicores=5000))
    assert exc.value.diagnostic.code is ProviderFailureCode.RESOURCES_UNAVAILABLE


def test_indeterminate_validation_holds_reservation_until_reconciled() -> None:
    provider = _provider()
    reservation, handle = _start(provider)
    result = provider.finish_validation(
        handle,
        WindowsValidationOutcome.INDETERMINATE,
        detail="validation worker connection lost",
    )
    assert result.outcome is WindowsValidationOutcome.INDETERMINATE
    assert provider.observe(handle).lifecycle is ProviderCandidateLifecycle.INDETERMINATE
    with pytest.raises(ExecutionProviderError) as exc:
        provider.release(reservation.reservation_id)
    assert exc.value.diagnostic.code is ProviderFailureCode.RESERVATION_STATE_INVALID


def test_reconciliation_preserves_per_observation_evidence() -> None:
    provider = _provider()
    reservation, handle = _start(provider)
    first = provider.finish_validation(
        handle,
        WindowsValidationOutcome.INDETERMINATE,
        detail="temporary provider uncertainty",
    )
    first_receipt = provider.collect_evidence(handle)[0]
    assert first_receipt.descriptor.test_summary is None
    assert "/indeterminate/" in first_receipt.descriptor.location
    assert first.evidence_ids == (first_receipt.descriptor.evidence_id,)

    summary = ValidationTestSummary(total=3, passed=3)
    second = provider.finish_validation(
        handle,
        WindowsValidationOutcome.PASS,
        test_summary=summary,
        detail="provider reconciled and validation passed",
    )
    receipts = provider.collect_evidence(handle)
    assert len(receipts) == 2
    assert receipts[0].descriptor.test_summary is None
    assert "/indeterminate/" in receipts[0].descriptor.location
    assert receipts[1].descriptor.test_summary == summary
    assert "/pass/" in receipts[1].descriptor.location
    assert second.evidence_ids == tuple(item.descriptor.evidence_id for item in receipts)
    assert provider.release(reservation.reservation_id).state.value == "released"
