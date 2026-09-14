# OP-032 independent implementation review

Reviewed implementation head: `df74e15d5688ccdba8e8d1323da80107e652ece7`
Verified base: `main` at `5144e20e6d3a3063823855872ae512b857503e1c`
Foundation CI run: `34813870499` / #135 (**PASS**)
Review result: **PASS pending final doc-only head CI**

This was a distinct Stone implementation-review pass over the durable provider resource ledger, provider/ledger reconciliation, restart semantics, reservation identity, full ProviderRequest preservation, disagreement reporting and explicit stale-capacity release.

## Automated verification

Foundation CI passed all six supported lanes:

- Ubuntu / Python 3.12
- Ubuntu / Python 3.13
- Ubuntu / Python 3.14
- Windows / Python 3.12
- Windows / Python 3.13
- Windows / Python 3.14

Each lane passed Ruff lint/format, strict source type checking, the full unit/boundary/headless Textual suite, source/wheel build, clean-wheel installation and retained CI evidence.

The representative reviewed tree exercises more than 300 tests; the OP-032-specific suite covers resource arithmetic, provider enforcement, restart reconciliation, identity/version mismatch, provider-local ID reuse, stale/missing provider state and explicit recovery paths.

## Review findings

- OP-003 `resource_reservations` remains the durable allocation authority. OP-032 adds reconciliation/provenance rather than introducing a competing resource table.
- `ApplicationSnapshot.resource_reservations` exposes the exact durable tuple used to derive `ResourceSummary`, allowing task/resource views to share one source.
- OP-014 providers retain hard enforcement authority. Over-capacity requests fail before a durable reservation is created.
- The ledger preserves the caller's complete `ProviderRequest`; capability, writable-path, network and isolation constraints cannot be dropped by a resource-only mirror.
- CPU, memory, storage and GPU are accounted as fungible dimensions; wall time remains a per-job ceiling, not a pooled capacity dimension.
- Provider-reported total/available capacity is compared with durable live reservations. Directional disagreements are surfaced explicitly rather than silently normalized.
- Restart preserves OP-003's fail-closed behavior: previously reserved/active durable reservations reopen as indeterminate and require provider reconciliation before returning to a known state.
- Missing provider reservation state, provider identity/version mismatch and full-request/incarnation mismatch remain indeterminate; absence is never inferred as release.
- External stale-capacity release requires an already-indeterminate durable reservation plus explicit actor, reason and timezone-aware timestamp. The confirmation is durably audited even if a half-write left the candidate binding absent.
- Durable Omnipanel reservation IDs are globally independent of provider-local IDs, allowing multiple providers or restarted providers to reuse values such as `reservation-0001` without overwriting durable history.
- Release/reconciliation proves the exact provider reservation incarnation using provider identity/version/interface, provider-local reservation ID, run, complete request, resources and provider creation timestamp.
- Provider identity/version changes under the same provider ID cannot inherit or release old reservations.
- Durable/reconciliation timestamps are monotonic; stale provider/confirmation timestamps cannot move known state backwards.

## Defects found and reconciled during review

### Resource-only request reconstruction could weaken OP-014 policy

The first ledger draft accepted resource quantities and rebuilt a reduced `ProviderRequest`. That could discard capability, writable-path, network or isolation constraints and turn OP-032 into a side door around OP-014 enforcement.

The reconciled API accepts and persists the full `ProviderRequest`; provider reconciliation compares the complete request as well as the resource quantities.

### Provider-local reservation IDs were treated as globally unique

The first durable mirror reused the provider's reservation ID directly. Two providers, or one restarted provider, may legally both issue identifiers such as `reservation-0001`, risking durable overwrite or aliasing.

The reconciled ledger generates an independent `resource-<uuid>` durable ID and stores the raw provider-local ID in the typed binding. A regression proves same raw IDs from different providers coexist as separate durable reservations.

### Same provider ID/version was insufficient to identify a reservation incarnation

A restarted provider can reuse both its provider identity and a provider-local reservation ID. Releasing the old durable reservation against that newer provider-local record could affect unrelated work.

The reconciled release/reconciliation path verifies run ID, full request, resource quantities and original provider `created_at` in addition to identity/version and local ID. A regression creates a restarted provider reusing `reservation-0001` and proves release of the older durable reservation is refused.

### Missing-binding half-write was initially unrecoverable

A crash after the OP-003 durable row is written but before the candidate/provider binding is persisted can leave an indeterminate capacity hold that cannot be source-reconciled.

The reconciled design permits only explicit out-of-band release of such an already-indeterminate reservation. Actor, reason and timestamp are persisted as a separate reconciliation audit even though the missing binding cannot be reconstructed.

### Timestamp reconciliation could move durable state backwards

Provider observations and manual confirmations may carry timestamps older than the latest durable state.

The reconciled implementation keeps durable/binding reconciliation timestamps monotonic and rejects external-release confirmation timestamps older than the durable reservation timestamp. A dedicated regression retains this rule.

### Mechanical Ruff formatting

Superseded CI heads exposed formatter-only deltas after the semantic review fixes. The pinned formatter changes were applied without semantic changes; the reviewed implementation head passes the full repository toolchain.

No further material defect was found after reconciliation.

## Independence note

This review was performed as a separate review pass/context from implementation. It is not represented as a second human reviewer, and no independent human sign-off is claimed.

OP-032 is Stone, so no additional user-promotion gate applies. The only change after the reviewed implementation head is this evidence document; merge remains gated on the resulting documentation-only head passing Foundation CI.
