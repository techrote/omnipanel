# OP-008 independent implementation review

Reviewed implementation head: `169fd55e8f24e04ccdaab9b67e15bbde8641c4e9`
Verified base: `main` at `7e4cfe938a220b4cc7f5576115baedade61e805c`
Verified GitHub pull-request merge ref: `9d554bd749df3d87c1fa19366d7b0cc07d06792b`
Foundation CI run: `34787399466` (**PASS**)
Review result: **PASS pending final doc-only head CI**

This was a distinct implementation-review pass over the OP-008 programme/DAG projection, project/metaissue/task navigation, orchestration-policy editor, persistence boundary, bulk defaults and headless Textual coverage.

## Automated verification

Foundation CI passed all six supported matrix lanes:

- Ubuntu / Python 3.12
- Ubuntu / Python 3.13
- Ubuntu / Python 3.14
- Windows / Python 3.12
- Windows / Python 3.13
- Windows / Python 3.14

Each lane passed Ruff lint and formatting, strict source type checking, unit/boundary/headless Textual tests, source/wheel build and clean-wheel installation checks.

The Ubuntu/Python 3.13 lane collected 251 tests and reported **248 passed, 3 skipped**. The three skips are the established native-Windows path-semantics cases and are covered by the Windows lanes.

## Review findings

- Stable OP task IDs remain canonical while GitHub issue numbers are presentation metadata only.
- Readiness comes from an injected OP-005 `WorkflowEngine`; widgets do not duplicate or supersede workflow authority.
- Administrative GitHub closure remains explicitly distinct from evidence completion: closed-but-unproven tasks render as `github=CLOSED evidence=UNPROVEN` and remain blocked.
- Project, metaissue and task scopes have explicit mouse-driven previous/next traversal, with the stable selected IDs visible in the panel.
- Policy editing covers load-bearing class, Single/Race/Diversity strategy, Race policy and expected value/wall-time/marginal-cost dimensions.
- Any real policy mutation invalidates a stale `UserPolicyDecision`.
- Applying a mandatory Steel/priceless/days/paid policy records a fresh explicit operator decision through the service boundary.
- Load-bearing edits preserve or raise the minimum Stone/Steel review topology required by OP-002 validation.
- Policies persist through `ApplicationServices.save_policy()` and the OP-003 store rather than being owned by widget lifetime.
- The bulk-default path cannot manufacture or bypass mandatory user decisions.
- A 250-task synthetic durable DAG keeps stable IDs visible and exercises the scroll-friendly projection.
- The shell still has no provider execution, acceptance-gate completion or promotion authority.

## Defects found and reconciled during review

### Mandatory persisted policy could be reset by bulk defaults

The first bulk-default implementation classified tasks using only immutable `TaskRecord.policy`. If an otherwise optional task had a persisted override that became Steel/priceless/days/paid, the bulk action could silently restore its optional baseline and thereby cross a mandatory-decision boundary.

The reconciled implementation evaluates both the effective persisted policy and the baseline target policy. If either requires an explicit user decision, that task is excluded from bulk writes and reported by stable task ID. An adversarial regression covers a persisted Steel override.

### Project/metaissue hierarchy was display-only

The first implementation rendered project/metaissue groupings but exposed only task-by-task traversal. That did not fully satisfy the issue requirement to build project and metaissue navigation.

The reconciled UI adds explicit previous/next project and metaissue controls. Traversal moves selection to a durable task in the adjacent stable scope and displays the selected `project_id`, `parent_metaissue_id` and `task_id`. A headless interaction test crosses two metaissues and then a project boundary.

No further material defect was found after those corrections.

## Independence note

This review was performed as a separate review pass/context from implementation. It is not represented as a second human reviewer, and no independent human sign-off is claimed.

The only change after the reviewed implementation head is this evidence document. Final merge therefore remains gated on the resulting documentation-only head passing the PR CI matrix.
