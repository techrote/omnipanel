"""Validated workflow manifests and evidence-aware readiness for OP-005.

GitHub issue state is administrative metadata only. Readiness and completion are derived
from stable IDs, the validated DAG, explicit external gates and reconciled evidence.
"""

from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from omnipanel.domain.contracts import (
    DisplayText,
    LoadBearing,
    LocationText,
    OpaqueId,
    RepositoryRef,
    StrictBool,
    TaskPolicyDefaults,
)

MAX_WORKFLOW_BYTES = 1024 * 1024
CURRENT_WORKFLOW_SCHEMA_VERSION: Literal[1] = 1
PositiveIssueNumber = Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]

_TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9]{0,15}-\d{3,6}$")
_METAISSUE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]{0,15}-M\d{3,6}$")
_POLICY_FIELDS = (
    "load_bearing",
    "expected_value",
    "expected_wall_time",
    "marginal_cost",
    "strategy",
    "race_policy",
    "review",
)


class WorkflowError(ValueError):
    """A workflow or readiness input is structurally invalid."""


class WorkflowModel(BaseModel):
    """Closed, immutable workflow configuration model."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class MetaissueSpec(WorkflowModel):
    """A stable metaissue envelope and its direct child membership."""

    id: str
    title: DisplayText
    children: Annotated[tuple[str, ...], Field(min_length=1, max_length=2048)]
    policy_defaults: TaskPolicyDefaults | None = None
    deferred: StrictBool = False

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if _METAISSUE_ID_RE.fullmatch(value) is None:
            raise ValueError("metaissue id must use the stable OP-M### form")
        return value

    @field_validator("children")
    @classmethod
    def _valid_children(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("metaissue children must not contain duplicates")
        invalid = [item for item in value if _TASK_ID_RE.fullmatch(item) is None]
        if invalid:
            raise ValueError("metaissue children must use stable OP-### task IDs")
        return value


class WorkflowTaskSpec(WorkflowModel):
    """A bounded task node; policy fields may inherit from its metaissue."""

    id: str
    title: DisplayText
    deps: Annotated[tuple[str, ...], Field(max_length=1024)] = ()
    load_bearing: LoadBearing | None = None
    policy_overrides: TaskPolicyDefaults | None = None
    external_gate: DisplayText | None = None
    deferred: StrictBool = False
    deferred_implementation: StrictBool = False

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if _TASK_ID_RE.fullmatch(value) is None:
            raise ValueError("task id must use the stable OP-### form")
        return value

    @field_validator("deps")
    @classmethod
    def _valid_deps(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("task dependencies must not contain duplicates")
        invalid = [item for item in value if _TASK_ID_RE.fullmatch(item) is None]
        if invalid:
            raise ValueError("task dependencies must use stable OP-### task IDs")
        return value

    @model_validator(mode="after")
    def _no_ambiguous_load_bearing_override(self) -> Self:
        if self.id in self.deps:
            raise ValueError("task cannot depend on itself")
        if (
            self.load_bearing is not None
            and self.policy_overrides is not None
            and self.policy_overrides.load_bearing is not None
            and self.load_bearing is not self.policy_overrides.load_bearing
        ):
            raise ValueError("load_bearing and policy_overrides.load_bearing disagree")
        return self


def _policy_values(policy: TaskPolicyDefaults | None) -> dict[str, object]:
    if policy is None:
        return {}
    result: dict[str, object] = {}
    for field_name in _POLICY_FIELDS:
        value = getattr(policy, field_name)
        if value is not None:
            result[field_name] = value
    return result


def _merge_policy_defaults(
    meta_defaults: TaskPolicyDefaults | None,
    task_overrides: TaskPolicyDefaults | None,
    load_bearing: LoadBearing | None,
) -> TaskPolicyDefaults:
    values = _policy_values(meta_defaults)
    if task_overrides is not None:
        for field_name in _POLICY_FIELDS:
            if field_name in task_overrides.model_fields_set:
                values[field_name] = getattr(task_overrides, field_name)
    if load_bearing is not None:
        values["load_bearing"] = load_bearing
    try:
        return TaskPolicyDefaults.model_validate(values)
    except ValidationError as exc:
        raise ValueError("incompatible inherited task policy") from exc


def _cycle_residue(tasks: Mapping[str, WorkflowTaskSpec]) -> tuple[str, ...]:
    indegree = {task_id: len(task.deps) for task_id, task in tasks.items()}
    successors: dict[str, list[str]] = {task_id: [] for task_id in tasks}
    for task in tasks.values():
        for predecessor in task.deps:
            successors[predecessor].append(task.id)

    queue: deque[str] = deque(
        sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    )
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for successor in successors[current]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)

    if visited == len(tasks):
        return ()
    return tuple(sorted(task_id for task_id, degree in indegree.items() if degree > 0))


class WorkflowManifest(WorkflowModel):
    """Versioned programme graph with validated stable identity and membership."""

    schema_version: Literal[1] = CURRENT_WORKFLOW_SCHEMA_VERSION
    programme: OpaqueId
    generated_on: DisplayText
    notes: DisplayText | None = None
    metaissues: Annotated[tuple[MetaissueSpec, ...], Field(min_length=1, max_length=512)]
    tasks: Annotated[tuple[WorkflowTaskSpec, ...], Field(min_length=1, max_length=4096)]

    @field_validator("schema_version", mode="before")
    @classmethod
    def _exact_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != CURRENT_WORKFLOW_SCHEMA_VERSION:
            raise ValueError("unsupported workflow schema_version; expected integer 1")
        return value

    @model_validator(mode="after")
    def _validate_graph(self) -> Self:
        task_ids = tuple(task.id for task in self.tasks)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("workflow contains duplicate task IDs")
        metaissue_ids = tuple(metaissue.id for metaissue in self.metaissues)
        if len(metaissue_ids) != len(set(metaissue_ids)):
            raise ValueError("workflow contains duplicate metaissue IDs")

        task_map = {task.id: task for task in self.tasks}
        membership: dict[str, MetaissueSpec] = {}
        for metaissue in self.metaissues:
            for child_id in metaissue.children:
                if child_id not in task_map:
                    raise ValueError(
                        f"metaissue {metaissue.id} references missing child {child_id}"
                    )
                previous = membership.get(child_id)
                if previous is not None:
                    raise ValueError(
                        f"task {child_id} belongs to both {previous.id} and {metaissue.id}"
                    )
                membership[child_id] = metaissue

        missing_membership = sorted(set(task_map) - set(membership))
        if missing_membership:
            raise ValueError("tasks missing metaissue membership: " + ", ".join(missing_membership))

        for task in self.tasks:
            for predecessor in task.deps:
                if predecessor not in task_map:
                    raise ValueError(
                        f"task {task.id} references missing prerequisite {predecessor}"
                    )
            resolved = _merge_policy_defaults(
                membership[task.id].policy_defaults,
                task.policy_overrides,
                task.load_bearing,
            )
            if resolved.load_bearing is None:
                raise ValueError(f"task {task.id} has no resolved load_bearing policy")

        residue = _cycle_residue(task_map)
        if residue:
            raise ValueError("workflow dependency cycle detected involving: " + ", ".join(residue))
        return self


class IssueBindings(WorkflowModel):
    """Stable-ID to GitHub issue-number bindings; null tasks are unpublished."""

    schema_version: Literal[1] = CURRENT_WORKFLOW_SCHEMA_VERSION
    recorded_on: DisplayText
    repository: RepositoryRef
    metaissues: dict[str, PositiveIssueNumber]
    tasks: dict[str, PositiveIssueNumber | None]
    publication_blocks: dict[str, LocationText] = Field(default_factory=dict)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _exact_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != CURRENT_WORKFLOW_SCHEMA_VERSION:
            raise ValueError("unsupported issue-binding schema_version; expected integer 1")
        return value

    @field_validator("metaissues")
    @classmethod
    def _valid_metaissue_keys(cls, value: dict[str, int]) -> dict[str, int]:
        if any(_METAISSUE_ID_RE.fullmatch(key) is None for key in value):
            raise ValueError("issue bindings contain an invalid stable metaissue ID")
        return value

    @field_validator("tasks")
    @classmethod
    def _valid_task_keys(cls, value: dict[str, int | None]) -> dict[str, int | None]:
        if any(_TASK_ID_RE.fullmatch(key) is None for key in value):
            raise ValueError("issue bindings contain an invalid stable task ID")
        return value

    @model_validator(mode="after")
    def _validate_numbers_and_blocks(self) -> Self:
        numbers = list(self.metaissues.values()) + [
            number for number in self.tasks.values() if number is not None
        ]
        if len(numbers) != len(set(numbers)):
            raise ValueError("a GitHub issue number is bound to more than one stable ID")

        unpublished = {task_id for task_id, number in self.tasks.items() if number is None}
        block_ids = set(self.publication_blocks)
        if block_ids != unpublished:
            raise ValueError(
                "publication_blocks must exactly describe tasks with null issue bindings"
            )
        return self


def validate_issue_bindings(manifest: WorkflowManifest, bindings: IssueBindings) -> None:
    """Require bindings to cover exactly the stable IDs declared by the manifest."""

    expected_metaissues = {metaissue.id for metaissue in manifest.metaissues}
    expected_tasks = {task.id for task in manifest.tasks}
    if set(bindings.metaissues) != expected_metaissues:
        missing = sorted(expected_metaissues - set(bindings.metaissues))
        extra = sorted(set(bindings.metaissues) - expected_metaissues)
        raise WorkflowError(f"metaissue binding drift; missing={missing}, extra={extra}")
    if set(bindings.tasks) != expected_tasks:
        missing = sorted(expected_tasks - set(bindings.tasks))
        extra = sorted(set(bindings.tasks) - expected_tasks)
        raise WorkflowError(f"task binding drift; missing={missing}, extra={extra}")


def _read_json(path: Path) -> object:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WorkflowError(f"workflow file could not be read: {path}") from exc
    if len(raw) > MAX_WORKFLOW_BYTES:
        raise WorkflowError(f"workflow file exceeds {MAX_WORKFLOW_BYTES} bytes: {path}")
    try:
        return cast(object, json.loads(raw.decode("utf-8-sig")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"workflow file must contain valid UTF-8 JSON: {path}") from exc


def load_workflow_manifest(path: Path) -> WorkflowManifest:
    """Load and structurally validate a workflow manifest."""

    try:
        return WorkflowManifest.model_validate(_read_json(path))
    except ValidationError as exc:
        raise WorkflowError(f"invalid workflow manifest {path}: {exc}") from exc


def load_issue_bindings(path: Path) -> IssueBindings:
    """Load and structurally validate stable-ID issue bindings."""

    try:
        return IssueBindings.model_validate(_read_json(path))
    except ValidationError as exc:
        raise WorkflowError(f"invalid issue bindings {path}: {exc}") from exc


class CompletionDisposition(StrEnum):
    """Evidence disposition; only terminal outcomes can satisfy dependencies."""

    PENDING = "pending"
    PASS = "pass"
    NO_GO = "no-go"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


_TERMINAL_DISPOSITIONS = {
    CompletionDisposition.PASS,
    CompletionDisposition.NO_GO,
    CompletionDisposition.DEFERRED,
}


class TaskEvidence(WorkflowModel):
    """Minimal reconciled-evidence state consumed by the readiness engine."""

    task_id: str
    issue_closed: StrictBool = False
    evidence_reconciled: StrictBool = False
    disposition: CompletionDisposition = CompletionDisposition.PENDING
    note: DisplayText | None = None

    @field_validator("task_id")
    @classmethod
    def _valid_task_id(cls, value: str) -> str:
        if _TASK_ID_RE.fullmatch(value) is None:
            raise ValueError("task evidence must use a stable OP-### ID")
        return value

    @model_validator(mode="after")
    def _terminal_evidence_is_explicit(self) -> Self:
        if self.disposition in _TERMINAL_DISPOSITIONS and not self.evidence_reconciled:
            raise ValueError("terminal task disposition requires reconciled evidence")
        if (
            self.disposition
            in {
                CompletionDisposition.NO_GO,
                CompletionDisposition.DEFERRED,
                CompletionDisposition.BLOCKED,
            }
            and self.note is None
        ):
            raise ValueError(f"{self.disposition.value} disposition requires an explicit note")
        return self

    def is_complete(self) -> bool:
        """Return whether this state may satisfy dependency completion."""

        return self.evidence_reconciled and self.disposition in _TERMINAL_DISPOSITIONS


@dataclass(frozen=True, slots=True)
class TaskReadiness:
    """Auditable readiness result for one stable task."""

    task_id: str
    issue_number: int | None
    ready: bool
    complete: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetaissueCompletion:
    """Evidence-based metaissue completion result."""

    metaissue_id: str
    issue_number: int
    complete: bool
    incomplete_children: tuple[str, ...]
    review_reconciled: bool


class WorkflowEngine:
    """Validated workflow graph plus evidence-aware readiness/completion queries."""

    def __init__(self, manifest: WorkflowManifest, bindings: IssueBindings) -> None:
        validate_issue_bindings(manifest, bindings)
        self.manifest = manifest
        self.bindings = bindings
        self._tasks = {task.id: task for task in manifest.tasks}
        self._metaissues = {metaissue.id: metaissue for metaissue in manifest.metaissues}
        self._membership = {
            child_id: metaissue
            for metaissue in manifest.metaissues
            for child_id in metaissue.children
        }

    @classmethod
    def from_paths(cls, manifest_path: Path, bindings_path: Path) -> Self:
        """Load the canonical files and return a validated engine."""

        return cls(load_workflow_manifest(manifest_path), load_issue_bindings(bindings_path))

    def issue_for(self, stable_id: str) -> int | None:
        """Resolve presentation issue number without changing stable identity."""

        if stable_id in self.bindings.tasks:
            return self.bindings.tasks[stable_id]
        if stable_id in self.bindings.metaissues:
            return self.bindings.metaissues[stable_id]
        raise WorkflowError(f"unknown stable ID: {stable_id}")

    def metaissue_for_task(self, task_id: str) -> MetaissueSpec:
        """Return the task's validated parent membership."""

        try:
            return self._membership[task_id]
        except KeyError as exc:
            raise WorkflowError(f"unknown task ID: {task_id}") from exc

    def resolved_policy_defaults(self, task_id: str) -> TaskPolicyDefaults:
        """Resolve metaissue defaults plus explicit task overrides."""

        try:
            task = self._tasks[task_id]
        except KeyError as exc:
            raise WorkflowError(f"unknown task ID: {task_id}") from exc
        metaissue = self._membership[task_id]
        try:
            return _merge_policy_defaults(
                metaissue.policy_defaults,
                task.policy_overrides,
                task.load_bearing,
            )
        except ValueError as exc:
            raise WorkflowError(f"task {task_id} has incompatible inherited policy") from exc

    def _state_map(self, evidence: Iterable[TaskEvidence]) -> dict[str, TaskEvidence]:
        states: dict[str, TaskEvidence] = {}
        for state in evidence:
            if state.task_id not in self._tasks:
                raise WorkflowError(f"evidence references unknown task {state.task_id}")
            if state.task_id in states:
                raise WorkflowError(f"duplicate evidence state for task {state.task_id}")
            states[state.task_id] = state
        return states

    def _evaluate_task(
        self,
        task_id: str,
        states: Mapping[str, TaskEvidence],
        satisfied_external_gates: frozenset[str],
        *,
        allow_deferred: bool,
        allow_unpublished: bool,
    ) -> TaskReadiness:
        try:
            task = self._tasks[task_id]
        except KeyError as exc:
            raise WorkflowError(f"unknown task ID: {task_id}") from exc

        issue_number = self.bindings.tasks[task_id]
        state = states.get(task_id)
        if state is not None and state.is_complete():
            return TaskReadiness(
                task_id=task_id,
                issue_number=issue_number,
                ready=False,
                complete=True,
                reasons=("reconciled terminal evidence already completes task",),
            )

        reasons: list[str] = []
        if task.deferred and not allow_deferred:
            reasons.append("task is explicitly deferred")
        if issue_number is None and not allow_unpublished:
            reasons.append("task has no published GitHub issue binding")
        if task.external_gate is not None and task.external_gate not in satisfied_external_gates:
            reasons.append(f"external gate not satisfied: {task.external_gate}")
        for predecessor in task.deps:
            predecessor_state = states.get(predecessor)
            if predecessor_state is None or not predecessor_state.is_complete():
                reasons.append(f"prerequisite lacks reconciled terminal evidence: {predecessor}")
        if state is not None and state.issue_closed and not state.is_complete():
            reasons.append("administratively closed without reconciled completion evidence")

        return TaskReadiness(
            task_id=task_id,
            issue_number=issue_number,
            ready=not reasons,
            complete=False,
            reasons=tuple(reasons),
        )

    def evaluate_task(
        self,
        task_id: str,
        evidence: Iterable[TaskEvidence] = (),
        *,
        satisfied_external_gates: Iterable[str] = (),
        allow_deferred: bool = False,
        allow_unpublished: bool = False,
    ) -> TaskReadiness:
        """Evaluate whether one task is complete, ready, or blocked and explain why."""

        states = self._state_map(evidence)
        gates = frozenset(satisfied_external_gates)
        return self._evaluate_task(
            task_id,
            states,
            gates,
            allow_deferred=allow_deferred,
            allow_unpublished=allow_unpublished,
        )

    def readiness_snapshot(
        self,
        evidence: Iterable[TaskEvidence] = (),
        *,
        satisfied_external_gates: Iterable[str] = (),
        allow_deferred: bool = False,
        allow_unpublished: bool = False,
    ) -> tuple[TaskReadiness, ...]:
        """Return deterministic readiness results in manifest task order."""

        states = self._state_map(evidence)
        gates = frozenset(satisfied_external_gates)
        return tuple(
            self._evaluate_task(
                task.id,
                states,
                gates,
                allow_deferred=allow_deferred,
                allow_unpublished=allow_unpublished,
            )
            for task in self.manifest.tasks
        )

    def metaissue_completion(
        self,
        metaissue_id: str,
        evidence: Iterable[TaskEvidence] = (),
        *,
        review_reconciled: bool = False,
    ) -> MetaissueCompletion:
        """Require reconciled terminal child evidence plus metaissue-level review."""

        try:
            metaissue = self._metaissues[metaissue_id]
        except KeyError as exc:
            raise WorkflowError(f"unknown metaissue ID: {metaissue_id}") from exc
        states = self._state_map(evidence)
        incomplete = tuple(
            child_id
            for child_id in metaissue.children
            if child_id not in states or not states[child_id].is_complete()
        )
        return MetaissueCompletion(
            metaissue_id=metaissue_id,
            issue_number=self.bindings.metaissues[metaissue_id],
            complete=not incomplete and review_reconciled,
            incomplete_children=incomplete,
            review_reconciled=review_reconciled,
        )


__all__ = [
    "CURRENT_WORKFLOW_SCHEMA_VERSION",
    "CompletionDisposition",
    "IssueBindings",
    "MetaissueCompletion",
    "MetaissueSpec",
    "TaskEvidence",
    "TaskReadiness",
    "WorkflowEngine",
    "WorkflowError",
    "WorkflowManifest",
    "WorkflowTaskSpec",
    "load_issue_bindings",
    "load_workflow_manifest",
    "validate_issue_bindings",
]
