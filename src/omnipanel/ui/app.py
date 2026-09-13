"""Textual operator shell plus the retained OP-001 inert bootstrap proof."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omnipanel import __version__
from omnipanel.config import AppConfig
from omnipanel.services import ApplicationServices, ApplicationSnapshot
from omnipanel.storage import StateError


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

    def __init__(self, config: AppConfig, services: ApplicationServices) -> None:
        super().__init__()
        self.config = config
        self.services = services
        self._panel = "overview"
        self._status = (
            "BLOCKER: execution disabled until a qualified provider and policy permit it."
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self._status, id="status-banner", markup=False)
        with HorizontalScroll(id="navigation"):
            for panel, label in self._PANEL_LABELS.items():
                yield Button(label, id=f"nav-{panel}")
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

    def _show_panel(self, panel: str) -> None:
        if panel not in self._PANEL_LABELS:
            return
        self._panel = panel
        self.query_one("#panel-title", Static).update(self._PANEL_LABELS[panel])
        try:
            snapshot = self.services.snapshot()
        except StateError as exc:
            self.show_blocker(str(exc))
            self.query_one("#panel-body", Static).update("Durable state is unavailable.")
            return
        self.query_one("#panel-body", Static).update(self._render_panel(panel, snapshot))

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
            if not snapshot.tasks:
                return "No durable tasks."
            return "\n".join(f"{task.task_id}  {task.display_name}" for task in snapshot.tasks)
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
