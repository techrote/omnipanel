# OP-017 master-driver interface

`src/omnipanel/master_driver.py` defines a replaceable master surface without granting a model or conversation channel execution authority.

## Lifecycle

A `MasterDriver` exposes three things: canonical `MasterIdentityRecord`, current availability, and deterministic `propose()` / `adjudicate()` calls over typed contracts.

`MasterLifecycle.run()` performs:

1. availability check;
2. bounded intake construction from the canonical `TaskRecord` plus provenance;
3. driver proposal;
4. fail-closed proposal normalization against task policy/provider bounds;
5. validation that the actual unique candidate set matches the normalized candidate count;
6. typed adjudication request over candidate/evidence IDs;
7. driver recommendation validation against exactly that candidate/evidence set.

The resulting `MasterLifecycleResult` is a normalized recommendation package. It is not commit/merge/deploy authority.

## Authority boundary

The canonical task and coordinator inputs remain authoritative. A master cannot:

- target a different task;
- change the resolved `TaskPolicy.strategy`;
- proceed when an explicit user policy decision is required but absent;
- request capability handles outside the task provider boundary;
- expand writable paths;
- enable network when the task forbids it;
- weaken required isolation;
- exceed task resource quantities;
- relax a specific authoritative provider class;
- cause a normalized candidate count to diverge from the actual adjudication candidate set;
- adjudicate another contract or select a candidate outside the request;
- cite evidence IDs that were not supplied to the adjudication request.

A task whose policy marks consequential promotion as user-controlled remains marked `promotion_requires_user` in the adjudication request. A master selection is therefore a recommendation, not a user-promotion substitute.

## Narrowing and provider requests

Master provider requests may be narrower than the task envelope. For example, a task allowing writes to `src/...` and `tests` may propose a candidate that writes only `tests`, or use fewer requested CPU/memory seconds. Broader requests fail with a typed `MasterLifecycleErrorCode` before a normalized contract is produced.

If the canonical task pins a provider class, the master must preserve it. If the task leaves provider class open, choosing a specific class is a narrowing constraint and is permitted.

## Identity and provenance

Master identity reuses the OP-002 `MasterIdentityRecord`; worker identity remains the distinct `WorkerIdentityRecord`. Driver replacement therefore changes driver/master provenance without changing the task/domain schema.

Conversation/model context is not copied wholesale into task contracts. `MasterProvenance` stores only:

- driver ID;
- SHA-256 digest of the supplied context;
- optional bounded conversation/location reference.

The canonical model, when applicable, belongs to `MasterIdentityRecord.model`.

## Decomposition

Master proposals may include bounded local decomposition steps. Step IDs and dependencies must be unique, dependencies must reference known steps, self-dependencies are forbidden, and cycles are rejected. These proposed steps are advisory plan structure; they do not automatically create durable OP task IDs.

## Fake master

`FakeMasterDriver` provides deterministic proposal/adjudication outputs for lifecycle tests. Replacing one fake driver identity with another produces the same normalized task schema and authoritative task/provider semantics; only master provenance/contract identity changes.

## Diagnostics

`MasterLifecycleError` carries stable typed codes for unavailable masters, task mismatch, missing user policy, strategy/candidate conflicts, invalid candidate sets, provider-boundary broadening, adjudication mismatch, unknown candidate selection and evidence-set mismatch. The operator/service layer can present these without parsing model prose.

Automated coverage is in `tests/test_master_driver.py`.
