# Omnipanel roadmap and dependency atlas

Plan baseline: 2026-09-14. `workflow.json` owns stable IDs/dependencies; `issue-bindings.json` binds published GitHub numbers. Issue closure is not evidence completion.

## Programme envelopes

| Stable metaissue | GitHub | Outcome |
|---|---:|---|
| OP-M001 | #1 | foundation, schemas, durable state, app services, DAG/readiness, interface registry |
| OP-M002 | #2 | mouse-driven Textual operator application |
| OP-M003 | #3 | component adapters, Execution Provider boundary and explicit provider qualification semantics |
| OP-M004 | #4 | master drivers and proposal channels |
| OP-M005 | #5 | Race, Diversity, acceptance/adjudication and cancellation/salvage |
| OP-M006 | #6 | model registry, rolling assessment and safety eligibility |
| OP-M007 | #7 | local resource scheduling and isolated worker pools |
| OP-M008 | #8 | workflow audit, resilience, security, provider-diversity qualification, test reliability, branch hygiene, performance and v1 convergence |
| OP-M009 | #9 | deferred web/remote/volatile-storage extensions |

## Delivery sequence

### Stage A — trustworthy substrate

Start OP-001 (#10). Then OP-002 (#11). After OP-002, OP-003 (#12) and OP-005 (#14) can proceed independently. OP-004 (#13) and OP-006 (#15) depend on the durable/schema foundation.

Expected result: headless Omnipanel services, durable state, evidence-aware DAG/readiness and versioned component-interface semantics.

### Stage B — first useful operator + synthetic single-run path

Once application services exist, OP-007 (#16) establishes the Textual shell. OP-008 (#17) and OP-009 (#18) can proceed in parallel. The first component integration work begins fixture-first with OP-012 (#21), while model identity starts at OP-027 (#35) and resource inventory after OP-014 at OP-032 (#40).

OP-017 (#26) establishes the generic master interface. OP-019 (#27) supplies the publishable first-class local-model driver path. OP-018 (Codex driver) is currently **unpublished/connector-blocked**; its absence must not be disguised by a guessed issue number.

OP-038 (#46) is the single-run MVP convergence gate. Its live/synthetic composition must be reported honestly.

### Stage C — speculative orchestration

OP-021 (#29) Race and OP-022 (#30) Diversity may proceed together after the generic provider/master contracts. OP-023 (#31) acceptance gates can proceed independently and then unlock OP-024 (#32) reviewer topology. OP-025 (#33) cancellation/salvage and OP-026 (#34) named policy profiles converge these paths.

Model assessment OP-028/#36 and OP-029/#37 can proceed beside the speculative state machines once OP-027 exists. OP-030/#38 hardens quarantine/Verboten before model-advisory OP-031/#39.

OP-039 (#47) is the Race/Diversity MVP integration gate.

### Stage D — local worker pools and hardening

OP-032/#40 resource reservations -> OP-033/#41 pool lifecycle. OP-034/#42 live Hyper-V/Ubuntu qualification waits for both a qualified Ansible contract and VM primitives. OP-035/#43 surplus compute is deliberately later because it depends on Race/Diversity and model-policy correctness.

OP-036/#44 is design-only volatile scratch planning; no RAMDisk implementation is on the v1 critical path.

OP-049/#76 defines explicit cross-provider qualification/evidence semantics after the generic provider and Windows validation adapter exist. It does not replace OP-013/#22 live Ansible qualification or OP-034/#42 Hyper-V/Ubuntu qualification. OP-050/#77 then adversarially exercises materially different provider shapes through the generic boundary and records unavailable live paths as `NOT RUN`.

OP-051/#78 is a focused reliability task for the observed Textual programme-policy timing flake. OP-052/#79 establishes conservative, dry-run-first branch lifecycle/pruning so merged/superseded refs can be removed without risking active or unique work. These two can proceed independently of provider qualification.

OP-040/#48 restart, OP-041/#49 independent security and OP-042/#50 performance can proceed after their respective MVP prerequisites. OP-043/#51 is the final v1 whole-system convergence audit; OP-M008/#8 itself does not close until its complete child evidence, including OP-050–OP-052, is reconciled.

### Stage E — deferred extensions

OP-044/#52 web-facing service contract -> OP-045/#53 web prototype.
OP-046/#54 remote-provider protocol shape is design-only until v1 is stable. OP-047 remote-provider implementation is **unpublished/connector-blocked**.
OP-048/#55 may implement RAMDisk/tmpfs acceleration only after measurements justify it.

## Safe concurrency principles

- Separate worktrees/branches and recorded base SHA for independent issues.
- Shared schemas/state migrations/application composition require coordination even when implementation files differ.
- TUI work may proceed against deterministic fixtures while live component adapters are externally gated.
- Model registry/metrics and speculative execution can progress in parallel until model-selection integration.
- Resource scheduling can use fake providers before Hyper-V/Ansible live qualification, but synthetic provider success must remain visibly distinct from live qualification.
- Branch cleanup must preserve default/protected refs, open-PR heads and any unique/unmerged history; names alone are never deletion evidence.
- Deferred metaissue OP-M009 is not part of v1 readiness.

## Mandatory user-policy pass

When a target project is imported/planned, Omnipanel should allow bulk defaults/skip for ordinary optional choices but require explicit user choices for tasks marked any of:
- `load_bearing = steel`
- `expected_value = priceless`
- `expected_wall_time = days`
- `marginal_cost = paid`

Per-task Race/Diversity/cancellation/review overrides are expected and survive as durable policy evidence.

## Publication blockers

See `issue-bindings.json` for exact records. OP-018 and OP-047 have no GitHub issue because the connector safety check refused their publication. Their stable workflow records remain planning context, not executable/published assignments.

## Definition of programme completion

Metaissues close only after child evidence is reconciled. V1 is not complete from green unit tests alone: OP-M008/#8 requires end-to-end, restart, security, resource/performance, provider-diversity and compatibility review, with unavailable live integrations explicitly distinguished from synthetic coverage. Known CI flakes and branch-lifecycle hazards must be classified and reconciled rather than normalized by reruns or ad-hoc cleanup.
