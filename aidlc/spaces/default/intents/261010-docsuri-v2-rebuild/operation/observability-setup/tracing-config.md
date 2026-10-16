# Tracing Config — u4-research-novelty Observability

Distributed tracing configuration for the u4-research-novelty unit. All tracing is local-only; no distributed tracing server or external tracing service is provisioned ($0 budget constraint).

## Tracing Configuration

| Trace element | Configuration | Value |
|---|---|---|
| Trace format | Explicit request → operation → receipt/job → delivery → claim/attempt → result → settlement obligation → accounting receipt links | Bounded local JSONL trace records |
| Trace ID | Operation correlation identifier | Opaque correlation identifier; never used as a credential, idempotency key or recovery command |
| Span attributes | Schema, event, owner/capability, safe outcome, opaque correlation/parent, attempt and committed sequence references, bounded policy/build identity, producer time, receipt time and local monotonic elapsed when valid | Bounded to 4 KiB per event; rejected if exceeds limit |
| Span count | At most 256 events and 1 MiB per producer; at most 4 enabled producers | Count bounded working sets plus producer buffers against the infrastructure memory lane |
| Trace retention | Same protected finite retention as ordinary evidence | Rotate within the optional observation allocation; expiry and byte limits both apply |
| Trace sampling | Not sampled; all mandatory owner facts are recorded | No sampling of mandatory owner facts; optional detail may be dropped with bounded counters |

## Tracing Guards

- No secrets, prompts, private text, or credentials in any trace span or attribute
- Trace ID is never used as a credential, idempotency key or recovery command
- No distributed tracing server (Jaeger, OpenTelemetry Collector, etc.) is provisioned
- No cross-service trace context propagation beyond the local synthetic realm
- No remote trace aggregation or export
