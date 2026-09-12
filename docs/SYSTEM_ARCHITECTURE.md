# Omnipanel system architecture

Status: selected planning baseline, 2026-09-12. This document defines cross-project architecture; component repositories own their internals.

## System objective

Provide flexible, partially model-agnostic orchestration with remote-shell-like usefulness while avoiding ambient remote-shell authority. Flexibility sits above deterministic trust boundaries.

## Layered architecture

```text
Human / Chat / Codex / local master
            |
            v
        Omnipanel
  planning, scheduling, adjudication
            |
     typed capability requests
            v
          Ansible
 trusted execution + isolation kernel
       /       |        \
 deterministic OMP/OpenCode future providers
       workers  via Ohmy
            |
   VMs / containers / worktrees

Interloc <---- evidence/status/proposals ----> Omnipanel
intrallm ---- pinned inert references -------> consumers
```

## Dependency direction

- Omnipanel may depend on stable Ansible, Interloc and Ohmy interface contracts.
- Ansible must not depend on Omnipanel; it remains a small headless trusted kernel.
- Interloc may observe and propose through qualified interfaces but does not acquire scheduler authority.
- Ohmy is a backend adapter, not the global scheduler.
- intrallm cannot introduce executable code or policy into trusted execution.

## Core Omnipanel services

1. **Project/programme service** — metaissues, child DAGs, readiness and evidence convergence.
2. **Task-contract service** — normalized task policy, load-bearing/economic dimensions, acceptance requirements and user overrides.
3. **Master-driver service** — Codex/local-model first-class drivers; Interloc proposal bridge.
4. **Candidate scheduler** — single, Race and Diversity strategies.
5. **Adjudication service** — public/hidden tests, invariant gates, reviewer requirements and candidate comparison.
6. **Resource scheduler** — CPU/RAM/execution-provider reservations and surplus-compute policy.
7. **Model registry** — structured identity, capability/trust classes, qualitative tags, maturity, quarantine and Verboten state.
8. **Interface registry** — pinned contract versions/SHAs and adapter compatibility.
9. **Evidence index** — references to durable evidence produced by lower layers; Omnipanel does not need to ingest every raw artifact.
10. **Operator application** — mouse-driven Textual TUI backed by UI-independent services.

## Durable job ownership

UI widgets and screens do not own execution lifetime. A durable run continues when a panel changes or the TUI is restarted. Explicit cancel/contain/kill actions are separate from UI closure.

## Credentials

Omnipanel stores capability handles/aliases and policy references, not raw model/GitHub secrets. Credential-bearing execution occurs through trusted providers or OS facilities. A compromised Omnipanel process should therefore have less direct blast radius than a universal credential vault.

## Acceptance as security boundary

Candidate-generated code is untrusted until adjudicated. Running tests executes candidate code, so hidden-test material, evaluator credentials, canonical repositories and privileged provider interfaces must not be exposed to the candidate environment. Acceptance is run in an independently controlled context.

## Fail-safe compatibility

Each external component presents an explicit qualified contract version. Unknown/incompatible versions are rejected before effects occur. Compatibility adapters may support multiple known versions, but no best-effort semantic guessing is permitted for authority, isolation, evidence or credential boundaries.

## Initial platform

- Python 3.12+
- Textual TUI
- Windows 11 control host
- Hyper-V execution-provider direction
- Ubuntu LTS reference Linux worker image
- local machine first; remote worker transport deferred
- RAMDisk/tmpfs optimization deferred

These are implementation choices, not permanent protocol constraints unless promoted by later ADR.
