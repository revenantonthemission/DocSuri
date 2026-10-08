# Security Requirements — IdempotencyService

## NFR2.1: Deterministic Key Generation (NFR4)
- **Requirement**: Key = SHA-256(`userId:paperId:taskType:JSON.stringify(params)`)
- **Rationale**: Deterministic = same params → same key = safe retry
- **Encoding**: UTF-8 → bytes → SHA-256 → hex string (64 chars)
- **Collision Resistance**: SHA-256 provides 128-bit collision resistance

## NFR2.2: localStorage Security
- **Requirement**: Keys stored in localStorage with namespaced key format
- **Key Format**: `idempotency:{paperId}:{taskType}`
- **Value**: JSON `{ key: string, createdAt: number, paramsHash: string }`
- **No Secrets**: Key is hash of params; not a secret itself
- **XSS Mitigation**: localStorage only accessible same-origin; CSP prevents script injection

## NFR2.3: Key Expiry & Cleanup
- **Requirement**: Keys expire after 30 days; purged on app initialization
- **Implementation**: `createdAt` timestamp checked on read; stale keys deleted
- **Server-Side TTL**: Gateway also enforces 24h TTL (defense in depth)

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR2.1, NFR2.2, NFR2.3 | OK |