# Model registry, assessment and eligibility policy

## Scope

Omnipanel needs practical, continuously updated model-selection signals. This is operational decision support, not a scientific benchmark programme and not publication-grade research.

## Canonical identity

Do not rank or ban parsed display names. Each model/provider variant has structured identity fields, for example:

```text
provider_id: openai
model_id: gpt-5.6-sol
display_name: GPT-5.6 Sol
family: gpt-5.6
```

Provider aliases and display names are metadata. Safety/assessment records bind canonical IDs and may explicitly link successor/alias identities after human review.

## Independent dimensions

A model has:
1. safety state;
2. capability/authority eligibility classes;
3. positive/negative qualitative tags;
4. within-tag rank;
5. maturity/confidence;
6. rolling per-model run metrics;
7. full historical evidence references.

Do not collapse these into one global score.

## Tags

Tags are non-exclusive and may be positive or negative. Initial examples, not a frozen vocabulary:

Positive:
- `eye_for_details`
- `dependable`
- `promising`
- `fast`
- `novel_problem_solving`

Negative:
- `poor_convergence`
- `slow_on_broad_tasks`
- `weak_novel_reasoning`
- `instruction_drift`
- `unreliable_self_report`

Task selection can weight tags differently. A fast/dependable model with weak novel reasoning may be excellent for explicit implementation but unsuitable for Labware R&D.

## Qualifiers

Tags may carry structured qualifiers/prefix/suffix metadata such as `maybe`, `veteran`, `new`, `old`, `tempAvail`. Qualifiers are stored separately from display text; no policy logic parses phrases.

Examples rendered to humans:
- `maybe dependable`
- `veteran eye for details`
- `promising tempAvail`

## Rank

Rank is subjective and comparable **only within the same tag**. Numbers are ordinal guidance, not universal capability scores. Ties mean roughly equal current confidence/preferences for that tagged quality.

## Maturity

Separate 1–9 scale:
- 1: day-one / almost no meaningful evidence;
- 2–8: user-calibrated confidence/stability;
- 9: mature first-class assessment suitable as a tiebreaker among otherwise comparable candidates.

High evidence volume may make a model eligible for maturity-9 pinning, but maturity transitions remain explicitly user-calibrated until policy is later refined.

## Rolling evidence

Decision UI emphasizes approximately the most recent 4–24 meaningful runs **per model**, with per-model metrics. Backend preserves complete run/evidence history subject to retention/storage policy. Recent runs receive more decision salience because model/provider behavior changes rapidly.

## Safety states

- active
- quarantined — absolutely unschedulable until intentional human reactivation.
- verboten — permanent ecosystem ban; no scheduler/master/task override may select it and normal UI/API provides no reactivation action.

Future rules may automatically quarantine or mark Verboten after repeated/severe unwanted behavior. Exact grading and thresholds are deliberately deferred until sufficient direct operational experience exists. No automation may reactivate a quarantined/Verboten model.

## Initial qualitative context

The following are handover context, not seeded production scores:
- Big Pickle has shown strong review/problem-solving capability and potentially poor convergence/stopping discipline on broad work.
- Ling 3 showed useful bounded implementation ability but needs independent review and reliable external evidence rather than self-report.
- Nemo 3.5 Lightning showed some valid review ability but missed an important known issue, timed out and created scratch files during a read-only review; treat as experimental/bounded until more evidence.
- Nemo 3 Ultra is intended to be Verboten in this ecosystem based on prior unwanted performance/behavior.

Actual registry initialization and user-confirmed scores/tags are implementation-stage tasks; documentation must not invent precise rankings not explicitly supplied.
