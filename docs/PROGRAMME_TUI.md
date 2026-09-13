# OP-008 programme/DAG and policy surface

OP-008 extends the OP-007 Textual shell without moving workflow authority or durable execution lifetime into widgets.

## Programme projection

The Tasks panel can render the validated OP-005 `WorkflowEngine` when one is supplied by the application/orchestration layer. Stable OP IDs remain canonical; GitHub issue numbers are presentation metadata. Each task shows dependencies, evidence-aware READY/BLOCKED/COMPLETE state and readiness reasons.

Administrative GitHub closure is intentionally separate from evidence completion. A `TaskEvidence` record with `issue_closed=true` but without reconciled terminal evidence renders as `github=CLOSED evidence=UNPROVEN`; it does not satisfy a dependency.

When no workflow engine is supplied, the panel still renders the durable project/metaissue/task/DAG records from `ApplicationServices`. This keeps the production shell useful without making the UI discover repository files or contact GitHub implicitly.

## Policy editing

The mouse-driven task action strip selects durable tasks and edits a draft of the effective task policy. Controls cycle:

- load-bearing class;
- Single/Race/Diversity strategy and Race policy;
- expected value;
- expected wall time;
- marginal cost.

Any policy change invalidates the previous `UserPolicyDecision`. Applying a policy records a fresh explicit operator decision when OP-002 marks the resulting policy mandatory: Steel, priceless expected value, days expected wall time or paid marginal cost. Load-bearing changes preserve or raise the minimum review topology required by Stone/Steel validation.

`Bulk optional defaults` deliberately skips every mandatory-decision task and reports their stable IDs. It cannot manufacture a user decision for Steel/priceless/days/paid tasks.

Policies persist through the OP-003 store via the OP-004 `ApplicationServices.save_policy()` boundary. Closing/reopening the TUI therefore does not own or erase policy state.

## Authority and scope

The presentation layer may request policy writes through services, but it does not decide workflow readiness, reinterpret issue closure as success, execute providers, satisfy acceptance gates or promote candidates. OP-005 remains the readiness authority; OP-002 validation remains the policy contract.

The optional workflow/evidence inputs are dependency-injected rather than implicitly read from `docs/` or GitHub. A later orchestration layer can supply reconciled workflow state without coupling the distributable TUI to a source checkout.
