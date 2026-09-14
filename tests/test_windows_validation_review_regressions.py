from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omnipanel.domain.contracts import ComponentContractRef
from omnipanel.execution_provider import ProviderIdentity
from omnipanel.windows_validation_provider import (
    WindowsValidationOutcome,
    WindowsValidationPlatform,
    WindowsValidationQualification,
    WindowsValidationQualificationState,
    WindowsValidationResult,
)

PLATFORM = WindowsValidationPlatform(
    platform_id="windows-validation-x64",
    os_version="Windows fixture",
    architecture="x86_64",
    image_id="win-fixture-image-v1",
    harness_id="validation-harness-v1",
)
NON_WINDOWS_PROVIDER = ProviderIdentity(
    provider_id="provider-general",
    provider_class="general-worker",
    implementation_version="1.0",
    interface_contract=ComponentContractRef(
        component_id="generic-provider",
        contract_id="execution-provider",
        contract_version="1.0",
    ),
)


def test_not_run_qualification_rejects_non_windows_provider_identity() -> None:
    with pytest.raises(ValueError, match="windows-validation provider"):
        WindowsValidationQualification(
            state=WindowsValidationQualificationState.NOT_RUN,
            platform=PLATFORM,
            reason="configured provider is unavailable",
            provider=NON_WINDOWS_PROVIDER,
        )


def test_validation_result_rejects_non_windows_provider_identity() -> None:
    with pytest.raises(ValueError, match="non-Windows provider identity"):
        WindowsValidationResult(
            run_id="run-review",
            task_id="OP-015",
            candidate_id="candidate-review",
            platform=PLATFORM,
            outcome=WindowsValidationOutcome.NOT_RUN,
            observed_at=datetime(2026, 9, 14, 6, 45, tzinfo=UTC),
            provider=NON_WINDOWS_PROVIDER,
            provider_job_id=None,
            test_summary=None,
            evidence_ids=(),
            detail="wrong provider identity must fail closed",
        )
