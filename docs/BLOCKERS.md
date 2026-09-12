# Blockers and externally gated work

Status date: 2026-09-12. This file distinguishes publication restrictions from implementation/runtime blockers.

| ID | Kind | State | Consequence |
|---|---|---|---|
| OP-018 | publication | connector safety check refused issue creation twice | Stable task remains in `workflow.json`, but there is no authorized GitHub assignment. Dependent v1 gates must acknowledge the missing published Codex-driver task or use another qualified master path without pretending OP-018 completed. |
| OP-047 | publication | connector safety check refused remote-provider implementation issue | OP-046 design may proceed after v1; actual remote provider implementation is unavailable until publication/authorization is explicitly resolved. |
| OP-013 | external qualification | needs a reviewed Ansible contract | Synthetic OP-012 work can proceed independently. |
| OP-016 | external qualification | needs an Ohmy contract/live implementation | Synthetic normalized-outcome work can proceed independently. |
| OP-020 | external qualification | needs a qualified Interloc integration contract | Synthetic bridge work can proceed independently; current Interloc planning records its own blocked integration publication. |
| OP-034 | external qualification | needs qualified VM/provider primitives beneath Ansible | Generic resource/provider work can proceed with fixtures. |

## Rule

A blocked/unpublished task is not recreated under another number to make the graph look complete. `issue-bindings.json` uses `null` for unpublished stable IDs. Metaissue completion must reconcile the blocker explicitly.

Synthetic fixtures can establish Omnipanel's own contract behavior but cannot be reported as live component acceptance.
