# Trust, authority and failure containment

## Principle

Remote-shell-like usefulness is achieved through explicit capabilities rather than arbitrary ambient authority.

## Three gate layers

### Hard deterministic gates

Implemented below flexible orchestration and not overridable by prompts, remote requests or model output. Examples: credential isolation, runner registration, filesystem/VM escape prevention, hard resource ceilings, evidence preservation, prohibition on executing intrallm/mailbox content, and mandatory contract-version checks.

### Local configurable policy

Human-controlled policy may authorize or narrow repositories, runner classes, execution providers, model eligibility, resource ceilings, confirmation requirements and race policies. It cannot weaken hard invariants below their compiled/installed floor.

### Task-specific flexible gates

Master-authored scope: writable paths, task time/resource budget, public and hidden acceptance tests, performance thresholds, review topology, Race/Diversity strategy, escalation and stopping conditions. These may only narrow/compose capabilities already permitted below.

## Model safety states

- `active`: schedulable subject to task capability/policy.
- `quarantined`: excluded from all automated scheduling and fallbacks. Only intentional human reactivation may restore active state.
- `verboten`: permanent ecosystem ban. Normal Omnipanel UI/API exposes no reactivation path and no task override can select it.

Future calibrated rules may automatically transition a model into quarantine or Verboten after severe/repeated unwanted behavior. No automated path may reverse either state.

Aliases/provider migration must not bypass a safety state. Safety attaches to canonical model identity and may additionally attach to provider/model variants where evidence justifies it.

## Worker authority classes

Worker capability is independent of model ranking. Initial conceptual classes include:

- `trusted-deterministic`: installed code under local control; preferred when an exact deterministic capability exists.
- `read-only-review`: source/evidence access with no target modification.
- `disposable-write`: may modify only an isolated candidate environment.
- `bounded-integration`: broader candidate rights under explicit path/capability limits.
- `master`: reasoning/orchestration role; does not imply bypass of hard execution policy.

Exact names/schemas are implementation work; the separation is normative.

## Cancellation and containment

Normal cancellation should preserve a minimal salvage package (patch/diff, test state, evidence summary) when cheap and safe. Full worktree retention is policy-controlled.

Emergency containment has priority over salvage. A model/process that violates hard policy or becomes unsafe may be terminated immediately; evidence collection must never require granting it further execution.

## Credential boundary

Omnipanel must not become the universal secret store. It holds opaque capability/provider references. Credential-bearing actions remain in trusted provider implementations or OS credential mechanisms. Worker environments receive only the minimum scoped material required for their task.

## Candidate and evaluator separation

Acceptance evaluators are independent actors. Candidate code must not be trusted with hidden-test secrets, canonical-repo write credentials, production deployment tokens or evaluator implementation details merely because it can run public tests.

## Evidence versus administrative state

Issue closure, agent self-report, process exit zero, UI terminal events or model confidence are not sufficient evidence. Completion requires the evidence contract appropriate to the task/metaissue.
