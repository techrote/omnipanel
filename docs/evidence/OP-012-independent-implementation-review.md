# OP-012 independent implementation review

Reviewed implementation: `beab3e32bc7108345a0631110c7eaa5e1ad39f52`
Foundation CI: `34784673948`
Result: **PASS**

This was a separate implementation-review pass over the synthetic Ansible contract, decoder, fixtures, tests and documentation.

## Review findings

- The adapter is explicitly synthetic and does not claim compatibility with the current live Ansible implementation.
- Exact `ansible / omnipanel-execution / synthetic-1` contract identity is required before any payload is treated as usable.
- Capability, resource, proposal, status, result and evidence messages are closed typed contracts.
- Running status may be partial, but succeeded/failed/cancelled status cannot be partial; success results require evidence.
- Status sequence handling rejects stale/duplicate observations rather than silently treating them as current.
- Resource availability cannot exceed provider totals.
- Evidence reports reuse canonical OP-002 evidence records instead of defining a competing evidence schema.
- No network, live Ansible installation, shell-command surface or credential assumption is needed for deterministic fixtures.

## Defects found and fixed during review

1. The fail-closed `_raise()` helper always raised at runtime but was typed as returning normally. Strict mypy therefore could not narrow the decoder after failure branches. It was changed to `-> Never`, making the type contract match runtime behavior without changing semantics.
2. A malformed raw `message_type` containing spaces, invalid punctuation or excessive length could violate the diagnostic model itself, escaping the promised `AnsibleAdapterError` boundary as a Pydantic validation failure. Diagnostic message types are now normalized to a bounded safe identifier or `unknown`, with direct regressions for blank, punctuated and oversized inputs.

The final reviewed SHA contains both fixes and the Ruff formatter-only cleanup that followed them.

## Independence note

This review was performed as a distinct review pass/context rather than by a second human reviewer. That limitation is explicit; no independent human sign-off is claimed.
