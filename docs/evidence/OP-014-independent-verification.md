# OP-014 independent verification

Pull request: #69 (`[OP-014] Generic execution provider abstraction`)
Verified implementation tree: the implementation tree identified by `OP-014-independent-review.md` (the first parent of that review-record commit)
Verified base: `main` at `21bff4906747d1bc39e0fa4ad8857512985c8b8c`
Verification result: **PASS at implementation scope**
Promotion state: **NOT PROMOTED — final evidence-head CI and explicit Steel user adjudication remain required**

This was a distinct verification pass against OP-014/#23 acceptance criteria and failure boundaries. The focus was whether the abstraction can produce false certainty about capacity, provenance, provider capability or adjudication.

## Acceptance-criteria verification

| #23 requirement | Verification evidence | Result |
| --- | --- | --- |
| Fake provider passes lifecycle tests | `tests/test_execution_provider.py` covers reserve/start/observe/terminal/cancel/release and deterministic repeated operation sequences | PASS |
| Fake provider passes resource tests | capacity subtraction/restoration, overcommit rejection and wall-time-ceiling semantics are covered | PASS |
| Fake provider passes error-handling tests | typed failures cover provider availability, class/capability mismatch, purpose mismatch, missing enforcement guarantees, reservation/candidate state and handle identity | PASS |
| Unsupported capabilities fail explicitly | missing capability handles are returned in `ProviderDiagnostic`; no silent fallback path exists | PASS |
| Provider identity/provenance is attached to run evidence | receipts contain full provider identity/version/interface plus run/task/candidate identity; `attach_provider_evidence()` preserves run adjudication fields | PASS |
| Local/virtualized/future-remote distinctions do not leak into scheduler architecture | `tests/fixtures/op014_provider_matrix.json` represents development, validation-only and remote-shaped providers through one API; source guard rejects reference-platform scheduler terms | PASS |
| Validation-only providers are representable | one provider description supports only `validation`; execution is rejected with `PURPOSE_UNSUPPORTED` and validation starts normally | PASS |

## Failure-injection verification

### Capacity uncertainty fails closed

An execution observation may become `INDETERMINATE`. Verification confirms that this does not free capacity or become a terminal success/failure surrogate:

- the associated reservation becomes `INDETERMINATE`;
- CPU/memory/storage/GPU allocation remains charged;
- `release()` fails while the job is unsettled;
- later reconciliation to a known settled lifecycle is permitted;
- evidence from both the uncertain and reconciled observations remains available.

This prevents scheduler overcommit after a provider/control-plane ambiguity.

### Capability and enforcement uncertainty fails closed

Verification exercises providers that lack each hard guarantee independently. A request requiring isolation, network-policy enforcement, filesystem-policy enforcement or resource-limit enforcement is rejected with a typed provider-neutral failure. Omnipanel does not simulate those guarantees above the provider boundary.

Unsupported capability handles and explicit provider-class mismatches are also rejected rather than relaxed to a nearby provider shape.

### Provenance boundaries fail closed

Verification confirms:

- a provider receipt's `EvidenceDescriptorRecord` must identify the same provider ID as the receipt;
- stale/misrouted handles with a different provider implementation identity are rejected;
- unknown provider jobs are rejected;
- evidence attachment rejects a different run ID;
- evidence attachment rejects a different task ID;
- evidence attachment rejects a candidate ID outside the durable run.

Provider implementation version and exact interface-contract reference remain part of the receipt's full provider identity.

### Execution success cannot become adjudication success

The provider module has no candidate-eligibility/adjudication API. Verification exercises provider `SUCCEEDED`, attaches its provider evidence to a still-running durable `RunRecord`, and confirms that:

- run status remains unchanged;
- selected candidate remains unset;
- provider lifecycle `succeeded` is distinct from candidate lifecycle `eligible`;
- no acceptance gate or reviewer state is mutated.

The adjudication boundary therefore remains above the execution provider.

## Architecture-neutrality verification

The fixture matrix instantiates three materially different provider descriptions through the same contract:

- a development/general worker;
- a validation-only Windows-shaped worker;
- a remote-shaped worker with GPU capacity.

OS family and placement kind are metadata. Required execution features are stable capability handles. The generic Python module contains no Ubuntu, Hyper-V or `windows-latest` scheduler semantics.

Remote transport remains intentionally unspecified. OP-014 establishes the normalized provider boundary without freezing a network protocol before a real remote-provider integration exists.

## Determinism verification

`FakeExecutionProvider` receives an explicit timezone-aware clock origin and uses deterministic counters. Given identical descriptions and operation sequences, verification confirms equal:

- reservation IDs and timestamps;
- provider job handles;
- terminal observations;
- provider evidence receipts and locations.

This keeps OP-014 unit tests reproducible without claiming that real providers are deterministic.

## Scope boundaries

This verification does **not** claim that a real Ansible, Hyper-V, container, Windows or remote provider is qualified. OP-006 compatibility negotiation and concrete adapter/provider qualification still apply independently. The fake verifies the generic contract and scheduler boundary only.

No human-independent verification is claimed. This was a separate verification pass/context from implementation and implementation review.

Because OP-014 is Steel, successful implementation verification does not authorize merge. The final evidence-document head must pass Foundation CI, after which explicit user promotion is still required.
