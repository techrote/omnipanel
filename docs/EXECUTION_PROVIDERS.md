# Execution providers, isolation and resource scheduling

## Execution Provider abstraction

Omnipanel schedules against an abstract Execution Provider rather than hardcoding one host/runtime. Initial conceptual providers:
- trusted local deterministic process;
- Linux VM/container worker;
- Windows validation VM;
- future remote machine/provider.

The provider contract describes capabilities, resource limits, isolation properties, lifecycle, evidence handles and qualified interface version. Distribution/transport details remain provider-specific.

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
