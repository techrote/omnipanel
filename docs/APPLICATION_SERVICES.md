# OP-004 application services

`src/omnipanel/services.py` is the UI-independent boundary between OP-003 durable state and presentation layers.

## State/service map

- `ApplicationSnapshot` exposes typed project, metaissue, task, run, candidate, evidence and model records plus persisted policy views and a resource summary.
- `ApplicationServices` owns no durable truth. Mutations are written through `StateStore`; service updates are process-local notifications only.
- `BoundedUpdateStream` retains a configurable fixed number of typed updates. It never grows without bound.
- `ServiceCursor` contains an event-stream epoch plus sequence number. Cursors are valid only for the current service-process epoch.

## Connect and reconnect semantics

A new subscriber calls `connect()` and receives a complete durable snapshot plus the current cursor.

A subscriber reconnecting with a valid same-epoch cursor receives only buffered updates newer than that cursor. If the cursor is too old for the bounded buffer, belongs to a previous process epoch, or is otherwise not replayable, the service returns a fresh durable snapshot instead of guessing what was missed.

This means UI lifetime is independent from state lifetime: restarting Textual or a future web presentation does not lose durable state, and restarting the service invalidates only the ephemeral replay buffer.

## Update semantics

Updates identify a topic (`record`, `policy`, `resource`), entity type and stable entity ID. They are invalidation/change notifications, not copies of authoritative state. Consumers obtain authoritative values from snapshots/views.

The initial OP-004 service surface wraps record, policy and resource-reservation writes so successful durable mutations emit updates. Later application services can extend the topic set without importing Textual or component-specific adapters into the core service module.

## Resource summary

The snapshot reports reservation counts by state and requested CPU, memory, storage and GPU totals for reservations that are not released. Indeterminate reservations remain visible and counted because OP-003 intentionally requires requalification rather than inventing release or success after interruption.

## Error and dependency boundary

- constructing services around a closed `StateStore` raises `ServiceConfigurationError`;
- corrupt durable reservation payloads surface as `StateCorruptionError`;
- stale/foreign cursors cause snapshot resynchronization rather than an exception or silent gap;
- core service code has no Textual dependency and does not import component adapter implementations.

Automated coverage is in `tests/test_services.py`, including reconnect, buffer overflow, process restart, durable snapshot recovery, typed update topics and resource summaries.
