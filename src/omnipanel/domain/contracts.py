"""Versioned, fail-closed core contracts for Omnipanel OP-002."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

CURRENT_SCHEMA_VERSION: Literal[1] = 1

# Scalar contract types. Display text is intentionally distinct from identifiers.
DisplayText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=160),
]
ProjectId = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
    ),
]
TaskId = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=6,
        max_length=32,
        pattern=r"^[A-Z][A-Z0-9]{0,15}-\d{3,6}$",
    ),
]
MetaissueId = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=7,
        max_length=32,
        pattern=r"^[A-Z][A-Z0-9]{0,15}-M\d{3,6}$",
    ),
]
OpaqueId = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=96,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
TagId = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    ),
]
QualifierId = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$",
    ),
]
CapabilityHandle = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]
RepositoryRef = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=3,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    ),
]
ContractVersion = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$",
    ),
]
CommitSha = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{40}$"),
]
Sha256 = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$"),
]
PathText = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=512),
]
LocationText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=1024),
]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]
ReviewCount = Annotated[int, Field(strict=True, ge=0, le=32)]
Maturity = Annotated[int, Field(strict=True, ge=1, le=9)]
OrdinalRank = Annotated[int, Field(strict=True, ge=1, le=65_535)]
StrictBool = Annotated[bool, Field(strict=True)]


class ContractModel(BaseModel):
    """Immutable schema model with closed-world fields."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
    )


class VersionedRecord(ContractModel):
    """Top-level persisted/exchanged record with explicit schema generation."""

    schema_version: Literal[1] = CURRENT_SCHEMA_VERSION

    @field_validator("schema_version", mode="before")
    @classmethod
    def _validate_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != CURRENT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version; expected integer {CURRENT_SCHEMA_VERSION}"
            )
        return value


def _unique(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


def _safe_path(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("paths must not contain control characters")
    return value


def _aware_datetime(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value


class LoadBearing(StrEnum):
    TISSUE = "tissue"
    LABWARE = "labware"
    STONE = "stone"
    STEEL = "steel"


class ExpectedValue(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PRICELESS = "priceless"


class ExpectedWallTime(StrEnum):
    INSTANT = "instant"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    DAYS = "days"


class MarginalCost(StrEnum):
    FREE = "free"
    LOCAL = "local"
    LOW = "low"
    QUOTA = "quota"
    PAID = "paid"


class RunStrategy(StrEnum):
    SINGLE = "single"
    RACE = "race"
    DIVERSITY = "diversity"


class RacePolicy(StrEnum):
    ASK = "ask"
    FIRST_VALID_FREE = "first-valid-free"
    FIRST_VALID_ALL = "first-valid-all"
    COLLECT_ALL = "collect-all"
    COST_CONSCIOUS = "cost-conscious"


class SafetyState(StrEnum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    VERBOTEN = "verboten"


class WorkerKind(StrEnum):
    DETERMINISTIC = "deterministic"
    MODEL = "model"


class WorkerAuthorityClass(StrEnum):
    TRUSTED_DETERMINISTIC = "trusted-deterministic"
    READ_ONLY_REVIEW = "read-only-review"
    DISPOSABLE_WRITE = "disposable-write"
    BOUNDED_INTEGRATION = "bounded-integration"
    MASTER = "master"


class GateType(StrEnum):
    PUBLIC_TEST = "public-test"
    HIDDEN_TEST = "hidden-test"
    INVARIANT = "invariant"
    INTEGRATION = "integration"
    MANUAL = "manual"
    REVIEW = "review"


class GateVisibility(StrEnum):
    CANDIDATE_VISIBLE = "candidate-visible"
    MASTER_ONLY = "master-only"


class GateOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_RUN = "not-run"


class EvidenceKind(StrEnum):
    LOG = "log"
    TEST_REPORT = "test-report"
    PATCH = "patch"
    DIFF = "diff"
    ARTIFACT = "artifact"
    REVIEW = "review"
    PROVENANCE = "provenance"
    METRIC = "metric"
    OTHER = "other"


class EvidenceProducerType(StrEnum):
    HUMAN = "human"
    MASTER = "master"
    WORKER = "worker"
    PROVIDER = "provider"
    CI = "ci"
    REVIEWER = "reviewer"


class TagPolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class RunStatus(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_ADJUDICATION = "awaiting-adjudication"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CONTAINED = "contained"


class CandidateStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    ELIGIBLE = "eligible"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CONTAINED = "contained"


class CancellationKind(StrEnum):
    USER = "user"
    POLICY = "policy"
    PREEMPTED = "preempted"
    PROVIDER_FAILURE = "provider-failure"
    CONTAINMENT = "containment"


class SalvageLevel(StrEnum):
    NONE = "none"
    MINIMAL = "minimal"
    FULL_WORKTREE = "full-worktree"


class EconomicDimensions(ContractModel):
    expected_value: ExpectedValue
    expected_wall_time: ExpectedWallTime
    marginal_cost: MarginalCost


class ReviewPolicy(ContractModel):
    self_check_required: StrictBool = True
    independent_implementation_reviews: ReviewCount = 0
    independent_verification_reviews: ReviewCount = 0
    consequential_promotion_requires_user: StrictBool = True


class UserPolicyDecision(ContractModel):
    decision_id: OpaqueId
    confirmed_by: OpaqueId
    confirmed_at: datetime
    note: DisplayText | None = None

    @field_validator("confirmed_at")
    @classmethod
    def _confirmed_at_aware(cls, value: datetime) -> datetime:
        return _aware_datetime(value, "confirmed_at")


class TaskPolicyDefaults(ContractModel):
    """Partial metaissue/project defaults; never an execution authorization."""

    load_bearing: LoadBearing | None = None
    expected_value: ExpectedValue | None = None
    expected_wall_time: ExpectedWallTime | None = None
    marginal_cost: MarginalCost | None = None
    strategy: RunStrategy | None = None
    race_policy: RacePolicy | None = None
    review: ReviewPolicy | None = None

    @model_validator(mode="after")
    def _race_policy_matches_strategy(self) -> Self:
        if self.race_policy is not None and self.strategy is not RunStrategy.RACE:
            raise ValueError("race_policy defaults require strategy='race'")
        return self


class TaskPolicy(ContractModel):
    """Resolved policy snapshot. Missing human choice remains restrictive/undecided."""

    load_bearing: LoadBearing
    economics: EconomicDimensions
    strategy: RunStrategy
    race_policy: RacePolicy | None = None
    review: ReviewPolicy
    user_decision: UserPolicyDecision | None = None

    @model_validator(mode="after")
    def _validate_policy(self) -> Self:
        if self.strategy is RunStrategy.RACE:
            if self.race_policy is None:
                raise ValueError("Race strategy requires an explicit race_policy")
        elif self.race_policy is not None:
            raise ValueError("race_policy is valid only for Race strategy")

        if self.load_bearing is LoadBearing.STONE:
            if self.review.independent_implementation_reviews < 1:
                raise ValueError("Stone tasks require independent implementation review")
        elif self.load_bearing is LoadBearing.STEEL:
            if self.review.independent_implementation_reviews < 1:
                raise ValueError("Steel tasks require independent implementation review")
            if self.review.independent_verification_reviews < 1:
                raise ValueError("Steel tasks require independent verification review")
            if not self.review.consequential_promotion_requires_user:
                raise ValueError("Steel tasks require explicit user adjudication before promotion")
        return self

    def requires_explicit_user_decision(self) -> bool:
        return (
            self.load_bearing is LoadBearing.STEEL
            or self.economics.expected_value is ExpectedValue.PRICELESS
            or self.economics.expected_wall_time is ExpectedWallTime.DAYS
            or self.economics.marginal_cost is MarginalCost.PAID
        )

    def is_execution_policy_decided(self) -> bool:
        return not self.requires_explicit_user_decision() or self.user_decision is not None


class ResourceRequest(ContractModel):
    """Provider resource request with explicit units; values are not grants."""

    cpu_millicores: NonNegativeInt = 0
    memory_mib: NonNegativeInt = 0
    storage_mib: NonNegativeInt = 0
    wall_time_seconds: NonNegativeInt = 0
    gpu_count: Annotated[int, Field(strict=True, ge=0, le=256)] = 0


class ProviderRequest(ContractModel):
    """Fail-closed request: no capabilities, writes or network unless requested."""

    provider_class: OpaqueId | None = None
    required_capability_handles: Annotated[tuple[CapabilityHandle, ...], Field(max_length=64)] = ()
    resources: ResourceRequest = ResourceRequest()
    writable_paths: Annotated[tuple[PathText, ...], Field(max_length=64)] = ()
    network_access: StrictBool = False
    isolation_required: StrictBool = True

    @field_validator("required_capability_handles")
    @classmethod
    def _unique_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "required_capability_handles")

    @field_validator("writable_paths")
    @classmethod
    def _validate_writable_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_safe_path(item) for item in value)
        return _unique(checked, "writable_paths")


class AcceptanceGate(ContractModel):
    gate_id: OpaqueId
    gate_type: GateType
    display_name: DisplayText
    visibility: GateVisibility
    independent_context_required: StrictBool = False
    required: StrictBool = True

    @model_validator(mode="after")
    def _hidden_gate_isolated(self) -> Self:
        if self.gate_type is GateType.HIDDEN_TEST:
            if self.visibility is not GateVisibility.MASTER_ONLY:
                raise ValueError("hidden tests must not be candidate-visible")
            if not self.independent_context_required:
                raise ValueError("hidden tests require an independent evaluator context")
        return self


class GateResult(ContractModel):
    gate_id: OpaqueId
    outcome: GateOutcome
    evidence_ids: Annotated[tuple[OpaqueId, ...], Field(max_length=64)] = ()
    note: DisplayText | None = None

    @field_validator("evidence_ids")
    @classmethod
    def _unique_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "evidence_ids")


class ProjectRecord(VersionedRecord):
    record_type: Literal["project"] = "project"
    project_id: ProjectId
    display_name: DisplayText
    repository: RepositoryRef | None = None
    root_metaissue_ids: Annotated[tuple[MetaissueId, ...], Field(max_length=256)] = ()

    @field_validator("root_metaissue_ids")
    @classmethod
    def _unique_roots(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "root_metaissue_ids")


class MetaissueRecord(VersionedRecord):
    record_type: Literal["metaissue"] = "metaissue"
    metaissue_id: MetaissueId
    project_id: ProjectId
    display_name: DisplayText
    child_task_ids: Annotated[tuple[TaskId, ...], Field(max_length=1024)] = ()
    policy_defaults: TaskPolicyDefaults | None = None
    evidence_gate_ids: Annotated[tuple[OpaqueId, ...], Field(max_length=128)] = ()

    @field_validator("child_task_ids")
    @classmethod
    def _unique_children(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "child_task_ids")

    @field_validator("evidence_gate_ids")
    @classmethod
    def _unique_gate_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "evidence_gate_ids")


class DagEdge(VersionedRecord):
    record_type: Literal["dag-edge"] = "dag-edge"
    predecessor_task_id: TaskId
    successor_task_id: TaskId

    @model_validator(mode="after")
    def _not_self_edge(self) -> Self:
        if self.predecessor_task_id == self.successor_task_id:
            raise ValueError("DAG edge cannot point a task to itself")
        return self


class TaskRecord(VersionedRecord):
    record_type: Literal["task"] = "task"
    task_id: TaskId
    project_id: ProjectId
    parent_metaissue_id: MetaissueId | None = None
    display_name: DisplayText
    prerequisite_task_ids: Annotated[tuple[TaskId, ...], Field(max_length=256)] = ()
    policy: TaskPolicy
    provider_request: ProviderRequest = ProviderRequest()
    acceptance_gates: Annotated[tuple[AcceptanceGate, ...], Field(max_length=128)] = ()

    @model_validator(mode="after")
    def _validate_task(self) -> Self:
        if self.task_id in self.prerequisite_task_ids:
            raise ValueError("task cannot depend on itself")
        _unique(self.prerequisite_task_ids, "prerequisite_task_ids")
        gate_ids = tuple(gate.gate_id for gate in self.acceptance_gates)
        _unique(gate_ids, "acceptance gate IDs")
        return self


class ModelRef(ContractModel):
    provider_id: OpaqueId
    model_id: OpaqueId


class ModelIdentityRecord(VersionedRecord):
    record_type: Literal["model-identity"] = "model-identity"
    ref: ModelRef
    display_name: DisplayText
    family: OpaqueId | None = None
    aliases: Annotated[tuple[DisplayText, ...], Field(max_length=32)] = ()

    @field_validator("aliases")
    @classmethod
    def _unique_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "aliases")


class ModelTagAssessment(ContractModel):
    tag_id: TagId
    polarity: TagPolarity
    rank: OrdinalRank | None = None
    qualifiers: Annotated[tuple[QualifierId, ...], Field(max_length=8)] = ()

    @field_validator("qualifiers")
    @classmethod
    def _unique_qualifiers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "qualifiers")


class ModelAssessmentRecord(VersionedRecord):
    record_type: Literal["model-assessment"] = "model-assessment"
    model: ModelRef
    safety_state: SafetyState
    capability_classes: Annotated[tuple[OpaqueId, ...], Field(max_length=32)] = ()
    tags: Annotated[tuple[ModelTagAssessment, ...], Field(max_length=64)] = ()
    maturity: Maturity
    recent_evidence_ids: Annotated[tuple[OpaqueId, ...], Field(max_length=24)] = ()

    @model_validator(mode="after")
    def _unique_dimensions(self) -> Self:
        _unique(self.capability_classes, "capability_classes")
        tag_keys = tuple(f"{tag.polarity.value}:{tag.tag_id}" for tag in self.tags)
        _unique(tag_keys, "model tag assessments")
        _unique(self.recent_evidence_ids, "recent_evidence_ids")
        return self

    def is_automatically_schedulable(self) -> bool:
        return self.safety_state is SafetyState.ACTIVE


class MasterIdentityRecord(VersionedRecord):
    record_type: Literal["master"] = "master"
    master_id: OpaqueId
    driver_id: OpaqueId
    model: ModelRef | None = None


class WorkerIdentityRecord(VersionedRecord):
    record_type: Literal["worker"] = "worker"
    worker_id: OpaqueId
    kind: WorkerKind
    authority_class: WorkerAuthorityClass
    model: ModelRef | None = None

    @model_validator(mode="after")
    def _worker_model_consistency(self) -> Self:
        if self.kind is WorkerKind.MODEL and self.model is None:
            raise ValueError("model workers require canonical model identity")
        if self.kind is WorkerKind.DETERMINISTIC and self.model is not None:
            raise ValueError("deterministic workers must not carry a model identity")
        return self


class CandidateIdentityRecord(VersionedRecord):
    record_type: Literal["candidate"] = "candidate"
    candidate_id: OpaqueId
    task_id: TaskId
    worker_id: OpaqueId


class EvidenceProducer(ContractModel):
    producer_type: EvidenceProducerType
    producer_id: OpaqueId


class TestSummary(ContractModel):
    total: NonNegativeInt
    passed: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    errors: NonNegativeInt = 0
    skipped: NonNegativeInt = 0

    @model_validator(mode="after")
    def _counts_add_up(self) -> Self:
        if self.passed + self.failed + self.errors + self.skipped != self.total:
            raise ValueError("test outcome counts must add up to total")
        return self


class EvidenceDescriptorRecord(VersionedRecord):
    record_type: Literal["evidence"] = "evidence"
    evidence_id: OpaqueId
    kind: EvidenceKind
    producer: EvidenceProducer
    location: LocationText
    created_at: datetime
    sha256: Sha256 | None = None
    source_commit: CommitSha | None = None
    media_type: (
        Annotated[
            str,
            StringConstraints(strict=True, strip_whitespace=True, min_length=3, max_length=127),
        ]
        | None
    ) = None
    test_summary: TestSummary | None = None

    @field_validator("created_at")
    @classmethod
    def _created_at_aware(cls, value: datetime) -> datetime:
        return _aware_datetime(value, "created_at")


class ComponentContractRef(ContractModel):
    component_id: OpaqueId
    contract_id: OpaqueId
    contract_version: ContractVersion


class ComponentContractIdentityRecord(VersionedRecord):
    record_type: Literal["component-contract"] = "component-contract"
    ref: ComponentContractRef
    repository: RepositoryRef
    source_commit: CommitSha
    qualification_evidence_ids: Annotated[tuple[OpaqueId, ...], Field(max_length=64)] = ()

    @field_validator("qualification_evidence_ids")
    @classmethod
    def _unique_qualification_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, "qualification_evidence_ids")


class CancellationOutcome(ContractModel):
    candidate_id: OpaqueId
    kind: CancellationKind
    salvage_level: SalvageLevel
    salvage_evidence_ids: Annotated[tuple[OpaqueId, ...], Field(max_length=64)] = ()
    salvage_unavailable_reason: DisplayText | None = None

    @model_validator(mode="after")
    def _validate_salvage(self) -> Self:
        _unique(self.salvage_evidence_ids, "salvage_evidence_ids")
        if self.salvage_level is SalvageLevel.NONE:
            if self.salvage_evidence_ids:
                raise ValueError("salvage_level='none' cannot include salvage evidence")
            if (
                self.kind is not CancellationKind.CONTAINMENT
                and self.salvage_unavailable_reason is None
            ):
                raise ValueError(
                    "normal cancellation without salvage must record why salvage was unavailable"
                )
        elif not self.salvage_evidence_ids:
            raise ValueError("retained salvage requires evidence references")
        return self


class CandidateRecord(VersionedRecord):
    record_type: Literal["candidate-state"] = "candidate-state"
    candidate: CandidateIdentityRecord
    status: CandidateStatus
    gate_results: Annotated[tuple[GateResult, ...], Field(max_length=128)] = ()
    evidence_ids: Annotated[tuple[OpaqueId, ...], Field(max_length=256)] = ()
    cancellation: CancellationOutcome | None = None

    @model_validator(mode="after")
    def _validate_candidate_state(self) -> Self:
        gate_ids = tuple(result.gate_id for result in self.gate_results)
        _unique(gate_ids, "gate result IDs")
        _unique(self.evidence_ids, "candidate evidence_ids")
        if self.status in {CandidateStatus.CANCELLED, CandidateStatus.CONTAINED}:
            if self.cancellation is None:
                raise ValueError("cancelled/contained candidates require a cancellation outcome")
            if self.cancellation.candidate_id != self.candidate.candidate_id:
                raise ValueError("cancellation outcome must refer to this candidate")
            if (
                self.status is CandidateStatus.CONTAINED
                and self.cancellation.kind is not CancellationKind.CONTAINMENT
            ):
                raise ValueError("contained candidates require containment cancellation kind")
        elif self.cancellation is not None:
            raise ValueError(
                "cancellation outcome is valid only for cancelled/contained candidates"
            )
        return self


class RunRecord(VersionedRecord):
    record_type: Literal["run"] = "run"
    run_id: OpaqueId
    task_id: TaskId
    master_id: OpaqueId
    strategy: RunStrategy
    candidate_ids: Annotated[tuple[OpaqueId, ...], Field(min_length=1, max_length=64)]
    status: RunStatus
    race_policy: RacePolicy | None = None
    selected_candidate_id: OpaqueId | None = None
    evidence_ids: Annotated[tuple[OpaqueId, ...], Field(max_length=256)] = ()

    @model_validator(mode="after")
    def _validate_run(self) -> Self:
        _unique(self.candidate_ids, "candidate_ids")
        _unique(self.evidence_ids, "run evidence_ids")
        if self.strategy is RunStrategy.SINGLE:
            if len(self.candidate_ids) != 1:
                raise ValueError("Single runs require exactly one candidate")
            if self.race_policy is not None:
                raise ValueError("Single runs cannot carry race_policy")
        elif self.strategy is RunStrategy.RACE:
            if len(self.candidate_ids) < 2:
                raise ValueError("Race runs require at least two candidates")
            if self.race_policy is None:
                raise ValueError("Race runs require explicit race_policy")
        else:
            if len(self.candidate_ids) < 2:
                raise ValueError("Diversity runs require at least two candidates")
            if self.race_policy is not None:
                raise ValueError("Diversity runs cannot carry race_policy")
        if (
            self.selected_candidate_id is not None
            and self.selected_candidate_id not in self.candidate_ids
        ):
            raise ValueError("selected_candidate_id must be one of candidate_ids")
        return self


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "VersionedRecord",
    "AcceptanceGate",
    "CandidateIdentityRecord",
    "CandidateRecord",
    "CandidateStatus",
    "CancellationKind",
    "CancellationOutcome",
    "ComponentContractIdentityRecord",
    "ComponentContractRef",
    "DagEdge",
    "EconomicDimensions",
    "EvidenceDescriptorRecord",
    "EvidenceKind",
    "EvidenceProducer",
    "EvidenceProducerType",
    "ExpectedValue",
    "ExpectedWallTime",
    "GateOutcome",
    "GateResult",
    "GateType",
    "GateVisibility",
    "LoadBearing",
    "MarginalCost",
    "MasterIdentityRecord",
    "MetaissueRecord",
    "ModelAssessmentRecord",
    "ModelIdentityRecord",
    "ModelRef",
    "ModelTagAssessment",
    "ProjectRecord",
    "ProviderRequest",
    "RacePolicy",
    "ResourceRequest",
    "ReviewPolicy",
    "RunRecord",
    "RunStatus",
    "RunStrategy",
    "SafetyState",
    "SalvageLevel",
    "TagPolarity",
    "TaskPolicy",
    "TaskPolicyDefaults",
    "TaskRecord",
    "TestSummary",
    "UserPolicyDecision",
    "WorkerAuthorityClass",
    "WorkerIdentityRecord",
    "WorkerKind",
]
