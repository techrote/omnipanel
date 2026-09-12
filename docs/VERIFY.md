# Verification and evidence gates

This file defines planned verification. It does not claim a runtime currently passes these gates.

## Evidence principles

Every meaningful run records source/base identities, task/metaissue ID, master/worker/provider identities, policy/profile, environment, commands or capability calls, exit/outcome, elapsed time, changed-file manifest including untracked files, test results and durable evidence references.

Administrative issue closure, process exit zero, model self-report and UI completion events are not substitutes for evidence.

## Test layers

### Unit/contract

Schemas, state machines, DAG validation, policy inheritance, model identity, tag/rank/maturity storage, safety-state transitions, interface negotiation and resource accounting.

### Deterministic integration

Synthetic Ansible, Interloc, Ohmy, intrallm and execution-provider fixtures. Inject restarts, stale generations, incompatible contracts, partial evidence, cancellation races and provider failures.

### TUI/application

Mouse/keyboard navigation, panel switching, reconnect, filtering, task policy editing and accessibility/readability. UI destruction must not cancel durable jobs.

### Execution integration

Qualified lower-layer adapters only. Verify candidate isolation, resource ceilings, cancellation/salvage, independent evaluator execution and Windows/Linux validation boundaries.

### System acceptance

End-to-end project import -> task contract -> master selection -> candidate execution -> adjudication -> evidence -> user decision, with component-version mismatch and restart/recovery cases.

## Named families

- `T-schema`: task/run/metaissue/model/interface schemas and migration.
- `T-dag`: dependency cycles, readiness and evidence-based completion.
- `T-policy`: task dimensions, profile inheritance, mandatory user decisions and fail-safe defaults.
- `T-model`: structured identity, tags, maturity, rolling windows, quarantine and Verboten enforcement.
- `T-interface`: supported/unsupported component contracts and independent integration failure.
- `T-race`: provisional winner, late superior candidate, cancellation rules, salvage and tie cases.
- `T-diversity`: collect-all semantics, comparison artifacts and no accidental early cancellation.
- `T-adjudication`: public/hidden tests, invariant checks, reviewer topology and evaluator isolation.
- `T-resource`: CPU/RAM reservations, oversubscription prevention, release/rebalance and surplus-compute preemption.
- `T-provider`: provider availability, lifecycle, typed failure and recovery.
- `T-ui`: persistent jobs across UI restart/panel destruction; operator actions are explicit.
- `T-restart`: Omnipanel crash/restart, durable state reconciliation and in-flight ambiguity.
- `T-security`: no credential centralization, no safety-state bypass, no unqualified execution path.
- `T-system`: single, Race and Diversity end-to-end scenarios using synthetic then qualified live components.

## Load-bearing verification policy

- **Tissue:** scoped self-check/contract gate; external review optional.
- **Labware:** containment, reproducibility/evidence and self-check; independent review may be deferred until promotion.
- **Stone:** self-check plus independent implementation review and required integration tests.
- **Steel:** independent implementation review, independent verification review, stronger failure/recovery tests and explicit user adjudication before consequential promotion.

## Negative outcomes

Research/Labware work may complete with a sound no-go or ambiguous result if its contract permits that outcome and retains evidence. Tests that cannot run are `NOT RUN`, never silently `PASS`.

## Release principle

Omnipanel does not claim system integration merely because synthetic adapters pass. Each live component integration is qualified against a pinned contract. A component mismatch disables only the affected integration and must not coerce a best-effort fallback with weaker semantics.
