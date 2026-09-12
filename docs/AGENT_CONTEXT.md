# Agent context / RAG routes

Use this file as the small retrieval index. Do not ingest every document indiscriminately.

## Universal reading

For any Omnipanel implementation task read:
1. root `README.md`;
2. the assigned GitHub issue/metaissue;
3. `docs/SYSTEM_ARCHITECTURE.md`;
4. `docs/TRUST_MODEL.md`;
5. the focused route below;
6. `docs/VERIFY.md` for the task's required evidence;
7. `docs/workflow.json` for stable IDs/dependencies.

Read `PROGRAMME_HANDOVER.md` when recovering broad intent or joining mid-programme. Read `PROVENANCE.md` when deciding whether a statement is a user requirement, selected design, observed component fact or deferred idea. `DECISIONS.md` is the concise selected-system ADR register.

## Focused routes

| Workstream | Read additionally |
|---|---|
| project foundation, schemas, state | METAISSUES, ORCHESTRATION_MODEL, DECISIONS |
| TUI/application services | SYSTEM_ARCHITECTURE, ORCHESTRATION_MODEL, VERIFY T-ui/T-restart |
| Ansible/execution providers | INTERFACES, EXECUTION_PROVIDERS, TRUST_MODEL |
| master drivers / Interloc | INTERFACES, ORCHESTRATION_MODEL, TRUST_MODEL |
| Race/Diversity/adjudication | ORCHESTRATION_MODEL, TRUST_MODEL, VERIFY T-race/T-diversity/T-adjudication |
| model registry/policy | MODEL_POLICY, TRUST_MODEL, VERIFY T-model |
| resource scheduling/VM pool | EXECUTION_PROVIDERS, ORCHESTRATION_MODEL, VERIFY T-resource/T-provider |
| metaissue/workflow tooling | METAISSUES, ROADMAP, workflow.json, VERIFY T-dag |
| release/security/convergence | all ADRs plus VERIFY and EXECUTION_LEDGER |

## Component lookup rule

Do not copy or assume external component internals from memory. `INTERFACES.md` gives the planning-time pin and authoritative repository. For an integration task, fetch the named component's current qualified contract and compare it with the Omnipanel adapter's supported versions. A newer component commit is not automatically compatible or incompatible.

## Implementation prompt template

Implement stable item `OP-xxx` in `techrote/omnipanel`.

- Confirm prerequisite evidence rather than relying on issue closure.
- Record base SHA and work in an isolated branch/worktree.
- Respect the issue's owned paths and task policy.
- Keep UI-independent services separate from Textual presentation.
- Never widen lower-layer privileges to make an integration convenient.
- Add positive/adversarial deterministic tests and the load-bearing review evidence required by VERIFY.
- If an external live component is unavailable/incompatible, use the defined synthetic fixture path and report the live gate `NOT RUN`; do not fabricate acceptance.
- Finish with a concise evidence report: inputs/base, changed files, commands/results, interface versions, security/invariant review, limitations and evidence paths.

## Metaissue review template

When assigned `OP-Mxxx`, do not reimplement every child blindly. Read the child evidence/DAG, reconcile contract conflicts and missing gates, run or request only the tests necessary for metaissue acceptance, identify administratively closed-but-unproven work, and produce an integration/no-go/blocker decision. A metaissue closes on evidence convergence, not issue count.
