# Omnipanel roadmap and dependency atlas

Plan baseline: 2026-09-15. `workflow.json` owns stable IDs/dependencies; `issue-bindings.json` binds published GitHub numbers. Issue closure is not evidence completion.

## Programme envelopes

| Stable metaissue | GitHub | Outcome |
|---|---:|---|
| OP-M001 | #1 | foundation, schemas, durable state, app services, DAG/readiness, interface registry |
| OP-M002 | #2 | mouse-driven Textual operator application with provenance-correct resource/provider qualification views |
| OP-M003 | #3 | component adapters, Execution Provider boundary and explicit provider qualification semantics |
| OP-M004 | #4 | master drivers and proposal channels |
| OP-M005 | #5 | Race, Diversity, acceptance/adjudication and cancellation/salvage |
| OP-M006 | #6 | model registry, rolling assessment and safety eligibility |
| OP-M007 | #7 | local resource scheduling and isolated worker pools |
| OP-M008 | #8 | workflow audit, resilience, security, provider-diversity qualification, RAG/status freshness, CI/runtime and protected-main promotion, explicit readiness authority, test reliability, branch hygiene, performance and v1 convergence |
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

OP-051/#78 is a focused reliability task for the observed Textual programme-policy timing flake. OP-052/#79 establishes conservative, dry-run-first branch lifecycle/pruning so merged/superseded refs can be removed without risking active or unique work.

OP-053/#81 removes obsolete live-status prose from universal RAG surfaces and establishes explicit freshness/status-source semantics. OP-054/#82 follows OP-010 and OP-049 so the resource dashboard cannot inherit qualification by provider ID alone and instead consumes exact provider identity/interface/evidence semantics. OP-055/#83 migrates Foundation CI away from the deprecated Node-20 action runtime while retaining immutable SHA pins and artifact evidence.

OP-056/#85 moves consequential promotion enforcement into the GitHub control plane: `main` must be protected against routine direct mutation, force-push/deletion and non-green promotion without turning the single-account/agent-review model into a deadlock. It also audits CI concurrency so canonical post-merge evidence is not silently cancelled by rapid successive merges. OP-057/#86 hardens readiness itself: negative terminal task dispositions require explicit task-contract permission, and external gates require typed provenance/evidence rather than caller-supplied display strings.

OP-040/#48 restart, OP-041/#49 independent security and OP-042/#50 performance can proceed after their respective MVP prerequisites. OP-043/#51 remains the final v1 whole-system convergence audit and explicitly waits for OP-050/#77 through OP-057/#86 where those tasks are non-deferred prerequisites.

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
- Resource/provider UI qualification projections must bind to exact provider identity/version/interface evidence; provider ID alone is not sufficient qualification provenance.
- Universal RAG/current-status prose must either derive from one explicit status source or carry unmistakable point-in-time semantics; duplicated hand-maintained task state is not authoritative.
- Third-party CI actions remain immutable-SHA pinned and must use GitHub-supported action runtimes; evidence retention is part of the verification contract.
- Canonical `main` promotion is expected to use the reviewed PR/check path. Until OP-056 live protection is verified, the absence of hosting-layer enforcement is an explicit blocker rather than permission to normalize direct pushes.
- A negative task disposition or external-integration assertion must not release downstream work merely because a caller supplies a note/string; OP-057 makes that authority machine-readable and fail-closed.
- Branch cleanup must preserve default/protected refs, open-PR heads and any unique/unmerged history; names alone are never deletion evidence.
- Deferred metaissue OP-M009 is not part of v1 readiness.

## Mandatory user-policy pass

When a target project is imported/planned, Omnipanel should allow bulk defaults/skip for ordinary optional choices but require explicit user choices for tasks marked any of:
- `load_bearing = steel`
- `expected_value = priceless`
- `expected_wall_time = days`
- `marginal_cost = paid`

Per-task Race/Diversity/cancellation/review overrides are expected and survive as durable policy evidence. OP-041 independently verifies that a prior decision cannot be replayed onto a materially changed consequential policy snapshot.

## Publication blockers

See `issue-bindings.json` for exact records. OP-018 and OP-047 have no GitHub issue because the connector safety check refused their publication. Their stable workflow records remain planning context, not executable/published assignments. OP-057 must make any permitted negative/deferred reconciliation path for such dependencies explicit in the task contract rather than relying on globally terminal `DEFERRED` semantics.

## Definition of programme completion

Metaissues close only after child evidence is reconciled. V1 is not complete from green unit tests alone: OP-M008/#8 requires end-to-end, restart, security, resource/performance, provider-diversity and compatibility review, with unavailable live integrations explicitly distinguished from synthetic coverage. Provider qualification presentation must preserve exact provenance; universal RAG/current-status surfaces must not contradict merged evidence; CI action runtimes must be supported with retained evidence verified; canonical promotion controls must be live and verified; task-completion/external-gate readiness authority must be explicit and provenance-bearing; known CI flakes and branch-lifecycle hazards must be classified and reconciled rather than normalized by reruns or ad-hoc cleanup.
