"""Validation-only Windows Execution Provider adapter for OP-015.

This module keeps provider lifecycle, validation outcome and live-environment qualification
as separate concepts. A provider job may complete successfully while validation fails,
and an unavailable live Windows environment is represented as NOT RUN rather than PASS.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from omnipanel.domain.contracts import (
    ComponentContractRef,
    ContractModel,
    DisplayText,
    EvidenceKind,
    OpaqueId,
    ProviderRequest,
    ResourceRequest,
    TaskId,
    TestSummary,
)
from omnipanel.execution_provider import (
    ExecutionProvider,
    ExecutionProviderError,
    FakeExecutionProvider,
    ProviderAvailability,
    ProviderCandidateHandle,
    ProviderCandidateLifecycle,
    ProviderCandidateObservation,
    ProviderCandidateRequest,
    ProviderDescription,
    ProviderDiagnostic,
    ProviderEvidenceReceipt,
    ProviderFailureCode,
    ProviderGuarantees,
    ProviderIdentity,
    ProviderInventory,
    ProviderMetadataItem,
    ProviderReservation,
    ProviderWorkPurpose,
)

WINDOWS_VALIDATION_PROVIDER_CLASS = "windows-validation"
WINDOWS_VALIDATION_CAPABILITY = "validation.windows"


class WindowsValidationOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_RUN = "not-run"
    INDETERMINATE = "indeterminate"


class WindowsValidationQualificationState(StrEnum):
    QUALIFIED = "qualified"
    NOT_RUN = "not-run"


class WindowsValidationPlatform(ContractModel):
    platform_id: OpaqueId
    os_family: Literal["windows"] = "windows"
    os_version: DisplayText
    architecture: OpaqueId
    image_id: OpaqueId
    harness_id: OpaqueId


class WindowsValidationQualification(ContractModel):
    state: WindowsValidationQualificationState
    platform: WindowsValidationPlatform
    reason: DisplayText
    provider: ProviderIdentity | None = None

    @model_validator(mode="after")
    def _qualified_requires_provider(self) -> Self:
        if self.state is WindowsValidationQualificationState.QUALIFIED:
            if self.provider is None:
                raise ValueError("qualified Windows validation requires provider identity")
            if self.provider.provider_class != WINDOWS_VALIDATION_PROVIDER_CLASS:
                raise ValueError("qualified Windows validation requires windows-validation provider")
        return self


class WindowsValidationResult(ContractModel):
    run_id: OpaqueId
    task_id: TaskId
    candidate_id: OpaqueId
    platform: WindowsValidationPlatform
    outcome: WindowsValidationOutcome
    observed_at: datetime
    provider: ProviderIdentity | None = None
    provider_job_id: OpaqueId | None = None
    test_summary: TestSummary | None = None
    evidence_ids: tuple[OpaqueId, ...] = Field(max_length=128)
    detail: DisplayText | None = None

    @field_validator("observed_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def _unique_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("evidence_ids must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _outcome_evidence_consistency(self) -> Self:
        if self.outcome is WindowsValidationOutcome.NOT_RUN:
            if self.provider_job_id is not None:
                raise ValueError("NOT RUN cannot carry a provider job")
            if self.test_summary is not None or self.evidence_ids:
                raise ValueError("NOT RUN cannot carry executed-test evidence")
            return self

        if self.provider is None or self.provider_job_id is None:
            raise ValueError("started validation requires provider and job identity")
        if not self.evidence_ids:
            raise ValueError("started validation requires evidence")

        if self.outcome in {WindowsValidationOutcome.PASS, WindowsValidationOutcome.FAIL}:
            if self.test_summary is None:
                raise ValueError("executed validation requires a test summary")
        if self.outcome is WindowsValidationOutcome.PASS and self.test_summary is not None:
            if self.test_summary.failed or self.test_summary.errors:
                raise ValueError("PASS cannot contain failed/error test counts")
        return self


class WindowsValidationProvider:
    """Validation-only adapter over the generic ExecutionProvider contract."""

    def __init__(
        self,
        backend: ExecutionProvider,
        *,
        platform: WindowsValidationPlatform,
    ) -> None:
        description = backend.describe()
        metadata = {item.key: item.value for item in description.metadata}
        if description.identity.provider_class != WINDOWS_VALIDATION_PROVIDER_CLASS:
            raise ValueError("Windows validation provider must use provider_class='windows-validation'")
        if set(description.supported_purposes) != {ProviderWorkPurpose.VALIDATION}:
            raise ValueError("Windows validation provider must advertise validation-only purpose")
        if WINDOWS_VALIDATION_CAPABILITY not in description.capabilities:
            raise ValueError("Windows validation provider lacks validation.windows capability")
        expected_metadata = {
            "os.family": "windows",
            "platform.id": platform.platform_id,
            "image.id": platform.image_id,
            "harness.id": platform.harness_id,
        }
        for key, expected in expected_metadata.items():
            if metadata.get(key) != expected:
                raise ValueError(f"provider metadata {key!r} does not match platform identity")
        self._backend = backend
        self.platform = platform

    def describe(self) -> ProviderDescription:
        return self._backend.describe()

    def inventory(self) -> ProviderInventory:
        return self._backend.inventory()

    def reserve(self, *, run_id: str, request: ProviderRequest) -> ProviderReservation:
        return self._backend.reserve(run_id=run_id, request=request)

    def reservation(self, reservation_id: str) -> ProviderReservation:
        return self._backend.reservation(reservation_id)

    def start(self, request: ProviderCandidateRequest) -> ProviderCandidateHandle:
        if request.purpose is not ProviderWorkPurpose.VALIDATION:
            raise ExecutionProviderError(
                ProviderDiagnostic(
                    code=ProviderFailureCode.PURPOSE_UNSUPPORTED,
                    summary="Windows validation provider accepts validation work only",
                    provider_id=self.describe().identity.provider_id,
                    reservation_id=request.reservation_id,
                    candidate_id=request.candidate_id,
                    missing_capability_handles=(),
                )
            )
        return self._backend.start(request)

    def observe(self, handle: ProviderCandidateHandle) -> ProviderCandidateObservation:
        return self._backend.observe(handle)

    def cancel(
        self,
        handle: ProviderCandidateHandle,
        *,
        reason: str,
    ) -> ProviderCandidateObservation:
        return self._backend.cancel(handle, reason=reason)

    def collect_evidence(
        self,
        handle: ProviderCandidateHandle,
    ) -> tuple[ProviderEvidenceReceipt, ...]:
        return self._backend.collect_evidence(handle)

    def release(self, reservation_id: str) -> ProviderReservation:
        return self._backend.release(reservation_id)


class SyntheticWindowsValidationProvider(WindowsValidationProvider):
    """Deterministic validation provider used until a live provider is qualified."""

    def __init__(
        self,
        *,
        provider_id: str,
        implementation_version: str,
        platform: WindowsValidationPlatform,
        capabilities: tuple[str, ...],
        total: ResourceRequest,
        clock_start: datetime,
        availability: ProviderAvailability = ProviderAvailability.AVAILABLE,
    ) -> None:
        description = ProviderDescription(
            identity=ProviderIdentity(
                provider_id=provider_id,
                provider_class=WINDOWS_VALIDATION_PROVIDER_CLASS,
                implementation_version=implementation_version,
                interface_contract=_windows_validation_contract(),
            ),
            capabilities=_validation_capabilities(capabilities),
            supported_purposes=(ProviderWorkPurpose.VALIDATION,),
            guarantees=ProviderGuarantees(
                isolation=True,
                resource_limits=True,
                network_policy=True,
                filesystem_policy=True,
            ),
            metadata=(
                ProviderMetadataItem(key="os.family", value="windows"),
                ProviderMetadataItem(key="platform.id", value=platform.platform_id),
                ProviderMetadataItem(key="image.id", value=platform.image_id),
                ProviderMetadataItem(key="harness.id", value=platform.harness_id),
                ProviderMetadataItem(key="environment.kind", value="synthetic"),
            ),
        )
        self._fake = FakeExecutionProvider(
            description,
            total,
            availability=availability,
            clock_start=clock_start,
        )
        self._evidence_summaries: dict[str, TestSummary | None] = {}
        self._evidence_outcomes: dict[str, WindowsValidationOutcome] = {}
        super().__init__(self._fake, platform=platform)

    def finish_validation(
        self,
        handle: ProviderCandidateHandle,
        outcome: WindowsValidationOutcome,
        *,
        test_summary: TestSummary | None = None,
        detail: str | None = None,
    ) -> WindowsValidationResult:
        if outcome is WindowsValidationOutcome.NOT_RUN:
            raise ValueError("NOT RUN is created from qualification state, not a started provider job")
        if outcome in {WindowsValidationOutcome.PASS, WindowsValidationOutcome.FAIL}:
            if test_summary is None:
                raise ValueError("PASS/FAIL validation requires test_summary")
            lifecycle = ProviderCandidateLifecycle.SUCCEEDED
        else:
            lifecycle = ProviderCandidateLifecycle.INDETERMINATE

        observation = self._fake.finish(
            handle,
            lifecycle,
            detail=detail or f"Windows validation {outcome.value}",
        )
        generic_receipts = self._fake.collect_evidence(handle)
        newest_evidence_id = generic_receipts[-1].descriptor.evidence_id
        self._evidence_summaries[newest_evidence_id] = test_summary
        self._evidence_outcomes[newest_evidence_id] = outcome
        receipts = self.collect_evidence(handle)
        return WindowsValidationResult(
            run_id=handle.run_id,
            task_id=handle.task_id,
            candidate_id=handle.candidate_id,
            platform=self.platform,
            outcome=outcome,
            observed_at=observation.observed_at,
            provider=handle.provider,
            provider_job_id=handle.provider_job_id,
            test_summary=test_summary,
            evidence_ids=tuple(receipt.descriptor.evidence_id for receipt in receipts),
            detail=detail,
        )

    def collect_evidence(
        self,
        handle: ProviderCandidateHandle,
    ) -> tuple[ProviderEvidenceReceipt, ...]:
        receipts = self._fake.collect_evidence(handle)
        return tuple(self._platform_receipt(receipt) for receipt in receipts)

    def _platform_receipt(
        self,
        receipt: ProviderEvidenceReceipt,
    ) -> ProviderEvidenceReceipt:
        descriptor = receipt.descriptor
        evidence_id = descriptor.evidence_id
        summary = self._evidence_summaries.get(evidence_id)
        outcome = self._evidence_outcomes.get(evidence_id)
        provider_lifecycle = descriptor.location.rsplit("/", 1)[-1]
        validation_state = outcome.value if outcome is not None else provider_lifecycle
        location = (
            f"validation://{receipt.provider.provider_id}/"
            f"{receipt.provider.implementation_version}/"
            f"{self.platform.platform_id}/{self.platform.image_id}/"
            f"{self.platform.harness_id}/{receipt.provider_job_id}/"
            f"{validation_state}/{evidence_id}"
        )
        enriched = descriptor.model_copy(
            update={
                "kind": EvidenceKind.TEST_REPORT if outcome is not None else descriptor.kind,
                "location": location,
                "test_summary": summary,
            }
        )
        return receipt.model_copy(update={"descriptor": enriched})


def validation_not_run_result(
    qualification: WindowsValidationQualification,
    *,
    run_id: str,
    task_id: str,
    candidate_id: str,
    observed_at: datetime,
) -> WindowsValidationResult:
    """Normalize an unavailable/unqualified live Windows environment to NOT RUN."""

    if qualification.state is not WindowsValidationQualificationState.NOT_RUN:
        raise ValueError("validation_not_run_result requires qualification state NOT RUN")
    return WindowsValidationResult(
        run_id=run_id,
        task_id=task_id,
        candidate_id=candidate_id,
        platform=qualification.platform,
        outcome=WindowsValidationOutcome.NOT_RUN,
        observed_at=observed_at,
        provider=qualification.provider,
        provider_job_id=None,
        test_summary=None,
        evidence_ids=(),
        detail=qualification.reason,
    )


def _validation_capabilities(capabilities: tuple[str, ...]) -> tuple[str, ...]:
    ordered = (WINDOWS_VALIDATION_CAPABILITY, *capabilities)
    return tuple(dict.fromkeys(ordered))


def _windows_validation_contract() -> ComponentContractRef:
    return ComponentContractRef(
        component_id="windows-validation-provider",
        contract_id="execution-provider",
        contract_version="1.0",
    )


__all__ = [
    "SyntheticWindowsValidationProvider",
    "WINDOWS_VALIDATION_CAPABILITY",
    "WINDOWS_VALIDATION_PROVIDER_CLASS",
    "WindowsValidationOutcome",
    "WindowsValidationPlatform",
    "WindowsValidationProvider",
    "WindowsValidationQualification",
    "WindowsValidationQualificationState",
    "WindowsValidationResult",
    "validation_not_run_result",
]
