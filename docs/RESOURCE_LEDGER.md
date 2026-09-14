# OP-032 host/provider resource inventory and reservation ledger

## Purpose

OP-032 joins two existing boundaries without changing either authority model:

- OP-014 Execution Providers own hard capacity enforcement and report their current inventory.
- OP-003 durable state owns Omnipanel's restart-safe reservation mirror.

`src/omnipanel/resource_ledger.py` adds the reconciliation layer between them. It does not trust worker-local build flags as capacity, does not invent provider resources, and does not silently overwrite a provider/ledger disagreement.

## Durable source of truth

The existing OP-003 `resource_reservations` table remains the authoritative durable resource allocation record. `ApplicationServices.resource_reservations()` exposes those records directly, and `ApplicationSnapshot.resource_reservations` contains the same tuple used to derive `ApplicationSnapshot.resources`.

This means later task and resource dashboards can use one durable reservation source rather than separately reconstructing allocation counts.

Candidate/provider metadata that did not exist in the original OP-003 storage record is stored as a typed `ResourceReservationBinding` in the existing durable component-observation store. The binding contains:

- globally unique Omnipanel durable reservation ID;
- provider-local reservation ID;
- run ID;
- candidate ID;
- full OP-014 provider identity, implementation version and interface contract;
- the full `ProviderRequest`, not merely its resource quantities;
- provider reservation creation time;
- reconciliation timestamps and explicit reconciliation provenance.

The legacy resource record remains backwards compatible while new OP-032 reservations gain candidate and provider provenance.

## Omnipanel ID versus provider-local ID

Provider reservation IDs are not assumed globally unique. Two providers may both return `reservation-0001`, and a restarted provider may reuse an earlier local identifier.

OP-032 therefore generates an independent `resource-<uuid>` durable ID for Omnipanel. The raw provider reservation ID lives in the binding and is used only when talking back to the exact provider identity that created it.

Before release or reconciliation, the ledger proves that the current provider reservation is the same reservation incarnation by matching:

- exact provider identity/version/interface;
- provider-local reservation ID;
- run ID;
- complete `ProviderRequest`;
- resource quantities;
- provider reservation creation timestamp.

This prevents a restarted provider from accidentally releasing or reconciling a newer reservation that reused an older local ID.

## Reservation path

`DurableResourceLedger.reserve_candidate()` sends the caller's complete `ProviderRequest` to the provider. It does **not** rebuild a resource-only request, because doing so could discard capability, writable-path, network or isolation constraints.

The provider therefore remains the hard-enforcement authority. If the provider rejects overcommit or an unsupported policy, no durable reservation is created.

After a provider reservation succeeds, Omnipanel mirrors its resource quantities and state into OP-003 durable state and persists the candidate/provider/request binding. Provider identity, run ID and the full request must round-trip unchanged.

There is no distributed transaction between an external provider and local SQLite. A process failure in the narrow interval after provider reservation but before the durable mirror may therefore leave provider capacity that Omnipanel cannot name. OP-032 handles this fail-closed: provider inventory will report less free capacity than the durable ledger expects, and that disagreement is surfaced explicitly rather than allocating the apparent missing capacity. A future provider-pool implementation may add provider-specific orphan cleanup only where the provider contract can prove it safely.

A second narrow interruption point can leave the OP-003 reservation row durable while its candidate/provider binding is absent. Such a reservation remains visible and counts against capacity. It is treated as indeterminate and can only be cleared by explicit out-of-band release confirmation; that confirmation is persisted as a separate reconciliation audit even when the missing binding cannot be reconstructed.

## Resource arithmetic

The ledger follows OP-014 semantics:

- CPU millicores, memory MiB, storage MiB and GPU count are fungible capacity dimensions;
- `wall_time_seconds` is a per-job ceiling, not a pool consumed by concurrent jobs.

For each provider the ledger computes:

1. provider-reported total capacity;
2. provider-reported currently available capacity;
3. total live durable reservations (`reserved`, `active` or `indeterminate`);
4. expected available capacity from provider total minus durable fungible reservations;
5. a signed delta: provider-reported available minus ledger-expected available.

Durable reservations that exceed provider total are never normalized away; they produce an indeterminate accounting state and a `durable-overcommit` issue.

## Accounting disagreements

`ProviderResourceView` can report:

- `consistent` — provider and durable ledger agree;
- `provider-reports-more-available` — provider appears to have released/forgotten capacity that the durable ledger still holds;
- `provider-reports-less-available` — provider reports external/untracked consumption or another source of reduced capacity;
- `mixed-disagreement` — dimensions disagree in different directions;
- `indeterminate` — provenance, identity, provider availability or durable accounting is not trustworthy enough for a directional conclusion.

Typed issues identify missing candidate bindings, provider identity/version mismatch, durable overcommit and provider-indeterminate state. These are presentation/placement inputs, not automatic repair instructions.

## Restart and reconciliation

OP-003 already converts `reserved` and `active` durable reservations to `indeterminate` when the state store reopens. OP-032 then explicitly queries the matching provider reservation.

`reconcile_reservation()` verifies all of the following before restoring a known state:

- durable provider ID matches the requested provider;
- durable binding exists;
- exact provider identity/version/interface matches the binding;
- provider-local reservation ID still exists;
- provider reservation creation timestamp matches the binding;
- run identity matches;
- full `ProviderRequest` matches the durable binding;
- resource quantities match the durable reservation.

A consistent provider observation maps back to `reserved`, `active`, `released` or `indeterminate`. Durable and reconciliation timestamps are monotonic: a stale provider timestamp cannot move Omnipanel state backwards in time.

If the provider reports the reservation missing, or identity/request/incarnation provenance disagrees, the durable record stays/returns `indeterminate`. Missing provider state is not interpreted as release.

## Explicit external release

`confirm_external_release()` exists for a stale reservation that has been independently inspected out of band. It is allowed only when the durable reservation is already `indeterminate` and requires an explicit actor, reason and timezone-aware timestamp that is not older than the durable reservation state.

The confirmation is stored independently as reconciliation audit evidence. If the candidate/provider binding exists, its reconciliation metadata is updated too; if an interrupted half-write left that binding absent, the explicit audit still permits the stale durable capacity hold to be resolved.

This updates only Omnipanel's durable mirror. If the provider still consumes the resources, the next provider view reports less free capacity than the ledger expects; the disagreement remains visible rather than being hidden by the override.

## Provider identity changes

A reservation is bound to the exact OP-014 provider identity, including implementation version and interface contract. Replacing `provider-a` version 1 with a different version under the same provider ID does not silently inherit live reservations. Provider views become indeterminate, release refuses the mismatched identity, and restart reconciliation refuses to treat the new provider as the old one.

Even when the provider identity is unchanged, a reused provider-local reservation ID is not enough to authorize release: run/request/creation provenance must still match the durable binding.

## Evidence and tests

`tests/test_resource_ledger.py` covers:

- candidate-bound reservation and release;
- application snapshot and resource summary using the same durable reservation tuple;
- provider-enforced overcommit rejection with no durable ghost reservation;
- active reservation restart -> indeterminate -> explicit provider reconciliation;
- provider-missing stale reservation remaining indeterminate until explicit out-of-band release;
- provider reporting less free capacity than the ledger expects;
- provider reporting more free capacity than the ledger expects;
- provider implementation-version mismatch;
- provider-local reservation-ID collisions across different providers without durable overwrite;
- protection against external-release override of a non-indeterminate reservation;
- explicit recovery of an indeterminate half-write with a missing binding;
- deterministic multi-provider snapshot ordering.

`tests/test_resource_ledger_review_regressions.py` additionally locks in Stone-review fixes for provider-local ID reuse and monotonic external-release timestamps.

NUMA/topology-specific optimization, provider-pool lifecycle/rebalancing and Hyper-V implementation remain outside OP-032 and are handled by later tasks.
