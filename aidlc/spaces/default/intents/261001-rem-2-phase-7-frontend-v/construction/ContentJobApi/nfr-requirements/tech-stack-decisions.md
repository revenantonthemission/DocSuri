# Tech Stack Decisions — ContentJobApi

## NFR6.1: HTTP Client — Native `fetch` + Custom Transport
- **Decision**: Custom `Transport` interface wrapping native `fetch`
- **Rationale**:
  - Mandated: NEVER use axios; use native fetch + custom Transport
  - Zero dependencies
  - Full control over headers, interceptors, retry logic
  - Type-safe request/response with Zod validation

## NFR6.2: Idempotency Hashing — `crypto.subtle`
- **Decision**: Native Web Crypto API (`crypto.subtle.digest`)
- **Rationale**:
  - Mandated: ALWAYS use native `crypto.subtle` for cryptographic operations
  - No external crypto libs (forbidden: no crypto-js, etc.)
  - Available in all target browsers

## NFR6.3: Schema Validation — Zod
- **Decision**: Zod for request/response validation
- **Rationale**:
  - Already in stack (used by BFF proxy)
  - TypeScript inference from schemas
  - Lightweight (~8KB) vs alternatives

## NFR6.4: LocalStorage Wrapper — Custom Hook
- **Decision**: `useIdempotencyStorage` hook abstracting localStorage
- **Rationale**:
  - Encapsulates key format `idempotency:{paperId}:{taskType}`
  - Handles JSON parse/stringify, TTL expiry, quota errors
  - Testable via hook mocking

## NFR6.5: TypeScript — Strict Mode
- **Decision**: Full strict TypeScript
- **No `any`**: All API shapes typed via Zod inference

## NFR6.6: Testing — Vitest + MSW
- **Decision**: Unit tests with Vitest; MSW for BFF mocking
- **Coverage Target**: ≥80% line coverage
- **E2E**: Playwright tests for full submission flow

## Traceability
| Inception NFR | Derived ID | Status |
|---------------|------------|--------|
| NFR1 (SEC-8) | NFR6.1 | OK |
| NFR4 (Idempotency) | NFR6.2, NFR6.4 | OK |
| NFR7 (Sentry) | NFR6.1 | OK |