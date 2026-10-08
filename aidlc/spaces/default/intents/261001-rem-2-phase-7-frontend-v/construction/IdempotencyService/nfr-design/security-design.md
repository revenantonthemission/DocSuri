# Security Design — IdempotencyService

## NFR2.1: Deterministic Key Generation
**Design**: `SHA-256(userId:paperId:taskType:JSON.stringify(params))`
- UTF-8 encoding → SHA-256 → hex string (64 chars)
- Same inputs → same key = safe retry

## NFR2.2: localStorage Security
**Design**: Namespaced keys, no secrets
- Format: `idempotency:{paperId}:{taskType}`
- Value: `{ key, createdAt, paramsHash }`
- Key is hash of params (not secret itself)
- XSS mitigation: CSP prevents script injection

## NFR2.3: Key Expiry & Cleanup
**Design**: 30-day client TTL + 24h server TTL
- Client: `createdAt` checked on read; stale → delete
- Server: Gateway Redis 24h TTL (defense in depth)

## Traceability
| NFR Requirement | Design Solution |
|-----------------|-----------------|
| NFR2.1 | SHA-256 deterministic generation |
| NFR2.2 | Namespaced localStorage, no secrets |
| NFR2.3 | 30-day client + 24h server TTL |