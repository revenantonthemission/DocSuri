# Tech Stack Decisions — IdempotencyService

## NFR6.1: Hashing — `crypto.subtle`
- **Decision**: Native Web Crypto API
- **Rationale**: Mandated; zero deps; FIPS 180-4 compliant

## NFR6.2: Storage — localStorage + Custom Hook
- **Decision**: `useIdempotencyStorage` hook wrapping localStorage
- **Rationale**: 
  - Mandated: ALWAYS store in localStorage with format `idempotency:{paperId}:{taskType}`
  - Hook encapsulates serialization, TTL, error handling
  - Testable via mock

## NFR6.3: Serialization — JSON + Custom Reviver
- **Decision**: JSON.stringify/parse with Date reviver for `createdAt`
- **Rationale**: Simple, no deps; Date handled explicitly

## NFR6.4: TypeScript — Strict
- **Decision**: Full strict mode; no `any`

## NFR6.5: Testing — Vitest
- **Decision**: Unit tests with Vitest; mock localStorage + crypto.subtle
- **Coverage Target**: ≥80% line coverage

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR4 (Idempotency) | NFR6.1, NFR6.2 | OK |