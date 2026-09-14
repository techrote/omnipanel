# OP-015 independent implementation review

Reviewed implementation head: `482340ea2cd91205fcce3d4384b87656bab1725c`
Verified base: `main` at `1458285890e66b046e9714d8e052e44eea5c30bb`
Foundation CI run: `34812028073` / #123 (**PASS**)
Review result: **PASS pending final doc-only head CI**

This was a distinct Stone implementation-review pass over the Windows validation-provider adapter, synthetic validation fixture, live-qualification boundary, resource behavior and evidence provenance.

## Automated verification

Foundation CI passed all six supported lanes:

- Ubuntu / Python 3.12
- Ubuntu / Python 3.13
- Ubuntu / Python 3.14
- Windows / Python 3.12
- Windows / Python 3.13
- Windows / Python 3.14

Each lane passed Ruff lint/format, strict source type checking, unit/boundary/headless Textual tests, source/wheel build and clean-wheel installation.

The representative Ubuntu/Python 3.13 run collected 304 tests in the immediately preceding reviewed tree and reported 301 passed / 3 established native-Windows path skips. The final implementation head preserves those semantics and passes the full six-lane matrix.

## Review findings

- Windows validation uses the generic OP-014 `ExecutionProvider` interface rather than a Windows-special scheduler path.
- The adapter is validation-only: provider class is `windows-validation`, purpose is exactly `validation`, and capability `validation.windows` is mandatory.
- Platform, image and validation-harness identities are adapter configuration. Candidate payload references cannot replace or redefine those identities.
- Provider job lifecycle and validation outcome remain separate. A validation FAIL can coexist with provider job `SUCCEEDED`, meaning the harness executed successfully and found a defect.
- Live qualification is a third independent state. When no qualified live Windows provider exists, the result is structurally `NOT RUN`; it has no provider job, test summary or executed-test evidence and cannot be mistaken for PASS.
- Synthetic validation inherits OP-014 bounded resource requests, over-capacity failure, indeterminate-state resource holding and explicit release semantics.
- PASS/FAIL evidence is emitted as a provider-attributed test report whose location binds provider/version, platform, image, harness, job, validation state and evidence ID.
- Result/qualification models fail closed if an attached provider identity is not itself classed as `windows-validation`.
- The implementation does not claim that the synthetic Windows fixture is a qualified live Windows environment.

## Defects found and reconciled during review

### Reconciliation could retroactively mutate historical evidence

The first evidence-enrichment design keyed test summary/outcome by provider job. If an indeterminate validation later reconciled to PASS or FAIL, collecting evidence again could make the earlier indeterminate receipt inherit the later result.

The reconciled implementation binds validation outcome and test summary per evidence ID. A regression verifies that the original indeterminate receipt remains summary-free and labelled indeterminate while the later receipt independently records PASS and its test summary.

### Result/qualification records could carry a non-Windows provider identity

The first models checked the adapter at construction time but could still be instantiated directly with an unrelated `general-worker` provider identity while claiming Windows validation provenance.

The reconciled validators require every attached provider identity, including optional provider identity on NOT RUN qualification/results, to use provider class `windows-validation`. Dedicated regressions cover both qualification and result records.

### Pytest collection warning exposed by strict warnings-as-errors

The test module initially imported `TestSummary` under its class name, causing pytest to inspect it as a possible test class. Because repository warnings are errors, collection failed even though product semantics were correct.

The import is now aliased as `ValidationTestSummary`. No production behavior changed.

### Mechanical Ruff findings

Superseded CI heads exposed formatter/import-order differences. These were reconciled mechanically. The reviewed head passes the pinned Ruff toolchain.

No further material defect was found after reconciliation.

## Independence note

This review was performed as a separate review pass/context from implementation. It is not represented as a second human reviewer, and no independent human sign-off is claimed.

OP-015 is Stone, so no additional user-promotion gate applies. The only change after the reviewed implementation head is this evidence document; merge remains gated on the resulting documentation-only head passing Foundation CI.
