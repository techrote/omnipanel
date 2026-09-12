# Omnipanel

Omnipanel is the system-level orchestration and operator-control project for the techrote agent-tooling ecosystem.

Its job is to decide **what should run, where, with which workers, under which evidence and review policy**. It does not replace the trusted execution kernel, communications broker, model-runtime adapters, or agent-visible reference plane.

## Ecosystem boundary

- `techrote/omnipanel` — system orchestration, operator TUI, master/worker scheduling, Race/Diversity execution policy, adjudication, resource scheduling, cross-project architecture.
- `techrote/ansible` — trusted execution kernel and privileged execution-provider primitives. Hard safety policy belongs below Omnipanel.
- `techrote/interloc` — communications, evidence courier, structured capability proposals and Chat-facing integration.
- `techrote/ohmy` — Oh My Pi-specific adapter/harness/compatibility work.
- `techrote/intrallm` — agent-visible reference/task/evidence data. It is not executable authority.

Component repositories remain authoritative for their own internals. Omnipanel owns system-level ADRs, interface compatibility, the cross-project roadmap and end-to-end orchestration policy.

## Product direction

Initial implementation target: Python 3.12+ with a mouse-driven Textual TUI and UI-independent application services suitable for a later web UI.

First-class master directions are Codex and local models. Interloc/Chat is a separately qualified functional bridge. Manual operation can use the same task/proposal surfaces rather than creating a third orchestration architecture.

The execution model supports deterministic trusted workers plus model workers. Speculative groups have two distinct semantics:

- **Race** — optimize time-to-eligible result under a selected completion/cancellation policy.
- **Diversity** — retain independent candidates for comparison, reconciliation or redundancy.

Passing acceptance tests makes a candidate eligible for adjudication; it never grants merge authority by itself.

## Reference corpus

Start with [Agent context](docs/AGENT_CONTEXT.md), then follow the focused route.

Canonical planning documents:
- [Programme handover](docs/PROGRAMME_HANDOVER.md)
- [System architecture](docs/SYSTEM_ARCHITECTURE.md)
- [Project map](docs/PROJECT_MAP.md)
- [Trust model](docs/TRUST_MODEL.md)
- [Orchestration model](docs/ORCHESTRATION_MODEL.md)
- [Metaissue specification](docs/METAISSUES.md)
- [Model policy](docs/MODEL_POLICY.md)
- [Execution providers/resources](docs/EXECUTION_PROVIDERS.md)
- [Pinned component contracts](docs/INTERFACES.md)
- [Verification](docs/VERIFY.md)
- [Roadmap](docs/ROADMAP.md)
- [Blockers and external gates](docs/BLOCKERS.md)
- [Decision register](docs/DECISIONS.md)
- [Planning provenance](docs/PROVENANCE.md)
- [Execution ledger](docs/EXECUTION_LEDGER.md)
- [Machine-readable workflow](docs/workflow.json)
- [Stable-ID issue bindings](docs/issue-bindings.json)

## Current state

This repository is in programme-definition and implementation-decomposition stage. Nine metaissues and 46 child task issues are published. Two stable tasks remain unpublished because the GitHub connector safety check refused their issue creation: OP-018 (Codex master driver) and OP-047 (remote Execution Provider implementation). They remain visible in the workflow/bindings as blocked planning records and are **not** authorized published assignments.

No Omnipanel runtime, worker scheduler, VM control, model-ranking engine or production TUI is claimed yet. Active work in Ansible, Interloc or other repositories is not silently incorporated as completed Omnipanel functionality.
