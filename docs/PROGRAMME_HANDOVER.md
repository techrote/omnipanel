# Omnipanel programme handover — 2026-09-12

## Purpose

This document captures the cross-project architectural intent established before Omnipanel implementation. It is a context-recovery document, not a claim that the described runtime exists.

Omnipanel is intended to provide remote-shell-like engineering capability without granting remote-shell-like ambient authority. The system combines deterministic trusted capabilities with model-driven orchestration, speculative parallel work, strong isolation, evidence-based adjudication and human control.

## Repository responsibilities

- **Omnipanel** — system orchestration, operator TUI, master/worker scheduling, Race/Diversity policy, acceptance/adjudication, resource scheduling, cross-project roadmap and system ADRs.
- **Ansible** — trusted execution kernel. It validates jobs, owns registered runner/execution-provider primitives, enforces hard safety/resource boundaries and produces execution evidence. It must remain useful headlessly.
- **Interloc** — communications/evidence courier and structured capability-proposal broker. It does not become the execution scheduler.
- **Ohmy** — Oh My Pi integration: provider/model adapters, RPC/headless harnesses, telemetry normalization and OMP-specific failure semantics.
- **intrallm** — agent-visible task/reference/evidence data plane. Data from it is inert; it cannot introduce executable runners or policy.

Component repositories remain authoritative for their internals. Omnipanel is authoritative for interfaces between them, system-level policy and the end-to-end orchestration roadmap.

## Authority hierarchy

1. Hard deterministic safety/containment rules — never overridable by a model or remote request.
2. Local configurable user policy — can authorize/narrow capabilities within hard limits.
3. Master-authored task contract — scope, acceptance tests, hidden tests, paths, resources, stop/escalation rules.
4. Worker execution — operates only within the resulting envelope.
5. Evidence and adjudication — passing tests creates an eligible candidate, not merge authority.
6. Human authority — consequential policy choices and explicit reactivation of quarantined models remain human decisions.

Omnipanel must not become a central raw-credential vault. It should use capability handles/references while credential-bearing operations remain in trusted lower layers or OS stores.

## Master/worker model

Codex and local-model masters are first-class v1 drivers. Interloc/Chat is a functional bridge. Manual terminal operation may use the same proposal/task surfaces.

Masters decompose work, define acceptance and hidden/adversarial tests, select execution strategy, reconcile evidence and make integration recommendations. Workers may be models or deterministic programs. Worker capability/trust is tracked separately from model identity.

## Speculative execution

**Race** minimizes time-to-eligible result. Cancellation is policy-driven; paid/premium candidates may be allowed to finish while free candidates are cancelled after a provisional winner. Every cancellation policy may preserve a cheap diff/test/evidence salvage package; full worktree preservation is configurable.

**Diversity** intentionally collects independent implementations/reviews for comparison, redundancy or novel approaches.

The default interactive policy may ask the user. Initial project planning may record per-task overrides. Unattended work uses explicit named policies such as ask, first-valid-free, first-valid-all, collect-all and cost-conscious.

## Task dimensions

Load-bearing class:
- `tissue` — disposable/minimal consequence.
- `labware` — exploratory R&D; strong containment and self-checking, but independent production-grade review may be deferred. A Mad Scientist profile is a first-class use case.
- `stone` — normal production engineering; implement, verify and obtain independent review.
- `steel` — system-critical; implementation, verification, independent review of both work and verification are expected.

Economics dimensions:
- expected value: none / low / medium / high / priceless
- expected wall time: instant / short / medium / long / days
- marginal cost: free / local / low / quota / paid

These dimensions may drive surplus-compute/scavenger scheduling. Cheap, low-value exploratory work may run when resources would otherwise idle, but must never delay higher-priority work or weaken containment.

## Metaissues

A metaissue is an orchestration/review envelope containing bounded child issues. Children may form a directed acyclic graph (DAG): dependencies may cross sibling branches but must never form cycles. Metaissue completion is evidence-based, not a count of administratively closed children. A frontier model may be assigned a metaissue to integrate/review its child work.

## Model assessment and safety states

Model identity is structured; display names are not authoritative keys. Positive and negative tags are independent, non-exclusive dimensions. Examples include `eye_for_details`, `dependable`, `promising`, `fast`, `poor_convergence`, `weak_novel_reasoning`.

Within-tag rank is subjective/comparative only. Maturity is separate: roughly 1 = essentially new, 2–8 = increasing user-calibrated confidence, 9 = mature/first-class assessment. Qualifiers/prefixes/suffixes such as `maybe`, `veteran`, `new`, `old`, `tempAvail` provide extra context without being parsed from a display string.

UI emphasis is the most recent ~4–24 meaningful runs per model; backend history should remain complete subject to storage policy.

Safety state is separate from ranking:
- active
- quarantined — cannot run again through automation; human reactivation required.
- verboten — permanent ecosystem ban; normal orchestration exposes no reactivation path.

Repeated severe unwanted behavior may trigger quarantine or Verboten under future calibrated rules. Exact scoring/automatic thresholds are deliberately deferred until operational experience exists.

## Execution infrastructure

Reference host is Windows 11. Hyper-V is the initial virtualization direction. Ubuntu LTS is the initial Linux worker image, but distro identity is an execution-provider detail, not protocol semantics.

Ansible owns trusted VM/container primitives and hard resource/isolation enforcement. Omnipanel decides allocation/scheduling. Execution Provider is the generic abstraction for local process, Linux VM/container, Windows validation VM and future remote workers.

Remote-worker implementation is deferred. Its architectural shape should be preserved without prematurely fixing a transport protocol.

RAMDisk/tmpfs support is deferred but anticipated. Disposable worktrees/build/temp state are appropriate candidates; persistent evidence and canonical repositories stay durable.

## UI

Initial implementation language: Python 3.12+.
Initial UI: mouse-driven Textual TUI. Backend/application state must remain UI-independent so a later web UI can use the same services. Closing/changing a UI panel must never implicitly own or cancel durable job lifetimes.

## Fail-safe component compatibility

Omnipanel uses pinned, versioned interface contracts rather than copied component documentation. If a component presents an incompatible contract, only that integration fails closed: no job is started and the operator receives an explicit incompatibility report. The adapter may support multiple explicitly qualified versions during migration; it must never guess security or authority semantics.

## Known operational lessons informing the design

- Administrative issue closure is not evidence of substantive completion.
- Worker self-report is not authoritative evidence.
- Read-only invariants include untracked-file creation.
- Provider/session terminal events do not necessarily mean model work succeeded; provider errors must be classified explicitly.
- Task-data refresh and executable-code update are separate operations.
- Cancellation should salvage useful candidate state when safe, but emergency containment must not wait indefinitely for cooperative salvage.
- Acceptance testing executes candidate code and is itself a security boundary; evaluators/hidden tests/credentials/canonical repositories require independent protection.

## Current component state known at handover

Published Ansible `main` was observed at `9f27ca4f4c9317ed8246851f2961adc8bdb2de74`; it contains the trust policy and original four-slot schema. A separate local Big Pickle implementation attempt was still in progress and must be independently reconciled before being treated as canonical.

Published Interloc `main` was observed at `491be0104df52b2b9307e7662b2bcb8d6467d169`; its planning baseline is mature, but runtime implementation has not started and some integration issue publication is explicitly blocked.

`techrote/ohmy` was observed as an empty private repository; its detailed programme remains to be created.

Omnipanel development must not silently mutate or claim completion for those repositories.
