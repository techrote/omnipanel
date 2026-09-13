# OP-002 core schema contracts

Status: OP-002 implementation contract, schema generation 1.

These models are the UI-independent typed boundary for Omnipanel tasks, runs, evidence and policy. They deliberately define data contracts, not durable storage, DAG readiness, scheduling, provider execution, component negotiation or the OP-007 TUI.

The implementation is in `src/omnipanel/domain/contracts.py`. Top-level records inherit `VersionedRecord` and carry both a closed `record_type` discriminator and `schema_version = 1`. Pydantic models reject unknown fields and invalid enum values rather than guessing semantics.

## Contract inventory

| Area | Top-level records | Important nested contracts |
|---|---|---|
| Programme identity | `ProjectRecord`, `MetaissueRecord`, `TaskRecord`, `DagEdge` | `TaskPolicyDefaults` |
| Task policy | `TaskRecord` | `TaskPolicy`, `EconomicDimensions`, `ReviewPolicy`, `UserPolicyDecision` |
| Provider/resource request | task-owned `ProviderRequest` | `ResourceRequest` |
| Acceptance/adjudication | task/candidate records | `AcceptanceGate`, `GateResult` |
| Actors | `MasterIdentityRecord`, `WorkerIdentityRecord`, `CandidateIdentityRecord` | `ModelRef` |
| Runs | `RunRecord`, `CandidateRecord` | `CancellationOutcome` |
| Evidence | `EvidenceDescriptorRecord` | `EvidenceProducer`, `TestSummary` |
| Component contracts | `ComponentContractIdentityRecord` | `ComponentContractRef` |
| Model identity/assessment | `ModelIdentityRecord`, `ModelAssessmentRecord` | `ModelRef`, `ModelTagAssessment` |

The checked-in synthetic examples are `tests/fixtures/op002_examples.json`. They are data-only and contain no credentials or executable provider payloads.

## Identity rules

Authoritative IDs are separate from display text.

- task IDs use the stable programme form such as `OP-001`;
- metaissue IDs use the stable form such as `OP-M001`;
- project, run, candidate, worker, provider, component and evidence IDs are bounded opaque identifiers;
- model identity is the structured pair `provider_id` + `model_id`;
- component contract identity is the structured triple `component_id` + `contract_id` + `contract_version`.

Display names and aliases are metadata. Renaming `display_name` cannot change any authoritative identity field. The schemas never infer IDs by parsing Markdown or UI labels.

Collections that participate in identity or dependency relationships reject duplicates. `TaskRecord` rejects self-dependencies and `DagEdge` rejects direct self-edges. General cycle detection and evidence-aware readiness remain OP-005 responsibilities.

## Versioning and migration boundary

Generation 1 records require the exact integer:

```json
{"schema_version": 1}
```

`2`, `"1"`, `true`, unknown record fields and unknown enum values fail validation. A future schema generation must be selected and migrated explicitly from the raw versioned payload before constructing the then-current typed record. Current readers must not reinterpret a future version as generation 1.

The version field is therefore a fail-closed migration hook, not a claim that migration code already exists. Durable state/migration implementation belongs to OP-003.

## Task policy invariants

`TaskPolicy` is a resolved policy snapshot. It models:

- load-bearing: `tissue`, `labware`, `stone`, `steel`;
- expected value: `none`, `low`, `medium`, `high`, `priceless`;
- expected wall time: `instant`, `short`, `medium`, `long`, `days`;
- marginal cost: `free`, `local`, `low`, `quota`, `paid`;
- execution strategy: `single`, `race`, `diversity`;
- the named Race policies: `ask`, `first-valid-free`, `first-valid-all`, `collect-all`, `cost-conscious`;
- self-check, independent implementation review, independent verification review and consequential-promotion/user adjudication requirements.

A Race requires an explicit named Race policy. Single and Diversity records reject a Race policy.

Review floors are enforced by the schema:

- Stone requires at least one independent implementation review.
- Steel requires at least one independent implementation review, at least one independent verification review and explicit user adjudication before consequential promotion.

The planning rule that `steel`, `priceless`, `days` or `paid` requires an explicit user choice is represented without granting authority by default. Such a `TaskPolicy` can exist with `user_decision = null`, but `is_execution_policy_decided()` remains false. A later scheduler/readiness service must refuse execution until a human decision record exists.

`TaskPolicyDefaults` is intentionally partial so a metaissue can represent inherited defaults. It is not an execution authorization.

## Fail-closed authority and provider requests

`ProviderRequest` is a request, never a grant. Defaults are deliberately restrictive:

- no required capability handles;
- no writable paths;
- no network access;
- isolation required;
- zero resource reservation.

Resource quantities use explicit integer units: CPU millicores, MiB memory, MiB storage, seconds of wall time and GPU count. String/boolean coercions are rejected for those fields.

The schemas contain capability *handles*, not credential material. There are no token/password/secret fields. Lower-layer providers remain responsible for installed capabilities, credentials and hard limits.

## Acceptance and evaluator separation

Acceptance gates distinguish candidate-visible and master-only material. A `hidden-test` gate is invalid unless it is both:

- `master-only`; and
- marked as requiring an independent evaluator context.

This encodes the candidate/evaluator separation without embedding evaluator implementation details or hidden assets in the task record.

Gate outcomes are explicit `pass`, `fail` or `not-run`; unavailable verification must not be serialized as a pass.

## Run semantics

`RunRecord` represents the three selected strategies directly:

- Single: exactly one candidate and no Race policy.
- Race: two or more candidates and an explicit named Race policy.
- Diversity: two or more candidates and no Race early-termination policy.

A selected candidate must belong to the run. Passing gates and selecting a candidate remain distinct concepts; neither field implies merge/deploy authority.

`CandidateRecord` keeps candidate state separate from worker/model identity and may reference gate/evidence results.

## Cancellation, containment and salvage

`CancellationOutcome` distinguishes normal policy/user/provider/preemption cancellation from emergency containment.

For normal cancellation, `salvage_level = "none"` requires an explicit reason why salvage was unavailable. Retained `minimal` or `full-worktree` salvage requires evidence references. Emergency containment may legitimately retain no salvage because containment outranks cooperative cleanup.

This is only the result contract. Cancellation state machines and provider effects belong to later issues.

## Model identity, assessment and safety

`ModelIdentityRecord` uses structured provider/model IDs. Display names and aliases cannot act as policy keys.

`ModelAssessmentRecord` keeps independent dimensions separate:

- safety state;
- capability classes;
- positive/negative tags;
- per-tag ordinal rank;
- structured qualifiers;
- maturity 1–9;
- up to 24 recent evidence references.

Tags are not a frozen vocabulary; the examples from `MODEL_POLICY.md` are representable, including `eye_for_details`, `poor_convergence`, `maybe`, `veteran` and `tempAvail`. Rank lives on a tag assessment and there is no global model rank.

`active` is the only state that `is_automatically_schedulable()` reports as schedulable. Both `quarantined` and `verboten` return false. The record intentionally exposes no automatic reactivation field or task-level safety override.

Full historical evidence belongs in the later durable evidence/state layer; the assessment record carries the bounded recent decision window.

## Component contract identity

`ComponentContractIdentityRecord` records a component/contract/version triple, authoritative repository, source commit and qualification-evidence references. It does not decide whether a presented component version is supported.

OP-006 owns the compatibility registry and fail-closed negotiation. OP-002 provides the unambiguous identity fields needed for that later decision and deliberately does not guess compatibility from source commit or display text.

## Scope boundaries

OP-002 does **not** implement:

- durable state or migrations (OP-003);
- UI-independent application services/event model (OP-004);
- DAG cycle/readiness engine (OP-005);
- component compatibility negotiation (OP-006);
- production TUI architecture (OP-007);
- worker/provider scheduling or effects;
- live Ansible, Interloc, Ohmy or intrallm integration;
- credential storage;
- automatic model quarantine/Verboten thresholds.

Tests should therefore establish schema representation and invariants without treating these downstream behaviours as complete.
