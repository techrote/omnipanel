"""Programme/DAG projection and safe policy-edit helpers for OP-008."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from omnipanel.domain.contracts import (
    EconomicDimensions,
    ExpectedValue,
    ExpectedWallTime,
    LoadBearing,
    MarginalCost,
    RacePolicy,
    ReviewPolicy,
    RunStrategy,
    TaskPolicy,
    TaskRecord,
    UserPolicyDecision,
)
from omnipanel.services import ApplicationSnapshot
from omnipanel.workflow import TaskEvidence, WorkflowEngine

PolicyField = Literal[
    "load-bearing",
    "strategy",
    "race-policy",
    "expected-value",
    "expected-wall-time",
    "marginal-cost",
]

_LOAD_BEARING_ORDER = (
    LoadBearing.TISSUE,
    LoadBearing.LABWARE,
    LoadBearing.STONE,
    LoadBearing.STEEL,
)
_STRATEGY_ORDER = (RunStrategy.SINGLE, RunStrategy.RACE, RunStrategy.DIVERSITY)
_RACE_POLICY_ORDER = (
    RacePolicy.ASK,
    RacePolicy.FIRST_VALID_FREE,
    RacePolicy.FIRST_VALID_ALL,
    RacePolicy.COLLECT_ALL,
    RacePolicy.COST_CONSCIOUS,
)
_VALUE_ORDER = (
    ExpectedValue.NONE,
    ExpectedValue.LOW,
    ExpectedValue.MEDIUM,
    ExpectedValue.HIGH,
    ExpectedValue.PRICELESS,
)
_TIME_ORDER = (
    ExpectedWallTime.INSTANT,
    ExpectedWallTime.SHORT,
    ExpectedWallTime.MEDIUM,
    ExpectedWallTime.LONG,
    ExpectedWallTime.DAYS,
)
_COST_ORDER = (
    MarginalCost.FREE,
    MarginalCost.LOCAL,
    MarginalCost.LOW,
    MarginalCost.QUOTA,
    MarginalCost.PAID,
)


@dataclass(frozen=True, slots=True)
class BulkPolicyPlan:
    """Bulk-default plan that deliberately excludes mandatory-decision tasks."""

    updates: tuple[tuple[str, TaskPolicy], ...]
    mandatory_task_ids: tuple[str, ...]


def _next[T](value: T, values: tuple[T, ...]) -> T:
    return values[(values.index(value) + 1) % len(values)]


def _validated_policy(policy: TaskPolicy, **updates: object) -> TaskPolicy:
    payload = policy.model_dump(mode="python")
    payload.update(updates)
    return TaskPolicy.model_validate(payload)


def _review_for_load_bearing(review: ReviewPolicy, target: LoadBearing) -> ReviewPolicy:
    payload = review.model_dump(mode="python")
    if target in {LoadBearing.STONE, LoadBearing.STEEL}:
        payload["independent_implementation_reviews"] = max(
            1, review.independent_implementation_reviews
        )
    if target is LoadBearing.STEEL:
        payload["independent_verification_reviews"] = max(
            1, review.independent_verification_reviews
        )
        payload["consequential_promotion_requires_user"] = True
    return ReviewPolicy.model_validate(payload)


def cycle_policy(policy: TaskPolicy, field: PolicyField) -> TaskPolicy:
    """Return one validated draft change and invalidate any stale human decision."""

    if field == "load-bearing":
        target = _next(policy.load_bearing, _LOAD_BEARING_ORDER)
        return _validated_policy(
            policy,
            load_bearing=target,
            review=_review_for_load_bearing(policy.review, target),
            user_decision=None,
        )
    if field == "strategy":
        target_strategy = _next(policy.strategy, _STRATEGY_ORDER)
        race_policy = (
            policy.race_policy or RacePolicy.ASK if target_strategy is RunStrategy.RACE else None
        )
        return _validated_policy(
            policy,
            strategy=target_strategy,
            race_policy=race_policy,
            user_decision=None,
        )
    if field == "race-policy":
        if policy.strategy is not RunStrategy.RACE:
            return policy
        current = policy.race_policy or RacePolicy.ASK
        return _validated_policy(
            policy,
            race_policy=_next(current, _RACE_POLICY_ORDER),
            user_decision=None,
        )

    economics = policy.economics
    if field == "expected-value":
        economics = EconomicDimensions(
            expected_value=_next(economics.expected_value, _VALUE_ORDER),
            expected_wall_time=economics.expected_wall_time,
            marginal_cost=economics.marginal_cost,
        )
    elif field == "expected-wall-time":
        economics = EconomicDimensions(
            expected_value=economics.expected_value,
            expected_wall_time=_next(economics.expected_wall_time, _TIME_ORDER),
            marginal_cost=economics.marginal_cost,
        )
    else:
        economics = EconomicDimensions(
            expected_value=economics.expected_value,
            expected_wall_time=economics.expected_wall_time,
            marginal_cost=_next(economics.marginal_cost, _COST_ORDER),
        )
    return _validated_policy(policy, economics=economics, user_decision=None)


def confirm_policy(
    task_id: str,
    policy: TaskPolicy,
    *,
    confirmed_by: str,
    confirmed_at: datetime,
) -> TaskPolicy:
    """Record the explicit operator decision required by consequential/economic policy."""

    decision: UserPolicyDecision | None = None
    if policy.requires_explicit_user_decision():
        decision = UserPolicyDecision(
            decision_id=f"ui-{task_id.lower()}-{int(confirmed_at.timestamp())}",
            confirmed_by=confirmed_by,
            confirmed_at=confirmed_at,
            note="Policy confirmed in the OP-008 operator surface",
        )
    return _validated_policy(policy, user_decision=decision)


def effective_policy(snapshot: ApplicationSnapshot, task: TaskRecord) -> TaskPolicy:
    """Resolve a durable policy override over the immutable task snapshot."""

    for view in snapshot.policies:
        if view.task_id == task.task_id:
            return view.policy
    return task.policy


def build_bulk_optional_policy_plan(snapshot: ApplicationSnapshot) -> BulkPolicyPlan:
    """Apply defaults only where OP-002 says an explicit user decision is unnecessary."""

    updates: list[tuple[str, TaskPolicy]] = []
    mandatory: list[str] = []
    for task in snapshot.tasks:
        if task.policy.requires_explicit_user_decision():
            mandatory.append(task.task_id)
        else:
            updates.append((task.task_id, _validated_policy(task.policy, user_decision=None)))
    return BulkPolicyPlan(updates=tuple(updates), mandatory_task_ids=tuple(mandatory))


def _policy_summary(policy: TaskPolicy) -> str:
    decision = "decided" if policy.is_execution_policy_decided() else "USER DECISION REQUIRED"
    race = f"/{policy.race_policy.value}" if policy.race_policy is not None else ""
    return (
        f"load={policy.load_bearing.value} strategy={policy.strategy.value}{race} "
        f"value={policy.economics.expected_value.value} "
        f"time={policy.economics.expected_wall_time.value} "
        f"cost={policy.economics.marginal_cost.value} decision={decision}"
    )


def _workflow_lines(workflow: WorkflowEngine, evidence: tuple[TaskEvidence, ...]) -> list[str]:
    readiness = {item.task_id: item for item in workflow.readiness_snapshot(evidence)}
    evidence_by_id = {item.task_id: item for item in evidence}
    specs = {item.id: item for item in workflow.manifest.tasks}
    lines = [f"Programme: {workflow.manifest.programme}"]
    for metaissue in workflow.manifest.metaissues:
        lines.append(f"\n{metaissue.id}  {metaissue.title}")
        for task_id in metaissue.children:
            spec = specs[task_id]
            state = evidence_by_id.get(task_id)
            ready = readiness[task_id]
            if ready.complete:
                readiness_label = "COMPLETE"
            elif ready.ready:
                readiness_label = "READY"
            else:
                readiness_label = "BLOCKED"
            if state is not None and state.issue_closed and not state.is_complete():
                evidence_label = "github=CLOSED evidence=UNPROVEN"
            elif state is not None and state.is_complete():
                github = "closed" if state.issue_closed else "open-or-unknown"
                evidence_label = f"github={github} evidence={state.disposition.value}"
            else:
                evidence_label = "github=open-or-unknown evidence=unreconciled"
            deps = ",".join(spec.deps) if spec.deps else "-"
            issue = f"#{ready.issue_number}" if ready.issue_number is not None else "unpublished"
            lines.append(f"  {task_id} {issue} [{readiness_label}] deps={deps} | {evidence_label}")
            for reason in ready.reasons:
                lines.append(f"    blocker: {reason}")
    return lines


def _durable_dag_lines(snapshot: ApplicationSnapshot) -> list[str]:
    lines: list[str] = []
    if snapshot.projects:
        lines.append(
            "Projects: "
            + ", ".join(f"{item.project_id} ({item.display_name})" for item in snapshot.projects)
        )
    if snapshot.metaissues:
        lines.append("Metaissues:")
        for item in snapshot.metaissues:
            children = ",".join(item.child_task_ids) if item.child_task_ids else "-"
            lines.append(f"  {item.metaissue_id} {item.display_name} children={children}")
    lines.append("Durable task DAG:")
    for task in snapshot.tasks:
        deps = ",".join(task.prerequisite_task_ids) if task.prerequisite_task_ids else "-"
        lines.append(f"  {task.task_id} {task.display_name} deps={deps}")
    if snapshot.dag_edges:
        lines.append(
            "Edges: "
            + ", ".join(
                f"{edge.predecessor_task_id}->{edge.successor_task_id}"
                for edge in snapshot.dag_edges
            )
        )
    return lines


def render_programme(
    snapshot: ApplicationSnapshot,
    *,
    workflow: WorkflowEngine | None = None,
    evidence: tuple[TaskEvidence, ...] = (),
    selected_task_id: str | None = None,
    draft_policy: TaskPolicy | None = None,
    notice: str | None = None,
) -> str:
    """Render a scroll-friendly stable-ID programme/DAG and policy-edit projection."""

    lines = (
        _workflow_lines(workflow, evidence)
        if workflow is not None
        else _durable_dag_lines(snapshot)
    )
    if not snapshot.tasks:
        lines.append("\nNo durable task policy records.")
        return "\n".join(lines)

    selected = next(
        (task for task in snapshot.tasks if task.task_id == selected_task_id), snapshot.tasks[0]
    )
    policy = (
        draft_policy
        if selected.task_id == selected_task_id and draft_policy is not None
        else effective_policy(snapshot, selected)
    )
    lines.extend(
        [
            "\nPolicy editor",
            f"  selected={selected.task_id} {selected.display_name}",
            f"  parent={selected.parent_metaissue_id or '-'}",
            f"  prerequisites={','.join(selected.prerequisite_task_ids) or '-'}",
            f"  {_policy_summary(policy)}",
            f"  acceptance-gates={','.join(gate.gate_id for gate in selected.acceptance_gates) or '-'}",
        ]
    )
    if notice:
        lines.append(f"  {notice}")
    return "\n".join(lines)


__all__ = [
    "BulkPolicyPlan",
    "PolicyField",
    "build_bulk_optional_policy_plan",
    "confirm_policy",
    "cycle_policy",
    "effective_policy",
    "render_programme",
]
