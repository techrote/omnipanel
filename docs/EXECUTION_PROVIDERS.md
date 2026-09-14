# Execution providers, isolation and resource scheduling

## Execution Provider abstraction

Omnipanel schedules against an abstract Execution Provider rather than hardcoding one host/runtime. Initial conceptual providers:
- trusted local deterministic process;
- Linux VM/container worker;
- Windows validation VM;
- future remote machine/provider.

The provider contract describes capabilities, resource limits, isolation properties, lifecycle, evidence handles and qualified interface version. Distribution/transport details remain provider-specific.

`src/omnipanel/execution_provider.py` is the executable OP-014 provider-neutral contract. It intentionally sits above concrete adapter/transport details and beside OP-006 interface negotiation. A provider still requires separately qualified component/adapter compatibility before a live integration can be trusted; implementing this Python protocol does not itself qualify Ansible or any other executor.

## OP-014 executable contract

### Identity and description

`ProviderIdentity` carries four authoritative fields:

- stable `provider_id`;
- stable `provider_class` used only when a task requests one explicitly;
- `implementation_version`;
- the exact `ComponentContractRef` implemented at the provider boundary.

Human-readable environment properties do not become scheduler architecture. `ProviderDescription.metadata` is a bounded key/value list suitable for facts such as operating-system family, placement kind or transport kind. The generic module contains no Ubuntu, Hyper-V or Windows scheduler branch.

Capabilities are stable handles. Work purpose is separate from capability: a provider may support `execution`, `validation`, or both. This permits a validation-only provider without defining a second scheduling API.

### Guarantees are provider-owned

`ProviderGuarantees` records whether the provider can enforce:

- isolation;
- resource limits;
- network policy;
- filesystem/writable-path policy.

Omnipanel does not emulate a missing guarantee. A `ProviderRequest` is validated against the provider description before reservation. Missing requested capabilities, provider-class mismatch, unavailable enforcement or unavailable capacity raise a typed `ExecutionProviderError` with an operator-readable `ProviderDiagnostic`.

The default OP-002 `ProviderRequest` is deliberately restrictive: isolation is required, network is not granted and writable paths are empty unless requested. A provider therefore needs policy enforcement below Omnipanel to honour those restrictions rather than merely accepting the request object.

### Availability and inventory

`ProviderInventory` carries the exact provider identity/version, explicit availability (`available`, `degraded`, `unavailable`, `indeterminate`), total resources, currently available resources and a timezone-aware observation timestamp.

CPU, memory, storage and GPU quantities are fungible capacity in the deterministic fake. `wall_time_seconds` is a per-job maximum ceiling, not a pool that is consumed by concurrent reservations. A request must fit that ceiling, but reserving 300 seconds does not subtract 300 seconds from another worker's allowable run duration.

`unavailable` and `indeterminate` providers reject new reservations. `degraded` remains visibly degraded but can accept work that its reported capabilities, guarantees and remaining capacity can satisfy.

### Reservation and candidate lifecycle

The neutral lifecycle is:

1. `reserve(run_id, ProviderRequest)`;
2. `start(ProviderCandidateRequest)` using that reservation;
3. `observe(ProviderCandidateHandle)` zero or more times;
4. provider reports `succeeded`, `failed`, `cancelled` or `indeterminate`;
5. collect provider evidence as observations accumulate;
6. release the reservation only after the candidate is settled as `succeeded`, `failed` or `cancelled`.

Reservation IDs, provider job IDs, run IDs, task IDs and candidate IDs remain distinct fields. A handle contains a full provider identity snapshot so stale/misrouted handles from another provider version fail closed. `reservation()` exposes the provider's current resource-state observation for reconciliation.

`indeterminate` is deliberately **not terminal**. It means the control layer cannot prove whether underlying work is still consuming resources. The reservation therefore becomes `INDETERMINATE`, remains charged against provider inventory and cannot be released. A later provider observation may reconcile that work to a known settled state; only then is release permitted. Evidence collected before and after reconciliation is retained rather than overwritten.

An active or indeterminate reservation cannot be released while its candidate is unsettled. Cancellation is an explicit provider lifecycle transition and produces provider evidence.

### Execution success is not acceptance

`ProviderCandidateLifecycle.SUCCEEDED` means only that the execution provider reports its job completed successfully. It does **not** mean:

- `CandidateStatus.ELIGIBLE`;
- acceptance gates passed;
- reviewer requirements were satisfied;
- a Race candidate won;
- a run may be promoted or merged.

Those decisions remain Omnipanel/master/adjudication responsibilities above the provider boundary. The generic provider module has no function that turns provider success into candidate eligibility.

### Evidence and provenance

Provider lifecycle transitions that the deterministic fake records produce `ProviderEvidenceReceipt` values. Each receipt contains:

- full provider identity, implementation version and interface contract;
- provider job, run and optional candidate identity;
- an `EvidenceDescriptorRecord` whose producer type is `provider` and whose producer ID exactly matches the provider identity.

The descriptor location also includes stable provider ID, provider implementation version, job ID and lifecycle. `attach_provider_evidence()` may add those evidence IDs to a durable `RunRecord`, but it changes no run status or selection field.

A real integration may persist the descriptor/artifact through the existing evidence/storage boundary. Live provider handles remain outside OP-003 durable state as designed.

### Typed failure surface

The current generic failure codes cover:

- provider unavailable/indeterminate;
- provider-class mismatch;
- unsupported capability or work purpose;
- missing isolation/network/filesystem/resource enforcement;
- insufficient resources;
- missing/invalid reservation;
- missing/invalid candidate state;
- request/handle mismatch;
- provider identity/version mismatch.

These are provider-neutral diagnostics. Concrete adapters may translate lower-level failures into this surface without leaking transport- or platform-specific control flow into tasks.

## Deterministic fake provider

`FakeExecutionProvider` is an in-memory test provider using a supplied timezone-aware clock origin, deterministic counters and deterministic evidence locations. Given the same provider description and operation sequence it returns identical reservations, handles, observations and evidence receipts.

The fake implements real resource accounting and the same capability/guarantee checks as the generic boundary. Its `finish()` method is deliberately a test-control surface rather than part of the `ExecutionProvider` protocol; it lets tests advance a provider job to a settled or indeterminate execution lifecycle without inventing adjudication authority. Indeterminate work remains charged until later reconciliation.

`tests/fixtures/op014_provider_matrix.json` describes development, validation-only and remote-shaped providers through the same contract. Platform and placement differences appear only as metadata/capabilities. `tests/test_execution_provider.py` and `tests/test_execution_provider_matrix.py` exercise lifecycle, resources, typed failures, provenance and architecture neutrality.

## Responsibility split

### Ansible

Owns privileged primitives and hard enforcement:
- create/start/stop/reset isolated execution environments;
- enforce hard CPU/RAM/storage/time/capability ceilings;
- instantiate registered runner types;
- protect credentials and canonical repositories;
- return typed status/evidence/results;
- refuse unsupported/incompatible requests.

### Omnipanel

Owns scheduling policy:
- choose provider/candidate placement;
- allocate requested CPU/RAM within available policy;
- construct Race/Diversity groups;
- decide continuation/cancellation/reuse;
- maintain user-visible resource state;
- drive surplus-compute policy.

Omnipanel cannot mint provider capabilities that Ansible has not installed/authorized.

## Initial host direction

Windows 11 is the reference control host. Hyper-V is the initial virtualization direction. Ubuntu LTS is the initial reference Linux worker image because it is common and well-supported; distro identity must remain provider metadata rather than appearing in task semantics.

A likely early architecture is a small pool of Linux worker VMs with cheap per-agent containers/process sandboxes, plus a cleaner Windows validation VM for platform-specific acceptance. One full VM per short-lived worker is not required.

## CPU scheduling

Workers must not independently assume all host cores are available. Provider-enforced quotas/affinity prevent multiple candidates from each launching full-host parallel builds. Omnipanel may rebalance resources as candidates finish/fail, subject to provider policy and reproducibility requirements.

Initial resource algorithms should be simple and observable. NUMA-aware optimization is deferred until the target Xeon hardware is available and measured.

## Memory and volatile storage

RAMDisk/tmpfs integration is a later optimization. Intended candidates include disposable worktrees, build trees, compiler intermediates, Python caches, temporary HOME/TMP state and VM differencing layers. Canonical repositories, accepted patches and evidence remain durable.

A RAMDisk must not double-spend memory thoughtlessly by storing whole VM root images in RAM while also assigning large guest memory. Prefer persistent immutable base images plus volatile differencing/work layers where measurements justify it.

## Remote workers

Remote execution implementation is deferred. Preserve architectural intent:
- same normalized task/provider contract where possible;
- explicit authenticated provider enrollment;
- no ambient trust inherited merely because a machine is reachable;
- evidence/provenance include provider identity;
- hard policy remains enforceable below master logic.

Do not freeze a network protocol before a real remote-worker requirement exists.

## Validation provider

Windows-specific acceptance should be able to run separately from speculative Linux development. A candidate that passes cheap/Linux gates can be promoted to a Windows validation stage without allowing the candidate worker to control that environment or its hidden acceptance assets.
