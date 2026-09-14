# OP-015 Windows validation provider

## Purpose

OP-015 represents a clean Windows-specific validation environment through the generic OP-014 `ExecutionProvider` contract. Windows validation is a provider capability and work purpose, not a second scheduler architecture.

The initial implementation is deterministic and synthetic. No qualified live Windows validation environment is claimed by this task. Until one is explicitly qualified, live verification is `NOT RUN`, never PASS.

## Three independent states

The adapter keeps three concepts separate:

1. **Provider job lifecycle** — queued/running/succeeded/failed/cancelled/indeterminate execution state from the provider.
2. **Windows validation outcome** — PASS/FAIL/NOT RUN/INDETERMINATE result of the Windows-specific validation work.
3. **Live qualification** — whether a real Windows validation provider has been explicitly qualified for use.

A provider job may report `SUCCEEDED` while the Windows validation outcome is `FAIL`: the validation harness ran successfully and found a defect. Provider terminality is therefore not acceptance.

If no qualified live environment is available, `validation_not_run_result()` produces an explicit `NOT RUN` record with no invented provider job, test summary or evidence.

## Validation-only provider shape

`WindowsValidationProvider` wraps the generic provider interface and requires:

- provider class `windows-validation`;
- purpose set exactly to `validation`;
- capability `validation.windows`;
- provider metadata matching the configured Windows platform, image and harness identities.

Attempting to start ordinary execution work is rejected with the generic typed `PURPOSE_UNSUPPORTED` diagnostic before backend start.

The scheduler can therefore select this provider with the same `ProviderRequest`/capability mechanism used for other providers. No Windows-special placement branch is required in scheduler code.

## Candidate versus validation authority

Candidate input is represented only by the provider candidate request/payload reference. The Windows platform image and validation harness identities are adapter configuration, not candidate-controlled fields.

Validation evidence locations bind:

- provider ID and implementation version;
- Windows platform ID;
- image ID;
- harness ID;
- provider job ID.

Candidate payload references are not used to derive or replace the harness/platform identity. A future live implementation must preserve the same separation so candidate code cannot select or rewrite hidden/platform-specific acceptance assets.

## Synthetic provider

`SyntheticWindowsValidationProvider` uses OP-014's deterministic `FakeExecutionProvider` underneath the Windows validation adapter. It inherits generic:

- provider availability;
- bounded CPU/RAM/storage/runtime requests;
- reservation/release accounting;
- typed capability/provider failures;
- indeterminate-state resource holding;
- provider evidence provenance.

`finish_validation()` is a synthetic test-control method. PASS and FAIL both settle the underlying provider job as `SUCCEEDED`, because the provider successfully ran the validation harness in either case. The separate `WindowsValidationResult` carries the validation outcome and test summary.

An INDETERMINATE validation outcome maps to provider indeterminate state and therefore holds the resource reservation until later reconciliation.

## Evidence

Executed synthetic validation enriches provider evidence as a `test-report` descriptor carrying the test summary and stable Windows platform/image/harness/provider identity in the evidence location.

`WindowsValidationResult` additionally records run, task, candidate, platform, provider/job identity, outcome, test summary and evidence IDs. `NOT RUN` is structurally prevented from carrying executed-test evidence.

## Live qualification gate

`tests/fixtures/op015_windows_validation.json` records the current live state as:

- `state: not-run`
- reason: no qualified live Windows validation provider is configured for OP-015.

This is intentional. A later live provider may be qualified only with an explicit provider/interface identity and source-matched evidence. Synthetic results remain synthetic and must not be relabelled as live qualification.

## Acceptance coverage

`tests/test_windows_validation_provider.py` verifies:

- the provider satisfies the generic `ExecutionProvider` shape while advertising validation only;
- ordinary execution work is rejected;
- PASS evidence records test, provider and Windows platform identity;
- validation FAIL remains distinct from provider execution failure and from PASS;
- candidate payload cannot replace platform/harness identity;
- unavailable live state becomes NOT RUN;
- over-capacity requests fail through generic resource accounting;
- indeterminate validation holds resources rather than freeing uncertain work.
