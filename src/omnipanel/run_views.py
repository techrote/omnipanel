"""Fail-closed run/candidate presentation helpers for OP-009.

The projection deliberately treats durable records and live observations as separate
sources. Durable run/candidate/evidence records survive UI restart; optional observations
supply ephemeral timing/provider/model context. Missing live context is rendered as
unknown or indeterminate rather than inferred from silence or terminal-looking text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from omnipanel.domain.contracts import (
    CandidateRecord,
    EvidenceDescriptorRecord,
    RunRecord,
    RunStatus,
)
from omnipanel.services import ApplicationSnapshot


class RunFreshness(StrEnum):
    LIVE = "live"
    STALE = "stale"
    DISCONNECTED = "disconnected"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class RunObservation:
    """Ephemeral provider/master observation used only to enrich the durable projection."""

    run_id: str
    state: RunFreshness
    observed_at: datetime
    candidate_id: str | None = None
    started_at: datetime | None = None
    last_event_at: datetime | None = None
    provider_id: str | None = None
    model_provider_id: str | None = None
    model_id: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("observed_at", "started_at", "last_event_at"):
            value = getattr(self, field_name)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{field_name} must include a timezone")
        if self.candidate_id is None and (self.model_provider_id is not None or self.model_id is not None):
            raise ValueError("candidate model identity requires candidate_id")
        if (self.model_provider_id is None) != (self.model_id is None):
            raise ValueError("model_provider_id and model_id must be supplied together")


def selected_run_id(snapshot: ApplicationSnapshot, current: str | None) -> str | None:
    ids = tuple(run.run_id for run in snapshot.runs)
    if not ids:
        return None
    return current if current in ids else ids[0]


def selected_candidate_id(
    snapshot: ApplicationSnapshot,
    run_id: str | None,
    current: str | None,
) -> str | None:
    run = next((item for item in snapshot.runs if item.run_id == run_id), None)
    if run is None:
        return None
    return current if current in run.candidate_ids else run.candidate_ids[0]


def _latest_observation(
    observations: tuple[RunObservation, ...],
    run_id: str,
    candidate_id: str | None,
) -> RunObservation | None:
    matches = tuple(
        item
        for item in observations
        if item.run_id == run_id and item.candidate_id == candidate_id
    )
    if not matches:
        return None
    return max(matches, key=lambda item: item.observed_at)


def _format_seconds(seconds: float) -> str:
    whole = max(0, int(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _run_liveness(run: RunRecord, observation: RunObservation | None) -> str:
    if observation is not None:
        return f"[{observation.state.value.upper()}]"
    if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.CONTAINED}:
        return "[HISTORICAL]"
    return "[INDETERMINATE]"


def _selection_text(run: RunRecord) -> str:
    selected = run.selected_candidate_id
    if selected is None:
        return "selection=none"
    if run.status is RunStatus.COMPLETED:
        return f"selection=accepted:{selected}"
    return f"selection=provisional:{selected} NOT-ACCEPTED"


def _review_text(snapshot: ApplicationSnapshot, run: RunRecord) -> str:
    task = next((item for item in snapshot.tasks if item.task_id == run.task_id), None)
    if task is None:
        return "review=requirements-unavailable (task record missing)"
    review = task.policy.review
    return (
        "review="
        f"self-check:{'yes' if review.self_check_required else 'no'} "
        f"implementation:{review.independent_implementation_reviews} "
        f"verification:{review.independent_verification_reviews} "
        f"user-promotion:{'yes' if review.consequential_promotion_requires_user else 'no'}"
    )


def _candidate_line(
    candidate_id: str,
    candidate: CandidateRecord | None,
    observation: RunObservation | None,
    *,
    selected: bool,
) -> str:
    marker = ">" if selected else " "
    if candidate is None:
        status = "indeterminate:no-durable-candidate-record"
        worker = "unknown"
    else:
        status = candidate.status.value
        worker = candidate.candidate.worker_id
    provider = observation.provider_id if observation and observation.provider_id else "unknown"
    if observation and observation.model_provider_id and observation.model_id:
        model = f"{observation.model_provider_id}/{observation.model_id}"
    else:
        model = "unknown"
    freshness = observation.state.value if observation else "indeterminate"
    return (
        f"{marker} {candidate_id}  status={status}  worker={worker}  "
        f"provider={provider}  model={model}  freshness={freshness}"
    )


def _evidence_text(item: EvidenceDescriptorRecord | None, evidence_id: str) -> str:
    if item is None:
        return f"- {evidence_id}: MISSING DESCRIPTOR"
    summary = ""
    if item.test_summary is not None:
        tests = item.test_summary
        summary = (
            f" tests={tests.passed}/{tests.total} pass; "
            f"fail={tests.failed} error={tests.errors} skip={tests.skipped}"
        )
    return f"- {item.evidence_id}: {item.kind.value} {item.location}{summary}"


def _ordered_evidence_ids(run: RunRecord, candidate: CandidateRecord | None) -> tuple[str, ...]:
    ids: list[str] = list(run.evidence_ids)
    if candidate is not None:
        ids.extend(candidate.evidence_ids)
        for gate in candidate.gate_results:
            ids.extend(gate.evidence_ids)
        if candidate.cancellation is not None:
            ids.extend(candidate.cancellation.salvage_evidence_ids)
    return tuple(dict.fromkeys(ids))


def render_run_detail(
    snapshot: ApplicationSnapshot,
    *,
    run_id: str | None = None,
    candidate_id: str | None = None,
    observations: tuple[RunObservation, ...] = (),
) -> str:
    """Render one run with comparable candidates, gates and evidence drill-down."""

    chosen_run_id = selected_run_id(snapshot, run_id)
    if chosen_run_id is None:
        return "No durable runs."
    run = next(item for item in snapshot.runs if item.run_id == chosen_run_id)
    chosen_candidate_id = selected_candidate_id(snapshot, chosen_run_id, candidate_id)
    candidates = {item.candidate.candidate_id: item for item in snapshot.candidates}
    evidence = {item.evidence_id: item for item in snapshot.evidence}
    run_observation = _latest_observation(observations, run.run_id, None)

    lines = [
        f"run={run.run_id}  task={run.task_id}  strategy={run.strategy.value}  "
        f"phase={run.status.value}  {_run_liveness(run, run_observation)}",
        _selection_text(run),
        _review_text(snapshot, run),
    ]
    if run.race_policy is not None:
        lines.append(f"race-policy={run.race_policy.value}")
    if run_observation is None:
        lines.extend(
            (
                "elapsed=unknown; last-event=unknown; live observation unavailable",
                "provider=unknown (not inferred from worker/model identity)",
            )
        )
    else:
        elapsed = (
            _format_seconds((run_observation.observed_at - run_observation.started_at).total_seconds())
            if run_observation.started_at is not None
            else "unknown"
        )
        last_event = (
            run_observation.last_event_at.isoformat()
            if run_observation.last_event_at is not None
            else "unknown"
        )
        provider = run_observation.provider_id or "unknown"
        lines.extend(
            (
                f"elapsed={elapsed}; last-event={last_event}; observed={run_observation.observed_at.isoformat()}",
                f"provider={provider}",
            )
        )
        if run_observation.note:
            lines.append(f"observation-note={run_observation.note}")

    lines.append("\nCandidates")
    for item_id in run.candidate_ids:
        observation = _latest_observation(observations, run.run_id, item_id)
        lines.append(
            _candidate_line(
                item_id,
                candidates.get(item_id),
                observation,
                selected=item_id == chosen_candidate_id,
            )
        )

    if chosen_candidate_id is None:
        return "\n".join(lines)

    selected_candidate = candidates.get(chosen_candidate_id)
    lines.append(f"\nCandidate detail: {chosen_candidate_id}")
    if selected_candidate is None:
        lines.append("state=INDETERMINATE; durable candidate state is missing")
        return "\n".join(lines)

    task = next((item for item in snapshot.tasks if item.task_id == run.task_id), None)
    gates = {item.gate_id: item for item in task.acceptance_gates} if task is not None else {}
    results = {item.gate_id: item for item in selected_candidate.gate_results}
    gate_ids = tuple(dict.fromkeys((*gates.keys(), *results.keys())))
    lines.append("Gates")
    if not gate_ids:
        lines.append("- none recorded")
    for gate_id in gate_ids:
        gate = gates.get(gate_id)
        result = results.get(gate_id)
        gate_type = gate.gate_type.value if gate is not None else "unknown"
        visibility = gate.visibility.value if gate is not None else "unknown"
        outcome = result.outcome.value if result is not None else "UNRECORDED"
        lines.append(
            f"- {gate_id}: type={gate_type} visibility={visibility} outcome={outcome}"
        )

    lines.append("Evidence")
    evidence_ids = _ordered_evidence_ids(run, selected_candidate)
    if not evidence_ids:
        lines.append("- none recorded")
    else:
        lines.extend(_evidence_text(evidence.get(item_id), item_id) for item_id in evidence_ids)
    if selected_candidate.cancellation is not None:
        cancellation = selected_candidate.cancellation
        lines.append(
            "Cancellation: "
            f"kind={cancellation.kind.value} salvage={cancellation.salvage_level.value}"
        )
    return "\n".join(lines)
