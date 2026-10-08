# Infrastructure Specification — IdempotencyService

## Client-Only Infrastructure

### Crypto
- **API**: `crypto.subtle.digest('SHA-256', data)` (native Web Crypto)
- **No Server Infrastructure**: Pure client-side

### Storage
- **localStorage**: Key format `idempotency:{paperId}:{taskType}`
- **Value**: `{ key, createdAt, paramsHash }`
- **TTL**: 30 days client-side, 24h server-side (gateway)
- **Fallback**: In-memory `Map` when quota exceeded

### Memory Fallback
```ts
const memoryFallback = new Map<string, IdempotencyEntry>();
// Session-only, lost on reload
```

## Traceability
| Logical Component | Infrastructure Need |
|-------------------|---------------------|
| generateIdempotencyKey | crypto.subtle (native) |
| useIdempotencyStorage | localStorage + memory Map |