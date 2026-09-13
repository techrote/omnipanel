# OP-004 independent implementation review

Reviewed implementation: `cb660b65278ab814899acae9a4a55bd54a19b796`
Integration base exercised by PR CI: `fbf4c1dcfc97d42626c9ec85e2473c20db7a8054`
Foundation CI: `34784133357`
Result: **PASS**

This was a separate Stone implementation-review pass over the application-service boundary, reconnect semantics, tests and documentation.

## Review findings

- Durable truth remains in OP-003 `StateStore`; update delivery is explicitly ephemeral and bounded.
- A fresh/foreign/overflowed cursor receives a new durable snapshot rather than a guessed or incomplete replay.
- Same-process valid cursors receive only newer typed invalidation updates.
- Service restart changes the event epoch while preserving durable state reconstruction.
- Snapshots cover project/metaissue/task state, DAG topology, run/candidate state, evidence, canonical model identities/assessments, policy views and resource summaries.
- Core service code has no Textual dependency and no component-adapter implementation dependency.
- Released reservations are excluded from live resource totals while indeterminate reservations remain visible for recovery/requalification.

## Defect found and fixed during review

The first generic record-update design used the narrower `OpaqueId` grammar for `ServiceUpdate.entity_id`. Valid durable record keys such as a DAG edge (`OP-003->OP-004`) contain structural punctuation not accepted by that grammar. A durable `put_record(DagEdge)` could therefore succeed and then fail while constructing its notification.

The reviewed implementation widens only the notification key envelope to bounded `LocationText`, adds DAG edges and canonical model identities to snapshots, and includes a regression that writes a `DagEdge` through `ApplicationServices`, verifies its structural key in the update stream and reconstructs it from the durable snapshot.

## Verification

Foundation CI `34784133357` passed all six Windows/Linux × Python 3.12/3.13/3.14 jobs, including Ruff lint/format, strict mypy, pytest, package build and clean-wheel installation. The integrated suite includes the previously merged OP-006 interface tests and the OP-004 service tests.

## Independence note

This review was performed as a distinct review pass/context rather than by a second human reviewer. That limitation is recorded explicitly; no independent human sign-off is claimed.
