# Logical Components — IdempotencyService

## Component Inventory

| Component | Type | Responsibility | Failure Domain |
|-----------|------|----------------|----------------|
| `generateIdempotencyKey()` | Function | SHA-256 hash generation | crypto.subtle |
| `useIdempotencyStorage` | Hook | localStorage CRUD + TTL | localStorage |
| `memoryFallback` | Map | In-memory fallback when quota exceeded | Memory |

## Failure Domains

```
IdempotencyService
├── generateIdempotencyKey()
│   └── crypto.subtle unavailable → fallback to UUID (non-deterministic, logged)
├── useIdempotencyStorage
│   ├── localStorage read parse error → delete + regenerate
│   ├── localStorage write quota → purge oldest → retry → Map fallback
│   └── localStorage permission denied → Map fallback
└── memoryFallback
    └── Session-only; lost on reload (acceptable for fallback)
```

## Isolation
- Pure functions + hook = testable, no shared state
- Memory fallback isolated per session

## Infrastructure Handoff
- None (client-only); server TTL handled by Gateway

## Traceability
| NFR Requirement | Logical Component |
|-----------------|-------------------|
| NFR1.1-1.2 | generateIdempotencyKey, useIdempotencyStorage |
| NFR2.1-2.3 | generateIdempotencyKey, useIdempotencyStorage |
| NFR3.1-3.2 | useIdempotencyStorage |
| NFR4.1-4.3 | useIdempotencyStorage, memoryFallback |
| NFR5.1-5.2 | generateIdempotencyKey, useIdempotencyStorage |