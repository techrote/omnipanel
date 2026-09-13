# Omnipanel

Omnipanel is the system-level orchestration and operator-control project for the techrote agent-tooling ecosystem.

Its job is to decide **what should run, where, with which workers, under which evidence and review policy**. It does not replace the trusted execution kernel, communications broker, model-runtime adapters, or agent-visible reference plane.

## Ecosystem boundary

- `techrote/omnipanel` — system orchestration, operator TUI, master/worker scheduling, Race/Diversity execution policy, adjudication, resource scheduling, cross-project architecture.
- `techrote/ansible` — trusted execution kernel and privileged execution-provider primitives. Hard safety policy belongs below Omnipanel.
- `techrote/interloc` — communications, evidence courier, structured capability proposals and Chat-facing integration.
- `techrote/ohmy` — Oh My Pi-specific adapter/harness/compatibility work.
- `techrote/intrallm` — agent-visible reference/task/evidence data. It is not executable authority.

Component repositories remain authoritative for their own internals. Omnipanel owns system-level ADRs, interface compatibility, the cross-project roadmap and end-to-end orchestration policy.

## Product direction

Initial implementation target: Python 3.12+ with a mouse-driven Textual TUI and UI-independent application services suitable for a later web UI.

First-class master directions are Codex and local models. Interloc/Chat is a separately qualified functional bridge. Manual operation can use the same task/proposal surfaces rather than creating a third orchestration architecture.

The execution model supports deterministic trusted workers plus model workers. Speculative groups have two distinct semantics:

- **Race** — optimize time-to-eligible result under a selected completion/cancellation policy.
- **Diversity** — retain independent candidates for comparison, reconciliation or redundancy.

Passing acceptance tests makes a candidate eligible for adjudication; it never grants merge authority by itself.

## Reference corpus

Start with [Agent context](docs/AGENT_CONTEXT.md), then follow the focused route.

Canonical planning documents:
- [Programme handover](docs/PROGRAMME_HANDOVER.md)
- [System architecture](docs/SYSTEM_ARCHITECTURE.md)
- [Project map](docs/PROJECT_MAP.md)
- [Trust model](docs/TRUST_MODEL.md)
- [Orchestration model](docs/ORCHESTRATION_MODEL.md)
- [Metaissue specification](docs/METAISSUES.md)
- [Model policy](docs/MODEL_POLICY.md)
- [Execution providers/resources](docs/EXECUTION_PROVIDERS.md)
- [Pinned component contracts](docs/INTERFACES.md)
- [Verification](docs/VERIFY.md)
- [Roadmap](docs/ROADMAP.md)
- [Blockers and external gates](docs/BLOCKERS.md)
- [Decision register](docs/DECISIONS.md)
- [Planning provenance](docs/PROVENANCE.md)
- [Execution ledger](docs/EXECUTION_LEDGER.md)
- [Machine-readable workflow](docs/workflow.json)
- [Stable-ID issue bindings](docs/issue-bindings.json)

Implementation references:
- [Development and startup](docs/DEVELOPMENT.md)
- [Core schema contracts](docs/SCHEMA_CONTRACTS.md)

## Current state

OP-001 / issue #10, the Python foundation, has completed implementation, automated acceptance and independent Stone review and has been merged to `main` through PR #56. The merge commit's full Windows/Linux × Python 3.12/3.13/3.14 Foundation CI also passed. A manual Windows 11 / Windows Terminal bootstrap smoke qualification subsequently passed for mouse/keyboard exit, terminal resizing, Unicode/literal path rendering and no unexpected state creation.

OP-002 / issue #11 is now **in implementation/self-verification** on draft PR #57. Its candidate defines versioned, UI-independent project/task/run/evidence/policy contracts plus synthetic round-trip/adversarial fixtures. The candidate's full Windows/Linux × Python 3.12/3.13/3.14 automated matrix passes at its tested implementation head. OP-002 remains **Steel**: independent implementation review, independent verification review and explicit user adjudication before consequential promotion/merge are still pending, so OP-002 is not complete or merged.

Nine metaissues and 46 child task issues are published. Two stable tasks remain unpublished because the GitHub connector safety check refused their issue creation: OP-018 (Codex master driver) and OP-047 (remote Execution Provider implementation). They remain visible in the workflow/bindings as blocked planning records and are **not** authorized published assignments.

The executable bootstrap provides typed startup settings, a read-only status command and a minimal non-executing Textual screen. The OP-002 candidate adds data contracts only. No durable state, readiness engine, worker scheduler, VM control, live component adapter, model-ranking service or production TUI is claimed yet. Active work in Ansible, Interloc or other repositories is not silently incorporated as completed Omnipanel functionality.

## Run the bootstrap

From the repository root in Windows PowerShell (Python 3.12+):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m omnipanel status
.\.venv\Scripts\python.exe -m omnipanel tui
```

Paste the complete block; the final command opens the dashboard. It cannot start jobs.
For Linux, configuration, clean installs and exact lint/type/test/build commands, see
[Development and startup](docs/DEVELOPMENT.md). See [OP-001 implementation evidence](docs/evidence/OP-001.md)
and the [independent Stone review](docs/evidence/OP-001-independent-review.md) for the retained OP-001 acceptance record.
