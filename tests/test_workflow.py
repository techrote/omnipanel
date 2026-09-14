from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omnipanel.domain.contracts import ExpectedValue, LoadBearing, RunStrategy
from omnipanel.workflow import (
    CompletionDisposition,
    IssueBindings,
    TaskEvidence,
    WorkflowEngine,
    WorkflowError,
    WorkflowManifest,
)

ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "docs" / "workflow.json"
BINDINGS_PATH = ROOT / "docs" / "issue-bindings.json"


def _engine() -> WorkflowEngine:
    return WorkflowEngine.from_paths(MANIFEST_PATH, BINDINGS_PATH)


def _manifest_payload() -> dict[str, object]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _bindings_payload() -> dict[str, object]:
    payload = json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _task(payload: dict[str, object], task_id: str) -> dict[str, object]:
    tasks = payload["tasks"]
    assert isinstance(tasks, list)
    for item in tasks:
        assert isinstance(item, dict)
        if item.get("id") == task_id:
            return item
    raise AssertionError(f"task not found: {task_id}")


def _pass(task_id: str, *, issue_closed: bool = True) -> TaskEvidence:
    return TaskEvidence(
        task_id=task_id,
        issue_closed=issue_closed,
        evidence_reconciled=True,
        disposition=CompletionDisposition.PASS,
    )


def test_checked_in_manifest_and_bindings_load() -> None:
    engine = _engine()
    assert len(engine.manifest.metaissues) == 9
    assert len(engine.manifest.tasks) == 52
    assert engine.issue_for("OP-005") == 14
    assert engine.issue_for("OP-M001") == 1
    assert engine.issue_for("OP-049") == 76
    assert engine.issue_for("OP-052") == 79
    assert engine.issue_for("OP-018") is None
    assert engine.issue_for("OP-047") is None


def test_unknown_or_coerced_workflow_versions_fail() -> None:
    for version in (2, "1", True, 1.0):
        payload = _manifest_payload()
        payload["schema_version"] = version
        with pytest.raises(ValidationError, match="schema_version"):
            WorkflowManifest.model_validate(payload)


def test_duplicate_task_id_fails() -> None:
    payload = _manifest_payload()
    tasks = payload["tasks"]
    assert isinstance(tasks, list)
    tasks.append(copy.deepcopy(tasks[0]))
    with pytest.raises(ValidationError, match="duplicate task IDs"):
        WorkflowManifest.model_validate(payload)


def test_duplicate_metaissue_child_fails() -> None:
    payload = _manifest_payload()
    metaissues = payload["metaissues"]
    assert isinstance(metaissues, list)
    first = metaissues[0]
    assert isinstance(first, dict)
    children = first["children"]
    assert isinstance(children, list)
    children.append(children[0])
    with pytest.raises(ValidationError, match="duplicates"):
        WorkflowManifest.model_validate(payload)


def test_missing_prerequisite_fails() -> None:
    payload = _manifest_payload()
    _task(payload, "OP-003")["deps"] = ["OP-999"]
    with pytest.raises(ValidationError, match="missing prerequisite OP-999"):
        WorkflowManifest.model_validate(payload)


def test_missing_metaissue_child_fails() -> None:
    payload = _manifest_payload()
    metaissues = payload["metaissues"]
    assert isinstance(metaissues, list)
    first = metaissues[0]
    assert isinstance(first, dict)
    children = first["children"]
    assert isinstance(children, list)
    children.append("OP-999")
    with pytest.raises(ValidationError, match="missing child OP-999"):
        WorkflowManifest.model_validate(payload)


def test_dependency_cycle_fails() -> None:
    payload = _manifest_payload()
    _task(payload, "OP-001")["deps"] = ["OP-002"]
    with pytest.raises(ValidationError, match="cycle"):
        WorkflowManifest.model_validate(payload)


def test_task_must_belong_to_exactly_one_metaissue() -> None:
    payload = _manifest_payload()
    metaissues = payload["metaissues"]
    assert isinstance(metaissues, list)
    second = metaissues[1]
    assert isinstance(second, dict)
    children = second["children"]
    assert isinstance(children, list)
    children.append("OP-001")
    with pytest.raises(ValidationError, match="belongs to both"):
        WorkflowManifest.model_validate(payload)


def test_unassigned_task_fails() -> None:
    payload = _manifest_payload()
    metaissues = payload["metaissues"]
    assert isinstance(metaissues, list)
    first = metaissues[0]
    assert isinstance(first, dict)
    children = first["children"]
    assert isinstance(children, list)
    children.remove("OP-001")
    with pytest.raises(ValidationError, match="missing metaissue membership"):
        WorkflowManifest.model_validate(payload)


def test_child_dag_can_cross_sibling_metaissues() -> None:
    engine = _engine()
    op038 = next(task for task in engine.manifest.tasks if task.id == "OP-038")
    parent_ids = {engine.metaissue_for_task(dep).id for dep in op038.deps}
    assert len(parent_ids) >= 5
    assert "OP-M002" in parent_ids
    assert "OP-M007" in parent_ids


def test_policy_defaults_resolve_from_task_and_metaissue() -> None:
    engine = _engine()
    assert engine.resolved_policy_defaults("OP-005").load_bearing is LoadBearing.STONE

    manifest = WorkflowManifest.model_validate(
        {
            "schema_version": 1,
            "programme": "policy-test",
            "generated_on": "2026-09-13",
            "metaissues": [
                {
                    "id": "OP-M100",
                    "title": "Policy parent",
                    "children": ["OP-101"],
                    "policy_defaults": {
                        "load_bearing": "stone",
                        "expected_value": "high",
                        "strategy": "single",
                    },
                }
            ],
            "tasks": [
                {
                    "id": "OP-101",
                    "title": "Inherited policy child",
                    "deps": [],
                    "policy_overrides": {"expected_value": "medium"},
                }
            ],
        }
    )
    bindings = IssueBindings.model_validate(
        {
            "schema_version": 1,
            "recorded_on": "2026-09-13",
            "repository": "techrote/omnipanel",
            "metaissues": {"OP-M100": 100},
            "tasks": {"OP-101": 101},
            "publication_blocks": {},
        }
    )
    inherited = WorkflowEngine(manifest, bindings).resolved_policy_defaults("OP-101")
    assert inherited.load_bearing is LoadBearing.STONE
    assert inherited.expected_value is ExpectedValue.MEDIUM
    assert inherited.strategy is RunStrategy.SINGLE


def test_incompatible_policy_inheritance_fails() -> None:
    with pytest.raises(ValidationError, match="incompatible inherited"):
        WorkflowManifest.model_validate(
            {
                "schema_version": 1,
                "programme": "policy-test",
                "generated_on": "2026-09-13",
                "metaissues": [
                    {
                        "id": "OP-M100",
                        "title": "Policy parent",
                        "children": ["OP-101"],
                        "policy_defaults": {
                            "load_bearing": "stone",
                            "strategy": "race",
                            "race_policy": "ask",
                        },
                    }
                ],
                "tasks": [
                    {
                        "id": "OP-101",
                        "title": "Conflicting child",
                        "deps": [],
                        "policy_overrides": {"strategy": "single"},
                    }
                ],
            }
        )


def test_bindings_must_match_manifest_stable_ids() -> None:
    manifest = WorkflowManifest.model_validate(_manifest_payload())
    payload = _bindings_payload()
    tasks = payload["tasks"]
    assert isinstance(tasks, dict)
    del tasks["OP-005"]
    bindings = IssueBindings.model_validate(payload)
    with pytest.raises(WorkflowError, match="binding drift"):
        WorkflowEngine(manifest, bindings)


def test_binding_issue_numbers_are_unique() -> None:
    payload = _bindings_payload()
    tasks = payload["tasks"]
    assert isinstance(tasks, dict)
    tasks["OP-005"] = tasks["OP-004"]
    with pytest.raises(ValidationError, match="more than one stable ID"):
        IssueBindings.model_validate(payload)


def test_null_bindings_require_exact_publication_block() -> None:
    payload = _bindings_payload()
    blocks = payload["publication_blocks"]
    assert isinstance(blocks, dict)
    del blocks["OP-018"]
    with pytest.raises(ValidationError, match="publication_blocks"):
        IssueBindings.model_validate(payload)


def test_stable_ids_survive_issue_renumbering() -> None:
    manifest = WorkflowManifest.model_validate(_manifest_payload())
    payload = _bindings_payload()
    tasks = payload["tasks"]
    assert isinstance(tasks, dict)
    tasks["OP-005"] = 9999
    bindings = IssueBindings.model_validate(payload)
    engine = WorkflowEngine(manifest, bindings)
    assert engine.issue_for("OP-005") == 9999
    assert next(task for task in engine.manifest.tasks if task.id == "OP-005").id == "OP-005"


def test_closed_without_evidence_does_not_satisfy_readiness() -> None:
    engine = _engine()
    stale_admin_state = TaskEvidence(task_id="OP-002", issue_closed=True)
    result = engine.evaluate_task("OP-003", [stale_admin_state])
    assert not result.ready
    assert not result.complete
    assert any("OP-002" in reason for reason in result.reasons)


def test_reconciled_prerequisite_releases_successor() -> None:
    engine = _engine()
    result = engine.evaluate_task("OP-003", [_pass("OP-002")])
    assert result.ready
    assert not result.complete
    assert result.reasons == ()


def test_completed_task_is_not_reported_ready_again() -> None:
    engine = _engine()
    result = engine.evaluate_task("OP-002", [_pass("OP-002")])
    assert result.complete
    assert not result.ready
    assert "already completes" in result.reasons[0]


def test_external_gate_is_explicit_and_fail_closed() -> None:
    engine = _engine()
    evidence = [_pass("OP-012")]
    blocked = engine.evaluate_task("OP-013", evidence)
    assert not blocked.ready
    assert any("qualified Ansible contract" in reason for reason in blocked.reasons)

    released = engine.evaluate_task(
        "OP-013",
        evidence,
        satisfied_external_gates=["qualified Ansible contract"],
    )
    assert released.ready


def test_unpublished_task_is_not_automatically_ready() -> None:
    engine = _engine()
    evidence = [_pass("OP-017")]
    blocked = engine.evaluate_task("OP-018", evidence)
    assert not blocked.ready
    assert any("no published GitHub issue" in reason for reason in blocked.reasons)

    planning_only = engine.evaluate_task("OP-018", evidence, allow_unpublished=True)
    assert planning_only.ready


def test_explicit_no_go_and_defer_are_terminal_only_with_evidence() -> None:
    with pytest.raises(ValidationError, match="reconciled evidence"):
        TaskEvidence(task_id="OP-002", disposition=CompletionDisposition.NO_GO, note="no-go")
    with pytest.raises(ValidationError, match="explicit note"):
        TaskEvidence(
            task_id="OP-002",
            evidence_reconciled=True,
            disposition=CompletionDisposition.DEFERRED,
        )

    no_go = TaskEvidence(
        task_id="OP-002",
        evidence_reconciled=True,
        disposition=CompletionDisposition.NO_GO,
        note="contract permits a sound negative result",
    )
    assert no_go.is_complete()
    assert _engine().evaluate_task("OP-003", [no_go]).ready


def test_deferred_programme_tasks_are_not_ready_without_explicit_opt_in() -> None:
    engine = _engine()
    evidence = [_pass("OP-004"), _pass("OP-043")]
    blocked = engine.evaluate_task("OP-044", evidence)
    assert not blocked.ready
    assert "explicitly deferred" in blocked.reasons

    opted_in = engine.evaluate_task("OP-044", evidence, allow_deferred=True)
    assert opted_in.ready


def test_metaissue_completion_requires_child_evidence_and_review() -> None:
    engine = _engine()
    children = engine.metaissue_for_task("OP-001").children
    all_pass = [_pass(child) for child in children]

    without_review = engine.metaissue_completion("OP-M001", all_pass)
    assert not without_review.complete
    assert without_review.incomplete_children == ()
    assert not without_review.review_reconciled

    complete = engine.metaissue_completion("OP-M001", all_pass, review_reconciled=True)
    assert complete.complete
    assert complete.incomplete_children == ()


def test_metaissue_issue_closure_does_not_replace_child_evidence() -> None:
    engine = _engine()
    partial = [_pass("OP-001"), TaskEvidence(task_id="OP-002", issue_closed=True)]
    result = engine.metaissue_completion("OP-M001", partial, review_reconciled=True)
    assert not result.complete
    assert "OP-002" in result.incomplete_children
    assert "OP-003" in result.incomplete_children


def test_duplicate_or_unknown_evidence_states_fail() -> None:
    engine = _engine()
    with pytest.raises(WorkflowError, match="duplicate evidence"):
        engine.readiness_snapshot([_pass("OP-001"), _pass("OP-001")])
    with pytest.raises(WorkflowError, match="unknown task"):
        engine.readiness_snapshot([_pass("OP-999")])


def test_readiness_snapshot_is_manifest_ordered() -> None:
    engine = _engine()
    snapshot = engine.readiness_snapshot()
    assert tuple(item.task_id for item in snapshot) == tuple(
        task.id for task in engine.manifest.tasks
    )
    assert snapshot[0].task_id == "OP-001"
    assert snapshot[0].ready
