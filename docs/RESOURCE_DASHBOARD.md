# OP-010 execution-provider and resource dashboard

## Purpose

The Resources panel is a presentation and reconciliation surface over OP-032 durable resource accounting and OP-014 provider inventory. It does not implement provider isolation, quota enforcement, VM lifecycle, scheduler placement or secret management inside widgets.

The default CLI now opens `ResourceOperatorApp`, a thin subclass of the stable `OperatorApp`. Existing Overview, Tasks, Runs, Evidence, Models and System behavior remains inherited; OP-010 adds a dedicated Resources panel and service-backed reconciliation controls.

## Authority split

The dashboard reads:

- durable tasks and their full `provider_request` from `ApplicationServices`;
- durable reservation state and provider accounting through `DurableResourceLedger`;
- typed presentation-only observations for provider qualification, worker-pool topology and surplus-compute activity.

The UI never marks a provider compatible merely because it exists. If no qualification observation is available, compatibility is `indeterminate`.

The UI never repairs capacity disagreement itself. Any provider/ledger accounting state other than `consistent` makes task placement `INDETERMINATE` until the underlying accounting is reconciled.

## Provider detail

For each provider the dashboard shows stable, non-secret operational fields:

- provider ID, class and implementation version;
- exact component/interface contract identity;
- explicit compatibility/qualification state;
- provider availability and OP-032 accounting state;
- supported execution purposes and capability handles;
- reported free/total CPU, memory, storage and GPU capacity;
- wall-time ceiling;
- durable ledger allocation and signed provider-versus-ledger delta;
- typed accounting issues;
- candidate-bound durable reservations.

Provider metadata is **allow-listed**, not dumped. The current visible keys are host/placement/OS/platform/environment/image/harness identity. Arbitrary metadata such as `credential.*`, tokens or raw secrets is not rendered. Synthetic tests inject sentinel credential-like metadata and assert that neither its key nor value appears in dashboard output.

## Task placement explanation

Each durable task already carries an OP-002 `provider_request`, so OP-010 evaluates that request directly against every provider. The dashboard explains a task as `ELIGIBLE`, `BLOCKED` or `INDETERMINATE` with explicit reasons.

Placement checks include:

- provider compatibility qualification;
- availability (`available`, `degraded`, `unavailable`, `indeterminate`);
- OP-032 resource-accounting consistency;
- work-purpose support;
- requested provider class;
- required capability handles;
- isolation, network-policy, filesystem-policy and resource-limit enforcement guarantees;
- CPU, memory, storage, wall-time ceiling and GPU availability.

A definitive incompatibility/unsupported capability/resource shortage is `BLOCKED`. Missing qualification or accounting uncertainty is `INDETERMINATE`. Degraded availability is visible; if no hard requirement fails, placement can remain eligible with the degraded state called out.

This is a projection only. It does not reserve or start a task.

## Worker pools

Pool topology is supplied as a typed `ProviderPoolObservation`, separate from provider inventory. Each pool displays:

- pool ID and explicit state (`active`, `degraded`, `paused`, `indeterminate`);
- configured versus currently visible provider count;
- aggregate reported free/total CPU and memory;
- missing provider IDs;
- operator-facing note.

A pool referencing a provider absent from the current ledger is rendered indeterminate rather than silently shrinking the configured pool.

The OP-010 fixture includes a degraded development pool and an active validation-only pool so the dashboard remains usable with multiple pools/provider classes.

## Validation-provider state

Validation-only providers are ordinary OP-014 providers whose `purposes` and capabilities identify their role. The Resources panel does not create a Windows-specific scheduling branch; a validation provider appears beside general workers with its provider class, purposes, capability handles and capacity.

## Surplus compute

Surplus-compute activity is a typed presentation observation with explicit state (`active`, `idle`, `paused`, `indeterminate`), provider, CPU allocation and reason. Absence of this observation renders `INDETERMINATE`; it is never inferred from spare provider capacity.

OP-010 does not implement surplus scheduling. It only makes that state visible for later OP-M005 policy work.

## Resource actions

The panel provides mouse controls for provider, reservation and task traversal plus:

- **Reconcile** — calls `DurableResourceLedger.reconcile_reservation()` and renders its typed status/detail/durable state. Widgets do not query provider internals directly.
- **Refresh** — re-reads provider inventory and durable reservation state and redraws the panel.

No destructive “force release” or provider lifecycle control is embedded in OP-010 widgets. Explicit out-of-band stale-release confirmation remains an OP-032 service operation with its own audit requirements.

Released resources disappear from live ledger allocation on the next render, while the historical reservation remains visible as `released`. The same durable reservation tuple drives `ApplicationSnapshot.resources`, preventing a separate UI counter from double-counting stale allocation.

## Synthetic fixture states

`tests/fixtures/op010_resource_dashboard.json` deliberately contains:

- a qualified general development provider;
- a qualified validation-only provider;
- a contract-qualified but unavailable development provider;
- a degraded two-provider development pool;
- an active validation pool;
- idle foreground-aware surplus-compute state.

The tests additionally create provider/ledger disagreement to verify that an apparently capable provider becomes placement-indeterminate when accounting is inconsistent.

No synthetic fixture is represented as live provider qualification.

## Verification

`tests/test_resource_views.py` covers the pure projection/placement rules, multi-provider/pool display, safe metadata allow-listing, release refresh and accounting disagreement.

`tests/test_resource_ui.py` covers headless Textual navigation, service-backed reconciliation, refresh after release, provider traversal, persistent global blocker visibility and empty-provider fail-closed presentation.
