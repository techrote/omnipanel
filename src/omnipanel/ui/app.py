"""OP-001 startup proof only. OP-007 owns the later operator application shell."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omnipanel import __version__
from omnipanel.config import AppConfig


class BootstrapApp(App[None]):
    """Show inert startup settings; closing this UI has no execution semantics."""

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
                "This is a startup proof, not the OP-007 operator application.\n"
                "Close dashboard closes only this view; it is not a stop-job action.",
                markup=False,
            )
        yield Button("Close dashboard", id="close-dashboard")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-dashboard":
            self.exit()
