# Scalability Design — IdempotencyService

## NFR3.1: 1000 Keys Capacity
**Design**: ~100 bytes/key × 1000 = ~100KB (well under 5MB)

## NFR3.2: Concurrent Tab Access
**Design**: Deterministic generation → same key; last-write-wins harmless

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR3.1 | ~100KB total |
| NFR3.2 | Deterministic = same key |