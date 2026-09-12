# Orchestration model

## Execution strategies

Omnipanel normalizes work into task contracts and may execute them through one of three strategies.

### Single

One selected candidate executes. Appropriate for deterministic workers, tightly bounded jobs, or a specifically requested/master-owned implementation.

### Race

Multiple independent candidates attempt the same bounded contract. The objective is minimum time-to-eligible result, subject to selected cancellation/salvage rules.

A candidate that clears the configured gates becomes a **provisional winner**. Passing never grants commit/merge/deploy authority by itself. Race policy decides whether other candidates are cancelled, salvaged or allowed to finish.

Initial named policy intentions:
- `ask`: pause for user decision after a provisional winner.
- `first-valid-free`: salvage/cancel free workers by default while paid/premium candidates may continue.
- `first-valid-all`: salvage/cancel all non-winners unless task override says otherwise.
- `collect-all`: Race start conditions but no early termination; useful where wall-clock comparison still matters.
- `cost-conscious`: use task value/time/cost/resource estimates to choose continuation.

Project planning may attach per-task overrides before execution. Tasks marked steel, priceless, days, or paid require an explicit user policy decision rather than a global “skip all” shortcut.

### Diversity

Candidates are intentionally allowed to finish so the master/user can compare architecture, implementation quality, independent defect findings, performance and maintainability. Diversity is not a slow Race; completion of multiple candidates is the purpose.

## Test-driven adjudication

The master should define the contract and key acceptance tests before candidate outcomes are known. Tests may have layers:

1. candidate-visible development tests;
2. master-controlled acceptance tests;
3. hidden/adversarial tests unavailable to the candidate environment;
4. invariant gates: allowed paths, Git state, untracked changes, resource ceilings, determinism/conservation/security constraints;
5. independent review requirements derived from load-bearing class.

Tests only prove the tested contract. High-risk Stone/Steel work may require source-level master/reviewer adjudication after all automated gates pass.

## Candidate salvage

Every candidate has a salvage policy. Default cancellation aims to persist an inexpensive package containing:
- candidate/base identity;
- patch/diff or equivalent changed-content manifest;
- changed-file list including untracked files;
- latest targeted/full test status;
- bounded final summary/error state;
- evidence pointers.

Full worktree retention is optional and may use expected value, expected wall time, marginal cost, available storage and remaining uniqueness to decide whether a losing candidate is worth preserving.

## Task dimensions

### Load-bearing

- `tissue`: disposable/minimal verification.
- `labware`: experimental R&D; containment and reproducibility matter, heavyweight independent review may be deferred until promotion.
- `stone`: production engineering; self-verification plus independent review.
- `steel`: systemic dependency; independent review of implementation and verification, with stronger redundancy/adjudication.

`labware` is intentionally not a simple point between tissue and stone. It expresses an R&D mode in which learning rate and experimentation are valuable even when intermediate code is disposable.

### Economics

- `expected_value`: none / low / medium / high / priceless
- `expected_wall_time`: instant / short / medium / long / days
- `marginal_cost`: free / local / low / quota / paid

Later policy may add coarse local-resource estimates. These fields are advisory scheduling signals, not promises of actual duration/value/cost.

## Mad Scientist profile

A first-class Labware profile should enable aggressive exploratory work in strongly isolated environments:
- broad experimental write scope within disposable targets;
- self-check required;
- independent review deferrable;
- Race/Diversity and surplus compute encouraged;
- evidence/salvage retained;
- no automatic production promotion;
- hard security/containment gates unchanged.

Useful outputs are promoted into a new Stone/Steel contract rather than retroactively treating exploratory work as production-verified.

## Surplus compute

Low-value, long-running, free/local speculative work may be scheduled opportunistically when compute would otherwise idle. Surplus jobs are preemptible/cancellable and may not delay higher-priority tasks or consume reserved validation resources.

## Master drivers

Codex and local-model masters are first-class v1 drivers. Interloc/Chat proposals are functional but may remain human-mediated depending on qualified Interloc capability. Masters operate through the same task-contract/adjudication services rather than obtaining bespoke execution authority.
