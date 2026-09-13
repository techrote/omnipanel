# OP-017 independent implementation review

Reviewed implementation head before review fix: `227690dfef0061b34036550ccb967a0f51a1c6a4`
Prior Foundation CI: `34785254214` (**PASS**, six Windows/Linux × Python 3.12/3.13/3.14 jobs)
Review result after reconciliation: **PASS pending fresh CI on the corrected head**

This was a separate implementation-review pass over the master-driver contracts, authority normalization, fake driver, lifecycle/adjudication tests and documentation.

## Review findings

- The generic `MasterDriver` surface is replaceable and reuses canonical OP-002 master identity rather than inventing a parallel identity schema.
- Task policy remains authoritative for strategy, mandatory user decisions and consequential-promotion requirements.
- Provider requests may narrow but cannot broaden provider class, capabilities, writable paths, network access, isolation requirements or resource quantities.
- Candidate-count/set checks prevent the master from adjudicating a different effective candidate population than the normalized contract.
- Adjudication is bound to the normalized contract, supplied candidates and supplied evidence IDs.
- Bounded provenance stores only driver identity, context digest and an optional bounded conversation reference; raw conversation history is not copied into the contract.
- Decomposition is advisory and rejects duplicate, unknown, self-referential and cyclic dependency structures.

## Defect found and fixed during review

`MasterLifecycle.normalize()` accepted a caller-supplied `MasterProvenance` without checking that its `driver_id` matched the active driver's canonical `MasterIdentityRecord.driver_id`. Because `normalize()` is a public lifecycle entrypoint, a caller could produce an otherwise valid normalized contract whose provenance attributed the proposal to another driver. That violated the documented provenance boundary even though the ordinary `run()` path constructed provenance correctly.

The corrected implementation snapshots the active identity inside normalization, rejects mismatched provenance with the typed `PROVENANCE_MISMATCH` diagnostic, uses that same identity for the resulting contract, documents the invariant, and adds an adversarial regression that attempts cross-driver provenance substitution.

## Independence note

This review was performed as a distinct review pass/context rather than by a second human reviewer. That limitation is explicit; no independent human sign-off is claimed.
