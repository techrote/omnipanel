# OP-009 run, candidate and adjudication view

## Purpose

The Runs panel is an operator projection over OP-004 durable application state. It does not own execution, infer provider success, or convert UI state into adjudication authority.

The view covers Single, Race and Diversity runs; candidate state; acceptance-gate outcomes; evidence references; review requirements; provisional versus accepted selection; and optional live timing/provider/model observations.

## Authority split

Durable `RunRecord`, `CandidateRecord`, `TaskRecord` and `EvidenceDescriptorRecord` values come from `ApplicationServices.snapshot()` and remain reconstructable after the TUI closes or restarts.

Live timing and connection information is deliberately separate. `RunObservation` is ephemeral presentation input. It can state freshness, observation/start/last-event timestamps, execution-provider identity and canonical model provider/model IDs. It cannot change a run, candidate, gate result or evidence record.

The current durable schema does **not** contain an authoritative candidate-to-execution-provider/model mapping. Therefore the Runs panel never derives an execution provider from a worker ID, model identity or model provider. Missing live context is shown as `unknown`/`INDETERMINATE` until a typed observation is available.

## Liveness and terminal state

For a non-terminal durable run without a matching live observation, the panel displays `[INDETERMINATE]`; worker silence is not treated as success or failure. A supplied observation may explicitly mark the view `LIVE`, `STALE`, `DISCONNECTED` or `INDETERMINATE`.

For a terminal durable run without live context, the panel displays `[HISTORICAL]`. That label only means the durable run has a terminal status. Acceptance is still represented separately through run selection, matching candidate state, gate state and evidence.

Elapsed and last-event fields are shown only when their source timestamps exist. Impossible live timestamps are rejected rather than normalized into plausible-looking timing.

## Provisional and accepted selection

`selected_candidate_id` is not rendered as an accepted winner merely because it exists. Until a run reaches durable `completed` state, a selected candidate is displayed as:

`selection=provisional:<candidate-id> NOT-ACCEPTED`

A completed run is rendered as accepted only when the selected durable candidate record exists, belongs to the same task and is `eligible`. Missing, mismatched or non-eligible candidate state produces `ACCEPTANCE-INDETERMINATE` instead. This is especially important for Race, where an early eligible result may be a provisional winner while sibling work, policy or review/adjudication remains outstanding.

Diversity uses the same durable candidate comparison view without introducing Race-style early-cancel semantics.

## Candidate comparison and evidence drill-down

The candidate list uses stable candidate and worker IDs. When live observations provide model identity, the display uses the canonical `<provider-id>/<model-id>` pair, not a human display name. A candidate record whose task identity does not match the run fails closed as an indeterminate task mismatch.

Selecting a candidate exposes:

- durable candidate status and cancellation/salvage state;
- the task's declared acceptance gates and candidate-recorded outcomes;
- missing gate outcomes as `UNRECORDED`, never PASS;
- run, candidate, gate and salvage evidence references, de-duplicated for display;
- evidence kind, location and test summary where a durable descriptor exists;
- missing evidence descriptors explicitly as `MISSING DESCRIPTOR`.

The run header displays the task's effective durable self-check, implementation-review, verification-review and user-promotion requirements, including a persisted OP-008 task-policy override where one exists. The UI reports those requirements; it does not satisfy them.

## Navigation and reconnect behavior

The Runs panel has mouse controls for previous/next run and previous/next candidate. Keyboard panel navigation remains `3` for Runs.

Closing the TUI does not stop a run. Reopening the application reconstructs durable run/candidate/evidence state through `ApplicationServices`. Ephemeral observations are not invented across a restart; until the live integration supplies fresh observations, active durable runs are visibly indeterminate.

## Fixture/acceptance matrix

| Scenario | Durable state | Live observation | Required presentation |
| --- | --- | --- | --- |
| Active | running | LIVE | live phase and supplied timing/provider context |
| Stale | running | STALE | stale marker; no success inference |
| Disconnected | running | DISCONNECTED | disconnected candidate/run context |
| Indeterminate | running | absent/indeterminate | `INDETERMINATE`, unknown timing/provider |
| Pass/eligible | candidate eligible + PASS gate | optional | recorded PASS plus evidence only |
| Fail/reject | candidate rejected/failed | optional | durable failure/rejection, never hidden by terminality |
| Cancel | candidate cancelled/contained | optional | cancellation and salvage detail |
| Historical completion | completed + matching eligible selected candidate | absent | historical marker and accepted selection |
| Inconsistent completion | completed + missing/mismatched/non-eligible selected candidate | optional | `ACCEPTANCE-INDETERMINATE` |
| Race provisional | running/awaiting adjudication + selected candidate | any | `provisional ... NOT-ACCEPTED` |

`tests/test_run_views.py`, `tests/test_run_view_matrix.py` and `tests/test_run_review_regressions.py` cover projection invariants and the fixture matrix. `tests/test_run_ui.py` covers Textual mouse navigation plus durable close/reopen reconstruction.
