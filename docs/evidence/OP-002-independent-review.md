# OP-002 independent Steel review

Date: 2026-09-13
Issue: #11 / OP-002
Implementation PR: #57
Reviewed implementation head: `0d17384b09f066a8b8e4529d2702bdf25455ad3a`
Reviewed merge commit: `ec84474b72169cf8dfc246213c98d0f49547d73a`
Post-merge Foundation CI: run `34730186538`

## Review status

**PASS with procedural reconciliation note.**

The OP-002 implementation satisfies the issue's Steel implementation and verification criteria on the exact code merged to `main`. No correctness, authority-broadening or schema-contract defect requiring a code change was found in this review.

PR #57 was merged before the independent Steel review lanes were durably recorded. This document is therefore a retrospective independent review of the exact merged tree rather than evidence that the review happened before merge. The sequencing error is recorded explicitly rather than rewritten as if the gate had run earlier.

## Independent implementation review

The review inspected the merged implementation directly rather than relying on the implementer's acceptance narrative.

### Versioning and closed-world validation

- `VersionedRecord` requires the exact integer schema generation `1`; strings, booleans, floats and future versions are rejected.
- All contract models inherit immutable `extra="forbid"` configuration.
- Top-level records carry closed `record_type` discriminators.
- Authoritative IDs are structurally separate from display text and aliases.

### Identity, DAG and collection invariants

- Stable project/task/metaissue identifiers are bounded and pattern-constrained.
- Task prerequisites reject self-dependency and duplicates.
- `DagEdge` rejects direct self-edges; general cycle detection remains correctly deferred to OP-005.
- Identity-bearing and evidence/reference collections reject duplicates where ambiguity would matter.

### Policy and authority invariants

- Stone requires an independent implementation review.
- Steel requires independent implementation and verification review counts plus consequential-promotion user adjudication.
- Steel/priceless/days/paid policy remains undecided until a structured user decision exists.
- Provider requests are fail-closed by default: no network, no writable paths, no capabilities, zero resources and isolation required.
- Resource units are explicit and strictly typed.
- Hidden-test gates must be master-only and require independent evaluator context.

### Model and worker safety

- Model identity is canonical provider/model identity rather than display text.
- Only `active` model assessments are automatically schedulable; quarantined and Verboten states fail closed.
- Worker authority class is modeled separately from model identity.
- Deterministic workers cannot carry a model identity and model workers require one.

### Run, evidence and cancellation semantics

- Single, Race and Diversity have distinct structural invariants; Race requires an explicit named policy.
- A selected candidate must belong to its run.
- Test evidence counts must add up and timestamps require timezone information.
- Cancellation/containment and salvage semantics require attributable evidence or an explicit no-salvage reason, with containment deliberately treated as the emergency exception.

### Scope control

The implementation remains a contract layer. It does not smuggle in OP-003 persistence, OP-004 services, OP-005 readiness, OP-006 compatibility negotiation, provider effects, credentials or production TUI behavior.

## Independent verification review

The adversarial/round-trip suite was read against the implementation. It covers, among other cases:

- checked-in representative record round trips;
- unknown/coerced schema-version rejection;
- extra-field rejection;
- strict resource typing and fail-closed provider defaults;
- hidden-gate separation;
- Stone/Steel review floors and explicit human-decision behavior;
- Race-policy leakage/inference failures;
- display text not acting as identity;
- task/DAG self-reference and duplicate rejection;
- model safety scheduling behavior;
- worker/model identity consistency;
- evidence timestamp/count invariants;
- Single/Race/Diversity structural rules;
- selected-candidate membership;
- cancellation/salvage/containment rules;
- model immutability and generated closed JSON Schema.

The merge commit `ec84474b72169cf8dfc246213c98d0f49547d73a` triggered Foundation CI run `34730186538`. GitHub reports six jobs covering Windows and Ubuntu on Python 3.12, 3.13 and 3.14. All six completed successfully. The jobs include editable installation, Ruff lint, Ruff formatting check, strict mypy, unit/boundary/headless Textual tests, sdist/wheel build, clean dependency-complete wheel installation and retained evidence.

This post-merge run independently establishes that the merged tree, not merely the pre-merge candidate SHA, passed the repository matrix.

## Findings

No blocking code findings.

One process finding is retained: PR #57 merged before the two independent Steel review lanes were durably recorded. The remedy is this exact-tree retrospective review plus explicit reconciliation; it is not appropriate to rewrite history or pretend the sequencing was correct.

## Acceptance mapping

- round-trip and adversarial validation tests: **PASS**
- unknown versions/extra invalid fields fail deliberately: **PASS**
- identity and policy invariants documented: **PASS**
- orchestration/model/metaissue examples representable: **PASS** via checked-in fixtures and targeted tests
- no security-sensitive default silently broadens authority: **PASS**
- independent implementation review: **PASS (retrospective exact-tree review)**
- independent verification review: **PASS (retrospective exact-tree review + merge CI)**

OP-002 is suitable for reconciliation and closure once the procedural note and merged evidence are recorded in the canonical ledger.
