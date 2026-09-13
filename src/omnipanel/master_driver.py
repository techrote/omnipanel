"""Replaceable master-driver contracts with fail-closed task normalization."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Never, Protocol

from pydantic import Field, model_validator

from omnipanel.domain.contracts import (
    ContractModel,
    DisplayText,
    LocationText,
    MasterIdentityRecord,
    OpaqueId,
    ProviderRequest,
    RunStrategy,
    Sha256,
    TaskId,
    TaskRecord,
)


class MasterAvailability(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class MasterDriverStatus(ContractModel):
    availability: MasterAvailability
    detail: DisplayText | None = None


class MasterProvenance(ContractModel):
    """Bounded provenance only; full conversations remain outside task contracts."""

    driver_id: OpaqueId
    context_sha256: Sha256
    conversation_ref: LocationText | None = None


class MasterTaskIntake(ContractModel):
    task: TaskRecord
    provenance: MasterProvenance


class ProposedSubtask(ContractModel):
    step_id: OpaqueId
    display_name: DisplayText
    depends_on: tuple[OpaqueId, ...] = Field(max_length=64)

    @model_validator(mode="after")
    def _validate_dependencies(self) -> ProposedSubtask:
        if self.step_id in self.depends_on:
            raise ValueError("proposed subtask cannot depend on itself")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("proposed subtask dependencies must be unique")
        return self


class MasterProposal(ContractModel):
    proposal_id: OpaqueId
    task_id: TaskId
    strategy: RunStrategy
    candidate_count: int = Field(strict=True, ge=1, le=64)
    provider_request: ProviderRequest
    decomposition: tuple[ProposedSubtask, ...] = Field(max_length=64)
    rationale: DisplayText

    @model_validator(mode="after")
    def _validate_decomposition(self) -> MasterProposal:
        step_ids = tuple(step.step_id for step in self.decomposition)
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("decomposition step IDs must be unique")
        known = set(step_ids)
        graph: dict[str, tuple[str, ...]] = {}
        for step in self.decomposition:
            unknown = set(step.depends_on) - known
            if unknown:
                raise ValueError("decomposition dependency refers to an unknown step")
            graph[step.step_id] = step.depends_on
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError("decomposition must be acyclic")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in graph[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)
        return self


class NormalizedTaskContract(ContractModel):
    contract_id: OpaqueId
    task_id: TaskId
    master: MasterIdentityRecord
    proposal_id: OpaqueId
    strategy: RunStrategy
    candidate_count: int = Field(strict=True, ge=1, le=64)
    provider_request: ProviderRequest
    acceptance_gate_ids: tuple[OpaqueId, ...] = Field(max_length=128)
    provenance: MasterProvenance


class MasterAdjudicationRequest(ContractModel):
    contract_id: OpaqueId
    task_id: TaskId
    candidate_ids: tuple[OpaqueId, ...] = Field(min_length=1, max_length=64)
    evidence_ids: tuple[OpaqueId, ...] = Field(max_length=256)
    promotion_requires_user: bool

    @model_validator(mode="after")
    def _unique_ids(self) -> MasterAdjudicationRequest:
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("candidate_ids must be unique")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be unique")
        return self


class MasterRecommendation(StrEnum):
    SELECT = "select"
    REJECT_ALL = "reject-all"
    REQUEST_USER = "request-user"


class MasterAdjudication(ContractModel):
    contract_id: OpaqueId
    recommendation: MasterRecommendation
    selected_candidate_id: OpaqueId | None = None
    evidence_ids: tuple[OpaqueId, ...] = Field(max_length=256)
    rationale: DisplayText

    @model_validator(mode="after")
    def _selection_shape(self) -> MasterAdjudication:
        if self.recommendation is MasterRecommendation.SELECT:
            if self.selected_candidate_id is None:
                raise ValueError("select recommendation requires selected_candidate_id")
        elif self.selected_candidate_id is not None:
            raise ValueError("selected_candidate_id is valid only for select recommendation")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("adjudication evidence_ids must be unique")
        return self


class MasterLifecycleResult(ContractModel):
    intake: MasterTaskIntake
    contract: NormalizedTaskContract
    adjudication_request: MasterAdjudicationRequest
    adjudication: MasterAdjudication


class MasterDriver(Protocol):
    @property
    def identity(self) -> MasterIdentityRecord: ...

    def status(self) -> MasterDriverStatus: ...

    def propose(self, intake: MasterTaskIntake) -> MasterProposal: ...

    def adjudicate(self, request: MasterAdjudicationRequest) -> MasterAdjudication: ...


class MasterLifecycleErrorCode(StrEnum):
    MASTER_UNAVAILABLE = "master-unavailable"
    PROVENANCE_MISMATCH = "provenance-mismatch"
    TASK_MISMATCH = "task-mismatch"
    USER_POLICY_REQUIRED = "user-policy-required"
    STRATEGY_CONFLICT = "strategy-conflict"
    CANDIDATE_COUNT_INVALID = "candidate-count-invalid"
    CANDIDATE_SET_INVALID = "candidate-set-invalid"
    PROVIDER_CLASS_BROADENED = "provider-class-broadened"
    CAPABILITY_BROADENED = "capability-broadened"
    RESOURCE_BROADENED = "resource-broadened"
    WRITE_SCOPE_BROADENED = "write-scope-broadened"
    NETWORK_BROADENED = "network-broadened"
    ISOLATION_WEAKENED = "isolation-weakened"
    ADJUDICATION_MISMATCH = "adjudication-mismatch"
    UNKNOWN_CANDIDATE = "unknown-candidate"
    EVIDENCE_MISMATCH = "evidence-mismatch"


class MasterLifecycleDiagnostic(ContractModel):
    code: MasterLifecycleErrorCode
    summary: DisplayText


class MasterLifecycleError(RuntimeError):
    def __init__(self, diagnostic: MasterLifecycleDiagnostic) -> None:
        super().__init__(diagnostic.summary)
        self.diagnostic = diagnostic


class MasterLifecycle:
    """Normalize advisory master output under canonical task policy and provider bounds."""

    def __init__(self, driver: MasterDriver) -> None:
        self.driver = driver

    def run(
        self,
        task: TaskRecord,
        *,
        context: str,
        candidate_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...] = (),
        conversation_ref: str | None = None,
    ) -> MasterLifecycleResult:
        status = self.driver.status()
        if status.availability is MasterAvailability.UNAVAILABLE:
            self._fail(
                MasterLifecycleErrorCode.MASTER_UNAVAILABLE,
                status.detail or "master driver is unavailable",
            )
        provenance = MasterProvenance(
            driver_id=self.driver.identity.driver_id,
            context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
            conversation_ref=conversation_ref,
        )
        intake = MasterTaskIntake(task=task, provenance=provenance)
        proposal = self.driver.propose(intake)
        contract = self.normalize(task, proposal, provenance)
        if len(candidate_ids) != contract.candidate_count:
            self._fail(
                MasterLifecycleErrorCode.CANDIDATE_COUNT_INVALID,
                "actual candidate count does not match normalized master proposal",
            )
        if len(candidate_ids) != len(set(candidate_ids)):
            self._fail(
                MasterLifecycleErrorCode.CANDIDATE_SET_INVALID,
                "candidate IDs must be unique before adjudication",
            )
        request = MasterAdjudicationRequest(
            contract_id=contract.contract_id,
            task_id=task.task_id,
            candidate_ids=candidate_ids,
            evidence_ids=evidence_ids,
            promotion_requires_user=task.policy.review.consequential_promotion_requires_user,
        )
        adjudication = self.driver.adjudicate(request)
        self._validate_adjudication(request, adjudication)
        return MasterLifecycleResult(
            intake=intake,
            contract=contract,
            adjudication_request=request,
            adjudication=adjudication,
        )

    def normalize(
        self,
        task: TaskRecord,
        proposal: MasterProposal,
        provenance: MasterProvenance,
    ) -> NormalizedTaskContract:
        identity = self.driver.identity
        if provenance.driver_id != identity.driver_id:
            self._fail(
                MasterLifecycleErrorCode.PROVENANCE_MISMATCH,
                "master provenance does not match the active driver identity",
            )
        if proposal.task_id != task.task_id:
            self._fail(MasterLifecycleErrorCode.TASK_MISMATCH, "proposal targets another task")
        if not task.policy.is_execution_policy_decided():
            self._fail(
                MasterLifecycleErrorCode.USER_POLICY_REQUIRED,
                "task requires an explicit user policy decision before execution",
            )
        if proposal.strategy is not task.policy.strategy:
            self._fail(
                MasterLifecycleErrorCode.STRATEGY_CONFLICT,
                "master proposal cannot override the authoritative task strategy",
            )
        if proposal.strategy is RunStrategy.SINGLE:
            if proposal.candidate_count != 1:
                self._fail(
                    MasterLifecycleErrorCode.CANDIDATE_COUNT_INVALID,
                    "single strategy requires exactly one candidate",
                )
        elif proposal.candidate_count < 2:
            self._fail(
                MasterLifecycleErrorCode.CANDIDATE_COUNT_INVALID,
                "race/diversity strategy requires at least two candidates",
            )
        self._validate_provider_bounds(task.provider_request, proposal.provider_request)
        contract_id = _contract_id(identity.master_id, proposal.proposal_id, task.task_id)
        return NormalizedTaskContract(
            contract_id=contract_id,
            task_id=task.task_id,
            master=identity,
            proposal_id=proposal.proposal_id,
            strategy=task.policy.strategy,
            candidate_count=proposal.candidate_count,
            provider_request=proposal.provider_request,
            acceptance_gate_ids=tuple(gate.gate_id for gate in task.acceptance_gates),
            provenance=provenance,
        )

    def _validate_provider_bounds(
        self, authoritative: ProviderRequest, requested: ProviderRequest
    ) -> None:
        if authoritative.provider_class is not None:
            if requested.provider_class != authoritative.provider_class:
                self._fail(
                    MasterLifecycleErrorCode.PROVIDER_CLASS_BROADENED,
                    "master proposal cannot relax the authoritative provider class",
                )
        requested_caps = set(requested.required_capability_handles)
        if not requested_caps.issubset(authoritative.required_capability_handles):
            self._fail(
                MasterLifecycleErrorCode.CAPABILITY_BROADENED,
                "master proposal requests capabilities outside the task boundary",
            )
        requested_paths = set(requested.writable_paths)
        if not requested_paths.issubset(authoritative.writable_paths):
            self._fail(
                MasterLifecycleErrorCode.WRITE_SCOPE_BROADENED,
                "master proposal requests writable paths outside the task boundary",
            )
        if requested.network_access and not authoritative.network_access:
            self._fail(
                MasterLifecycleErrorCode.NETWORK_BROADENED,
                "master proposal cannot enable network access forbidden by the task",
            )
        if authoritative.isolation_required and not requested.isolation_required:
            self._fail(
                MasterLifecycleErrorCode.ISOLATION_WEAKENED,
                "master proposal cannot weaken required isolation",
            )
        resource_fields = (
            "cpu_millicores",
            "memory_mib",
            "storage_mib",
            "wall_time_seconds",
            "gpu_count",
        )
        for field in resource_fields:
            if getattr(requested.resources, field) > getattr(authoritative.resources, field):
                self._fail(
                    MasterLifecycleErrorCode.RESOURCE_BROADENED,
                    f"master proposal exceeds authoritative {field}",
                )

    def _validate_adjudication(
        self, request: MasterAdjudicationRequest, adjudication: MasterAdjudication
    ) -> None:
        if adjudication.contract_id != request.contract_id:
            self._fail(
                MasterLifecycleErrorCode.ADJUDICATION_MISMATCH,
                "adjudication refers to another normalized contract",
            )
        if (
            adjudication.selected_candidate_id is not None
            and adjudication.selected_candidate_id not in request.candidate_ids
        ):
            self._fail(
                MasterLifecycleErrorCode.UNKNOWN_CANDIDATE,
                "adjudication selected a candidate outside the request",
            )
        if not set(adjudication.evidence_ids).issubset(request.evidence_ids):
            self._fail(
                MasterLifecycleErrorCode.EVIDENCE_MISMATCH,
                "adjudication cites evidence outside the supplied evidence set",
            )

    @staticmethod
    def _fail(code: MasterLifecycleErrorCode, summary: str) -> Never:
        raise MasterLifecycleError(MasterLifecycleDiagnostic(code=code, summary=summary))


class FakeMasterDriver:
    """Deterministic driver used to verify replacement and lifecycle semantics."""

    def __init__(
        self,
        identity: MasterIdentityRecord,
        proposal: MasterProposal,
        adjudication: MasterAdjudication,
        *,
        availability: MasterAvailability = MasterAvailability.AVAILABLE,
    ) -> None:
        self._identity = identity
        self._proposal = proposal
        self._adjudication = adjudication
        self._availability = availability

    @property
    def identity(self) -> MasterIdentityRecord:
        return self._identity

    def status(self) -> MasterDriverStatus:
        detail = (
            None
            if self._availability is MasterAvailability.AVAILABLE
            else "fake master unavailable"
        )
        return MasterDriverStatus(availability=self._availability, detail=detail)

    def propose(self, intake: MasterTaskIntake) -> MasterProposal:
        return self._proposal

    def adjudicate(self, request: MasterAdjudicationRequest) -> MasterAdjudication:
        if self._adjudication.contract_id == "derive-from-request":
            return self._adjudication.model_copy(update={"contract_id": request.contract_id})
        return self._adjudication


def _contract_id(master_id: str, proposal_id: str, task_id: str) -> str:
    digest = hashlib.sha256(f"{master_id}:{proposal_id}:{task_id}".encode()).hexdigest()[:32]
    return f"master-contract-{digest}"


__all__ = [
    "FakeMasterDriver",
    "MasterAdjudication",
    "MasterAdjudicationRequest",
    "MasterAvailability",
    "MasterDriver",
    "MasterDriverStatus",
    "MasterLifecycle",
    "MasterLifecycleDiagnostic",
    "MasterLifecycleError",
    "MasterLifecycleErrorCode",
    "MasterLifecycleResult",
    "MasterProposal",
    "MasterProvenance",
    "MasterRecommendation",
    "MasterTaskIntake",
    "NormalizedTaskContract",
    "ProposedSubtask",
]
