# OP-009 independent implementation review

Reviewed implementation head: `dab1a49bcda0419f24d6297173b29e62d13fd858`
Verified base: `main` at `f44c9ea56f19e0cee329c53cab3e535da43f15fd`
Verified GitHub pull-request merge ref: `7bd7c6c1f909a4ff21f403280f59ba10758a0535`
Foundation CI run: `34795260233` (**PASS**)
Review result: **PASS pending final doc-only head CI**

This was a distinct implementation-review pass over the OP-009 run/candidate projection, durable-versus-live authority boundary, Single/Race/Diversity presentation, provisional/accepted selection semantics, gate/evidence drill-down, reconnect behavior and headless Textual coverage.

## Automated verification

Foundation CI passed all six supported matrix lanes:

- Ubuntu / Python 3.12
- Ubuntu / Python 3.13
- Ubuntu / Python 3.14
- Windows / Python 3.12
- Windows / Python 3.13
- Windows / Python 3.14

Each lane passed Ruff lint and formatting, strict source type checking, unit/boundary/headless Textual tests, source/wheel build and clean-wheel installation checks.

The Ubuntu/Python 3.13 lane collected 269 tests and reported **266 passed, 3 skipped**. The three skips are the established native-Windows path-semantics cases and are covered by the Windows lanes.

## Review findings

- Durable `RunRecord`, `CandidateRecord`, `TaskRecord` and `EvidenceDescriptorRecord` values remain the persisted source of truth; optional `RunObservation` data is presentation-only and cannot mutate adjudication state.
- Active durable runs without a live observation render `INDETERMINATE`; worker silence is never interpreted as success or failure.
- Explicit live observations can state `LIVE`, `STALE`, `DISCONNECTED` or `INDETERMINATE`, plus timing/provider/model context, without manufacturing durable state.
- The current durable schema has no authoritative candidate-to-execution-provider/model mapping, so provider/model identity is never inferred from worker IDs or display names.
- Canonical model identity, when supplied by a live observation, is rendered as the stable `<provider-id>/<model-id>` pair.
- A selected candidate on an active Race remains `provisional ... NOT-ACCEPTED`; selection alone is not represented as acceptance.
- A completed run is represented as accepted only when its selected durable candidate exists, belongs to the same task and is `eligible`; missing, mismatched or non-eligible state fails closed as `ACCEPTANCE-INDETERMINATE`.
- Failed/cancelled/contained terminal runs cannot be presented as provisional or accepted winners merely because a selection ID is recorded.
- Candidate/task identity mismatch is surfaced explicitly and blocks contextual gate/evidence drill-down rather than crossing task provenance boundaries.
- The run header uses the effective persisted OP-008 policy override, when present, for self-check, implementation-review, verification-review and user-promotion requirements.
- Acceptance gates preserve declared type, visibility and required/optional state; missing results render `UNRECORDED`, never PASS.
- Evidence drill-down preserves durable run/candidate/gate/salvage references, locations and test summaries; missing descriptors are explicit rather than silently omitted.
- Cancellation kind and salvage level remain visible for cancelled candidates.
- Closing/reopening the TUI reconstructs durable run/candidate/evidence state while deliberately dropping unpersisted live observations back to an indeterminate presentation.
- Mouse previous/next run and candidate traversal remains presentation-only; the shell gains no provider execution, gate-completion or promotion authority.

## Defects found and reconciled during review

### Completed selection could overstate acceptance

The first projection rendered any `selected_candidate_id` on a completed run as accepted, even if the candidate record was missing or non-eligible.

The reconciled projection requires a matching durable candidate for the same task with `CandidateStatus.ELIGIBLE`. Missing, mismatched and non-eligible candidate states now render `ACCEPTANCE-INDETERMINATE`, with dedicated regressions.

### Reviewer requirements ignored persisted task-policy overrides

The first projection read reviewer requirements only from immutable `TaskRecord.policy`, so an explicit OP-008 persisted override could be hidden from the run view.

The reconciled projection resolves the effective persisted `PolicyView` first and falls back to the task baseline only when no override exists. A regression verifies the overridden implementation/verification/user-promotion requirements.

### Cross-task candidate records were not rejected

The first candidate lookup keyed only by candidate ID. A malformed/corrupt durable snapshot could therefore associate a same-ID candidate from another task with the current run.

The reconciled projection checks candidate task identity before status, selection acceptance, gate or evidence presentation. Task mismatches fail closed as indeterminate.

### Impossible observation timestamps could create plausible-looking timing

The first live-observation type required timezone-aware timestamps but allowed `started_at` or `last_event_at` to be later than `observed_at`.

The reconciled type rejects those temporally impossible inputs instead of clamping or synthesizing credible-looking timing.

### Terminal non-completed selections were labelled provisional

The first selection renderer treated every non-completed run with a selected candidate as provisional, including failed/cancelled/contained runs.

The reconciled renderer reserves `provisional` for planned/queued/running/awaiting-adjudication states. Terminal non-completed selections are explicitly recorded as `NOT-ACCEPTED` with their terminal run status.

### Optional gates were rendered as unknown requirement state

The first gate renderer collapsed `required=False` into `unknown` because it tested truthiness rather than field presence.

The reconciled renderer distinguishes `required=yes`, `required=no` and `required=unknown` only when no gate contract exists. A regression covers an optional review gate.

### Existing Textual policy test had an event-loop race on Windows 3.12

Foundation CI on the reviewed feature branch exposed a pre-existing OP-008 test assumption: after `pilot.click("#policy-apply")`, the test immediately inspected persistence even though the button handler could still be queued. On one Windows/Python 3.12 run the assertion executed before `_apply_policy`, and teardown then removed the widgets while the queued handler was still executing.

The test now performs `await pilot.pause()` after the click, using Textual's test synchronization mechanism to drain pending UI work before asserting durable state. No policy/application semantics changed. The corrected head passed the full six-lane matrix, including Windows/Python 3.12.

No further material defect was found after those corrections.

## Independence note

This review was performed as a separate review pass/context from implementation. It is not represented as a second human reviewer, and no independent human sign-off is claimed.

The only change after the reviewed implementation head is this evidence document. Final merge therefore remains gated on the resulting documentation-only head passing the PR CI matrix.
