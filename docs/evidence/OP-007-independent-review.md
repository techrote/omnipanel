# OP-007 independent implementation review

Reviewed implementation: `852fc1cd0c16e61fdcc5f668a90400da615deadc`
Implementation CI: `34784823152`
Result: **PASS pending evidence-head integration CI**

This was a separate Stone implementation-review pass over the service-backed Textual shell, CLI lifecycle, headless interaction tests and terminal-resize contract.

## Review findings

- `OperatorApp` is presentation over `ApplicationServices`; panel changes reconstruct their view from the current durable-service snapshot rather than retaining an authoritative UI copy.
- Overview, Tasks, Runs, Evidence, Models and System are reachable by mouse buttons and numeric keyboard fallbacks. `q` closes presentation only.
- The blocker/status banner is composed outside panel content and remains visible across navigation. OP-007 deliberately adds no execute, stop, merge or promotion controls.
- `omnipanel status` remains read-only and does not open/create durable state. `omnipanel tui` explicitly owns a `StateStore` context and closes it after the Textual application exits.
- Small terminals use horizontal navigation scrolling plus vertical content scrolling; keyboard navigation remains available when a button is outside the visible horizontal region.
- Reopening Textual application objects over the same services does not destroy or replace durable application state.
- The OP-001 `BootstrapApp` remains only as the inert clean-wheel/startup smoke target; the interactive `tui` command now launches `OperatorApp`.

## First-run findings and fixes

The first OP-007 CI run found no failure in the seven new operator interaction tests. It exposed two compatibility/style issues only:

1. the long-standing CLI help test still required the word `bootstrap`; the parser description was revised to retain that backward-compatible wording while describing the new local operator interface;
2. Ruff requested deterministic formatting changes in the new Textual code.

Both were corrected without changing operator-shell semantics. The reviewed implementation SHA then passed the full Foundation CI matrix.

## Integration note

The implementation CI merge ref was constructed before OP-012 landed on `main`. This review evidence commit intentionally triggers a new PR CI merge ref. OP-007 must not merge unless that evidence-head run passes against the then-current `main`; this prevents the earlier green run from being treated as sufficient cross-branch integration evidence.

## Independence note

This review was performed as a distinct review pass/context rather than by a second human reviewer. That limitation is explicit; no independent human sign-off is claimed.
