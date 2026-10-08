# Scalability Requirements — IdempotencyService

## NFR3.1: Key Storage Capacity
- **Target**: Support 1000 unique paper/taskType combinations
- **Storage**: ~100KB total (100 bytes/key × 1000)
- **Quota**: Well under 5MB localStorage limit

## NFR3.2: Concurrent Access
- **Target**: Multiple tabs generating keys for same paper/taskType
- **Behavior**: Deterministic generation → same key; localStorage last-write-wins (harmless)

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR3.1, NFR3.2 | OK |