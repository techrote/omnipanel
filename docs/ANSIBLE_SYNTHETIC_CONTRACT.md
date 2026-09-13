# OP-012 synthetic Ansible adapter contract

Status: deterministic development/test contract. **This is not a live Ansible qualification and does not claim that the current four-slot prototype implements this API.** Live compatibility remains a separate OP-013 gate.

## Contract identity

Synthetic fixtures use:

- component: `ansible`
- contract: `omnipanel-execution`
- version: `synthetic-1`

`SyntheticAnsibleAdapter` accepts only that exact identity/version. Unknown versions, alternate contract identities and malformed contract references fail closed with a typed `AnsibleAdapterError` before a payload is treated as usable.

## Message inventory

| Message | Purpose | Key invariants |
|---|---|---|
| `capability-discovery` | provider identity and capability handles | duplicate capability handles rejected |
| `resource-provider-summary` | total/available coarse resources | available values may not exceed totals |
| `job-proposal` | deterministic proposed unit of work | stable job/task IDs, explicit capability/resource request and opaque payload reference |
| `job-status` | monotonic lifecycle observation | timezone-aware timestamp; stale/duplicate sequence rejected by status entrypoint; terminal status cannot be partial |
| `job-result` | terminal/indeterminate normalized result | running/queued results rejected; success requires evidence |
| `evidence-report` | evidence produced for a job | embeds canonical OP-002 `EvidenceDescriptorRecord` objects |

The synthetic contract deliberately does not expose arbitrary shell commands, provider credentials, or assumptions about the implementation details of the published slot-v1 prototype.

## Status semantics

Lifecycle values are `queued`, `running`, `succeeded`, `failed`, `cancelled` and `indeterminate`. Completeness is independent: non-terminal observations may be `partial`, but a terminal succeeded/failed/cancelled status must be complete. A partial terminal payload is malformed rather than interpreted as success.

`decode_status(..., previous_sequence=N)` requires a strictly newer sequence. Duplicate or older observations surface `stale-status`; they are not silently accepted as current state.

## Failure model

Adapter errors are normalized into operator-readable diagnostics:

- `incompatible-contract` — exact component/contract/version is not supported;
- `malformed-payload` — schema, message type, invariants or required data are invalid;
- `stale-status` — status sequence is not newer than the caller's known sequence.

The original Pydantic validation error is retained as exception cause where applicable, while callers can reason over the stable diagnostic code.

## Fixture inventory

`tests/fixtures/op012_ansible_synthetic.json` contains deterministic capability, resource, job proposal, running/partial status, malformed partial-terminal status, success result, evidence report and unsupported-version examples. Tests mutate those fixtures to cover malformed fields, contract identity drift, stale sequences, impossible resource summaries and success without evidence.

No Ansible installation, network access or live component process is needed to run the fixtures. This is intentional: Omnipanel can develop provider-neutral service/UI behavior before OP-013 qualifies one real Ansible contract.

## Relationship to later work

OP-013 may map an explicitly reviewed live Ansible contract into these normalized semantics. It must record the live source revision and contract identity separately and demonstrate compatibility; it may not declare a live contract compatible simply because its display/version strings resemble `synthetic-1`.

OP-014 can then consume these normalized capability/resource/lifecycle concepts while keeping provider enforcement below Omnipanel.
