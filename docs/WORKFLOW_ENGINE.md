# OP-005 workflow and readiness engine

Status: OP-005 implementation contract, workflow schema generation 1.

`src/omnipanel/workflow.py` loads and validates the repository's machine-readable
`docs/workflow.json` and `docs/issue-bindings.json`, then exposes evidence-aware task
readiness and metaissue completion queries. It is a pure planning/readiness layer: it
does not persist state, contact GitHub, start workers, call providers or mutate issues.

## Authority and identity

Stable `OP-###` task IDs and `OP-M###` metaissue IDs are authoritative. GitHub issue
numbers are presentation/coordination bindings only. Changing an issue number does not
change graph identity, evidence identity or dependency semantics.

A binding with `null` means the task is intentionally unpublished. The default readiness
query fails closed for an unpublished task. `allow_unpublished=True` exists only for
offline planning/audit views; it does not publish or authorize the task.

## Manifest validation

Generation 1 requires exact integer `schema_version = 1`. Models are immutable and reject
unknown fields. Validation rejects:

- duplicate task or metaissue IDs;
- duplicate child membership;
- missing children or prerequisites;
- tasks with no metaissue membership or membership in more than one metaissue;
- direct self-dependencies and general dependency cycles;
- invalid stable-ID forms;
- unresolved or internally incompatible inherited policy;
- duplicate GitHub issue-number bindings;
- binding sets that drift from the stable IDs in the manifest;
- `null` task bindings without a matching publication-block record.

Dependencies may cross metaissue boundaries. Metaissues organize outcome/review envelopes;
they do not impose a tree restriction on the task DAG.

## Policy inheritance

A metaissue may carry `policy_defaults`. A task may carry `policy_overrides`; the existing
compact `load_bearing` task field remains an explicit task-level override. Resolution is:

1. metaissue defaults;
2. fields explicitly present in `policy_overrides`, including an explicit `null` used to
   clear an inherited optional value;
3. the task's compact `load_bearing` field.

The merged result is revalidated through OP-002 `TaskPolicyDefaults`. Incompatible
inheritance, such as inheriting a Race policy and overriding only the strategy to Single,
fails rather than being guessed or silently repaired. Every task must resolve a
`load_bearing` value.

## Evidence versus administrative state

GitHub closure is not completion evidence. `TaskEvidence.issue_closed` is retained only so
an audit/readiness view can expose the mismatch. A dependency is satisfied only by a
reconciled terminal evidence disposition.

Terminal dispositions are:

- `pass`;
- `no-go`;
- `deferred`.

`no-go` and `deferred` require an explicit note as well as `evidence_reconciled = true`.
The producer of reconciled evidence is responsible for emitting those terminal negative
results only when the task contract permits them; OP-005 does not invent permission from
issue prose. `pending` and `blocked` do not satisfy dependencies.

## Readiness truth table

| Condition | Complete | Ready | Result |
|---|---:|---:|---|
| reconciled terminal evidence exists | yes | no | task already complete |
| prerequisite lacks reconciled terminal evidence | no | no | blocked with predecessor ID |
| task has required external gate not supplied | no | no | blocked with gate name |
| GitHub issue is closed but completion evidence is absent | no | no | reconciliation required |
| task binding is `null` | no | no | unpublished by default |
| task is marked `deferred` | no | no | deferred by default |
| all prerequisites/effects gates satisfied and no completion evidence yet | no | yes | executable/plannable frontier |

Deferred and unpublished tasks can be included explicitly for planning/audit snapshots;
those switches do not alter the manifest or confer runtime authority.

## External gates

A task with `external_gate` is not ready until the caller supplies that exact gate in the
`satisfied_external_gates` set. Gate satisfaction is an explicit input rather than being
inferred from component availability, issue comments or nearby task completion.

Examples in the checked-in workflow include qualified Ansible, Ohmy, Interloc and VM
prerequisites.

## Metaissue completion

A metaissue is complete only when:

1. every direct child has reconciled terminal evidence; and
2. the caller records `review_reconciled = true` for the metaissue-level review.

Closing the metaissue or all of its GitHub child issues is intentionally insufficient.
This matches `docs/METAISSUES.md`: administrative state and evidence state are distinct.

## Public API

Primary entry points:

- `WorkflowEngine.from_paths(manifest_path, bindings_path)`;
- `WorkflowEngine.evaluate_task(...)`;
- `WorkflowEngine.readiness_snapshot(...)`;
- `WorkflowEngine.metaissue_completion(...)`;
- `WorkflowEngine.resolved_policy_defaults(...)`;
- `WorkflowEngine.issue_for(...)`;
- `load_workflow_manifest(...)` and `load_issue_bindings(...)` for lower-level tooling.

The engine returns immutable result objects with explicit reasons so later OP-004 services,
OP-007/OP-008 TUI views and OP-037 auditors can consume the same semantics without
reimplementing graph rules.

## Scope boundary

OP-005 does **not** provide:

- OP-003 durable storage or migrations;
- OP-004 event/application services;
- GitHub polling or issue mutation;
- scheduler/provider execution;
- credential or capability handling;
- OP-006 component compatibility negotiation;
- proof that a live external gate is qualified;
- automatic approval of negative outcomes.

Tests use the checked-in programme graph plus synthetic mutations to verify cycles,
duplicates, missing edges/membership, policy inheritance, binding drift, cross-metaissue
DAG edges, administrative-closure mismatch, external gates, deferred/unpublished tasks,
stable issue renumbering and metaissue evidence/review completion.
