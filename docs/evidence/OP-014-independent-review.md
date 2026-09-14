# OP-014 independent implementation review

Pull request: #69 (`[OP-014] Generic execution provider abstraction`)
Reviewed implementation tree: the first parent of the commit adding this review record on `implement/op-014-execution-provider`
Verified base: `main` at `21bff4906747d1bc39e0fa4ad8857512985c8b8c`
Review result: **PASS after reconciliation**
Promotion state: **NOT PROMOTED — Steel user adjudication remains required**

This was a distinct implementation-review pass over the provider-neutral scheduling boundary, deterministic fake provider, resource accounting, provider identity/provenance, validation-only representation and the separation between provider execution success and Omnipanel adjudication.

## Review findings

- The generic provider contract remains independent of Ubuntu, Windows, Hyper-V and remote-transport scheduler branches. Platform/placement facts are ordinary metadata and capabilities.
- `ProviderIdentity` binds stable provider ID, provider class, implementation version and exact component/interface contract identity.
- Provider-owned isolation, resource, network and filesystem guarantees are explicit. Missing requested guarantees fail closed with typed diagnostics rather than being emulated by Omnipanel.
- CPU, memory, storage and GPU are accounted as fungible capacity in the deterministic fake. `wall_time_seconds` is correctly treated as a per-job ceiling rather than a concurrent capacity pool.
- Provider availability is distinct from capacity. Unavailable/indeterminate providers reject new reservations; degraded providers remain visibly degraded and may accept only otherwise-supported work.
- Execution and validation use one provider abstraction with separate work-purpose semantics, so validation-only providers do not require a parallel scheduler API.
- Provider `SUCCEEDED` means only execution success. No provider API can mint `CandidateStatus.ELIGIBLE`, acceptance-gate PASS, Race victory, run acceptance or promotion authority.
- Provider handles bind provider identity/version plus job, run, task, candidate, purpose and reservation identity. Stale/misrouted handles fail closed.
- Evidence receipts carry provider identity/version/interface contract and run/task/candidate provenance. Attaching provider evidence adds evidence references only; it does not mutate run status or selection.
- Resource reservations remain charged until explicit release. Known terminal execution does not silently free capacity before the scheduler releases it.

## Defects found and reconciled during review

### Indeterminate provider work was initially treated as terminal

The first implementation considered `ProviderCandidateLifecycle.INDETERMINATE` terminal. That would have allowed a reservation to be released while underlying work might still be consuming CPU, memory, storage or GPU capacity.

The reconciled implementation treats indeterminate as an unsettled, fail-closed state. The reservation becomes `ProviderReservationState.INDETERMINATE`, remains charged against inventory and cannot be released. A later observation may reconcile the job to `SUCCEEDED`, `FAILED` or `CANCELLED`; evidence from the indeterminate observation is retained rather than overwritten.

A dedicated regression verifies held capacity, release refusal, later reconciliation, cumulative evidence and eventual release.

### Provider evidence lacked task-bound provenance

The first receipt shape carried run and candidate identity but not task identity. In malformed/misrouted state, a colliding candidate ID could therefore make provenance ambiguous across tasks.

The reconciled `ProviderEvidenceReceipt` includes `task_id`, the fake binds it from the candidate handle, and `attach_provider_evidence()` rejects cross-run, cross-task and cross-candidate receipts explicitly.

A dedicated regression verifies all three provenance boundaries.

### Mechanical formatter findings

A superseded Foundation CI run showed Ruff-format-only differences after the first review correction. The exact mechanical formatter rewrites were applied without semantic change before the reviewed implementation tree was frozen.

## Independence note

This review was performed as a separate review pass/context from implementation. It is not represented as a second human reviewer, and no independent human sign-off is claimed.

Because OP-014 is Steel, this review is necessary but not sufficient for merge. Independent verification, final-head CI and explicit user promotion remain mandatory.
