"""Textual operator shell plus the retained OP-001 inert bootstrap proof."""

from __future__ import annotations

from datetime import UTC, datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omnipanel import __version__
from omnipanel.config import AppConfig
from omnipanel.domain.contracts import TaskPolicy
from omnipanel.programme import (
    PolicyField,
    build_bulk_optional_policy_plan,
    confirm_policy,
    cycle_policy,
    effective_policy,
    render_programme,
)
from omnipanel.services import ApplicationServices, ApplicationSnapshot
from omnipanel.storage import StateError
from omnipanel.workflow import TaskEvidence, WorkflowEngine


class OperatorApp(App[None]):
    """Mouse-first presentation over UI-independent application services."""

    TITLE = "Omnipanel"
    SUB_TITLE = "Operator shell"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("1", "overview", "Overview"),
        Binding("2", "tasks", "Tasks"),
        Binding("3", "runs", "Runs"),
        Binding("4", "evidence", "Evidence"),
        Binding("5", "models", "Models"),
        Binding("6", "system", "System"),
        Binding("q", "quit", "Close"),
    ]
    CSS = """
    Screen { layout: vertical; }
    #status-banner { height: auto; min-height: 1; padding: 0 1; }
    #navigation { height: 3; padding: 0 1; }
    #navigation Button { min-width: 12; margin-right: 1; }
    #task-actions { height: 3; padding: 0 1; display: none; }
    #task-actions Button { min-width: 12; margin-right: 1; }
    #operator-content { height: 1fr; padding: 1 2; }
    #panel-title { text-style: bold; margin-bottom: 1; }
    #panel-body { width: 100%; height: auto; }
    """

    _PANEL_LABELS = {
        "overview": "Overview",
        "tasks": "Tasks",
        "runs": "Runs",
        "evidence": "Evidence",
        "models": "Models",
        "system": "System",
    }

    def __init__(
        self,
        config: AppConfig,
        services: ApplicationServices,
        *,
        workflow: WorkflowEngine | None = None,
        task_evidence: tuple[TaskEvidence, ...] = (),
    ) -> None:
        super().__init__()
        self.config = config
        self.services = services
        self.workflow = workflow
        self.task_evidence = task_evidence
        self._panel = "overview"
        self._status = (
            "BLOCKER: execution disabled until a qualified provider and policy permit it."
        )
        self._selected_task_id: str | None = None
        self._draft_policy: TaskPolicy | None = None
        self._draft_task_id: str | None = None
        self._policy_notice: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._status, id="status-banner", markup=False)
        with HorizontalScroll(id="navigation"):
            for panel, label in self._PANEL_LABELS.items():
                yield Button(label, id=f"nav-{panel}")
        with HorizontalScroll(id="task-actions"):
            yield Button("Prev project", id="project-prev")
            yield Button("Next project", id="project-next")
            yield Button("Prev metaissue", id="metaissue-prev")
            yield Button("Next metaissue", id="metaissue-next")
            yield Button("Prev task", id="task-prev")
            yield Button("Next task", id="task-next")
            yield Button("Load bearing", id="policy-load-bearing")
            yield Button("Strategy", id="policy-strategy")
            yield Button("Race policy", id="policy-race-policy")
            yield Button("Value", id="policy-expected-value")
            yield Button("Time", id="policy-expected-wall-time")
            yield Button("Cost", id="policy-marginal-cost")
            yield Button("Apply policy", id="policy-apply")
            yield Button("Bulk optional defaults", id="policy-bulk-defaults")
        with VerticalScroll(id="operator-content"):
            yield Static("Overview", id="panel-title", markup=False)
            yield Static("Loading durable state…", id="panel-body", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._show_panel("overview")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("nav-"):
            panel = button_id.removeprefix("nav-")
            if panel in self._PANEL_LABELS:
                self._show_panel(panel)
            return
        if button_id == "project-prev":
            self._move_project(-1)
            return
        if button_id == "project-next":
            self._move_project(1)
            return
        if button_id == "metaissue-prev":
            self._move_metaissue(-1)
            return
        if button_id == "metaissue-next":
            self._move_metaissue(1)
            return
        if button_id == "task-prev":
            self._move_task(-1)
            return
        if button_id == "task-next":
            self._move_task(1)
            return
        if button_id.startswith("policy-"):
            action = button_id.removeprefix("policy-")
            if action == "apply":
                self._apply_policy()
            elif action == "bulk-defaults":
                self._bulk_optional_defaults()
            else:
                self._cycle_policy(action)

    def action_overview(self) -> None:
        self._show_panel("overview")

    def action_tasks(self) -> None:
        self._show_panel("tasks")

    def action_runs(self) -> None:
        self._show_panel("runs")

    def action_evidence(self) -> None:
        self._show_panel("evidence")

    def action_models(self) -> None:
        self._show_panel("models")

    def action_system(self) -> None:
        self._show_panel("system")

    def show_blocker(self, message: str) -> None:
        """Keep a consequential blocker/error visible across panel changes."""

        self._status = f"BLOCKER: {message}"
        self.query_one("#status-banner", Static).update(self._status)

    def _snapshot(self) -> ApplicationSnapshot | None:
        try:
            return self.services.snapshot()
        except StateError as exc:
            self.show_blocker(str(exc))
            self.query_one("#panel-body", Static).update("Durable state is unavailable.")
            return None

    def _show_panel(self, panel: str) -> None:
        if panel not in self._PANEL_LABELS:
            return
        self._panel = panel
        self.query_one("#task-actions", HorizontalScroll).display = panel == "tasks"
        self.query_one("#panel-title", Static).update(self._PANEL_LABELS[panel])
        snapshot = self._snapshot()
        if snapshot is None:
            return
        if panel == "tasks":
            self._ensure_selected_task(snapshot)
        self.query_one("#panel-body", Static).update(self._render_panel(panel, snapshot))

    def _ensure_selected_task(self, snapshot: ApplicationSnapshot) -> None:
        task_ids = tuple(task.task_id for task in snapshot.tasks)
        if not task_ids:
            self._selected_task_id = None
            self._draft_policy = None
            self._draft_task_id = None
            return
        if self._selected_task_id not in task_ids:
            self._selected_task_id = task_ids[0]
            self._draft_policy = None
            self._draft_task_id = None

    def _select_task(self, task_id: str, *, notice: str | None = None) -> None:
        self._selected_task_id = task_id
        self._draft_policy = None
        self._draft_task_id = None
        self._policy_notice = notice
        self._show_panel("tasks")

    def _move_project(self, delta: int) -> None:
        snapshot = self._snapshot()
        if snapshot is None or not snapshot.tasks:
            return
        self._ensure_selected_task(snapshot)
        assert self._selected_task_id is not None
        selected = next(task for task in snapshot.tasks if task.task_id == self._selected_task_id)
        project_ids = tuple(dict.fromkeys(task.project_id for task in snapshot.tasks))
        index = project_ids.index(selected.project_id)
        target_project = project_ids[(index + delta) % len(project_ids)]
        target_task = next(task for task in snapshot.tasks if task.project_id == target_project)
        self._select_task(target_task.task_id, notice=f"Project scope: {target_project}")

    def _move_metaissue(self, delta: int) -> None:
        snapshot = self._snapshot()
        if snapshot is None or not snapshot.tasks:
            return
        self._ensure_selected_task(snapshot)
        assert self._selected_task_id is not None
        selected = next(task for task in snapshot.tasks if task.task_id == self._selected_task_id)
        metaissue_ids = tuple(
            dict.fromkeys(
                task.parent_metaissue_id
                for task in snapshot.tasks
                if task.parent_metaissue_id is not None
            )
        )
        if not metaissue_ids:
            return
        current = selected.parent_metaissue_id
        if current is None or current not in metaissue_ids:
            target_metaissue = metaissue_ids[0 if delta > 0 else -1]
        else:
            index = metaissue_ids.index(current)
            target_metaissue = metaissue_ids[(index + delta) % len(metaissue_ids)]
        target_task = next(
            task for task in snapshot.tasks if task.parent_metaissue_id == target_metaissue
        )
        self._select_task(target_task.task_id, notice=f"Metaissue scope: {target_metaissue}")

    def _move_task(self, delta: int) -> None:
        snapshot = self._snapshot()
        if snapshot is None or not snapshot.tasks:
            return
        self._ensure_selected_task(snapshot)
        task_ids = tuple(task.task_id for task in snapshot.tasks)
        assert self._selected_task_id is not None
        index = task_ids.index(self._selected_task_id)
        self._select_task(task_ids[(index + delta) % len(task_ids)])

    def _selected_policy(self, snapshot: ApplicationSnapshot) -> TaskPolicy | None:
        self._ensure_selected_task(snapshot)
        if self._selected_task_id is None:
            return None
        task = next(task for task in snapshot.tasks if task.task_id == self._selected_task_id)
        if self._draft_task_id == task.task_id and self._draft_policy is not None:
            return self._draft_policy
        policy = effective_policy(snapshot, task)
        self._draft_policy = policy
        self._draft_task_id = task.task_id
        return policy

    def _cycle_policy(self, field: str) -> None:
        snapshot = self._snapshot()
        if snapshot is None:
            return
        policy = self._selected_policy(snapshot)
        if policy is None:
            return
        allowed: tuple[PolicyField, ...] = (
            "load-bearing",
            "strategy",
            "race-policy",
            "expected-value",
            "expected-wall-time",
            "marginal-cost",
        )
        if field not in allowed:
            return
        updated = cycle_policy(policy, field)
        self._draft_policy = updated
        self._policy_notice = "Draft changed; Apply policy persists it."
        self._show_panel("tasks")

    def _apply_policy(self) -> None:
        snapshot = self._snapshot()
        if snapshot is None:
            return
        policy = self._selected_policy(snapshot)
        if policy is None or self._selected_task_id is None:
            return
        confirmed = confirm_policy(
            self._selected_task_id,
            policy,
            confirmed_by="human:operator",
            confirmed_at=datetime.now(UTC),
        )
        self.services.save_policy(self._selected_task_id, confirmed)
        self._draft_policy = confirmed
        self._draft_task_id = self._selected_task_id
        self._policy_notice = (
            "Policy persisted; mandatory choice recorded explicitly where required."
        )
        self._show_panel("tasks")

    def _bulk_optional_defaults(self) -> None:
        snapshot = self._snapshot()
        if snapshot is None:
            return
        plan = build_bulk_optional_policy_plan(snapshot)
        for task_id, policy in plan.updates:
            self.services.save_policy(task_id, policy)
        blocked = ",".join(plan.mandatory_task_ids) or "none"
        self._policy_notice = (
            f"Bulk defaults saved for {len(plan.updates)} optional task(s); "
            f"mandatory decisions skipped: {blocked}."
        )
        self._draft_policy = None
        self._draft_task_id = None
        self._show_panel("tasks")

    def _render_panel(self, panel: str, snapshot: ApplicationSnapshot) -> str:
        if panel == "overview":
            return (
                f"Projects: {len(snapshot.projects)}\n"
                f"Tasks: {len(snapshot.tasks)}\n"
                f"Runs: {len(snapshot.runs)}\n"
                f"Evidence: {len(snapshot.evidence)}\n"
                f"Models: {len(snapshot.model_identities)} identities / "
                f"{len(snapshot.models)} assessments\n"
                f"State: {self.config.data_dir}"
            )
        if panel == "tasks":
            draft = self._selected_policy(snapshot)
            body = render_programme(
                snapshot,
                workflow=self.workflow,
                evidence=self.task_evidence,
                selected_task_id=self._selected_task_id,
                draft_policy=draft,
                notice=self._policy_notice,
            )
            selected = next(
                (task for task in snapshot.tasks if task.task_id == self._selected_task_id),
                None,
            )
            if selected is None:
                return body
            return (
                f"Scope: project={selected.project_id} "
                f"metaissue={selected.parent_metaissue_id or '-'} task={selected.task_id}\n"
                f"{body}"
            )
        if panel == "runs":
            if not snapshot.runs:
                return "No durable runs."
            return "\n".join(
                f"{run.run_id}  {run.status.value}  task={run.task_id}" for run in snapshot.runs
            )
        if panel == "evidence":
            if not snapshot.evidence:
                return "No durable evidence records."
            return "\n".join(
                f"{item.evidence_id}  {item.kind.value}  {item.location}"
                for item in snapshot.evidence
            )
        if panel == "models":
            if not snapshot.model_identities and not snapshot.models:
                return "No durable model records."
            identities = [
                f"{item.ref.provider_id}/{item.ref.model_id}  {item.display_name}"
                for item in snapshot.model_identities
            ]
            assessments = [
                f"{item.model.provider_id}/{item.model.model_id}  safety={item.safety_state.value}"
                for item in snapshot.models
            ]
            return (
                "Identities\n"
                + "\n".join(identities or ["(none)"])
                + ("\n\nAssessments\n" + "\n".join(assessments or ["(none)"]))
            )
        return (
            f"Durable DB: {self.services.store.paths.database}\n"
            f"Schema generation: {self.services.store.schema_version}\n"
            f"Update buffer: {self.services.updates.capacity}\n"
            f"Reservations: {snapshot.resources.total}\n"
            f"Indeterminate reservations: {snapshot.resources.indeterminate}\n"
            "Provider execution: disabled by this shell"
        )


class BootstrapApp(App[None]):
    """Retained inert startup proof used by packaging/smoke verification."""

    TITLE = "Omnipanel"
    SUB_TITLE = "OP-001 | Bootstrap only"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("q", "quit", "Close dashboard")]
    CSS = """
    #content { padding: 1 2; }
    #summary { margin-bottom: 1; }
    #settings { margin-bottom: 1; }
    #close-dashboard { dock: bottom; margin: 0 2 1 2; }
    """

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="content"):
            yield Static(
                f"Omnipanel {__version__}\n\n"
                "Python foundation is installed.\n"
                "Execution is disabled. No providers or credentials are loaded.",
                id="summary",
                markup=False,
            )
            yield Static(
                f"State path (not created): {self.config.data_dir}\n"
                f"Configured log level: {self.config.log_level.value}",
                id="settings",
                markup=False,
            )
            yield Static(
                "This is a startup proof retained for package verification.\n"
                "Close dashboard closes only this view; it is not a stop-job action.",
                markup=False,
            )
        yield Button("Close dashboard", id="close-dashboard")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-dashboard":
            self.exit()