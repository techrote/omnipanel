"""Resource-aware operator shell layered over the stable OP-007/OP-009 app."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omnipanel.config import AppConfig
from omnipanel.execution_provider import ExecutionProviderError
from omnipanel.resource_ledger import DurableResourceLedger, ResourceLedgerError
from omnipanel.resource_views import (
    ResourceDashboardObservations,
    render_resource_dashboard,
    selected_provider_id,
    selected_reservation_id,
    selected_resource_task_id,
)
from omnipanel.run_views import RunObservation
from omnipanel.services import ApplicationServices, ApplicationSnapshot
from omnipanel.storage import RecordNotFoundError
from omnipanel.ui.app import OperatorApp
from omnipanel.workflow import TaskEvidence, WorkflowEngine


class ResourceOperatorApp(OperatorApp):
    """OperatorApp with provider/resource projections and service-backed reconciliation."""

    BINDINGS = [
        Binding("1", "overview", "Overview"),
        Binding("2", "tasks", "Tasks"),
        Binding("3", "runs", "Runs"),
        Binding("4", "evidence", "Evidence"),
        Binding("5", "resources", "Resources"),
        Binding("6", "models", "Models"),
        Binding("7", "system", "System"),
        Binding("q", "quit", "Close"),
    ]
    CSS = OperatorApp.CSS + """
    #resource-actions { height: 3; padding: 0 1; display: none; }
    #resource-actions Button { min-width: 13; margin-right: 1; }
    """
    _PANEL_LABELS = {
        "overview": "Overview",
        "tasks": "Tasks",
        "runs": "Runs",
        "evidence": "Evidence",
        "resources": "Resources",
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
        run_observations: tuple[RunObservation, ...] = (),
        resource_ledger: DurableResourceLedger | None = None,
        resource_observations: ResourceDashboardObservations | None = None,
    ) -> None:
        super().__init__(
            config,
            services,
            workflow=workflow,
            task_evidence=task_evidence,
            run_observations=run_observations,
        )
        self.resource_ledger = resource_ledger or DurableResourceLedger(services, {})
        self.resource_observations = resource_observations or ResourceDashboardObservations()
        self._selected_resource_provider_id: str | None = None
        self._selected_resource_reservation_id: str | None = None
        self._selected_resource_task_id: str | None = None
        self._resource_notice: str | None = None

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
        with HorizontalScroll(id="run-actions"):
            yield Button("Prev run", id="run-prev")
            yield Button("Next run", id="run-next")
            yield Button("Prev candidate", id="candidate-prev")
            yield Button("Next candidate", id="candidate-next")
        with HorizontalScroll(id="resource-actions"):
            yield Button("Prev provider", id="resource-provider-prev")
            yield Button("Next provider", id="resource-provider-next")
            yield Button("Prev reservation", id="resource-reservation-prev")
            yield Button("Next reservation", id="resource-reservation-next")
            yield Button("Prev task", id="resource-task-prev")
            yield Button("Next task", id="resource-task-next")
            yield Button("Reconcile", id="resource-reconcile")
            yield Button("Refresh", id="resource-refresh")
        with VerticalScroll(id="operator-content"):
            yield Static("Overview", id="panel-title", markup=False)
            yield Static("Loading durable state…", id="panel-body", markup=False)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        resource_actions = {
            "resource-provider-prev": lambda: self._move_resource_provider(-1),
            "resource-provider-next": lambda: self._move_resource_provider(1),
            "resource-reservation-prev": lambda: self._move_resource_reservation(-1),
            "resource-reservation-next": lambda: self._move_resource_reservation(1),
            "resource-task-prev": lambda: self._move_resource_task(-1),
            "resource-task-next": lambda: self._move_resource_task(1),
            "resource-reconcile": self._reconcile_resource,
            "resource-refresh": self._refresh_resources,
        }
        action = resource_actions.get(button_id)
        if action is not None:
            action()
            return
        super().on_button_pressed(event)

    def action_resources(self) -> None:
        self._show_panel("resources")

    def _show_panel(self, panel: str) -> None:
        super()._show_panel(panel)
        self.query_one("#resource-actions", HorizontalScroll).display = panel == "resources"

    def _render_panel(self, panel: str, snapshot: ApplicationSnapshot) -> str:
        if panel != "resources":
            return super()._render_panel(panel, snapshot)
        try:
            resources = self.resource_ledger.snapshot()
        except (ExecutionProviderError, ResourceLedgerError, RecordNotFoundError) as exc:
            return (
                "Resource dashboard: INDETERMINATE\n"
                f"typed resource error: {exc}\n"
                f"Durable reservations: {snapshot.resources.total}"
            )
        return render_resource_dashboard(
            snapshot,
            resources,
            observations=self.resource_observations,
            selected_provider=self._selected_resource_provider_id,
            selected_reservation=self._selected_resource_reservation_id,
            selected_task=self._selected_resource_task_id,
            notice=self._resource_notice,
        )

    def _resource_snapshot(self):
        return self.resource_ledger.snapshot()

    def _ensure_resource_selection(self, snapshot: ApplicationSnapshot) -> None:
        resources = self._resource_snapshot()
        self._selected_resource_provider_id = selected_provider_id(
            resources,
            self._selected_resource_provider_id,
        )
        self._selected_resource_reservation_id = selected_reservation_id(
            resources,
            self._selected_resource_provider_id,
            self._selected_resource_reservation_id,
        )
        self._selected_resource_task_id = selected_resource_task_id(
            snapshot,
            self._selected_resource_task_id,
        )

    def _move_resource_provider(self, delta: int) -> None:
        snapshot = self._snapshot()
        if snapshot is None:
            return
        resources = self._resource_snapshot()
        provider_ids = tuple(
            item.description.identity.provider_id for item in resources.providers
        )
        if not provider_ids:
            self._resource_notice = "No providers are currently configured."
            self._show_panel("resources")
            return
        current = selected_provider_id(resources, self._selected_resource_provider_id)
        assert current is not None
        index = provider_ids.index(current)
        self._selected_resource_provider_id = provider_ids[(index + delta) % len(provider_ids)]
        self._selected_resource_reservation_id = None
        self._selected_resource_task_id = selected_resource_task_id(
            snapshot,
            self._selected_resource_task_id,
        )
        self._resource_notice = None
        self._show_panel("resources")

    def _move_resource_reservation(self, delta: int) -> None:
        snapshot = self._snapshot()
        if snapshot is None:
            return
        self._ensure_resource_selection(snapshot)
        resources = self._resource_snapshot()
        provider_id = self._selected_resource_provider_id
        if provider_id is None:
            return
        provider = next(
            item
            for item in resources.providers
            if item.description.identity.provider_id == provider_id
        )
        reservation_ids = tuple(item.reservation_id for item in provider.reservations)
        if not reservation_ids:
            self._resource_notice = f"Provider {provider_id} has no durable reservations."
            self._show_panel("resources")
            return
        current = selected_reservation_id(
            resources,
            provider_id,
            self._selected_resource_reservation_id,
        )
        assert current is not None
        index = reservation_ids.index(current)
        self._selected_resource_reservation_id = reservation_ids[
            (index + delta) % len(reservation_ids)
        ]
        self._resource_notice = None
        self._show_panel("resources")

    def _move_resource_task(self, delta: int) -> None:
        snapshot = self._snapshot()
        if snapshot is None or not snapshot.tasks:
            return
        current = selected_resource_task_id(snapshot, self._selected_resource_task_id)
        assert current is not None
        task_ids = tuple(item.task_id for item in snapshot.tasks)
        index = task_ids.index(current)
        self._selected_resource_task_id = task_ids[(index + delta) % len(task_ids)]
        self._resource_notice = None
        self._show_panel("resources")

    def _reconcile_resource(self) -> None:
        snapshot = self._snapshot()
        if snapshot is None:
            return
        try:
            self._ensure_resource_selection(snapshot)
            provider_id = self._selected_resource_provider_id
            reservation_id = self._selected_resource_reservation_id
            if provider_id is None:
                self._resource_notice = "Reconcile not run: no provider selected."
            elif reservation_id is None:
                self._resource_notice = "Reconcile not run: no reservation selected."
            else:
                result = self.resource_ledger.reconcile_reservation(
                    provider_id=provider_id,
                    reservation_id=reservation_id,
                    reconciled_by="human:operator-ui",
                )
                self._resource_notice = (
                    f"Reconcile {result.status.value}: {result.detail} "
                    f"durable={result.durable_state.value}"
                )
        except (ExecutionProviderError, ResourceLedgerError, RecordNotFoundError) as exc:
            self._resource_notice = f"Reconcile blocked: {exc}"
        self._show_panel("resources")

    def _refresh_resources(self) -> None:
        self._resource_notice = "Provider inventory and durable reservations refreshed."
        self._show_panel("resources")


__all__ = ["ResourceOperatorApp"]
