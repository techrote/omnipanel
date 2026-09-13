# Component interface registry

Status date: 2026-09-13. This file records component identities, compatibility policy and the OP-006 executable negotiation contract. It does not certify that any live integration is installed.

## Compatibility policy

Omnipanel stores small versioned interface contracts and links to authoritative component documentation rather than copying whole component manuals. Adapters declare the exact contract versions they support.

If a component presents an incompatible contract, that integration is unavailable until its adapter is explicitly updated and verified. Omnipanel must not guess changed field or state semantics. Independent integrations may continue operating.

A source commit change alone is not necessarily an incompatibility: contract identity and qualified semantics are the primary compatibility boundary.

## OP-006 executable contract

`src/omnipanel/interfaces.py` implements fail-closed negotiation before any integration effect. A qualified path requires all of the following:

- the adapter has an explicit qualification for the component;
- the observed contract identity exactly matches a qualified contract identity;
- the observed contract version exactly matches one qualified adapter version;
- both the observed component contract and adapter qualification carry evidence IDs.

No semantic-version ranges, display strings, source revisions or best-effort conversions are used to infer compatibility. An observed `1.0.1` contract therefore does not inherit qualification from `1.0`.

A source revision is stored separately from `contract_version`. A component may move to a new source commit without becoming incompatible when its qualified contract identity and semantics remain unchanged.

### Compatibility outcomes

| Observation | Result | Diagnostic |
|---|---|---|
| exact component + contract + version, both sides evidenced | `qualified` | none |
| adapter has no qualification for component | `incompatible` | `component-unsupported` |
| contract identity differs | `incompatible` | `contract-unsupported` |
| contract version lacks an exact qualification | `incompatible` | `version-unqualified` plus qualified versions |
| observed contract has no qualification evidence | `incompatible` | `observation-unqualified` |

The result is a typed `CompatibilityDecision`, so OP-004 services and later UI code can present the diagnostic without importing component-specific adapter logic.

### Migration windows

Several exact versions can be qualified simultaneously. The OP-006 fixture demonstrates an Ansible adapter with both `execution/1.0` and `execution/1.1` qualified. During that migration window either exact version succeeds; `2.0` still fails closed until it receives its own qualification evidence.

### Persistence

Adapter qualifications and compatibility decisions are persisted through the OP-003 component-observation store. Their evidence references therefore survive restart and can be retrieved independently of UI lifetime. Persisted decisions are observations, not authority to perform an effect: a caller must still use the current decision and applicable policy before execution.

### Isolation

Compatibility is decided per adapter/component pair. An incompatible Ansible observation does not globally disable an independently qualified Interloc integration.

Automated coverage lives in `tests/test_interfaces.py` with the matrix fixture `tests/fixtures/op006_compatibility.json`.

## Observed component state

### Ansible

Repository: `techrote/ansible`
Observed published main: `9f27ca4f4c9317ed8246851f2961adc8bdb2de74`

Published documentation defines Ansible as the trusted human-initiated execution plane and separates trusted executable orchestration from agent-visible task/reference data. The published schema is an early four-slot prototype, so Omnipanel must not treat it as the final system contract.

### Interloc

Repository: `techrote/interloc`
Observed published main: `491be0104df52b2b9307e7662b2bcb8d6467d169`

Published planning defines Interloc as the communications/evidence broker. Its Ansible integration remains separately gated; Omnipanel development must support synthetic fixtures until a qualified live contract exists.

### Ohmy

Repository: `techrote/ohmy`
Observed state at intake: empty private repository.

Planned role: Oh My Pi-specific compatibility and normalized model/runtime results. It does not own cross-project scheduling policy.

### intrallm

Repository: `techrote/intrallm`
Observed published main: `01ddd0c1d39cde95f0b73090e1b0236209a287a9`

Role: agent-visible reference/task/evidence data plane. References are data, not executable authority. Data refresh and trusted-code updates remain separate operations.

### Omnipanel

Repository: `techrote/omnipanel`

Owns system-level interface compatibility, orchestration semantics and the cross-project roadmap. Each component remains authoritative for its own internals.
