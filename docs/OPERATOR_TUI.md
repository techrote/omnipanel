# OP-007 operator Textual shell

The first operator shell is one cohesive Textual application backed by `ApplicationServices`. It does not own durable programme state and it does not enable provider execution.

## Interaction map

| Surface | Mouse | Keyboard | Durable source |
|---|---|---|---|
| Overview | `Overview` button | `1` | aggregate service snapshot |
| Tasks | `Tasks` button | `2` | durable `TaskRecord` values |
| Runs | `Runs` button | `3` | durable `RunRecord` values |
| Evidence | `Evidence` button | `4` | durable evidence descriptors |
| Models | `Models` button | `5` | canonical model identities + assessments |
| System | `System` button | `6` | storage schema/path, update buffer and resource summary |
| Close | terminal/window controls | `q` | closes presentation only |

Navigation re-reads the current `ApplicationServices` snapshot. Switching panels therefore cannot make a Textual widget the authoritative copy of programme state, and a second UI instance over the same services sees the same durable data.

## Status and blocker surface

`#status-banner` is always composed above navigation/content. The default message explicitly states that execution is blocked until a qualified provider and policy permit it. `OperatorApp.show_blocker()` replaces that text with a consequential blocker/error and panel changes do not clear it.

The shell intentionally has no execute/stop/merge buttons in OP-007. A UI close action is not a stop-job action.

## Resize behavior

Navigation is inside `HorizontalScroll`; panel content is inside `VerticalScroll`. This keeps all controls/content reachable without requiring a minimum terminal size or spawning separate terminal windows. Headless tests exercise 40×12, 50×14, 80×24 and 120×40 terminals.

Very small terminals may require horizontal scrolling to reach later mouse buttons; numeric keyboard bindings remain available regardless of horizontal scroll position. Long records are plain text and may wrap/scroll rather than using a dense table at this stage.

## CLI lifecycle

`omnipanel status` remains read-only and does not open the state store. `omnipanel tui` now opens `StateStore`, constructs `ApplicationServices`, runs `OperatorApp`, and closes the store when the application exits. Failure to open durable state returns a distinct CLI error instead of silently displaying stale UI state.

The old `BootstrapApp` remains only as the inert packaging/startup smoke fixture used by OP-001 verification; the interactive `tui` command launches `OperatorApp`.

## Test coverage

`tests/test_operator_ui.py` covers mouse navigation, numeric keyboard navigation, service refresh after a durable mutation, blocker persistence, small/large terminal sizes, and reopening UI objects without losing application state. Existing OP-001 bootstrap tests continue to prove that the retained smoke fixture creates no state.
