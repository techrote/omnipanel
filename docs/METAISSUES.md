# Metaissue and task-DAG specification

## Purpose

A GitHub issue may represent either a bounded executable task or a higher-level orchestration/review envelope. Omnipanel must not infer type from prose alone.

## Stable identity

Every Omnipanel programme item has a stable ID independent of GitHub numbering:
- `OP-M###` — metaissue
- `OP-###` — bounded child/standalone task

GitHub issue numbers are presentation/coordination identifiers only. The machine-readable workflow manifest binds stable ID to issue number once published.

Issue bodies carry an explicit marker near the top:

```text
Omnipanel-ID: OP-M001
Kind: meta
```

or

```text
Omnipanel-ID: OP-001
Kind: task
```

Labels may mirror type when convenient but are not the source of truth.

## Metaissue semantics

A metaissue defines:
- outcome/acceptance envelope;
- children and their dependency graph;
- concurrency/serialization considerations;
- integration/review responsibilities;
- task policy defaults and mandatory per-task user choices;
- evidence needed to call the parent complete;
- frontier-model integration/audit prompt.

A metaissue may be assigned wholesale to a capable master/frontier model for audit, reconciliation or integration. That does not grant the model additional execution authority; child work remains governed by normal task contracts.

## Child DAG

Children form a directed acyclic graph (DAG), not necessarily a tree. A child may depend on several siblings or on a task in another compatible metaissue. Cycles are invalid and must be rejected by offline planning checks.

Example:

```text
OP-M100
  OP-101 research ----\
  OP-102 implementation A --+--> OP-105 integration
  OP-103 implementation B --/
  OP-104 tests --------------/
```

## Completion

Administrative issue closure never automatically satisfies a dependency or closes a metaissue. Completion requires:
1. required child evidence exists and is reconciled;
2. conditional branches have an explicit pass/no-go/defer result;
3. interface/acceptance conflicts are resolved or recorded as blockers;
4. metaissue-level verification/review has passed;
5. remaining limitations are intentional and documented.

A child may complete with a sound negative result when its contract permits no-go as success.

## Policy inheritance

Metaissues may provide default load-bearing/economic/Race/Diversity/review policy. Children may override explicitly. `steel`, `priceless`, `days` or `paid` tasks require explicit user policy selection during the initial orchestration-preference pass; a bulk skip/default action cannot silently decide them.

## Side repositories/forks

If future experimental work genuinely conflicts with canonical project conventions, a disposable side repository/fork may be created through separately authorized tooling. The metaissue specification should remain stable rather than weakening fundamental conventions to accommodate one exceptional experiment.

## Reconciliation

Workflow tooling must detect:
- duplicate stable IDs;
- missing children/prerequisites;
- dependency cycles;
- issue-number drift;
- closed-without-evidence states;
- incompatible task policy inheritance;
- path/resource lock conflicts where represented.
