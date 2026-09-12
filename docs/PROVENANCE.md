# Planning provenance and requirement reconciliation

Baseline date: 2026-09-12.

Use these classes:
- **R** user requirement
- **P** user preference
- **D** selected design
- **F** observed component fact
- **A** assumption to verify
- **O** optional/deferred idea

## Reconciled requirements

- R: build a flexible architecture with remote-shell-like capability while retaining deterministic and configurable security/isolation gates.
- R: use Omnipanel for system orchestration/control and system-level planning rather than create another meta repository.
- R: preserve Ansible as the trusted execution kernel and Interloc as communications/evidence plane; use Ohmy for OMP-specific work and intrallm as inert reference/task data.
- R: initial Omnipanel implementation is Python 3.12+ with a mouse-driven Textual TUI; later web UI should reuse UI-independent services.
- R: Codex and local-model masters are first-class; Chat/Interloc is a functional bridge.
- R: Race and Diversity are distinct initial orchestration primitives with per-task policy overrides.
- R: cancelled candidates should normally leave cheap salvage evidence; continuation/cancellation may consider expected value, wall time and marginal cost.
- R: deterministic trusted workers are preferred when an exact deterministic capability exists.
- R: model assessment is operational, rolling and multidimensional rather than a publication-quality benchmark programme.
- R: positive and negative tags are independent; within-tag rank has no cross-tag meaning; maturity is separate.
- R: quarantine forbids all automated scheduling until deliberate human reactivation; Verboten is permanently banned through normal ecosystem controls.
- R: task load-bearing classes include tissue, labware, stone and steel; Labware supports a deliberate Mad Scientist R&D profile.
- R: metaissues contain bounded child DAGs and can be handed to a frontier model for whole-envelope audit/integration.
- R: metaissue completion is evidence-based, not administrative child closure.
- R: Omnipanel cross-project integration should use pinned/versioned contracts and fail safe on incompatible semantics.
- R: Ansible should own privileged VM/container primitives while Omnipanel owns allocation/scheduling policy.
- R: remote-worker implementation and RAMDisk/tmpfs optimization are deferred but their architectural shape should not be blocked.

## Selected design versus deferred calibration

Selected now:
- component ownership boundaries;
- fail-closed interface compatibility;
- task/metaissue identity structure;
- Race/Diversity distinction;
- load-bearing/economic dimensions;
- model safety-state semantics;
- worker/provider responsibility split;
- Python/Textual v1 stack;
- initial Windows/Hyper-V + Ubuntu-LTS provider direction.

Deliberately deferred:
- exact automatic quarantine/Verboten thresholds;
- final tag vocabulary and rank methodology;
- exact maturity transition rules beyond the 1–9 intent;
- numeric wall-time/value/cost thresholds;
- RAMDisk size/layout policy;
- remote-worker transport protocol;
- NUMA/resource optimization for the future 18-core Xeon host.

## Observed repository facts at planning intake

- `techrote/omnipanel` was empty before this publication run.
- Published Ansible main observed at `9f27ca4f4c9317ed8246851f2961adc8bdb2de74`; its published slot schema is an early prototype.
- Published Interloc main observed at `491be0104df52b2b9307e7662b2bcb8d6467d169`; planning is mature but runtime implementation has not started, and some integration publication is explicitly blocked.
- `techrote/ohmy` was empty.
- Published intrallm main observed at `01ddd0c1d39cde95f0b73090e1b0236209a287a9`.

## Important empirical lessons incorporated

- Big Pickle produced useful engineering/review work in earlier tasks but showed severe late-stage recursive debugging/convergence risk on broad Ansible work.
- A Big Pickle OMP attempt was not an engineering failure: provider calls repeatedly returned 429 FreeUsageLimitError and the controller misclassified retry exhaustion as a successful terminal lifecycle. This motivates strict backend error normalization in Ohmy and evidence-based run status in Omnipanel.
- Nemo 3.5 Lightning produced some valid review observations but missed a known important defect, timed out and created untracked scratch files during a read-only probation. This motivates capability-bounded workers, untracked-file invariant checks and rolling task-specific model assessment.
- CyberSand issue reconciliation demonstrated that administrative closure can diverge from substantive completion. Omnipanel metaissues therefore depend on evidence, not GitHub state alone.

## Non-authority note

This document preserves design provenance; it does not override a component's current implementation facts. When cross-project intent conflicts with a component's newer qualified contract, the integration must be reconciled explicitly rather than silently assuming this baseline still applies.
