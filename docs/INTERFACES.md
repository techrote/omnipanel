# Component interface registry

Status date: 2026-09-12. This file records planning-time component identities and compatibility policy. It does not certify that any integration is installed.

## Compatibility policy

Omnipanel stores small versioned interface contracts and links to authoritative component documentation rather than copying whole component manuals. Adapters declare the contract versions they support.

If a component presents an incompatible contract, that integration is unavailable until its adapter is explicitly updated and verified. Omnipanel must not guess changed field or state semantics. Independent integrations may continue operating.

A source commit change alone is not necessarily an incompatibility: contract identity and qualified semantics are the primary compatibility boundary.

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
