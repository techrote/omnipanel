"""Deterministic synthetic Ansible-facing contract for OP-012.

This is deliberately not a claim about the current live Ansible API. It gives Omnipanel a
stable fixture boundary until a separately qualified live contract exists.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Never

from pydantic import Field, ValidationError, field_validator, model_validator

from omnipanel.domain.contracts import (
    CapabilityHandle,
    ComponentContractRef,
    ContractModel,
    EvidenceDescriptorRecord,
    OpaqueId,
    ResourceRequest,
    TaskId,
)

SYNTHETIC_ANSIBLE_CONTRACT = ComponentContractRef(
    component_id="ansible",
    contract_id="omnipanel-execution",
    contract_version="synthetic-1",
)
_MESSAGE_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class AnsibleAdapterErrorCode(StrEnum):
    INCOMPATIBLE_CONTRACT = "incompatible-contract"
    MALFORMED_PAYLOAD = "malformed-payload"
    STALE_STATUS = "stale-status"


class AnsibleAdapterDiagnostic(ContractModel):
    code: AnsibleAdapterErrorCode
    summary: str = Field(min_length=1, max_length=160)
    message_type: OpaqueId


class AnsibleAdapterError(RuntimeError):
    def __init__(self, diagnostic: AnsibleAdapterDiagnostic) -> None:
        super().__init__(diagnostic.summary)
        self.diagnostic = diagnostic


class SyntheticAnsibleMessage(ContractModel):
    contract: ComponentContractRef


class CapabilityDiscovery(SyntheticAnsibleMessage):
    message_type: Literal["capability-discovery"] = "capability-discovery"
    provider_id: OpaqueId
    capabilities: tuple[CapabilityHandle, ...] = Field(max_length=64)

    @field_validator("capabilities")
    @classmethod
    def _unique_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("capabilities must not contain duplicates")
        return value


class ResourceProviderSummary(SyntheticAnsibleMessage):
    message_type: Literal["resource-provider-summary"] = "resource-provider-summary"
    provider_id: OpaqueId
    total: ResourceRequest
    available: ResourceRequest

    @model_validator(mode="after")
    def _available_within_total(self) -> ResourceProviderSummary:
        fields = (
            "cpu_millicores",
            "memory_mib",
            "storage_mib",
            "wall_time_seconds",
            "gpu_count",
        )
        for field in fields:
            if getattr(self.available, field) > getattr(self.total, field):
                raise ValueError(f"available {field} cannot exceed total")
        return self


class JobProposal(SyntheticAnsibleMessage):
    message_type: Literal["job-proposal"] = "job-proposal"
    job_id: OpaqueId
    task_id: TaskId
    required_capabilities: tuple[CapabilityHandle, ...] = Field(max_length=64)
    resources: ResourceRequest
    payload_ref: OpaqueId

    @field_validator("required_capabilities")
    @classmethod
    def _unique_required_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("required_capabilities must not contain duplicates")
        return value


class JobLifecycle(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INDETERMINATE = "indeterminate"


class StatusCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class JobStatus(SyntheticAnsibleMessage):
    message_type: Literal["job-status"] = "job-status"
    job_id: OpaqueId
    sequence: int = Field(strict=True, ge=0, le=2_147_483_647)
    lifecycle: JobLifecycle
    completeness: StatusCompleteness = StatusCompleteness.COMPLETE
    observed_at: datetime
    evidence_ids: tuple[OpaqueId, ...] = Field(max_length=64)

    @field_validator("observed_at")
    @classmethod
    def _aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def _terminal_status_complete(self) -> JobStatus:
        terminal = {
            JobLifecycle.SUCCEEDED,
            JobLifecycle.FAILED,
            JobLifecycle.CANCELLED,
        }
        if self.lifecycle in terminal and self.completeness is not StatusCompleteness.COMPLETE:
            raise ValueError("terminal job status cannot be partial")
        return self


class JobResult(SyntheticAnsibleMessage):
    message_type: Literal["job-result"] = "job-result"
    job_id: OpaqueId
    lifecycle: JobLifecycle
    evidence_ids: tuple[OpaqueId, ...] = Field(max_length=128)
    detail: str = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def _terminal_result(self) -> JobResult:
        if self.lifecycle not in {
            JobLifecycle.SUCCEEDED,
            JobLifecycle.FAILED,
            JobLifecycle.CANCELLED,
            JobLifecycle.INDETERMINATE,
        }:
            raise ValueError("job result requires a terminal or indeterminate lifecycle")
        if self.lifecycle is JobLifecycle.SUCCEEDED and not self.evidence_ids:
            raise ValueError("successful job result requires evidence")
        return self


class EvidenceReport(SyntheticAnsibleMessage):
    message_type: Literal["evidence-report"] = "evidence-report"
    job_id: OpaqueId
    evidence: tuple[EvidenceDescriptorRecord, ...] = Field(max_length=64)


MESSAGE_MODELS: dict[str, type[SyntheticAnsibleMessage]] = {
    "capability-discovery": CapabilityDiscovery,
    "resource-provider-summary": ResourceProviderSummary,
    "job-proposal": JobProposal,
    "job-status": JobStatus,
    "job-result": JobResult,
    "evidence-report": EvidenceReport,
}


def _diagnostic_message_type(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    candidate = value.strip()
    if not candidate or len(candidate) > 96 or _MESSAGE_TYPE_PATTERN.fullmatch(candidate) is None:
        return "unknown"
    return candidate


class SyntheticAnsibleAdapter:
    """Strict decoder and stale-status guard for deterministic fixtures."""

    def decode(self, payload: Any) -> SyntheticAnsibleMessage:
        if not isinstance(payload, dict):
            self._raise(
                AnsibleAdapterErrorCode.MALFORMED_PAYLOAD,
                "payload must be an object",
                "unknown",
            )
        type_name = _diagnostic_message_type(payload.get("message_type"))
        contract = payload.get("contract")
        try:
            observed = ComponentContractRef.model_validate(contract)
        except ValidationError:
            self._raise(
                AnsibleAdapterErrorCode.MALFORMED_PAYLOAD,
                "payload contract reference is malformed",
                type_name,
            )
        if observed != SYNTHETIC_ANSIBLE_CONTRACT:
            self._raise(
                AnsibleAdapterErrorCode.INCOMPATIBLE_CONTRACT,
                "payload contract is not the supported synthetic Ansible contract",
                type_name,
            )
        model = MESSAGE_MODELS.get(type_name)
        if model is None:
            self._raise(
                AnsibleAdapterErrorCode.MALFORMED_PAYLOAD,
                "message_type is unknown",
                type_name,
            )
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            diagnostic = AnsibleAdapterDiagnostic(
                code=AnsibleAdapterErrorCode.MALFORMED_PAYLOAD,
                summary=f"{type_name} payload failed schema validation",
                message_type=type_name,
            )
            raise AnsibleAdapterError(diagnostic) from exc

    def decode_status(self, payload: Any, *, previous_sequence: int | None = None) -> JobStatus:
        message = self.decode(payload)
        if not isinstance(message, JobStatus):
            self._raise(
                AnsibleAdapterErrorCode.MALFORMED_PAYLOAD,
                "expected job-status payload",
                getattr(message, "message_type", "unknown"),
            )
        if previous_sequence is not None and message.sequence <= previous_sequence:
            self._raise(
                AnsibleAdapterErrorCode.STALE_STATUS,
                "job status sequence is stale or duplicated",
                message.message_type,
            )
        return message

    @staticmethod
    def _raise(code: AnsibleAdapterErrorCode, summary: str, message_type: str) -> Never:
        raise AnsibleAdapterError(
            AnsibleAdapterDiagnostic(
                code=code,
                summary=summary,
                message_type=message_type,
            )
        )


__all__ = [
    "AnsibleAdapterDiagnostic",
    "AnsibleAdapterError",
    "AnsibleAdapterErrorCode",
    "CapabilityDiscovery",
    "EvidenceReport",
    "JobLifecycle",
    "JobProposal",
    "JobResult",
    "JobStatus",
    "ResourceProviderSummary",
    "SYNTHETIC_ANSIBLE_CONTRACT",
    "StatusCompleteness",
    "SyntheticAnsibleAdapter",
]
