# Architecture decision register

Status: selected planning baseline, 2026-09-12. Later amendments require evidence and explicit update; component-local decisions remain in component repos.

| ADR | Decision | Consequence |
|---|---|---|
| OP-ADR-01 | Omnipanel is the system-level orchestration/control-plane product and programme-integration home. | No separate fifth “meta planning” repo is required. |
| OP-ADR-02 | Component repos own internals; Omnipanel owns cross-project contracts, compatibility and roadmap. | Avoid duplicated/stale component manuals. |
| OP-ADR-03 | Python 3.12+ and Textual are the v1 implementation/UI stack. | Fast iteration and mouse-driven TUI; backend services stay UI-independent for later web UI. |
| OP-ADR-04 | Ansible remains the trusted execution kernel; Omnipanel schedules through it. | Privileged provider operations and hard limits stay below flexible orchestration. |
| OP-ADR-05 | Interloc remains communications/evidence/proposal plane. | It does not become the scheduler or universal execution authority. |
| OP-ADR-06 | Ohmy owns Oh My Pi-specific runtime adaptation. | OMP compatibility/error semantics do not leak into generic orchestration. |
| OP-ADR-07 | intrallm is inert reference/task/evidence data. | Data refresh cannot introduce executable runners/policy. |
| OP-ADR-08 | Interface contracts are pinned/versioned and incompatible integrations fail closed. | Availability may be reduced temporarily; authority semantics are never guessed. |
| OP-ADR-09 | Codex and local-model master drivers are first-class; Interloc bridge is functional/gated. | Master logic uses normalized task services rather than bespoke authority paths. |
| OP-ADR-10 | Race and Diversity are distinct first-milestone orchestration primitives. | Race permits early provisional winner/cancellation policy; Diversity deliberately retains alternatives. |
| OP-ADR-11 | Passing tests creates an eligible candidate, not merge authority. | Master/user adjudication and load-bearing review requirements remain explicit. |
| OP-ADR-12 | Task policy includes load-bearing plus expected value/wall-time/marginal-cost dimensions. | Quality gates and compute economics are separable. |
| OP-ADR-13 | `labware` and Mad Scientist are first-class R&D modes. | Exploration can be fast/contained without production-grade review at every intermediate step. |
| OP-ADR-14 | Metaissues contain bounded child DAGs and close on reconciled evidence. | Administrative child closure does not prove parent completion. |
| OP-ADR-15 | Deterministic trusted workers are preferred where an exact deterministic capability exists. | “Zeroth-class” refers to reliability/ownership, not intellectual ranking. |
| OP-ADR-16 | Model assessment is multidimensional: safety state, capability class, tags, within-tag rank, maturity and rolling metrics. | No universal leaderboard; positive and negative traits coexist. |
| OP-ADR-17 | Quarantine blocks all automation until human reactivation; Verboten is permanent through normal orchestration. | No fallback, rank update or master override can silently restore eligibility. |
| OP-ADR-18 | Omnipanel stores capability references, not a universal set of raw credentials. | Reduce central privileged blast radius. |
| OP-ADR-19 | Windows 11/Hyper-V is the reference host direction; Ubuntu LTS is an initial Linux provider image only. | Provider protocol remains distro-neutral and remote execution can be added later. |
| OP-ADR-20 | UI components never own durable execution lifetimes. | TUI restart/panel changes cannot implicitly kill work. |
| OP-ADR-21 | Cancellation salvages cheap evidence when safe; containment outranks salvage. | Unsafe workers may be terminated without cooperative cleanup. |
| OP-ADR-22 | Candidate acceptance is an independent execution/security boundary. | Hidden tests/evaluator assets remain separate from candidate environments. |
| OP-ADR-23 | RAMDisk/tmpfs optimization and remote-worker transport are deferred. | Preserve architecture hooks without premature implementation complexity. |
