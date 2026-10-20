# DocSuri v2 — Contract summary

Date: 2026-10-14 (Asia/Seoul). Contract release 3.0.0: coordinated U2 C03/C13 amendment;
C02 adds its reauthenticated lifecycle preparation and strict profile lifecycle
revision projection at coordinated 3.0.0; other
contracts retain their explicit 2.0.0 version. Required reset result identity
is a breaking shape change, not automatically additive compatibility. No mounted
U1 reset consumer was found in the bounded implementation inventory. Public
activation still requires external-consumer evidence. U1 amendment
under the approved Code Generation plan. The original review remains historical
evidence for release 1.0.0; amended contracts require finished-work review and
executable closure evidence. This document does not establish runtime readiness.
See the [amendment and compatibility record](../../construction/u1-integrated-paper-journey/code-generation/contract-amendment.md).
Contract release 3.1.0 is an additive minor step: C09 2.1.0 carries U6's approved
amendments A1–A7, A9, A10 and the A6 extension; every frozen C09 property keeps its
name, type and requiredness except the two named changes (connectionId optional on
ExportConnectionRead and ExportConnectionReadHttp; ExportDestinationEntry, a superset
of ExportDestination, on the two destination response properties).
Basis: the [confirmed contract plan](contract-design-questions.md),
[approved unit catalogue](../units-generation/unit-of-work.md),
[unit DAG](../units-generation/unit-of-work-dependency.md),
[domain ownership](../domain-design/components.md) and
[requirements](../requirements-analysis/requirements.md).

## Scope and reading guide

These contracts define the complete retained service boundary. One application
release composes U1 and its U2–U6 contributions; U8 completes that assembly. U7
is a separately controlled operator executable. The 19 construction dependencies
are mapped below without introducing network services for embedded modules.
Unit IDs identify implementation responsibility; component names identify the
authoritative business owner. The same component evolves from U1 into later
units instead of acquiring a second store or owner.

Read the boundary table and invariants first. C00 is the canonical JSON Schema
2020-12 type registry. Each `yaml contract` block is DocSuri's small project-owned
interface format: `operations` names a request type, success type, required
authority, error vocabulary and semantic obligations; `invariants` and `checks`
are normative. Each invocation returns either its named success type or C00
`Error`, never an untyped exception across the boundary. These in-process and
message contracts are not OpenAPI/AsyncAPI documents. C13 and the C10 evidence
binding carry genuine OpenAPI 3.1.1 documents. Their schemas are self-contained
copies of C00 with references adapted to OpenAPI; the verifier checks them.

The formal schemas specify transport shapes. Authorization, state transitions,
deduplication, current policy and content eligibility are additional normative
checks: passing JSON validation cannot grant authority or prove durability.
The `x-limit-policy`, `x-policy-limit` and `x-policy-bound` annotations name a mandatory runtime admission check, not
JSON Schema assertions. Every enabled operation must have an approved finite
limit/deadline/retry policy; unresolved values block that operation before work
or sensitive persistence. This defines the contract without inventing the
baseline-dependent numeric targets or retention periods.

## Common authority, acknowledgement and failure rules

1. Derive `Principal` and `CommandContext` at a trusted server/executor boundary.
   Browser JSON, owner IDs, headers, stored references, old sessions and event
   payloads cannot assert authority. Recheck current account/consent/source and
   operation permissions at admission, private reads/assets/events and before
   effects. Revocation versus effect commit must have an owner-defined
   linearization point; checking once before a long job is insufficient.
2. Scope an idempotency key to the verified owner, operation kind and normalized
   input hash. Same key/same intent recovers the original logical outcome; a
   changed intent conflicts. Keys are required for logical mutations even when
   the common context permits omission for reads. Durable acceptance requires
   both the authoritative record and a recoverable execution obligation. A
   transport queue acknowledgement is never a result.
3. Reads of prepared results, previews and acknowledged drafts never start work
   or repeat an export. Distinguish a retry of uncertain submission from a
   deliberate new run. A terminal failed/cancelled operation is not silently
   restarted under its old key. Any explicit re-execution uses a new logical
   identity, rechecks policy and preserves the previous receipt.
4. Use owner-scoped monotonically advancing revisions/sequences. Optimistic
   writes compare the expected revision atomically; return safe conflict without
   overwriting. The client obtains current state through a fresh authorized read;
   Error.details remains fieldNames-only. Current authorization and exact original
   normalized-intent receipt replay precede fresh CAS. Same-key replay still
   requires current read authority. A successful cancellation is terminal and
   excludes later effects; a cancellation request alone is not success.
5. Lost responses/timeouts can mean an effect committed. Return/recover
   `UNKNOWN_OUTCOME` or the domain's typed unknown disposition until reconciled.
   Never claim remote exactly-once delivery. Duplicate suppression and
   reconciliation have durable owners. Compensating or retry effects need their
   own current authorization and provider-safe semantics.
6. All requests and lists are bounded by approved admission policy. Cursor
   tokens bind filter/query hash, owner scope, schema version and result snapshot;
   altered or expired cursors yield a typed error, not a different page silently.
   Do not embed credentials or readable private text in a cursor.
7. Unknown enum/state versions are incompatible unless explicitly specified as
   extensible display vocabulary. Producers validate their own emitted shape.
   Strict request schemas reject unexpected authority/control fields. Readers
   may ignore safe additive response fields after compatible schema publication;
   a new required request field or changed meaning requires a new major contract
   version and coordinated consumers. This is not permission to ignore an
   unknown authorization, deletion or completion state.
8. Error JSON carries a stable code, safe localization key and correlation ID.
   Korean UI text resolves `messageKey`; errors retain query context, focus and
   acknowledged work. No token, stack trace, private prompt or existence leak
   appears in error details. Protected resource absence and foreign ownership
   share the same externally observable not-found behavior.

## HTTP, streaming and integration binding

The proposed browser URI namespace is `/api/v2`; it is an interface proposal,
not removal of an existing route or a new third-party API product. One trusted
same-origin boundary performs authentication and supplies internal context.
The chosen implementation may use a BFF or an equivalent server boundary; it
must preserve streaming, status, cookies and error/result semantics end to end.
Client-supplied identity headers never substitute for verified context.

Named JSON operations use POST, including complex queries, with their precise
request/response schemas. This operation-oriented shape keeps filter and private
text out of URLs; POST query operations remain read-only and cannot trigger jobs.
Dedicated GET bindings cover session bootstrap, capabilities, job state/result,
events and protected assets. The HTTP operation table specifies access for each
operation. No generic call-by-name endpoint exposes internal methods.

Secure HttpOnly session cookies are restricted to the application origin with
an appropriate SameSite policy; identity callback binding must be compatible
without relaxing CSRF checks. Session bootstrap supplies a CSRF token bound to
the current session or anonymous pre-authentication context. Browser POSTs
validate Origin and that token, including credential/account entry flows.
Session issuance/rotation/revocation uses response cookies through the trusted
transport, not browser-visible token fields. Never put bearer credentials into
localStorage, URLs or event cursors. Purpose-bound MFA continuation and withdrawn-account recovery credentials use
separate protected cookies/proofs; neither grants an active account session.
One-time MFA enrollment material is an explicit secret response, bound to current
reauthentication and no-store delivery; no response or client logging is allowed.
Authentication replies do not expose account
existence through reset/resend or provider-link errors.

HTTP maps malformed payload to 400/422, absent authentication to 401, general
permission/MFA denial to 403, protected absent/foreign resource to 404,
revision/idempotency conflicts to 409, authorized expired result to 410,
rate/usage admission to 429, unavailable/incompatible/unresolved policy to 503,
and deadline expiry to 504. `UNKNOWN_OUTCOME` is 409 with a receipt/reconciliation
lookup where available, not evidence of absence. Domain typed conflict outcomes
may use a success envelope only when its discriminator is explicit; UI never
renders it as a saved acknowledgement. Permanent request/policy errors are not
blindly retried. Retryable errors respect an advertised delay and a bounded
owner policy. Error-status families are documented in OpenAPI, including default
errors; an HTTP status alone never determines whether a remote effect happened.

SSE uses UTF-8 `text/event-stream`, real newline-delimited `id`, `event` and
`data` fields and a blank line terminating each event. The `data` is the full
authorized `JobSnapshot`, so reconnection never depends on a missed text delta.
`id` is the decimal job sequence; `event` is `snapshot` or `reset`. Validate a
`Last-Event-ID` header on native reconnection; an explicit fresh connection may
use `afterSeq`. If both are present they must agree. A cursor beyond the current
sequence is invalid. A retained replay gap emits `reset` with the current full
snapshot, after which live updates continue. Duplicate/older snapshots are
ignored; a stream loss invokes the same authoritative snapshot GET under bounded
polling/backoff. Native EventSource does not need custom bearer headers.

Authenticate before stream creation and enforce revocation during delivery.
Terminal snapshots close the client subscription; idle heartbeat comments carry
no state or sequence. JSON and SSE must agree on job owner, kind, seq, result and
error. Private stream/result/asset responses are no-store; intermediate proxies
must preserve framing and avoid buffering the whole job. Browser status never
claims completion from a closed socket or progress percentage. Numeric progress
requires `0 <= current <= total`; otherwise use indeterminate progress.

## Architectural choices and alternatives

| Decision | Selected proposal | Alternative and consequence |
|---|---|---|
| Embedded boundaries | Typed module interfaces with schema-checked payloads | HTTP per feature adds deployment and network failure modes without measured need under one-maintainer/$0 constraints |
| Accepted work | Durable owner record plus recoverable delivery obligation and deduplicated facts | Fire-and-forget dispatch loses accepted work; a universal job authority obscures operation-specific cancellation/retention |
| Progress | Full monotone snapshots through SSE with polling recovery | Delta-only streaming needs additional replay reconstruction and can misrepresent missed results |
| API evolution | Versioned v2 contracts plus evidence-based legacy transition | Indefinite unmeasured compatibility promises or immediate legacy deletion both outrun the consumer inventory |
| Policy values | Versioned policy references with explicit admission blockers | Guessing retention/resource numbers would pre-empt required user/evidence decisions; unbounded defaults violate $0 capacity |

These choices preserve domain ownership and the approved DAG. They select no
language, framework, database, broker, hosting provider, migration policy or
paid fallback. Security/privacy consequences are enforced through current
authority, owner-local writes, bounded admission and the unresolved-policy table.

## Contracts table

| # | Provider Unit | Consumer | Mechanism | Owner |
|---|---|---|---|---|
| C01 | U1 | U2, U3, U4, U5, U6, U8 | typed-module | WebWorkspace |
| C02 | U1, U2 | U3, U4, U5, U6, U8, External: public web | typed-module | AccountAccess |
| C03 | U1, U2 | U3, U4, U8, External: public web | typed-module | Library, Personalization, UsageEntitlements |
| C04 | U1, U3 | U1, U2, U3, U4, U8 | durable-command-fact | CorpusContent |
| C05 | U1, U3 | U1, U2, U3, U4, U5, U8 | durable-command-fact | Discovery |
| C06 | U1, U3 | U1, U3, U8 | durable-command-fact | PaperAssistance |
| C07 | U4 | U4, U6, U8 | durable-command-fact | ResearchWorkspace |
| C08 | U5 | U5, U8, Email delivery adapter | durable-command-fact | TopicsDigests |
| C09 | U6 | U6, U8, Notion adapter | durable-command-fact | ApprovedExport |
| C10 | U7 | U8, External: authorized operator | typed-module / controlled executable | PlatformControl |
| C11 | U1, U8 | U8, External: authorized administrator | typed-module | ServiceOperations |
| C12 | U1, U2, U3, U4, U5, U6 | External: Google / ORCID / source and citation APIs / approved model and extraction / email / Notion | typed adapter envelope; provider wire profile required | AccountAccess, CorpusContent, Discovery, PaperAssistance, ResearchWorkspace, TopicsDigests, ApprovedExport |
| C14 | U1, U3, U4, U5, U6 | U1, U3, U4, U5, U6, U8, External: configured execution adapter | durable-command-fact | CorpusContent, PaperAssistance, ResearchWorkspace, TopicsDigests, ApprovedExport |
| C13 | U1 initial / U2–U6 contributions / U8 complete | External: DocSuri browser and confirmed existing clients | HTTP/JSON, SSE, protected bytes | WebWorkspace binding; each domain retains operation authority |

## Unit dependency and requirement mapping

Every DAG edge is mapped to a contract family. Shared C00 types and C12 provider obligations apply wherever consumed. Parent FR coverage is the union of its subrequirements; a mapping is responsibility, not proof of implemented parity. No unit-level dependency is inferred merely from a module callback.

```yaml traceability
requirements:
  FR1:
  - C01
  - C04
  - C05
  FR1.1:
  - C04
  - C05
  FR1.2:
  - C04
  - C05
  FR1.3:
  - C05
  FR2:
  - C01
  - C04
  - C07
  FR2.1:
  - C04
  FR2.2:
  - C04
  FR2.3:
  - C07
  FR3:
  - C01
  - C06
  FR3.1:
  - C06
  FR3.2:
  - C06
  FR3.3:
  - C06
  FR3.4:
  - C06
  FR4:
  - C06
  FR4.1:
  - C06
  FR4.2:
  - C06
  FR5:
  - C01
  - C03
  - C04
  - C05
  FR5.1:
  - C03
  FR5.2:
  - C03
  - C05
  FR5.3:
  - C03
  - C04
  FR6:
  - C01
  - C02
  - C09
  FR6.1:
  - C02
  FR6.2:
  - C02
  FR6.3:
  - C02
  - C09
  FR6.4:
  - C02
  FR7:
  - C02
  FR7.1:
  - C02
  FR7.2:
  - C02
  FR8:
  - C02
  - C03
  - C08
  FR8.1:
  - C02
  - C08
  FR8.2:
  - C03
  FR9:
  - C03
  - C04
  - C05
  FR9.1:
  - C03
  - C04
  - C05
  FR9.2:
  - C05
  FR10:
  - C02
  - C03
  - C06
  FR10.1:
  - C03
  - C06
  FR10.2:
  - C02
  - C03
  FR11:
  - C02
  - C03
  FR11.1:
  - C03
  FR11.2:
  - C02
  - C03
  FR12:
  - C02
  - C05
  - C08
  FR12.1:
  - C08
  FR12.2:
  - C02
  - C05
  - C08
  FR13:
  - C01
  - C05
  - C07
  FR13.1:
  - C05
  - C07
  FR13.2:
  - C07
  FR13.3:
  - C07
  FR14:
  - C01
  - C02
  - C07
  - C09
  FR14.1:
  - C07
  FR14.2:
  - C02
  - C07
  - C09
  FR15:
  - C01
  - C07
  - C09
  FR15.1:
  - C07
  - C09
  FR15.2:
  - C07
  FR16:
  - C01
  - C02
  - C07
  - C09
  FR16.1:
  - C07
  - C09
  FR16.2:
  - C02
  - C07
  - C09
  FR17:
  - C02
  - C03
  - C06
  - C07
  FR17.1:
  - C02
  - C03
  FR17.2:
  - C03
  - C06
  - C07
  FR18:
  - C04
  FR18.1:
  - C04
  FR18.2:
  - C04
  FR18.3:
  - C04
  FR19:
  - C01
  - C08
  - C11
  FR19.1:
  - C08
  - C11
  FR19.2:
  - C01
  - C11
  FR19.3:
  - C11
  FR20:
  - C10
  FR20.1:
  - C10
  FR20.2:
  - C10
edges:
- consumer: U2
  provider: U1
  contracts:
  - C01
  - C02
  - C03
- consumer: U3
  provider: U1
  contracts:
  - C01
  - C04
  - C05
  - C06
  - C14
- consumer: U3
  provider: U2
  contracts:
  - C02
  - C03
- consumer: U4
  provider: U1
  contracts:
  - C01
  - C14
- consumer: U4
  provider: U2
  contracts:
  - C02
  - C03
- consumer: U4
  provider: U3
  contracts:
  - C04
  - C05
- consumer: U5
  provider: U1
  contracts:
  - C01
  - C14
- consumer: U5
  provider: U2
  contracts:
  - C02
  - C03
- consumer: U5
  provider: U3
  contracts:
  - C04
  - C05
- consumer: U6
  provider: U1
  contracts:
  - C01
  - C14
- consumer: U6
  provider: U2
  contracts:
  - C02
  - C03
- consumer: U6
  provider: U4
  contracts:
  - C07
  - C09
- consumer: U8
  provider: U1
  contracts:
  - C01
  - C11
  - C13
  - C14
- consumer: U8
  provider: U2
  contracts:
  - C02
  - C03
- consumer: U8
  provider: U3
  contracts:
  - C04
  - C05
  - C06
- consumer: U8
  provider: U4
  contracts:
  - C07
- consumer: U8
  provider: U5
  contracts:
  - C08
- consumer: U8
  provider: U6
  contracts:
  - C09
- consumer: U8
  provider: U7
  contracts:
  - C10
```

## C00 — Canonical data schemas

Identifiers and revision strings have format limits; these are wire-shape decisions, not workload or service-quality targets. Schemas are the shared source for typed operations and the HTTP copies below.

```yaml shared-schema
$schema: https://json-schema.org/draft/2020-12/schema
$id: urn:docsuri:v2:schemas
$defs:
  Id: {type: string, minLength: 1, maxLength: 128}
  Revision: {type: string, minLength: 1, maxLength: 128}
  Time: {type: string, format: date-time}
  Hash: {type: string, pattern: '^[a-f0-9]{64}$'}
  PolicyRef: {type: object, properties: {policyId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}}, required: [policyId, revision],
      additionalProperties: false}
  Principal: {oneOf: [{type: object, properties: {kind: {const: anonymous}, requestScope: {$ref: '#/$defs/Id'}}, required: [kind, requestScope],
          additionalProperties: false}, {type: object, properties: {kind: {const: account}, accountId: {$ref: '#/$defs/Id'}, authorityRevision: {
              $ref: '#/$defs/Revision'}, roles: {type: array, items: {type: string, enum: [user, admin]}, x-limit-policy: AdmissionPolicy
                bounds length; unresolved policy blocks admission.}, mfa: {type: boolean}}, required: [kind, accountId, authorityRevision,
            roles, mfa], additionalProperties: false}, {type: object, properties: {kind: {const: operator}, actorId: {$ref: '#/$defs/Id'},
            authorityRef: {$ref: '#/$defs/Id'}}, required: [kind, actorId, authorityRef], additionalProperties: false}]}
  CommandContext: {type: object, properties: {requestId: {$ref: '#/$defs/Id'}, principal: {$ref: '#/$defs/Principal'}, idempotencyKey: {$ref: '#/$defs/Id'},
        expectedRevision: {$ref: '#/$defs/Revision'}, policyRevision: {$ref: '#/$defs/PolicyRef'}}, required: [requestId, principal],
      additionalProperties: false}
  Error: {type: object, properties: {code: {type: string, enum: [APPROVAL_REQUIRED, CANCELLED, CAPACITY_EXHAUSTED, CONFLICT, CONSENT_REVOKED,
            DEADLINE_EXCEEDED, DEPENDENCY_UNAVAILABLE, EXPIRED, FORBIDDEN, IDEMPOTENCY_CONFLICT, INCOMPATIBLE, INCOMPATIBLE_VERSION,
            INTERNAL_ERROR, INVALID_ARGUMENT, INVALID_CONTENT, INVALID_INPUT, INVALID_TOKEN, MFA_REQUIRED, NOT_FOUND, NOT_READY, OUTCOME_UNKNOWN,
            POLICY_DENIED, POLICY_UNRESOLVED, QUOTA_EXCEEDED, RATE_LIMITED, SNAPSHOT_EXPIRED, SOURCE_INELIGIBLE, STALE_REVISION, UNAUTHENTICATED,
            UNKNOWN_OUTCOME]}, requestId: {$ref: '#/$defs/Id'}, retryable: {type: boolean}, messageKey: {$ref: '#/$defs/Id'}, retryAfterSeconds: {
          type: integer, minimum: 0}, details: {type: object, properties: {fieldNames: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy
                bounds length; unresolved policy blocks admission.}}, required: [fieldNames], additionalProperties: false}}, required: [
        code, requestId, retryable, messageKey], additionalProperties: false}
  PaperRef: {type: object, properties: {paperId: {$ref: '#/$defs/Id'}, versionId: {$ref: '#/$defs/Id'}, eligibilityRevision: {$ref: '#/$defs/Revision'}},
      required: [paperId, versionId, eligibilityRevision], additionalProperties: false}
  ResultRef: {type: object, properties: {resultId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'},
        mediaType: {type: string, minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.}},
      required: [resultId, revision, contentHash, mediaType], additionalProperties: false}
  PageRequest: {type: object, properties: {cursor: {anyOf: [{type: string, minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes and characters
                before persistence/processing.}, {type: 'null'}]}, limit: {type: integer, minimum: 1, x-limit-policy: bounded by selected
            admission policy}}, required: [], additionalProperties: false}
  PageInfo: {type: object, properties: {nextCursor: {anyOf: [{type: string, minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes and
                characters before persistence/processing.}, {type: 'null'}]}, snapshotRevision: {$ref: '#/$defs/Revision'}}, required: [
        nextCursor, snapshotRevision], additionalProperties: false}
  Ack: {type: object, properties: {resourceId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, requestId: {$ref: '#/$defs/Id'}},
      required: [resourceId, revision, requestId], additionalProperties: false}
  Progress: {oneOf: [{type: object, properties: {mode: {const: indeterminate}}, required: [mode], additionalProperties: false}, {type: object,
          properties: {mode: {const: determinate}, current: {type: integer, minimum: 0}, total: {type: integer, minimum: 1}}, required: [
            mode, current, total], additionalProperties: false}]}
  JobReceipt: {type: object, properties: {jobId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, seq: {type: integer, minimum: 0}, state: {type: string,
          enum: [accepted, running, cancel_requested, succeeded, failed, cancelled]}, requestId: {$ref: '#/$defs/Id'}, acceptedAt: {$ref: '#/$defs/Time'}},
      required: [jobId, revision, seq, state, requestId, acceptedAt], additionalProperties: false}
  JobSnapshot: {type: object, properties: {jobId: {$ref: '#/$defs/Id'}, kind: {$ref: '#/$defs/Id'}, state: {type: string, enum: [accepted, running, cancel_requested,
            succeeded, failed, cancelled]}, revision: {$ref: '#/$defs/Revision'}, seq: {type: integer, minimum: 0}, ownerId: {$ref: '#/$defs/Id'},
        progress: {$ref: '#/$defs/Progress'}, result: {anyOf: [{$ref: '#/$defs/ResultRef'}, {type: 'null'}]}, error: {anyOf: [{$ref: '#/$defs/Error'},
            {type: 'null'}]}, acceptedAt: {$ref: '#/$defs/Time'}}, required: [jobId, kind, state, revision, seq, ownerId, progress, result, error,
        acceptedAt], additionalProperties: false, allOf: [{if: {properties: {state: {const: succeeded}}}, then: {properties: {result: {$ref: '#/$defs/ResultRef'},
              error: {type: 'null'}}}}, {if: {properties: {state: {const: failed}}}, then: {properties: {error: {$ref: '#/$defs/Error'}, result: {
                type: 'null'}}}}, {if: {properties: {state: {enum: [accepted, running, cancel_requested, cancelled]}}}, then: {properties: {result: {
                type: 'null'}}}}]}
  JsonValue: {anyOf: [{type: [string, number, boolean, 'null']}, {type: array, items: {$ref: '#/$defs/JsonValue'}}, {type: object, additionalProperties: {
            $ref: '#/$defs/JsonValue'}}]}
  OperatorEvidenceRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, targetId: {$ref: '#/$defs/Id'}, inputHash: {$ref: '#/$defs/Hash'},
        requiredGeneration: {$ref: '#/$defs/Revision'}}, required: [context, targetId, inputHash, requiredGeneration], additionalProperties: false}
  OperatorEvidence: {type: object, properties: {evidenceId: {$ref: '#/$defs/Id'}, targetId: {$ref: '#/$defs/Id'}, inputHash: {$ref: '#/$defs/Hash'},
        generation: {$ref: '#/$defs/Revision'}, observedAt: {$ref: '#/$defs/Time'}, compatibility: {type: string, enum: [compatible,
            incompatible, unknown]}, checks: {type: array, items: {type: object, properties: {name: {$ref: '#/$defs/Id'}, outcome: {
                type: string, enum: [pass, fail, unknown]}, evidenceRef: {$ref: '#/$defs/Id'}}, required: [name, outcome, evidenceRef],
            additionalProperties: false}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}}, required: [
        evidenceId, targetId, inputHash, generation, observedAt, compatibility, checks], additionalProperties: false}
  OperatorExecuteRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, operation: {$ref: '#/$defs/Id'}, targetId: {$ref: '#/$defs/Id'},
        inputHash: {$ref: '#/$defs/Hash'}, evidenceId: {$ref: '#/$defs/Id'}, evidenceGeneration: {$ref: '#/$defs/Revision'}, authorityRef: {
          $ref: '#/$defs/Id'}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, operation, targetId, inputHash, evidenceId,
        evidenceGeneration, authorityRef, policy], additionalProperties: false}
  OperatorReceiptRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, operationId: {$ref: '#/$defs/Id'}}, required: [context,
        operationId], additionalProperties: false}
  OperatorReceipt: {type: object, properties: {operationId: {$ref: '#/$defs/Id'}, receiptId: {$ref: '#/$defs/Id'}, targetId: {$ref: '#/$defs/Id'},
        inputHash: {$ref: '#/$defs/Hash'}, authorityRef: {$ref: '#/$defs/Id'}, evidenceId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        outcome: {type: string, enum: [accepted, running, succeeded, failed, unknown]}, effectRefs: {type: array, items: {$ref: '#/$defs/Id'},
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}, reconciliationEvidence: {type: array,
          items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}}, required: [
        operationId, receiptId, targetId, inputHash, authorityRef, evidenceId, revision, outcome, effectRefs, reconciliationEvidence],
      additionalProperties: false}
  OpsQuery: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}, capability: {$ref: '#/$defs/Id'}},
      required: [context, page], additionalProperties: false}
  OpsObservation: {type: object, properties: {observationId: {$ref: '#/$defs/Id'}, capability: {$ref: '#/$defs/Id'}, component: {$ref: '#/$defs/Id'},
        observedAt: {$ref: '#/$defs/Time'}, revision: {$ref: '#/$defs/Revision'}, status: {type: string, enum: [available, degraded,
            unavailable, unknown]}, evidenceRef: {$ref: '#/$defs/Id'}, limitations: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy
            bounds length; unresolved policy blocks admission.}}, required: [observationId, capability, component, observedAt, revision,
        status, evidenceRef, limitations], additionalProperties: false}
  OpsObservationPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/OpsObservation'}, x-limit-policy: AdmissionPolicy bounds
            length; unresolved policy blocks admission.}, page: {$ref: '#/$defs/PageInfo'}}, required: [items, page], additionalProperties: false}
  OpsIncident: {type: object, properties: {incidentId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, capabilities: {type: array,
          items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}, correlationIds: {
          type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.},
        state: {type: string, enum: [open, investigating, recovering, resolved]}, evidenceRefs: {type: array, items: {$ref: '#/$defs/Id'},
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}}, required: [incidentId, revision, capabilities,
        correlationIds, state, evidenceRefs], additionalProperties: false}
  OpsIncidentPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/OpsIncident'}, x-limit-policy: AdmissionPolicy bounds length;
            unresolved policy blocks admission.}, page: {$ref: '#/$defs/PageInfo'}}, required: [items, page], additionalProperties: false}
  OpsRecoveryRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, incidentId: {$ref: '#/$defs/Id'}, ownerComponent: {$ref: '#/$defs/Id'},
        operation: {$ref: '#/$defs/Id'}, targetId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}, evidenceRefs: {
          type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.},
        policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, incidentId, ownerComponent, operation, targetId, expectedRevision,
        evidenceRefs, policy], additionalProperties: false}
  ProviderRequest: {oneOf: [{type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {
              $ref: '#/$defs/Revision'}, operation: {const: identity.profile}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {
              anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderIdentityProfileRead}, validatedPayload: {
              $ref: '#/$defs/ProviderIdentityProfileRead'}, effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}},
          required: [context, adapterId, adapterRevision, operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload,
            effectId, policy], additionalProperties: false}, {type: object, properties: {context: {$ref: '#/$defs/CommandContext'},
            adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {$ref: '#/$defs/Revision'}, operation: {const: source.search}, ownerComponent: {
              $ref: '#/$defs/Id'}, credentialRef: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderSourceSearch},
            validatedPayload: {$ref: '#/$defs/ProviderSourceSearch'}, effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {
              $ref: '#/$defs/PolicyRef'}}, required: [context, adapterId, adapterRevision, operation, ownerComponent, credentialRef,
            requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false}, {type: object, properties: {context: {
              $ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {$ref: '#/$defs/Revision'}, operation: {
              const: notion.inspect}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]},
            requestSchemaId: {const: ProviderNotionInspect}, validatedPayload: {$ref: '#/$defs/ProviderNotionInspect'}, effectId: {
              anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, adapterId,
            adapterRevision, operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false},
        {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {
              $ref: '#/$defs/Revision'}, operation: {const: effect.reconcile}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {
              anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderEffectReconcile}, validatedPayload: {
              $ref: '#/$defs/ProviderEffectReconcile'}, effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}},
          required: [context, adapterId, adapterRevision, operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload,
            effectId, policy], additionalProperties: false}, {type: object, properties: {context: {$ref: '#/$defs/CommandContext'},
            adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {$ref: '#/$defs/Revision'}, operation: {const: identity.exchange}, ownerComponent: {
              $ref: '#/$defs/Id'}, credentialRef: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderIdentityExchange},
            validatedPayload: {$ref: '#/$defs/ProviderIdentityExchange'}, effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]},
            policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, adapterId, adapterRevision, operation, ownerComponent, credentialRef,
            requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false}, {type: object, properties: {context: {
              $ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {$ref: '#/$defs/Revision'}, operation: {
              const: source.read}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]},
            requestSchemaId: {const: ProviderSourceRead}, validatedPayload: {$ref: '#/$defs/ProviderSourceRead'}, effectId: {anyOf: [
                {$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, adapterId, adapterRevision,
            operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false},
        {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {
              $ref: '#/$defs/Revision'}, operation: {const: citation.read}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {
              anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderCitationRead}, validatedPayload: {$ref: '#/$defs/ProviderCitationRead'},
            effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, adapterId,
            adapterRevision, operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false},
        {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {
              $ref: '#/$defs/Revision'}, operation: {const: model.generate}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {
              anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderModelRequest}, validatedPayload: {$ref: '#/$defs/ProviderModelRequest'},
            effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, adapterId,
            adapterRevision, operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false},
        {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {
              $ref: '#/$defs/Revision'}, operation: {const: attachment.extract}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {
              anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderExtractionRequest}, validatedPayload: {
              $ref: '#/$defs/ProviderExtractionRequest'}, effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}},
          required: [context, adapterId, adapterRevision, operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload,
            effectId, policy], additionalProperties: false}, {type: object, properties: {context: {$ref: '#/$defs/CommandContext'},
            adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {$ref: '#/$defs/Revision'}, operation: {const: email.send}, ownerComponent: {
              $ref: '#/$defs/Id'}, credentialRef: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, requestSchemaId: {const: ProviderEmailRequest},
            validatedPayload: {$ref: '#/$defs/ProviderEmailRequest'}, effectId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {
              $ref: '#/$defs/PolicyRef'}}, required: [context, adapterId, adapterRevision, operation, ownerComponent, credentialRef,
            requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false}, {type: object, properties: {context: {
              $ref: '#/$defs/CommandContext'}, adapterId: {$ref: '#/$defs/Id'}, adapterRevision: {$ref: '#/$defs/Revision'}, operation: {
              const: notion.write}, ownerComponent: {$ref: '#/$defs/Id'}, credentialRef: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]},
            requestSchemaId: {const: ProviderNotionRequest}, validatedPayload: {$ref: '#/$defs/ProviderNotionRequest'}, effectId: {
              anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, adapterId,
            adapterRevision, operation, ownerComponent, credentialRef, requestSchemaId, validatedPayload, effectId, policy], additionalProperties: false}]}
  ProviderOutcome: {type: object, properties: {requestId: {$ref: '#/$defs/Id'}, adapterRevision: {$ref: '#/$defs/Revision'}, outcome: {type: string,
          enum: [succeeded, rejected, retry_later, unknown]}, responseSchemaId: {$ref: '#/$defs/Id'}, validatedPayload: {anyOf: [{
              $ref: '#/$defs/ProviderIdentityProfileResult'}, {$ref: '#/$defs/ProviderSourceSearchResult'}, {$ref: '#/$defs/ProviderNotionInspection'},
            {$ref: '#/$defs/ProviderEffectEvidence'}, {$ref: '#/$defs/ProviderIdentityResult'}, {$ref: '#/$defs/ProviderSourceResult'},
            {$ref: '#/$defs/ProviderCitationResult'}, {$ref: '#/$defs/ProviderModelResult'}, {$ref: '#/$defs/ProviderExtractionResult'},
            {$ref: '#/$defs/ProviderEmailResult'}, {$ref: '#/$defs/ProviderNotionResult'}, {type: 'null'}]}, remoteReference: {anyOf: [
            {$ref: '#/$defs/Id'}, {type: 'null'}]}, retryAfterSeconds: {anyOf: [{type: integer, minimum: 0}, {type: 'null'}]}, evidenceRefs: {
          type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}},
      required: [requestId, adapterRevision, outcome, responseSchemaId, validatedPayload, remoteReference, retryAfterSeconds, evidenceRefs],
      additionalProperties: false}
  DispatchCommand: {type: object, properties: {messageId: {$ref: '#/$defs/Id'}, contractVersion: {const: 2.0.0}, ownerComponent: {$ref: '#/$defs/Id'}, operationId: {
          $ref: '#/$defs/Id'}, operationKind: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, inputRevision: {$ref: '#/$defs/Revision'}, inputHash: {
          $ref: '#/$defs/Hash'}, authorityRevision: {$ref: '#/$defs/Revision'}, policy: {$ref: '#/$defs/PolicyRef'}, payloadRef: {$ref: '#/$defs/Id'},
        acceptedAt: {$ref: '#/$defs/Time'}, attempt: {type: integer, minimum: 1}}, required: [messageId, contractVersion, ownerComponent, operationId,
        operationKind, ownerId, inputRevision, inputHash, authorityRevision, policy, payloadRef, acceptedAt, attempt], additionalProperties: false}
  DispatchFact: {type: object, properties: {messageId: {$ref: '#/$defs/Id'}, causationId: {$ref: '#/$defs/Id'}, ownerComponent: {$ref: '#/$defs/Id'}, operationId: {
          $ref: '#/$defs/Id'}, kind: {$ref: '#/$defs/Id'}, outcome: {type: string, enum: [progress, succeeded, failed, cancelled, unknown]}, resultRef: {
          anyOf: [{$ref: '#/$defs/ResultRef'}, {type: 'null'}]}, error: {anyOf: [{$ref: '#/$defs/Error'}, {type: 'null'}]}, claim: {$ref: '#/$defs/ExecutionClaim'},
        expectedJobRevision: {$ref: '#/$defs/Revision'}, inputHash: {$ref: '#/$defs/Hash'}, progress: {anyOf: [{$ref: '#/$defs/Progress'}, {type: 'null'}]},
        prepared: {anyOf: [{$ref: '#/$defs/AssistanceResult'}, {$ref: '#/$defs/ResearchArtifact'}, {type: 'null'}]}, usageRecordId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}},
      required: [messageId, causationId, ownerComponent, operationId, kind, outcome, resultRef, error, claim, expectedJobRevision, inputHash, progress,
        prepared, usageRecordId], additionalProperties: false, allOf: [{if: {properties: {outcome: {const: progress}}}, then: {properties: {progress: {
                $ref: '#/$defs/Progress'}, error: {type: 'null'}, resultRef: {type: 'null'}, prepared: {type: 'null'}}}}, {if: {properties: {outcome: {
                const: failed}}}, then: {properties: {error: {$ref: '#/$defs/Error'}, resultRef: {type: 'null'}, prepared: {type: 'null'}}}}, {if: {
            properties: {ownerComponent: {const: PaperAssistance}, outcome: {const: succeeded}}}, then: {properties: {prepared: {$ref: '#/$defs/AssistanceResult'},
              resultRef: {$ref: '#/$defs/ResultRef'}, usageRecordId: {$ref: '#/$defs/Id'}, error: {type: 'null'}}}},
        {if: {properties: {ownerComponent: {const: ResearchWorkspace}}},
          then: {properties: {prepared: {anyOf: [{$ref: '#/$defs/ResearchArtifact'}, {type: 'null'}]}}},
          else: {properties: {prepared: {anyOf: [{$ref: '#/$defs/AssistanceResult'}, {type: 'null'}]}}}},
        {if: {properties: {ownerComponent: {const: ResearchWorkspace}, outcome: {const: succeeded}}},
          then: {properties: {prepared: {$ref: '#/$defs/ResearchArtifact'}, resultRef: {$ref: '#/$defs/ResultRef'},
              usageRecordId: {$ref: '#/$defs/Id'}, error: {type: 'null'}, progress: {type: 'null'}}}},
        {if: {properties: {ownerComponent: {const: ResearchWorkspace}, outcome: {not: {const: succeeded}}}},
          then: {properties: {prepared: {type: 'null'}, resultRef: {type: 'null'}}}}]}
  DispatchAck: {type: object, properties: {messageId: {$ref: '#/$defs/Id'}, operationId: {$ref: '#/$defs/Id'}, disposition: {type: string, enum: [
            committed, duplicate, rejected, retry_later]}, recordedRevision: {$ref: '#/$defs/Revision'}}, required: [messageId, operationId,
        disposition, recordedRevision], additionalProperties: false}
  ProviderIdentityExchange: {type: object, properties: {provider: {type: string, enum: [google, orcid]}, authorizationCode: {type: string, minLength: 1, x-limit-policy: AdmissionPolicy
            bounds bytes and characters before persistence/processing.}, redirectBindingId: {$ref: '#/$defs/Id'}, stateBindingId: {
          $ref: '#/$defs/Id'}, nonceBindingId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}}, required: [provider, authorizationCode,
        redirectBindingId, stateBindingId, nonceBindingId], additionalProperties: false}
  ProviderIdentityResult: {type: object, properties: {provider: {type: string, enum: [google, orcid]}, subject: {$ref: '#/$defs/Id'}, issuer: {type: string,
          minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.}, credentialRef: {
          $ref: '#/$defs/Id'}, verifiedClaimsRevision: {$ref: '#/$defs/Revision'}, consentedScopeIds: {type: array, items: {$ref: '#/$defs/Id'},
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}}, required: [provider, subject, issuer,
        credentialRef, verifiedClaimsRevision, consentedScopeIds], additionalProperties: false}
  ProviderSourceRead: {type: object, properties: {sourceId: {$ref: '#/$defs/Id'}, recordId: {$ref: '#/$defs/Id'}, version: {$ref: '#/$defs/Revision'},
        requestedUse: {type: string, enum: [metadata, read, model, redistribute]}, permissionPolicy: {$ref: '#/$defs/PolicyRef'}},
      required: [sourceId, recordId, version, requestedUse, permissionPolicy], additionalProperties: false}
  ProviderSourceResult: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, sourceId: {$ref: '#/$defs/Id'}, contentRef: {anyOf: [{$ref: '#/$defs/Id'},
            {type: 'null'}]}, permissionDecisionRef: {$ref: '#/$defs/Id'}, observedAt: {$ref: '#/$defs/Time'}}, required: [paper, sourceId,
        contentRef, permissionDecisionRef, observedAt], additionalProperties: false}
  ProviderCitationRead: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, page: {$ref: '#/$defs/PageRequest'}}, required: [paper, page], additionalProperties: false}
  ProviderCitationResult: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, references: {type: array, items: {$ref: '#/$defs/PaperRef'}, x-limit-policy: AdmissionPolicy
            bounds length; unresolved policy blocks admission.}, page: {$ref: '#/$defs/PageInfo'}, observedAt: {$ref: '#/$defs/Time'},
        complete: {type: boolean}}, required: [paper, references, page, observedAt, complete], additionalProperties: false}
  ProviderModelRequest: {type: object, properties: {operationId: {$ref: '#/$defs/Id'}, modelProfile: {$ref: '#/$defs/Id'}, modelRevision: {$ref: '#/$defs/Revision'},
        modeId: {$ref: '#/$defs/Id'}, inputRefs: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds
            length; unresolved policy blocks admission.}, inputHash: {$ref: '#/$defs/Hash'}, languageId: {$ref: '#/$defs/Id'}, outputSchemaId: {
          $ref: '#/$defs/Id'}, permissionPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [operationId, modelProfile, modelRevision,
        modeId, inputRefs, inputHash, languageId, outputSchemaId, permissionPolicy], additionalProperties: false}
  ProviderModelResult: {type: object, properties: {operationId: {$ref: '#/$defs/Id'}, result: {$ref: '#/$defs/ResultRef'}, modelRevision: {$ref: '#/$defs/Revision'},
        inputHash: {$ref: '#/$defs/Hash'}, groundingEvidenceRefs: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy
            bounds length; unresolved policy blocks admission.}}, required: [operationId, result, modelRevision, inputHash, groundingEvidenceRefs],
      additionalProperties: false}
  ProviderExtractionRequest: {type: object, properties: {ownerId: {$ref: '#/$defs/Id'}, attachmentId: {$ref: '#/$defs/Id'}, inputHash: {$ref: '#/$defs/Hash'},
        mediaType: {type: string, minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.},
        contentRef: {$ref: '#/$defs/Id'}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [ownerId, attachmentId, inputHash, mediaType,
        contentRef, policy], additionalProperties: false}
  ProviderExtractionResult: {type: object, properties: {attachmentId: {$ref: '#/$defs/Id'}, inputHash: {$ref: '#/$defs/Hash'}, textRef: {anyOf: [{$ref: '#/$defs/Id'},
            {type: 'null'}]}, outcome: {type: string, enum: [complete, partial, rejected]}, limitations: {type: array, items: {$ref: '#/$defs/Id'},
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}}, required: [attachmentId, inputHash,
        textRef, outcome, limitations], additionalProperties: false}
  ProviderEmailRequest: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, recipientRef: {$ref: '#/$defs/Id'}, templateId: {$ref: '#/$defs/Id'},
        templateRevision: {$ref: '#/$defs/Revision'}, variablesRef: {$ref: '#/$defs/Id'}, authorityRevision: {$ref: '#/$defs/Revision'},
        policy: {$ref: '#/$defs/PolicyRef'}}, required: [effectId, recipientRef, templateId, templateRevision, variablesRef, authorityRevision,
        policy], additionalProperties: false}
  ProviderEmailResult: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, providerMessageId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]},
        disposition: {type: string, enum: [accepted, rejected, unknown]}}, required: [effectId, providerMessageId, disposition], additionalProperties: false}
  ProviderNotionRequest: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, approvalId: {$ref: '#/$defs/Id'}, connectionId: {$ref: '#/$defs/Id'},
        destinationId: {$ref: '#/$defs/Id'}, artifact: {$ref: '#/$defs/ResultRef'}, previewHash: {$ref: '#/$defs/Hash'}, contentHash: {
          $ref: '#/$defs/Hash'}, marker: {type: string, minLength: 1, maxLength: 200}}, required: [
        effectId, approvalId, connectionId, destinationId, artifact, previewHash], additionalProperties: false}
  ProviderNotionResult: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, remotePageId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, disposition: {
          type: string, enum: [committed, rejected, unknown]}, providerRequestId: {$ref: '#/$defs/Id'}, refusalClass: {$ref: '#/$defs/ProviderNotionRefusalClass'}},
      required: [effectId, remotePageId, disposition], additionalProperties: false}
  ProviderNotionRefusalClass: {type: string, enum: [token-invalid, no-access, destination-missing, content-rejected, workspace-block-limit, provider-blocked]}
  ProviderIdentityProfileRead: {type: object, properties: {provider: {type: string, enum: [google, orcid]}, subject: {$ref: '#/$defs/Id'}, credentialRef: {$ref: '#/$defs/Id'},
        consentRevision: {$ref: '#/$defs/Revision'}}, required: [provider, subject, credentialRef, consentRevision], additionalProperties: false}
  ProviderIdentityProfileResult: {type: object, properties: {provider: {type: string, enum: [google, orcid]}, subject: {$ref: '#/$defs/Id'}, profileRevision: {
          $ref: '#/$defs/Revision'}, displayName: {anyOf: [{type: string, minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes
                and characters before persistence/processing.}, {type: 'null'}]}, orcid: {anyOf: [{type: string, minLength: 1, x-limit-policy: AdmissionPolicy
                bounds bytes and characters before persistence/processing.}, {type: 'null'}]}, affiliations: {type: array, items: {
            type: string, minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.},
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}, observedAt: {$ref: '#/$defs/Time'}},
      required: [provider, subject, profileRevision, displayName, orcid, affiliations, observedAt], additionalProperties: false}
  ProviderSourceSearch: {type: object, properties: {sourceId: {$ref: '#/$defs/Id'}, query: {type: string, minLength: 1, x-limit-policy: AdmissionPolicy
            bounds bytes and characters before persistence/processing.}, scope: {type: string, enum: [papers, permitted_web]}, page: {
          $ref: '#/$defs/PageRequest'}, permissionPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [sourceId, query, scope, page, permissionPolicy],
      additionalProperties: false}
  ProviderSourceSearchResult: {type: object, properties: {sourceId: {$ref: '#/$defs/Id'}, items: {type: array, items: {type: object, properties: {sourceRecordId: {
                $ref: '#/$defs/Id'}, version: {$ref: '#/$defs/Revision'}, title: {type: string, minLength: 1, x-limit-policy: AdmissionPolicy
                  bounds bytes and characters before persistence/processing.}, url: {type: string, format: uri}, snippet: {type: string,
                minLength: 1, x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.}, permissionDecisionRef: {
                $ref: '#/$defs/Id'}, observedAt: {$ref: '#/$defs/Time'}}, required: [sourceRecordId, version, title, url, snippet,
              permissionDecisionRef, observedAt], additionalProperties: false}, x-limit-policy: AdmissionPolicy bounds length; unresolved
            policy blocks admission.}, page: {$ref: '#/$defs/PageInfo'}, complete: {type: boolean}}, required: [sourceId, items, page,
        complete], additionalProperties: false}
  ProviderNotionInspect: {type: object, properties: {connectionId: {$ref: '#/$defs/Id'}, connectionRevision: {$ref: '#/$defs/Revision'}, page: {$ref: '#/$defs/PageRequest'}},
      required: [connectionId, connectionRevision, page], additionalProperties: false}
  ProviderNotionInspection: {type: object, properties: {connectionId: {$ref: '#/$defs/Id'}, connectionRevision: {$ref: '#/$defs/Revision'}, valid: {type: boolean},
        destinations: {type: array, items: {type: object, properties: {destinationId: {$ref: '#/$defs/Id'}, title: {type: string, minLength: 1,
                x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.}, revision: {$ref: '#/$defs/Revision'},
              writable: {type: boolean}, readable: {type: boolean}, creationCapability: {$ref: '#/$defs/ExportCreationCapability'}}, required: [
              destinationId, title, revision, writable], additionalProperties: false}, x-limit-policy: AdmissionPolicy
            bounds length; unresolved policy blocks admission.}, page: {$ref: '#/$defs/PageInfo'}, observedAt: {$ref: '#/$defs/Time'},
        workspaceName: {type: string, minLength: 1, maxLength: 2000}, integrationIdentity: {$ref: '#/$defs/Id'}},
      required: [connectionId, connectionRevision, valid, destinations, page, observedAt], additionalProperties: false}
  ProviderEffectReconcile: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, providerId: {$ref: '#/$defs/Id'}, credentialRef: {$ref: '#/$defs/Id'},
        requestHash: {$ref: '#/$defs/Hash'}, remoteReference: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, marker: {type: string, minLength: 1,
          maxLength: 200}, destinationId: {$ref: '#/$defs/Id'}, firstAttemptStartedAt: {$ref: '#/$defs/Time'}, writerIdentity: {$ref: '#/$defs/Id'}},
      required: [effectId, providerId, credentialRef, requestHash, remoteReference], additionalProperties: false}
  ProviderEffectEvidence: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, disposition: {type: string, enum: [committed, definitely_not_committed,
            unknown]}, remoteReference: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, evidenceHash: {anyOf: [{$ref: '#/$defs/Hash'},
            {type: 'null'}]}, observedAt: {$ref: '#/$defs/Time'}, scanComplete: {type: boolean}}, required: [effectId, disposition, remoteReference,
        evidenceHash, observedAt], additionalProperties: false}
  LibraryFilter: {type: object, properties: {filterId: {$ref: '#/$defs/Id'}, operatorId: {$ref: '#/$defs/Id'}, values: {type: array, items: {oneOf: [
              {type: string, x-policy-bound: search filter value}, {type: integer}, {type: boolean}]}, x-policy-bound: search vocabulary
            entry and approved input policy}}, required: [filterId, operatorId, values], additionalProperties: false}
  LibraryQueryContext: {type: object, properties: {query: {type: string, minLength: 1, x-policy-bound: search query size/input policy, description: Bound
            by the named approved policy before processing.}, modeId: {$ref: '#/$defs/Id'}, orderId: {$ref: '#/$defs/Id'}, filters: {
          type: array, items: {$ref: '#/$defs/LibraryFilter'}, x-policy-bound: retained filter vocabulary and search policy}, vocabularyRevision: {
          $ref: '#/$defs/Revision'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [query, modeId, orderId, filters, vocabularyRevision,
        policyRef], additionalProperties: false, description: 'Canonical submitted query/refinement context shared by search, saved
        queries and history. Unknown or unsupported vocabulary IDs are rejected; no arbitrary query-engine syntax is accepted through
        filters.'}
  HostContractBinding: {type: object, properties: {contractId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, schemaDigest: {$ref: '#/$defs/Hash'}},
      required: [contractId, revision, schemaDigest], additionalProperties: false}
  HostRouteContribution: {type: object, properties: {routeId: {$ref: '#/$defs/Id'}, pathTemplate: {type: string, minLength: 1, x-policy-bound: trusted route-template
            policy, description: Bound by the named approved policy before processing.}, titleKey: {$ref: '#/$defs/Id'}, capabilityId: {
          $ref: '#/$defs/Id'}, accessRuleId: {$ref: '#/$defs/Id'}, viewFactoryId: {$ref: '#/$defs/Id'}}, required: [routeId, pathTemplate,
        titleKey, capabilityId, accessRuleId, viewFactoryId], additionalProperties: false}
  HostContribution: {type: object, properties: {contributionId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, components: {type: array,
          items: {type: string, enum: [AccountAccess, CorpusContent, Discovery, Library, PaperAssistance, ResearchWorkspace, Personalization,
              TopicsDigests, ApprovedExport, UsageEntitlements, ServiceOperations, PlatformControl, WebWorkspace]}, maxItems: 13, uniqueItems: true},
        requires: {type: array, items: {$ref: '#/$defs/HostContractBinding'}, x-policy-bound: compiled application contract manifest},
        provides: {type: array, items: {$ref: '#/$defs/HostContractBinding'}, x-policy-bound: compiled application contract manifest},
        routes: {type: array, items: {$ref: '#/$defs/HostRouteContribution'}, x-policy-bound: compiled route manifest}, capabilityIds: {
          type: array, items: {$ref: '#/$defs/Id'}, x-policy-bound: compiled capability manifest, uniqueItems: true}, lifecycleParticipantIds: {
          type: array, items: {$ref: '#/$defs/Id'}, x-policy-bound: required participant manifest, uniqueItems: true}}, required: [
        contributionId, revision, components, requires, provides, routes, capabilityIds, lifecycleParticipantIds], additionalProperties: false,
      description: 'Trusted compiled application contribution, not an externally installable plugin or browser registration request.'}
  HostRegisterInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contribution: {$ref: '#/$defs/HostContribution'}, expectedManifestRevision: {
          $ref: '#/$defs/Revision'}}, required: [context, contribution, expectedManifestRevision], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  HostManifestResult: {type: object, properties: {manifestRevision: {$ref: '#/$defs/Revision'}, acceptedContributionIds: {type: array, items: {$ref: '#/$defs/Id'},
          x-policy-bound: compiled contribution manifest, uniqueItems: true}, ready: {type: boolean}, missingRequiredBindings: {type: array,
          items: {$ref: '#/$defs/HostContractBinding'}, x-policy-bound: compiled dependency manifest}, missingLifecycleParticipants: {
          type: array, items: {$ref: '#/$defs/Id'}, x-policy-bound: required participant manifest, uniqueItems: true}}, required: [
        manifestRevision, acceptedContributionIds, ready, missingRequiredBindings, missingLifecycleParticipants], additionalProperties: false}
  HostInspectInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, manifestRevision: {$ref: '#/$defs/Revision'}}, required: [
        context, manifestRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted
        boundary, never accepted from a public body.'}
  HostCapability: {type: object, properties: {capabilityId: {$ref: '#/$defs/Id'}, owner: {type: string, enum: [AccountAccess, CorpusContent, Discovery,
            Library, PaperAssistance, ResearchWorkspace, Personalization, TopicsDigests, ApprovedExport, UsageEntitlements, ServiceOperations,
            PlatformControl, WebWorkspace]}, state: {type: string, enum: [available, degraded, unavailable, unknown]}, observedAt: {
          $ref: '#/$defs/Time'}, evidenceRevision: {$ref: '#/$defs/Revision'}, reasonKey: {$ref: '#/$defs/Id'}}, required: [capabilityId,
        owner, state, observedAt, evidenceRevision, reasonKey], additionalProperties: false}
  HostCapabilitiesInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  HostCapabilitiesPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/HostCapability'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  HostPaperReturnContext: {type: object, properties: {kind: {const: paper}, paper: {$ref: '#/$defs/PaperRef'}, anchorId: {$ref: '#/$defs/Id'}}, required: [
        kind, paper], additionalProperties: false}
  HostSearchReturnContext: {type: object, properties: {kind: {const: search}, queryContext: {$ref: '#/$defs/LibraryQueryContext'}, resultWindowId: {$ref: '#/$defs/Id'},
        resultPosition: {type: integer, minimum: 0}}, required: [kind, queryContext, resultWindowId], additionalProperties: false}
  HostRouteReturnContext: {type: object, properties: {kind: {const: route}, routeId: {$ref: '#/$defs/Id'}}, required: [kind, routeId], additionalProperties: false}
  HostReturnContext: {oneOf: [{$ref: '#/$defs/HostPaperReturnContext'}, {$ref: '#/$defs/HostSearchReturnContext'}, {$ref: '#/$defs/HostRouteReturnContext'}]}
  HostNavigationInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, routeId: {$ref: '#/$defs/Id'}, returnContext: {$ref: '#/$defs/HostReturnContext'}},
      required: [context, routeId], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted
        boundary, never accepted from a public body.'}
  HostNavigationItem: {type: object, properties: {routeId: {$ref: '#/$defs/Id'}, titleKey: {$ref: '#/$defs/Id'}, path: {type: string, minLength: 1, x-policy-bound: registered
            relative route policy, description: Bound by the named approved policy before processing.}, capabilityId: {$ref: '#/$defs/Id'},
        available: {type: boolean}, reasonKey: {$ref: '#/$defs/Id'}}, required: [routeId, titleKey, path, capabilityId, available],
      additionalProperties: false}
  HostNavigationResult: {type: object, properties: {manifestRevision: {$ref: '#/$defs/Revision'}, authorityRevision: {$ref: '#/$defs/Revision'}, items: {
          type: array, items: {$ref: '#/$defs/HostNavigationItem'}, x-policy-bound: authorized compiled navigation manifest}, resolvedRouteId: {
          $ref: '#/$defs/Id'}, returnContext: {$ref: '#/$defs/HostReturnContext'}, clearPriorOwnerState: {type: boolean}}, required: [
        manifestRevision, authorityRevision, items, resolvedRouteId, clearPriorOwnerState], additionalProperties: false}
  HostObservation: {type: object, properties: {observationId: {$ref: '#/$defs/Id'}, requestId: {$ref: '#/$defs/Id'}, capabilityId: {$ref: '#/$defs/Id'},
        observedAt: {$ref: '#/$defs/Time'}, outcomeCode: {$ref: '#/$defs/Id'}, operationReference: {$ref: '#/$defs/Id'}, evidenceRevision: {
          $ref: '#/$defs/Revision'}}, required: [observationId, requestId, capabilityId, observedAt, outcomeCode, evidenceRevision],
      additionalProperties: false}
  HostObservationInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, observation: {$ref: '#/$defs/HostObservation'}}, required: [
        context, observation], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  AccessSecret: {type: string, minLength: 1, x-policy-bound: credential input policy, description: 'Sensitive proof/credential; never logged, reflected
        or placed in a URL.', writeOnly: true, x-sensitive: true}
  AccessEmail: {type: string, format: email, x-policy-bound: email normalization and size policy}
  AccessPublicSession: {type: object, properties: {sessionId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, authorityRevision: {$ref: '#/$defs/Revision'},
        verified: {type: boolean}, authenticationLevel: {type: string, enum: [primary, mfa]}, expiresAt: {$ref: '#/$defs/Time'}}, required: [
        sessionId, accountId, authorityRevision, verified, authenticationLevel], additionalProperties: false}
  AccessAnonymousSession: {type: object, properties: {state: {const: anonymous}, requestId: {$ref: '#/$defs/Id'}}, required: [state, requestId], additionalProperties: false}
  AccessKnownSession: {type: object, properties: {state: {const: authenticated}, session: {$ref: '#/$defs/AccessPublicSession'}}, required: [state, session],
      additionalProperties: false}
  AccessSessionStatus: {oneOf: [{$ref: '#/$defs/AccessAnonymousSession'}, {$ref: '#/$defs/AccessKnownSession'}, {$ref: '#/$defs/AccessMfaContinuation'}]}
  AccessSessionInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}}, required: [context], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessRegisterInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, email: {$ref: '#/$defs/AccessEmail'}, password: {$ref: '#/$defs/AccessSecret'},
        displayName: {type: string, minLength: 1, x-policy-bound: profile display-name policy, description: Bound by the named approved
            policy before processing.}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [context, email, password, policyRef], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessChallengeDelivery: {type: object, properties: {requestId: {$ref: '#/$defs/Id'}, acknowledgement: {const: accepted}, messageKey: {$ref: '#/$defs/Id'}},
      required: [requestId, acknowledgement, messageKey], additionalProperties: false, description: 'Existence-neutral public acknowledgement.
        It does not expose account existence, challenge secrets or recipient-specific delivery facts.'}
  AccessEmailRequestInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, email: {$ref: '#/$defs/AccessEmail'}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [context, email, policyRef], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  AccessChallengeProof: {type: object, properties: {challengeId: {$ref: '#/$defs/Id'}, proof: {$ref: '#/$defs/AccessSecret'}, flowBinding: {$ref: '#/$defs/Id'}},
      required: [challengeId, proof, flowBinding], additionalProperties: false}
  AccessVerifyEmailInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, verification: {$ref: '#/$defs/AccessChallengeProof'}}, required: [
        context, verification], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  AccessLoginInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, email: {$ref: '#/$defs/AccessEmail'}, password: {$ref: '#/$defs/AccessSecret'},
        policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [context, email, password, policyRef], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessMfaContinuation: {type: object, properties: {state: {const: mfa_required}, challengeId: {$ref: '#/$defs/Id'}, flowBinding: {$ref: '#/$defs/Id'},
        expiresAt: {$ref: '#/$defs/Time'}}, required: [state, challengeId, flowBinding, expiresAt], additionalProperties: false}
  AccessLoginResult: {oneOf: [{$ref: '#/$defs/AccessKnownSession'}, {$ref: '#/$defs/AccessMfaContinuation'}]}
  AccessLogoutInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}}, required: [context], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessPasswordResetInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, verification: {$ref: '#/$defs/AccessChallengeProof'}, newPassword: {
          $ref: '#/$defs/AccessSecret'}}, required: [context, verification, newPassword], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessPasswordChangeInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, currentPassword: {$ref: '#/$defs/AccessSecret'}, newPassword: {
          $ref: '#/$defs/AccessSecret'}}, required: [context, currentPassword, newPassword], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessEmailChangeInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, currentProof: {$ref: '#/$defs/AccessSecret'}, newEmail: {
          $ref: '#/$defs/AccessEmail'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [context, currentProof, newEmail, policyRef],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  AccessEmailChangeCompleteInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, verification: {$ref: '#/$defs/AccessChallengeProof'}}, required: [
        context, verification], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  AccessBeginIdentityInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, provider: {type: string, enum: [google, orcid]}, intent: {
          type: string, enum: [sign_in, link]}, returnRouteId: {$ref: '#/$defs/Id'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [
        context, provider, intent, returnRouteId, policyRef], additionalProperties: false, description: 'Internal envelope; context
        is derived by the trusted boundary, never accepted from a public body.'}
  AccessProviderRedirect: {type: object, properties: {flowId: {$ref: '#/$defs/Id'}, provider: {type: string, enum: [google, orcid]}, authorizationUrl: {
          type: string, format: uri, x-policy-bound: allowlisted provider redirect length}, expiresAt: {$ref: '#/$defs/Time'}}, required: [
        flowId, provider, authorizationUrl, expiresAt], additionalProperties: false, description: URL generated from configured provider
        and registered callback binding; never copied from a caller-controlled destination.}
  AccessCompleteIdentityInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, flowId: {$ref: '#/$defs/Id'}, callbackState: {$ref: '#/$defs/AccessSecret'},
        authorizationCode: {$ref: '#/$defs/AccessSecret'}, callbackBinding: {$ref: '#/$defs/Id'}}, required: [context, flowId, callbackState,
        authorizationCode, callbackBinding], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  AccessIdentityLink: {type: object, properties: {identityLinkId: {$ref: '#/$defs/Id'}, provider: {type: string, enum: [google, orcid]}, providerSubject: {
          type: string, minLength: 1, x-policy-bound: provider subject policy, description: Bound by the named approved policy before
            processing.}, revision: {$ref: '#/$defs/Revision'}, profileAvailable: {type: boolean}}, required: [identityLinkId, provider,
        providerSubject, revision, profileAvailable], additionalProperties: false}
  AccessIdentitySignedIn: {type: object, properties: {state: {const: signed_in}, identityLink: {$ref: '#/$defs/AccessIdentityLink'}, session: {$ref: '#/$defs/AccessPublicSession'}},
      required: [state, identityLink, session], additionalProperties: false}
  AccessIdentityLinked: {type: object, properties: {state: {const: linked}, identityLink: {$ref: '#/$defs/AccessIdentityLink'}}, required: [state, identityLink],
      additionalProperties: false}
  AccessIdentityMfa: {type: object, properties: {state: {const: mfa_required}, mfaChallenge: {$ref: '#/$defs/AccessMfaContinuation'}}, required: [state,
        mfaChallenge], additionalProperties: false}
  AccessIdentityResult: {oneOf: [{$ref: '#/$defs/AccessIdentitySignedIn'}, {$ref: '#/$defs/AccessIdentityLinked'}, {$ref: '#/$defs/AccessIdentityMfa'}]}
  AccessUnlinkIdentityInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, identityLinkId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [context, identityLinkId, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  AccessIdentityListInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  AccessIdentityPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/AccessIdentityLink'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  AccessOrcidProfileInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, identityLinkId: {$ref: '#/$defs/Id'}}, required: [context,
        identityLinkId], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  AccessOrcidWork: {type: object, properties: {sourceId: {$ref: '#/$defs/Id'}, title: {type: string, minLength: 1, x-policy-bound: ORCID work-title
            policy, description: Bound by the named approved policy before processing.}, externalIdentifiers: {type: array, items: {
            type: string, minLength: 1, x-policy-bound: ORCID external identifier policy, description: Bound by the named approved
              policy before processing.}, x-policy-bound: ORCID work identifier policy}, sourceUrl: {type: string, format: uri, x-policy-bound: eligible
            profile source URL policy}}, required: [sourceId, title, externalIdentifiers], additionalProperties: false}
  AccessOrcidProfile: {type: object, properties: {identityLinkId: {$ref: '#/$defs/Id'}, subject: {type: string, minLength: 1, x-policy-bound: ORCID subject
            policy, description: Bound by the named approved policy before processing.}, revision: {$ref: '#/$defs/Revision'}, provenance: {
          type: string, minLength: 1, x-policy-bound: profile provenance policy, description: Bound by the named approved policy before
            processing.}, displayName: {type: string, minLength: 1, x-policy-bound: profile display-name policy, description: Bound
            by the named approved policy before processing.}, works: {type: array, items: {$ref: '#/$defs/AccessOrcidWork'}, x-policy-bound: approved
            ORCID enrichment count policy}, coverage: {type: string, enum: [complete, partial, unavailable]}}, required: [identityLinkId,
        subject, revision, provenance, works, coverage], additionalProperties: false}
  AccessMfaVerifyInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, verification: {$ref: '#/$defs/AccessChallengeProof'}, factorKind: {
          type: string, enum: [totp, recovery_proof]}}, required: [context, verification, factorKind], additionalProperties: false,
      description: 'Pre-authentication request: context may contain an anonymous principal. The trusted transport separately validates
        the protected primary-authentication continuation cookie, binds it to verification.challengeId/flowBinding and the server-owned
        primary-authentication record, and passes only a verified invocation. The factor proof is untrusted until checked; neither
        a full session nor a caller-claimed account is required.'}
  AccessMfaEnrollmentInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, currentProof: {$ref: '#/$defs/AccessSecret'}, policyRef: {
          $ref: '#/$defs/PolicyRef'}}, required: [context, currentProof, policyRef], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessMfaEnrollment: {type: object, properties: {enrollmentId: {$ref: '#/$defs/Id'}, deliveryReference: {$ref: '#/$defs/Id'}, expiresAt: {$ref: '#/$defs/Time'},
        nextAction: {const: confirm_factor}}, required: [enrollmentId, deliveryReference, expiresAt, nextAction], additionalProperties: false,
      description: Protected one-time enrollment delivery is separate from ordinary JSON/log output; no factor seed or recovery code
        is returned here.}
  AccessEnrollmentSecret: {type: string, minLength: 1, x-policy-bound: protected MFA enrollment-material policy, description: Secret output permitted only
        by the protected single-use enrollment-material response; redact entirely from diagnostics and do not cache or persist in the
        client., readOnly: true, x-sensitive: true, x-protected-one-time: true}
  AccessMfaMaterialInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, enrollmentId: {$ref: '#/$defs/Id'}, deliveryReference: {
          $ref: '#/$defs/Id'}, currentProof: {$ref: '#/$defs/AccessSecret'}}, required: [context, enrollmentId, deliveryReference,
        currentProof], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never
        accepted from a public body.'}
  AccessMfaMaterial: {type: object, properties: {enrollmentId: {$ref: '#/$defs/Id'}, seed: {$ref: '#/$defs/AccessEnrollmentSecret'}, provisioningUri: {
          $ref: '#/$defs/AccessEnrollmentSecret'}, recoveryCodes: {type: array, items: {$ref: '#/$defs/AccessEnrollmentSecret'}, x-policy-bound: approved
            MFA recovery-code count/size policy, uniqueItems: true}, expiresAt: {$ref: '#/$defs/Time'}}, required: [enrollmentId, seed,
        provisioningUri, recoveryCodes, expiresAt], additionalProperties: false, description: 'Dedicated protected response only. provisioningUri
        encodes this enrollment''s seed and account/issuer binding and may be rendered as a QR locally, without an external QR service.
        Recovery codes remain unusable before successful enrollment confirmation. The trusted HTTP adapter applies Cache-Control: no-store
        and excludes the response from logging, tracing, generic result caches and persisted client storage.'}
  AccessMfaConfirmInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, enrollmentId: {$ref: '#/$defs/Id'}, verification: {$ref: '#/$defs/AccessChallengeProof'}},
      required: [context, enrollmentId, verification], additionalProperties: false, description: 'Internal envelope; context is derived
        by the trusted boundary, never accepted from a public body.'}
  AccessMfaRecoveryInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, verification: {$ref: '#/$defs/AccessChallengeProof'}, policyRef: {
          $ref: '#/$defs/PolicyRef'}}, required: [context, verification, policyRef], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessProfileValue: {oneOf: [{type: string, x-policy-bound: declared profile field policy}, {type: boolean}, {type: array, items: {$ref: '#/$defs/Id'},
          x-policy-bound: declared profile multi-choice policy, uniqueItems: true}, {type: 'null'}]}
  AccessProfileFieldDefinition: {type: object, properties: {fieldId: {$ref: '#/$defs/Id'}, labelKey: {$ref: '#/$defs/Id'}, valueKind: {type: string, enum: [text,
            boolean, single_choice, multi_choice]}, mutable: {type: boolean}, nullable: {type: boolean}, choiceIds: {type: array, items: {
            $ref: '#/$defs/Id'}, x-policy-bound: retained profile choice vocabulary, uniqueItems: true}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [fieldId, labelKey, valueKind, mutable, nullable, choiceIds, policyRef], additionalProperties: false}
  AccessProfileField: {type: object, properties: {fieldId: {$ref: '#/$defs/Id'}, value: {$ref: '#/$defs/AccessProfileValue'}}, required: [fieldId, value],
      additionalProperties: false}
  AccessProfileInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}}, required: [context], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessProfile: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, lifecycleRevision: {$ref: '#/$defs/Revision'}, email: {$ref: '#/$defs/AccessEmail'},
        emailVerified: {type: boolean}, fieldVocabularyRevision: {$ref: '#/$defs/Revision'}, definitions: {type: array, items: {$ref: '#/$defs/AccessProfileFieldDefinition'},
          x-policy-bound: retained editable-profile field vocabulary}, fields: {type: array, items: {$ref: '#/$defs/AccessProfileField'},
          x-policy-bound: retained editable-profile field vocabulary}}, required: [accountId, revision, email, emailVerified, fieldVocabularyRevision,
        definitions, fields, lifecycleRevision], additionalProperties: false}
  AccessProfileUpdateInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, fieldVocabularyRevision: {$ref: '#/$defs/Revision'}, changes: {type: array,
          items: {$ref: '#/$defs/AccessProfileField'}, x-policy-bound: retained mutable-profile field vocabulary}, policyRef: {$ref: '#/$defs/PolicyRef'},
        expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, fieldVocabularyRevision, changes, policyRef, expectedRevision], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessConsentRecord: {type: object, properties: {consentId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, purposeId: {$ref: '#/$defs/Id'},
        decision: {type: string, enum: [granted, revoked]}, revision: {$ref: '#/$defs/Revision'}, effectiveAt: {$ref: '#/$defs/Time'},
        policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [consentId, accountId, purposeId, decision, revision, effectiveAt, policyRef],
      additionalProperties: false}
  AccessConsentListInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  AccessConsentPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/AccessConsentRecord'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  AccessConsentUpdateInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, purposeId: {$ref: '#/$defs/Id'}, decision: {type: string,
          enum: [granted, revoked]}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, purposeId, decision, policyRef, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  AccessAuthorityInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, accountId: {$ref: '#/$defs/Id'}, operationId: {$ref: '#/$defs/Id'},
        resourceOwnerId: {$ref: '#/$defs/Id'}, requiredConsentPurposeIds: {type: array, items: {$ref: '#/$defs/Id'}, x-policy-bound: registered
            operation consent requirements, uniqueItems: true}}, required: [context, accountId, operationId, requiredConsentPurposeIds],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  AccessAuthorityDecision: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, operationId: {$ref: '#/$defs/Id'}, decision: {type: string, enum: [
            allow, deny]}, authorityRevision: {$ref: '#/$defs/Revision'}, consentRevisions: {type: array, items: {$ref: '#/$defs/AccessConsentRecord'},
          x-policy-bound: registered operation consent requirements}, reasonKey: {$ref: '#/$defs/Id'}, evaluatedAt: {$ref: '#/$defs/Time'}},
      required: [accountId, operationId, decision, authorityRevision, consentRevisions, reasonKey, evaluatedAt], additionalProperties: false}
  LifecycleAction: {type: string, enum: [withdraw, reactivate, erase]}
  LifecycleScope: {type: string, enum: [live_records, derived_artifacts, pending_work, caches, backups, restore_enforcement, external_copies]}
  LifecycleParticipant: {type: object, properties: {participantId: {$ref: '#/$defs/Id'}, component: {type: string, enum: [AccountAccess, CorpusContent,
            Discovery, Library, PaperAssistance, ResearchWorkspace, Personalization, TopicsDigests, ApprovedExport, UsageEntitlements,
            ServiceOperations, PlatformControl, WebWorkspace]}, contractRevision: {$ref: '#/$defs/Revision'}, requiredScopes: {type: array,
          items: {$ref: '#/$defs/LifecycleScope'}, maxItems: 7, uniqueItems: true}}, required: [participantId, component, contractRevision,
        requiredScopes], additionalProperties: false}
  LifecycleManifestInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, manifestRevision: {$ref: '#/$defs/Revision'}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, participants: {type: array, items: {$ref: '#/$defs/LifecycleParticipant'}, maxItems: 13}}, required: [
        context, manifestRevision, policyRef, participants], additionalProperties: false, description: 'Internal envelope; context
        is derived by the trusted boundary, never accepted from a public body.'}
  AccessLifecyclePrepareInput:
    type: object
    properties:
      context: {$ref: '#/$defs/CommandContext'}
      currentProof: {$ref: '#/$defs/AccessSecret'}
      action: {type: string, enum: [withdraw, erase]}
      expectedRevision: {$ref: '#/$defs/Revision'}
      policyRef: {$ref: '#/$defs/PolicyRef'}
    required: [context, currentProof, action, expectedRevision, policyRef]
    additionalProperties: false
  AccessLifecyclePrepareInputHttp:
    type: object
    properties:
      currentProof: {$ref: '#/$defs/AccessSecret'}
      action: {type: string, enum: [withdraw, erase]}
      expectedRevision: {$ref: '#/$defs/Revision'}
      policyRef: {$ref: '#/$defs/PolicyRef'}
    required: [currentProof, action, expectedRevision, policyRef]
    additionalProperties: false
  AccessLifecycleConfirmation:
    type: object
    properties:
      confirmationRef: {$ref: '#/$defs/Id'}
      action: {type: string, enum: [withdraw, erase]}
      revision: {$ref: '#/$defs/Revision'}
      expiresAt: {$ref: '#/$defs/Time'}
    required: [confirmationRef, action, revision, expiresAt]
    additionalProperties: false
  LifecycleRequestInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, action: {type: string, enum: [withdraw, erase]}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, confirmationRef: {$ref: '#/$defs/Id'}}, required: [context, action, policyRef, confirmationRef],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  LifecycleReactivationInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, verification: {$ref: '#/$defs/AccessChallengeProof'}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, confirmationRef: {$ref: '#/$defs/Id'}}, required: [context, verification, policyRef, confirmationRef],
      additionalProperties: false, description: Public pre-authentication envelope; no caller account ID or active session is required.
        Account and withdrawn lifecycle identity are resolved exclusively from the verified purpose-bound reactivation proof. Trusted
        transport context may remain anonymous until this limited recovery authority is verified.}
  LifecycleReactivationResult: {type: object, properties: {lifecycleRequestId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, state: {type: string,
          enum: [accepted, running, complete, blocked, failed]}, access: {type: string, enum: [reactivation_pending, sign_in_required]},
        policyRef: {$ref: '#/$defs/PolicyRef'}, requestId: {$ref: '#/$defs/Id'}, reasonKey: {$ref: '#/$defs/Id'}}, required: [lifecycleRequestId,
        revision, state, access, policyRef, requestId, reasonKey], additionalProperties: false, description: 'Safe status after valid
        reactivation proof; never a full session or a promise that erased data was restored. A protected limited recovery binding,
        issued through trusted cookie transport, permits lifecycle.inspect for this request alone while normal account authority remains
        unavailable.', allOf: [{if: {properties: {state: {const: complete}}}, then: {properties: {access: {const: sign_in_required}}}},
        {if: {properties: {state: {type: string, enum: [accepted, running, blocked, failed]}}}, then: {properties: {access: {const: reactivation_pending}}}}]}
  LifecycleScopeDisposition: {type: object, properties: {scope: {$ref: '#/$defs/LifecycleScope'}, disposition: {type: string, enum: [erased, retained_by_policy,
            revoked, not_applicable, pending, blocked]}, evidenceReference: {$ref: '#/$defs/Id'}, reasonKey: {$ref: '#/$defs/Id'}},
      required: [scope, disposition, reasonKey], additionalProperties: false, allOf: [{if: {properties: {disposition: {type: string,
                enum: [erased, retained_by_policy, revoked, not_applicable]}}}, then: {required: [evidenceReference]}}]}
  LifecycleParticipantDisposition: {type: object, properties: {participantId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, state: {type: string, enum: [
            pending, running, acknowledged, failed, blocked]}, scopes: {type: array, items: {$ref: '#/$defs/LifecycleScopeDisposition'},
          maxItems: 7}, observedAt: {$ref: '#/$defs/Time'}}, required: [participantId, revision, state, scopes, observedAt], additionalProperties: false}
  LifecycleRequest: {type: object, properties: {lifecycleRequestId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, action: {$ref: '#/$defs/LifecycleAction'},
        revision: {$ref: '#/$defs/Revision'}, policyRef: {$ref: '#/$defs/PolicyRef'}, manifestRevision: {$ref: '#/$defs/Revision'},
        authorityRevision: {$ref: '#/$defs/Revision'}, revocation: {type: string, enum: [not_required, pending, effective]}, state: {
          type: string, enum: [accepted, running, complete, blocked, failed]}, participants: {type: array, items: {$ref: '#/$defs/LifecycleParticipantDisposition'},
          maxItems: 13}, completionEvidenceRef: {$ref: '#/$defs/Id'}}, required: [lifecycleRequestId, accountId, action, revision,
        policyRef, manifestRevision, authorityRevision, revocation, state, participants], additionalProperties: false, allOf: [{if: {
            properties: {state: {const: complete}}}, then: {required: [completionEvidenceRef], properties: {revocation: {type: string,
                enum: [not_required, effective]}}}}]}
  LifecycleStatusInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, lifecycleRequestId: {$ref: '#/$defs/Id'}}, required: [context,
        lifecycleRequestId], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  LifecycleWorkTicket: {type: object, properties: {lifecycleRequestId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, participant: {$ref: '#/$defs/LifecycleParticipant'},
        action: {$ref: '#/$defs/LifecycleAction'}, requestRevision: {$ref: '#/$defs/Revision'}, authorityRevision: {$ref: '#/$defs/Revision'},
        manifestRevision: {$ref: '#/$defs/Revision'}, policyRef: {$ref: '#/$defs/PolicyRef'}, workReference: {$ref: '#/$defs/Id'}},
      required: [lifecycleRequestId, accountId, participant, action, requestRevision, authorityRevision, manifestRevision, policyRef,
        workReference], additionalProperties: false}
  LifecyclePendingInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, participantId: {$ref: '#/$defs/Id'}, page: {$ref: '#/$defs/PageRequest'}},
      required: [context, participantId, page], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  LifecycleWorkPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/LifecycleWorkTicket'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  LifecycleAcknowledgeInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, work: {$ref: '#/$defs/LifecycleWorkTicket'}, disposition: {
          $ref: '#/$defs/LifecycleParticipantDisposition'}, evidenceDigest: {$ref: '#/$defs/Hash'}}, required: [context, work, disposition,
        evidenceDigest], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  LifecycleRestoreInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, accountId: {$ref: '#/$defs/Id'}, participantId: {$ref: '#/$defs/Id'},
        restoreSetReference: {$ref: '#/$defs/Id'}, policyRef: {$ref: '#/$defs/PolicyRef'}, recordedAuthorityRevision: {$ref: '#/$defs/Revision'},
        scopes: {type: array, items: {$ref: '#/$defs/LifecycleScope'}, maxItems: 7, uniqueItems: true}}, required: [context, accountId,
        participantId, restoreSetReference, policyRef, recordedAuthorityRevision, scopes], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LifecycleRestoreDecision: {type: object, properties: {decision: {type: string, enum: [allow, deny, requires_reconciliation]}, authorityRevision: {$ref: '#/$defs/Revision'},
        policyRef: {$ref: '#/$defs/PolicyRef'}, reasonKey: {$ref: '#/$defs/Id'}, decisionReference: {$ref: '#/$defs/Id'}}, required: [
        decision, authorityRevision, policyRef, reasonKey, decisionReference], additionalProperties: false}
  LifecycleApplyInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, work: {$ref: '#/$defs/LifecycleWorkTicket'}}, required: [
        context, work], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never
        accepted from a public body.'}
  LibrarySavedPaper: {type: object, properties: {savedPaperId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        savedPaper: {$ref: '#/$defs/PaperRef'}, resolvedPaper: {$ref: '#/$defs/PaperRef'}, savedTitle: {type: string, minLength: 1,
          x-policy-bound: paper metadata display policy, description: Bound by the named approved policy before processing.}, sourceDisposition: {
          type: string, enum: [available, source_only, canonicalized, withdrawn, unavailable, restricted]}, reasonKey: {$ref: '#/$defs/Id'}},
      required: [savedPaperId, accountId, revision, savedPaper, sourceDisposition, reasonKey], additionalProperties: false}
  LibrarySavePaperInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [context, paper, policyRef], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  LibrarySavedPaperInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, savedPaperId: {$ref: '#/$defs/Id'}}, required: [context,
        savedPaperId], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never
        accepted from a public body.'}
  LibraryPaperListInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  LibraryPaperPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/LibrarySavedPaper'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  LibrarySavedSearch: {type: object, properties: {savedSearchId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        queryContext: {$ref: '#/$defs/LibraryQueryContext'}, label: {type: string, minLength: 1, x-policy-bound: saved-search label
            policy, description: Bound by the named approved policy before processing.}}, required: [savedSearchId, accountId, revision,
        queryContext], additionalProperties: false}
  LibrarySaveSearchInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, queryContext: {$ref: '#/$defs/LibraryQueryContext'}, label: {
          type: string, minLength: 1, x-policy-bound: saved-search label policy, description: Bound by the named approved policy before
            processing.}}, required: [context, queryContext], additionalProperties: false, description: 'Internal envelope; context
        is derived by the trusted boundary, never accepted from a public body.'}
  LibrarySavedSearchInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, savedSearchId: {$ref: '#/$defs/Id'}}, required: [context,
        savedSearchId], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never
        accepted from a public body.'}
  LibrarySearchListInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  LibrarySearchPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/LibrarySavedSearch'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  LibraryHistoryRecord: {type: object, properties: {historyId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, searchExecutionId: {$ref: '#/$defs/Id'},
        queryContext: {$ref: '#/$defs/LibraryQueryContext'}, recordedAt: {$ref: '#/$defs/Time'}, admissionSequence: {type: integer,
          minimum: 0}, completionSequence: {type: integer, minimum: 0}, clearBoundary: {$ref: '#/$defs/Revision'}}, required: [historyId,
        accountId, searchExecutionId, queryContext, recordedAt, admissionSequence, completionSequence, clearBoundary], additionalProperties: false}
  LibraryHistoryListInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  LibraryHistoryPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/LibraryHistoryRecord'}, x-policy-bound: accepted PageRequest.limit and
            approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'},
        clearBoundary: {$ref: '#/$defs/Revision'}}, required: [items, page, appliedLimit, policyRef, clearBoundary], additionalProperties: false}
  LibraryHistoryInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, historyId: {$ref: '#/$defs/Id'}}, required: [context, historyId],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  LibraryHistoryFactInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, fact: {$ref: '#/$defs/SearchCompletedFact'}}, required: [
        context, fact], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never
        accepted from a public body.'}
  LibraryHistoryFactResult: {type: object, properties: {disposition: {type: string, enum: [recorded, duplicate, suppressed_by_clear, suppressed_by_lifecycle]},
        historyId: {$ref: '#/$defs/Id'}, clearBoundary: {$ref: '#/$defs/Revision'}, requestId: {$ref: '#/$defs/Id'}}, required: [disposition,
        clearBoundary, requestId], additionalProperties: false}
  LibraryClearHistoryInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [context, policyRef, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted
        boundary, never accepted from a public body.'}
  LibraryClearHistoryResult: {type: object, properties: {ack: {$ref: '#/$defs/Ack'}, checkpoint: {$ref: '#/$defs/SearchHistoryCheckpoint'}, clearBoundary: {
          $ref: '#/$defs/Revision'}}, required: [ack, checkpoint, clearBoundary], additionalProperties: false, description: 'Server-captured
        Discovery admission checkpoint, not a caller-selected cutoff. Facts admitted at/before the cutoff remain suppressed even if
        they finish after clear.'}
  SettingsSearchDefaults: {type: object, properties: {modeId: {$ref: '#/$defs/Id'}, orderId: {$ref: '#/$defs/Id'}, filters: {type: array, items: {$ref: '#/$defs/LibraryFilter'},
          x-policy-bound: retained filter vocabulary and search policy}, vocabularyRevision: {$ref: '#/$defs/Revision'}}, required: [
        modeId, orderId, filters, vocabularyRevision], additionalProperties: false}
  SettingsAssistanceDefaults: {type: object, properties: {actionId: {$ref: '#/$defs/Id'}, languageId: {$ref: '#/$defs/Id'}, presentationLevelId: {$ref: '#/$defs/Id'},
        vocabularyRevision: {$ref: '#/$defs/Revision'}}, required: [actionId, languageId, presentationLevelId, vocabularyRevision],
      additionalProperties: false}
  SettingsSnapshot: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, settingsId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        timeZone: {type: [string, 'null'], minLength: 1, maxLength: 100, description: 'Explicit owner IANA timezone; null means unconfigured.'},
        searchDefaults: {$ref: '#/$defs/SettingsSearchDefaults'}, assistanceDefaults: {$ref: '#/$defs/SettingsAssistanceDefaults'},
        appearance: {type: string, enum: [light, dark, system]}, onboarding: {type: string, enum: [not_started, in_progress, completed,
            skipped]}, interestIds: {type: array, items: {$ref: '#/$defs/Id'}, x-policy-bound: retained interest vocabulary and profile
            policy, uniqueItems: true}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [accountId, settingsId, revision, searchDefaults,
        assistanceDefaults, appearance, onboarding, interestIds, policyRef], additionalProperties: false}
  SettingsReadInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}}, required: [context], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  SettingsUpdateInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, searchDefaults: {$ref: '#/$defs/SettingsSearchDefaults'}, assistanceDefaults: {
          $ref: '#/$defs/SettingsAssistanceDefaults'}, timeZone: {type: string, minLength: 1, maxLength: 100}, appearance: {type: string, enum: [light, dark, system]}, policyRef: {$ref: '#/$defs/PolicyRef'},
        expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, policyRef, expectedRevision], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.', anyOf: [{required: [searchDefaults]}, {required: [
            assistanceDefaults]}, {required: [appearance]}, {required: [timeZone]}]}
  SettingsOnboardingInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, action: {type: string, enum: [save_interests, complete, skip]}, interestIds: {
          type: array, items: {$ref: '#/$defs/Id'}, x-policy-bound: retained interest vocabulary and onboarding policy, uniqueItems: true}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, action, interestIds, policyRef, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  SettingsSuggestion: {type: object, properties: {interestId: {$ref: '#/$defs/Id'}, labelKey: {$ref: '#/$defs/Id'}, source: {type: string, enum: [orcid,
            retained_manual_vocabulary]}, sourceRevision: {$ref: '#/$defs/Revision'}, reasonKey: {$ref: '#/$defs/Id'}}, required: [
        interestId, labelKey, source, sourceRevision, reasonKey], additionalProperties: false}
  SettingsSuggestionInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}, identityLinkId: {$ref: '#/$defs/Id'}},
      required: [context, page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  SettingsSuggestionPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/SettingsSuggestion'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  SettingsRecentPaper: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, lastActivityAt: {$ref: '#/$defs/Time'}, activityReference: {$ref: '#/$defs/Id'},
        sourceDisposition: {type: string, enum: [available, source_only, withdrawn, unavailable, restricted]}}, required: [paper, lastActivityAt,
        activityReference, sourceDisposition], additionalProperties: false}
  SettingsRecentInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  SettingsRecentPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/SettingsRecentPaper'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  SettingsBehaviorEvent: {type: object, properties: {eventId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, paper: {$ref: '#/$defs/PaperRef'},
        activityId: {$ref: '#/$defs/Id'}, occurredAt: {$ref: '#/$defs/Time'}, consentRevision: {$ref: '#/$defs/Revision'}, inputBoundary: {
          $ref: '#/$defs/Revision'}, authorityRevision: {$ref: '#/$defs/Revision'}}, required: [eventId, accountId, paper, activityId,
        occurredAt, consentRevision, inputBoundary, authorityRevision], additionalProperties: false}
  SettingsBehaviorInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, event: {$ref: '#/$defs/SettingsBehaviorEvent'}}, required: [
        context, event], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  SettingsBehaviorResult: {type: object, properties: {disposition: {type: string, enum: [recorded, duplicate, suppressed_by_consent, suppressed_by_reset,
            suppressed_by_lifecycle]}, inputBoundary: {$ref: '#/$defs/Revision'}, requestId: {$ref: '#/$defs/Id'}}, required: [disposition,
        inputBoundary, requestId], additionalProperties: false}
  SettingsProfileProjection: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, profileId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        inputBoundary: {$ref: '#/$defs/Revision'}, consentRevision: {$ref: '#/$defs/Revision'}, disposition: {type: string, enum: [
            ready, cold_start, disabled, unavailable]}, interestIds: {type: array, items: {$ref: '#/$defs/Id'}, x-policy-bound: permitted
            profile projection policy, uniqueItems: true}, reasonKey: {$ref: '#/$defs/Id'}}, required: [accountId, profileId, revision,
        inputBoundary, consentRevision, disposition, interestIds, reasonKey], additionalProperties: false}
  SettingsProjectionInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, accountId: {$ref: '#/$defs/Id'}, purposeId: {$ref: '#/$defs/Id'}},
      required: [context, accountId, purposeId], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  SettingsResetPrepareInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, action: {type: string, enum: [delete_behavior, reset_profile]}, currentProof: {$ref: '#/$defs/AccessSecret'}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, action, currentProof, policyRef, expectedRevision], additionalProperties: false}
  SettingsResetConfirmation: {type: object, properties: {confirmationRef: {$ref: '#/$defs/Id'}, action: {type: string, enum: [delete_behavior, reset_profile]}, revision: {$ref: '#/$defs/Revision'}, expiresAt: {$ref: '#/$defs/Time'}}, required: [confirmationRef, action, revision, expiresAt], additionalProperties: false}
  SettingsResetInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, action: {type: string, enum: [delete_behavior, reset_profile]}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, confirmationRef: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, action,
        policyRef, confirmationRef, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted
        boundary, never accepted from a public body.'}
  SettingsResetResult: {type: object, properties: {resetId: {$ref: '#/$defs/Id'}, ack: {$ref: '#/$defs/Ack'}, inputBoundary: {$ref: '#/$defs/Revision'}, consentRevision: {$ref: '#/$defs/Revision'},
        disposition: {type: string, enum: [complete, pending, blocked]}, remainingScopeReasonKey: {$ref: '#/$defs/Id'}}, required: [
        resetId, ack, inputBoundary, consentRevision, disposition], additionalProperties: false}
  SettingsResetListInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, view: {type: string, enum: [outstanding, history]}, page: {$ref: '#/$defs/PageRequest'}}, required: [context, view, page], additionalProperties: false}
  SettingsResetInspectInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, resetId: {$ref: '#/$defs/Id'}}, required: [context, resetId], additionalProperties: false}
  SettingsResetSummary:
    type: object
    properties:
      resetId: {$ref: '#/$defs/Id'}
      action: {type: string, enum: [delete_behavior, reset_profile]}
      acceptedAt: {$ref: '#/$defs/Time'}
      acceptedSettingsRevision: {$ref: '#/$defs/Revision'}
      inputBoundary: {$ref: '#/$defs/Revision'}
      policyRef: {$ref: '#/$defs/PolicyRef'}
      manifestRevision: {$ref: '#/$defs/Revision'}
      statusRevision: {$ref: '#/$defs/Revision'}
      observedAt: {$ref: '#/$defs/Time'}
      disposition: {type: string, enum: [pending, blocked, complete]}
      reasonKey: {$ref: '#/$defs/Id'}
    required: [resetId, action, acceptedAt, acceptedSettingsRevision, inputBoundary, policyRef, manifestRevision, statusRevision, observedAt, disposition, reasonKey]
    additionalProperties: false
  SettingsResetScopeStatus:
    type: object
    properties:
      participantId: {$ref: '#/$defs/Id'}
      scopeId: {$ref: '#/$defs/Id'}
      manifestRevision: {$ref: '#/$defs/Revision'}
      workGeneration: {$ref: '#/$defs/Revision'}
      disposition: {type: string, enum: [pending, blocked, complete]}
      reasonKey: {$ref: '#/$defs/Id'}
      evidenceRef: {oneOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}
      updatedAt: {$ref: '#/$defs/Time'}
    required: [participantId, scopeId, manifestRevision, workGeneration, disposition, reasonKey, evidenceRef, updatedAt]
    additionalProperties: false
  SettingsResetStatus:
    type: object
    properties:
      reset: {$ref: '#/$defs/SettingsResetSummary'}
      scopes: {type: array, minItems: 1, maxItems: 32, items: {$ref: '#/$defs/SettingsResetScopeStatus'}}
    required: [reset, scopes]
    additionalProperties: false
  SettingsResetPage:
    type: object
    properties:
      items: {type: array, maxItems: 50, items: {$ref: '#/$defs/SettingsResetSummary'}}
      page: {$ref: '#/$defs/PageInfo'}
      appliedLimit: {type: integer, minimum: 1, maximum: 50}
      policyRef: {$ref: '#/$defs/PolicyRef'}
    required: [items, page, appliedLimit, policyRef]
    additionalProperties: false
  AdmissionIdentity:
    type: object
    properties:
      operation: {$ref: '#/$defs/UsageOperation'}
      generation: {$ref: '#/$defs/Revision'}
      accountId: {$ref: '#/$defs/Id'}
      intentDigest: {$ref: '#/$defs/Hash'}
      periodId: {$ref: '#/$defs/Id'}
      quantities: {type: array, minItems: 1, maxItems: 16, items: {$ref: '#/$defs/UsageQuantity'}}
      policyRef: {$ref: '#/$defs/PolicyRef'}
    required: [operation, generation, accountId, intentDigest, periodId, quantities, policyRef]
    additionalProperties: false
  AdmissionIntent:
    type: object
    properties:
      identity: {$ref: '#/$defs/AdmissionIdentity'}
      state: {type: string, enum: [open, accepted, closed]}
      revision: {$ref: '#/$defs/Revision'}
      acceptedAt: {$ref: '#/$defs/Time'}
      reservationId: {oneOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}
      effectRef: {oneOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}
    required: [identity, state, revision, acceptedAt, reservationId, effectRef]
    additionalProperties: false
  AdmissionClosedEvidence:
    type: object
    properties:
      identity: {$ref: '#/$defs/AdmissionIdentity'}
      state: {const: closed}
      closureRevision: {$ref: '#/$defs/Revision'}
      reasonKey: {$ref: '#/$defs/Id'}
      closedAt: {$ref: '#/$defs/Time'}
      evidenceRef: {$ref: '#/$defs/Id'}
    required: [identity, state, closureRevision, reasonKey, closedAt, evidenceRef]
    additionalProperties: false
  AdmissionAllocateInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, identity: {$ref: '#/$defs/AdmissionIdentity'}}, required: [context, identity], additionalProperties: false}
  AdmissionInspectInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, identity: {$ref: '#/$defs/AdmissionIdentity'}}, required: [context, identity], additionalProperties: false}
  AdmissionAcceptInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, identity: {$ref: '#/$defs/AdmissionIdentity'}, reservationId: {$ref: '#/$defs/Id'}, effectRef: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, identity, reservationId, effectRef, expectedRevision], additionalProperties: false}
  AdmissionCloseInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, identity: {$ref: '#/$defs/AdmissionIdentity'}, reasonKey: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, identity, reasonKey, expectedRevision], additionalProperties: false}
  SettingsConsentBoundaryInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, consent: {$ref: '#/$defs/AccessConsentRecord'}}, required: [
        context, consent], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  UsageOperation: {type: object, properties: {operationOwner: {type: string, enum: [AccountAccess, CorpusContent, Discovery, Library, PaperAssistance,
            ResearchWorkspace, Personalization, TopicsDigests, ApprovedExport, UsageEntitlements, ServiceOperations, PlatformControl,
            WebWorkspace]}, operationId: {$ref: '#/$defs/Id'}, inputRevision: {$ref: '#/$defs/Revision'}}, required: [operationOwner,
        operationId, inputRevision], additionalProperties: false}
  UsageQuantity: {type: object, properties: {metricId: {$ref: '#/$defs/Id'}, quantity: {type: integer, minimum: 0}}, required: [metricId, quantity],
      additionalProperties: false}
  UsageKnownMeasure: {type: object, properties: {state: {const: known}, metricId: {$ref: '#/$defs/Id'}, allocated: {type: integer, minimum: 0}, used: {
          type: integer, minimum: 0}, reserved: {type: integer, minimum: 0}, remaining: {type: integer, minimum: 0}, periodId: {$ref: '#/$defs/Id'},
        periodStart: {$ref: '#/$defs/Time'}, periodEnd: {$ref: '#/$defs/Time'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [
        state, metricId, allocated, used, reserved, remaining, periodId, periodStart, periodEnd, policyRef], additionalProperties: false}
  UsageUnknownMeasure: {type: object, properties: {state: {const: unknown}, metricId: {$ref: '#/$defs/Id'}, reasonKey: {$ref: '#/$defs/Id'}}, required: [
        state, metricId, reasonKey], additionalProperties: false}
  UsageMeasure: {oneOf: [{$ref: '#/$defs/UsageKnownMeasure'}, {$ref: '#/$defs/UsageUnknownMeasure'}]}
  UsageInspectInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  UsageMeasurePage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/UsageMeasure'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  UsagePlanPresentation: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, tierId: {$ref: '#/$defs/Id'}, labelKey: {$ref: '#/$defs/Id'}, source: {
          type: string, enum: [mock, administrative_assignment]}, revision: {$ref: '#/$defs/Revision'}, policyRef: {$ref: '#/$defs/PolicyRef'},
        paymentOccurred: {const: false}}, required: [accountId, tierId, labelKey, source, revision, policyRef, paymentOccurred], additionalProperties: false}
  UsagePlanInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}}, required: [context], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsageEntitlement: {type: object, properties: {entitlementId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, tierId: {$ref: '#/$defs/Id'},
        revision: {$ref: '#/$defs/Revision'}, assignmentSource: {type: string, enum: [mock, administrative_assignment]}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, effectiveAt: {$ref: '#/$defs/Time'}, disposition: {type: string, enum: [active, revoked]}}, required: [
        entitlementId, accountId, tierId, revision, assignmentSource, policyRef, effectiveAt, disposition], additionalProperties: false}
  UsageGrantInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, accountId: {$ref: '#/$defs/Id'}, tierId: {$ref: '#/$defs/Id'}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, reasonKey: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, accountId,
        tierId, policyRef, reasonKey, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted
        boundary, never accepted from a public body.'}
  UsageRevokeInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, accountId: {$ref: '#/$defs/Id'}, entitlementId: {$ref: '#/$defs/Id'}, policyRef: {
          $ref: '#/$defs/PolicyRef'}, reasonKey: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [context, accountId,
        entitlementId, policyRef, reasonKey, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  UsageReserveInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, operation: {$ref: '#/$defs/UsageOperation'}, quantities: {
          type: array, items: {$ref: '#/$defs/UsageQuantity'}, x-policy-bound: registered operation accounting metrics}, policyRef: {
          $ref: '#/$defs/PolicyRef'}}, required: [context, operation, quantities, policyRef], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsageRecord: {type: object, properties: {usageRecordId: {$ref: '#/$defs/Id'}, accountId: {$ref: '#/$defs/Id'}, operation: {$ref: '#/$defs/UsageOperation'},
        revision: {$ref: '#/$defs/Revision'}, periodId: {$ref: '#/$defs/Id'}, policyRef: {$ref: '#/$defs/PolicyRef'}, disposition: {
          type: string, enum: [reserved, committed, released, refunded, unknown]}, quantities: {type: array, items: {$ref: '#/$defs/UsageQuantity'},
          x-policy-bound: registered operation accounting metrics}, effectReference: {$ref: '#/$defs/Id'}, reasonKey: {$ref: '#/$defs/Id'}},
      required: [usageRecordId, accountId, operation, revision, periodId, policyRef, disposition, quantities, reasonKey], additionalProperties: false}
  UsageSettleInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, usageRecordId: {$ref: '#/$defs/Id'}, operation: {$ref: '#/$defs/UsageOperation'},
        decision: {type: string, enum: [commit, release, refund]}, actualQuantities: {type: array, items: {$ref: '#/$defs/UsageQuantity'},
          x-policy-bound: registered operation accounting metrics}, effectReference: {$ref: '#/$defs/Id'}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [context, usageRecordId, operation, decision, actualQuantities, effectReference, policyRef], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsageReconcileInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, operation: {$ref: '#/$defs/UsageOperation'}}, required: [
        context, operation], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  UsageRecordsInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted
        from a public body.'}
  UsageRecordsPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/UsageRecord'}, x-policy-bound: accepted PageRequest.limit
            and approved list policy}, page: {$ref: '#/$defs/PageInfo'}, appliedLimit: {type: integer, minimum: 1}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [items, page, appliedLimit, policyRef], additionalProperties: false}
  CorpusRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}, purpose: {type: string,
          enum: [metadata, read, assistance, research, citation, saved-reference]}}, required: [context, paper, purpose], additionalProperties: false}
  CorpusResolve: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, identifier: {type: string, minLength: 1, x-policy-limit: Resolve
            content/input byte and character limits before enabling this operation.}, versionLabel: {type: string, minLength: 1}},
      required: [context, identifier], additionalProperties: false}
  CorpusIdentity: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, requestedIdentifier: {type: string, minLength: 1, x-policy-limit: Resolve
            content/input byte and character limits before enabling this operation.}, canonicalDisposition: {type: string, enum: [
            same, alias, withdrawn, unavailable, restricted]}, metadataRevision: {$ref: '#/$defs/Revision'}, title: {type: string,
          minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}, sourceUrls: {
          type: array, items: {type: string, minLength: 1, format: uri}}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [paper, requestedIdentifier,
        canonicalDisposition, metadataRevision, title, sourceUrls, policy], additionalProperties: false}
  CorpusSection: {type: object, properties: {sectionId: {$ref: '#/$defs/Id'}, heading: {type: string}, text: {type: string}, anchor: {$ref: '#/$defs/Id'}},
      required: [sectionId, heading, text, anchor], additionalProperties: false}
  CorpusAssetRef: {type: object, properties: {assetId: {$ref: '#/$defs/Id'}, mediaType: {type: string, minLength: 1}, contentHash: {$ref: '#/$defs/Hash'},
        altText: {type: string}, sectionId: {$ref: '#/$defs/Id'}}, required: [assetId, mediaType, contentHash, altText], additionalProperties: false}
  CorpusContent: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'},
        sections: {type: array, items: {$ref: '#/$defs/CorpusSection'}}, assets: {type: array, items: {$ref: '#/$defs/CorpusAssetRef'}},
        sourceUrls: {type: array, items: {type: string, minLength: 1, format: uri}}, coverage: {type: string, enum: [complete, partial]},
        limitations: {type: array, items: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits
              before enabling this operation.}}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [paper, contentRevision, contentHash,
        sections, assets, sourceUrls, coverage, limitations, policy], additionalProperties: false}
  CorpusContentRead: {oneOf: [{type: object, properties: {availability: {const: ready}, content: {$ref: '#/$defs/CorpusContent'}}, required: [availability,
            content], additionalProperties: false}, {type: object, properties: {availability: {type: string, enum: [absent, building,
                unsupported, failed, withdrawn, restricted]}, paper: {$ref: '#/$defs/PaperRef'}, reasonKey: {type: string, minLength: 1},
            retryable: {type: boolean}}, required: [availability, paper, reasonKey, retryable], additionalProperties: false}]}
  CorpusAssetRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'},
        assetId: {$ref: '#/$defs/Id'}}, required: [context, paper, contentRevision, assetId], additionalProperties: false}
  CorpusAsset: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, asset: {$ref: '#/$defs/CorpusAssetRef'}, readHandle: {$ref: '#/$defs/Id'},
        policy: {$ref: '#/$defs/PolicyRef'}}, required: [paper, asset, readHandle, policy], additionalProperties: false}
  CorpusRunRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, operation: {type: string, enum: [ingest, incremental-refresh,
            rebuild, reprocess]}, sourceScopeIds: {type: array, items: {$ref: '#/$defs/Id'}, minItems: 1, uniqueItems: true}, authoritativeInputRevision: {
          $ref: '#/$defs/Revision'}, inputManifestHash: {$ref: '#/$defs/Hash'}, sourcePolicy: {$ref: '#/$defs/PolicyRef'}, compatibilityRevision: {
          $ref: '#/$defs/Revision'}}, required: [context, operation, sourceScopeIds, authoritativeInputRevision, inputManifestHash,
        sourcePolicy, compatibilityRevision], additionalProperties: false}
  CorpusRunRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, runId: {$ref: '#/$defs/Id'}}, required: [context, runId],
      additionalProperties: false}
  CorpusEffectDisposition: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, stage: {type: string, enum: [source, control, content, projection,
            publication]}, state: {type: string, enum: [pending, committed, failed, unknown]}, evidenceHash: {anyOf: [{$ref: '#/$defs/Hash'},
            {type: 'null'}]}, error: {anyOf: [{$ref: '#/$defs/Error'}, {type: 'null'}]}}, required: [effectId, stage, state, evidenceHash,
        error], additionalProperties: false}
  CorpusRun: {type: object, properties: {runId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, job: {$ref: '#/$defs/JobSnapshot'},
        inputManifestHash: {$ref: '#/$defs/Hash'}, effects: {type: array, items: {$ref: '#/$defs/CorpusEffectDisposition'}}, committedWatermark: {
          anyOf: [{type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this
                operation.}, {type: 'null'}]}, publicationGeneration: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}}, required: [
        runId, revision, job, inputManifestHash, effects, committedWatermark, publicationGeneration], additionalProperties: false}
  CorpusProjectionEntry: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'},
        chunkId: {$ref: '#/$defs/Id'}, sectionId: {$ref: '#/$defs/Id'}, text: {type: string, minLength: 1, x-policy-limit: Resolve
            content/input byte and character limits before enabling this operation.}, representationHandle: {anyOf: [{$ref: '#/$defs/Id'},
            {type: 'null'}]}}, required: [paper, contentRevision, contentHash, chunkId, sectionId, text, representationHandle], additionalProperties: false}
  CorpusProjectionBatch: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, runId: {$ref: '#/$defs/Id'}, generationId: {$ref: '#/$defs/Id'},
        batchId: {$ref: '#/$defs/Id'}, batchHash: {$ref: '#/$defs/Hash'}, compatibilityRevision: {$ref: '#/$defs/Revision'}, entries: {
          type: array, items: {$ref: '#/$defs/CorpusProjectionEntry'}, minItems: 1}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [
        context, runId, generationId, batchId, batchHash, compatibilityRevision, entries, policy], additionalProperties: false}
  CorpusPublicationRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, runId: {$ref: '#/$defs/Id'}, generationId: {$ref: '#/$defs/Id'},
        expectedPublishedGeneration: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, inputManifestHash: {$ref: '#/$defs/Hash'}, verifiedBatchIds: {
          type: array, items: {$ref: '#/$defs/Id'}, uniqueItems: true}, verificationEvidenceHash: {$ref: '#/$defs/Hash'}, compatibilityRevision: {
          $ref: '#/$defs/Revision'}, eligibilityRevision: {$ref: '#/$defs/Revision'}}, required: [context, runId, generationId, expectedPublishedGeneration,
        inputManifestHash, verifiedBatchIds, verificationEvidenceHash, compatibilityRevision, eligibilityRevision], additionalProperties: false}
  CorpusPublication: {type: object, properties: {generationId: {$ref: '#/$defs/Id'}, publicationRevision: {$ref: '#/$defs/Revision'}, manifestHash: {
          $ref: '#/$defs/Hash'}, compatibilityRevision: {$ref: '#/$defs/Revision'}, eligibilityRevision: {$ref: '#/$defs/Revision'},
        publishedAt: {$ref: '#/$defs/Time'}, complete: {const: true}}, required: [generationId, publicationRevision, manifestHash,
        compatibilityRevision, eligibilityRevision, publishedAt, complete], additionalProperties: false}
  CorpusProjectionRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, requiredCompatibilityRevision: {$ref: '#/$defs/Revision'}},
      required: [context, requiredCompatibilityRevision], additionalProperties: false}
  CorpusEligibilityChange: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}, disposition: {type: string,
          enum: [eligible, withdrawn, restricted, unavailable]}, reasonKey: {type: string, minLength: 1}, sourceEvidenceHash: {$ref: '#/$defs/Hash'},
        policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, paper, disposition, reasonKey, sourceEvidenceHash, policy], additionalProperties: false}
  CorpusChangeFact: {type: object, properties: {factId: {$ref: '#/$defs/Id'}, paper: {$ref: '#/$defs/PaperRef'}, previousEligibilityRevision: {$ref: '#/$defs/Revision'},
        eligibilityRevision: {$ref: '#/$defs/Revision'}, disposition: {type: string, enum: [eligible, withdrawn, restricted, unavailable,
            canonical-alias]}, occurredAt: {$ref: '#/$defs/Time'}, sequence: {type: integer, minimum: 0}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [factId, paper, previousEligibilityRevision, eligibilityRevision, disposition, occurredAt, sequence, policy], additionalProperties: false}
  CorpusChangeRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, afterSequence: {type: integer, minimum: 0}, page: {$ref: '#/$defs/PageRequest'}},
      required: [context, afterSequence, page], additionalProperties: false}
  CorpusChangePage: {type: object, properties: {facts: {type: array, items: {$ref: '#/$defs/CorpusChangeFact'}}, page: {$ref: '#/$defs/PageInfo'}},
      required: [facts, page], additionalProperties: false}
  SearchRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, query: {$ref: '#/$defs/LibraryQueryContext'}, page: {$ref: '#/$defs/PageRequest'},
        snapshotRevision: {$ref: '#/$defs/Revision'}}, required: [context, query, page], additionalProperties: false}
  SearchHit: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, title: {type: string, minLength: 1, x-policy-limit: Resolve content/input
            byte and character limits before enabling this operation.}, authors: {type: array, items: {type: string, minLength: 1,
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}}, publishedAt: {anyOf: [
            {$ref: '#/$defs/Time'}, {type: 'null'}]}, snippet: {type: string}, sourceUrl: {type: string, minLength: 1, format: uri},
        availability: {type: string, enum: [readable, source-only, building, unavailable, restricted]}, matchExplanation: {type: string}},
      required: [paper, title, authors, publishedAt, snippet, sourceUrl, availability, matchExplanation], additionalProperties: false}
  SearchResponse: {type: object, properties: {executionId: {$ref: '#/$defs/Id'}, query: {$ref: '#/$defs/LibraryQueryContext'}, hits: {type: array,
          items: {$ref: '#/$defs/SearchHit'}}, page: {$ref: '#/$defs/PageInfo'}, publication: {$ref: '#/$defs/CorpusPublication'},
        outcome: {type: string, enum: [complete, partial, degraded]}, effectiveModeId: {$ref: '#/$defs/Id'}, limitations: {type: array,
          items: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this
              operation.}}}, required: [executionId, query, hits, page, publication, outcome, effectiveModeId, limitations], additionalProperties: false}
  SearchHistoryCheckpointRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}}, required: [context], additionalProperties: false}
  SearchHistoryCheckpoint: {type: object, properties: {ownerId: {$ref: '#/$defs/Id'}, admissionSequence: {type: integer, minimum: 0}, revision: {$ref: '#/$defs/Revision'}},
      required: [ownerId, admissionSequence, revision], additionalProperties: false}
  SearchCompletedFact: {type: object, properties: {factId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, executionId: {$ref: '#/$defs/Id'}, query: {
          $ref: '#/$defs/LibraryQueryContext'}, admissionSequence: {type: integer, minimum: 0}, completionSequence: {type: integer,
          minimum: 0}, completedAt: {$ref: '#/$defs/Time'}, snapshotRevision: {$ref: '#/$defs/Revision'}, authorityRevision: {$ref: '#/$defs/Revision'},
        historyPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [factId, ownerId, executionId, query, admissionSequence, completionSequence,
        completedAt, snapshotRevision, authorityRevision, historyPolicy], additionalProperties: false}
  SearchFactsRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, afterCompletionSequence: {type: integer, minimum: 0}, page: {
          $ref: '#/$defs/PageRequest'}}, required: [context, afterCompletionSequence, page], additionalProperties: false}
  SearchFactsPage: {type: object, properties: {facts: {type: array, items: {$ref: '#/$defs/SearchCompletedFact'}}, page: {$ref: '#/$defs/PageInfo'}},
      required: [facts, page], additionalProperties: false}
  SearchFactAck: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, factId: {$ref: '#/$defs/Id'}, consumerId: {const: Library},
        disposition: {type: string, enum: [recorded, duplicate, suppressed-by-clear, suppressed-by-lifecycle]}, consumerEvidenceRevision: {
          $ref: '#/$defs/Revision'}}, required: [context, factId, consumerId, disposition, consumerEvidenceRevision], additionalProperties: false}
  CitationRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}, direction: {type: string,
          enum: [cited, citing, both]}, page: {$ref: '#/$defs/PageRequest'}, traversalPolicy: {$ref: '#/$defs/PolicyRef'}, snapshotRevision: {
          $ref: '#/$defs/Revision'}}, required: [context, paper, direction, page, traversalPolicy], additionalProperties: false}
  CitationNode: {type: object, properties: {nodeId: {$ref: '#/$defs/Id'}, paper: {anyOf: [{$ref: '#/$defs/PaperRef'}, {type: 'null'}]}, title: {
          anyOf: [{type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this
                operation.}, {type: 'null'}]}, sourceUrl: {anyOf: [{type: string, minLength: 1, format: uri}, {type: 'null'}]}, disposition: {
          type: string, enum: [eligible, unknown, incomplete, restricted, withdrawn]}}, required: [nodeId, paper, title, sourceUrl,
        disposition], additionalProperties: false}
  CitationEdge: {type: object, properties: {fromNodeId: {$ref: '#/$defs/Id'}, toNodeId: {$ref: '#/$defs/Id'}, sourceUrl: {type: string, minLength: 1,
          format: uri}, observedAt: {$ref: '#/$defs/Time'}}, required: [fromNodeId, toNodeId, sourceUrl, observedAt], additionalProperties: false}
  CitationResponse: {type: object, properties: {snapshotId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, root: {$ref: '#/$defs/PaperRef'},
        nodes: {type: array, items: {$ref: '#/$defs/CitationNode'}}, edges: {type: array, items: {$ref: '#/$defs/CitationEdge'}}, freshness: {
          type: string, enum: [current, stale, unknown]}, coverage: {type: string, enum: [complete, partial]}, limitations: {type: array,
          items: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this
              operation.}}, page: {$ref: '#/$defs/PageInfo'}}, required: [snapshotId, revision, root, nodes, edges, freshness, coverage,
        limitations, page], additionalProperties: false}
  AssistanceOption: {type: object, properties: {optionId: {$ref: '#/$defs/Id'}, operation: {type: string, enum: [summary, translation]}, sourceLanguageId: {
          $ref: '#/$defs/Id'}, targetLanguageId: {$ref: '#/$defs/Id'}, presentationLevelId: {$ref: '#/$defs/Id'}, labelKey: {type: string,
          minLength: 1}}, required: [optionId, operation, sourceLanguageId, targetLanguageId, presentationLevelId, labelKey], additionalProperties: false}
  AssistanceOptionsRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}}, required: [context,
        paper], additionalProperties: false}
  AssistanceOptions: {type: object, properties: {revision: {$ref: '#/$defs/Revision'}, options: {type: array, items: {$ref: '#/$defs/AssistanceOption'}},
        policy: {$ref: '#/$defs/PolicyRef'}, limitations: {type: array, items: {type: string, minLength: 1, x-policy-limit: Resolve
              content/input byte and character limits before enabling this operation.}}}, required: [revision, options, policy, limitations],
      additionalProperties: false}
  AssistanceRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'},
        contentHash: {$ref: '#/$defs/Hash'}, operation: {type: string, enum: [summary, translation]}, optionId: {$ref: '#/$defs/Id'},
        optionsRevision: {$ref: '#/$defs/Revision'}, glossaryRevision: {$ref: '#/$defs/Revision'}, processingPolicy: {$ref: '#/$defs/PolicyRef'}},
      required: [context, paper, contentRevision, contentHash, operation, optionId, optionsRevision, glossaryRevision, processingPolicy],
      additionalProperties: false}
  AssistanceJobRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, jobId: {$ref: '#/$defs/Id'}}, required: [context, jobId],
      additionalProperties: false}
  AssistanceResult: {type: object, properties: {result: {$ref: '#/$defs/ResultRef'}, ownerId: {$ref: '#/$defs/Id'}, jobId: {$ref: '#/$defs/Id'}, paper: {
          $ref: '#/$defs/PaperRef'}, sourceContentHash: {$ref: '#/$defs/Hash'}, operation: {type: string, enum: [summary, translation]},
        optionId: {$ref: '#/$defs/Id'}, glossaryRevision: {$ref: '#/$defs/Revision'}, sections: {type: array, items: {$ref: '#/$defs/CorpusSection'}},
        coverage: {type: string, enum: [complete, partial, abstained]}, limitations: {type: array, items: {type: string, minLength: 1,
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}}, methodRevision: {$ref: '#/$defs/Revision'}},
      required: [result, ownerId, jobId, paper, sourceContentHash, operation, optionId, glossaryRevision, sections, coverage, limitations,
        methodRevision], additionalProperties: false}
  AssistanceResultRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, jobId: {$ref: '#/$defs/Id'}, result: {$ref: '#/$defs/ResultRef'}},
      required: [context, jobId], additionalProperties: false}
  AssistanceResultRead: {oneOf: [{type: object, properties: {availability: {const: ready}, prepared: {$ref: '#/$defs/AssistanceResult'}}, required: [availability,
            prepared], additionalProperties: false}, {type: object, properties: {availability: {type: string, enum: [pending, failed,
                expired, withdrawn, restricted]}, jobId: {$ref: '#/$defs/Id'}, reasonKey: {type: string, minLength: 1}}, required: [
            availability, jobId, reasonKey], additionalProperties: false}]}
  AssistanceGlossaryTerm: {type: object, properties: {termId: {$ref: '#/$defs/Id'}, source: {type: string, minLength: 1, x-policy-limit: Resolve content/input
            byte and character limits before enabling this operation.}, preferred: {type: string, minLength: 1, x-policy-limit: Resolve
            content/input byte and character limits before enabling this operation.}, languageId: {$ref: '#/$defs/Id'}}, required: [
        termId, source, preferred, languageId], additionalProperties: false}
  AssistanceGlossaryRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}}, required: [context], additionalProperties: false}
  AssistanceGlossary: {type: object, properties: {ownerId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, normalizationPolicy: {$ref: '#/$defs/PolicyRef'},
        terms: {type: array, items: {$ref: '#/$defs/AssistanceGlossaryTerm'}}}, required: [ownerId, revision, normalizationPolicy,
        terms], additionalProperties: false}
  AssistanceGlossaryWrite: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, expectedRevision: {$ref: '#/$defs/Revision'}, normalizationPolicy: {
          $ref: '#/$defs/PolicyRef'}, terms: {type: array, items: {$ref: '#/$defs/AssistanceGlossaryTerm'}}}, required: [context, expectedRevision,
        normalizationPolicy, terms], additionalProperties: false}
  AssistanceComplete: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, jobId: {$ref: '#/$defs/Id'}, factId: {$ref: '#/$defs/Id'}, claim: {$ref: '#/$defs/ExecutionClaim'},
        expectedJobRevision: {$ref: '#/$defs/Revision'}, inputHash: {$ref: '#/$defs/Hash'}, prepared: {$ref: '#/$defs/AssistanceResult'}, usageRecordId: {
          $ref: '#/$defs/Id'}}, required: [context, jobId, factId, claim, expectedJobRevision, inputHash, prepared, usageRecordId], additionalProperties: false}
  ResearchScope: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, publicPapers: {type: array, items: {$ref: '#/$defs/PaperRef'}}, attachmentIds: {
          type: array, items: {$ref: '#/$defs/Id'}, uniqueItems: true}, webReferences: {type: array, items: {type: string, minLength: 1,
            format: uri}}, scopePolicy: {$ref: '#/$defs/PolicyRef'}}, required: [contextId, publicPapers, attachmentIds, webReferences,
        scopePolicy], additionalProperties: false}
  ResearchContextCreate: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, purpose: {type: string, enum: [research, novelty]}, policy: {
          $ref: '#/$defs/PolicyRef'}}, required: [context, purpose, policy], additionalProperties: false}
  ResearchContext: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        purpose: {type: string, enum: [research, novelty]}, lifecycle: {type: string, enum: [active, deleting, deleted]}}, required: [
        contextId, ownerId, revision, purpose, lifecycle], additionalProperties: false}
  ResearchContextRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contextId: {$ref: '#/$defs/Id'}}, required: [context, contextId],
      additionalProperties: false}
  ResearchSessionCreate: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, title: {type: string, minLength: 1, x-policy-limit: Resolve
            content/input byte and character limits before enabling this operation.}, scope: {$ref: '#/$defs/ResearchScope'}}, required: [
        context, title, scope], additionalProperties: false}
  ResearchSessionRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, sessionId: {$ref: '#/$defs/Id'}}, required: [context, sessionId],
      additionalProperties: false}
  ResearchSession: {type: object, properties: {sessionId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        scope: {$ref: '#/$defs/ResearchScope'}, lifecycle: {type: string, enum: [active, deleting, deleted]}, turnIds: {type: array,
          items: {$ref: '#/$defs/Id'}}, pendingJobIds: {type: array, items: {$ref: '#/$defs/Id'}}, deletionBoundary: {anyOf: [{$ref: '#/$defs/Revision'},
            {type: 'null'}]}}, required: [sessionId, ownerId, revision, scope, lifecycle, turnIds, pendingJobIds, deletionBoundary],
      additionalProperties: false}
  ResearchSessionList: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false}
  ResearchSessions: {type: object, properties: {sessions: {type: array, items: {$ref: '#/$defs/ResearchSession'}}, page: {$ref: '#/$defs/PageInfo'}},
      required: [sessions, page], additionalProperties: false}
  ResearchDelete: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, scope: {type: string, enum: [one-session, all-sessions]},
        sessionId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}, confirmed: {const: true}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [context, scope, expectedRevision, confirmed, policy], additionalProperties: false, allOf: [{if: {properties: {scope: {
                const: one-session}}}, then: {required: [sessionId]}, else: {not: {required: [sessionId]}}}]}
  ResearchDeletion: {type: object, properties: {requestId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, state: {type: string, enum: [
            accepted, in-progress, complete, limited, failed]}, tombstoneBoundary: {$ref: '#/$defs/Revision'}, policy: {$ref: '#/$defs/PolicyRef'},
        remainingJobIds: {type: array, items: {$ref: '#/$defs/Id'}}, limitations: {type: array, items: {type: string, minLength: 1,
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}}}, required: [requestId,
        revision, state, tombstoneBoundary, policy, remainingJobIds, limitations], additionalProperties: false}
  ResearchAttachmentStart: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contextId: {$ref: '#/$defs/Id'}, fileName: {type: string,
          minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}, mediaType: {
          type: string, enum: [application/pdf, text/plain]}, byteLength: {type: integer, minimum: 1, x-policy-limit: Maximum permitted
            attachment bytes; unresolved means refuse.}, contentHash: {$ref: '#/$defs/Hash'}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [context, contextId, fileName, mediaType, byteLength, contentHash, policy], additionalProperties: false}
  ResearchUploadPermit: {type: object, properties: {uploadId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'}, contentHash: {
          $ref: '#/$defs/Hash'}, writeHandle: {$ref: '#/$defs/Id'}, expiresAt: {$ref: '#/$defs/Time'}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [uploadId, ownerId, contextId, contentHash, writeHandle, expiresAt, policy], additionalProperties: false}
  ResearchAttachmentFinish: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, uploadId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'},
        contentHash: {$ref: '#/$defs/Hash'}}, required: [context, uploadId, contextId, contentHash], additionalProperties: false}
  ResearchAttachment: {type: object, properties: {attachmentId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'},
        revision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'}, state: {type: string, enum: [processing, ready,
            partial, unsupported, failed, deleted]}, assetIds: {type: array, items: {$ref: '#/$defs/Id'}}, limitations: {type: array,
          items: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this
              operation.}}}, required: [attachmentId, ownerId, contextId, revision, contentHash, state, assetIds, limitations], additionalProperties: false}
  ResearchAttachmentRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contextId: {$ref: '#/$defs/Id'}, attachmentId: {$ref: '#/$defs/Id'}},
      required: [context, contextId, attachmentId], additionalProperties: false}
  ResearchPrivateAssetRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contextId: {$ref: '#/$defs/Id'}, attachmentId: {$ref: '#/$defs/Id'},
        assetId: {$ref: '#/$defs/Id'}}, required: [context, contextId, attachmentId, assetId], additionalProperties: false}
  ResearchPrivateAsset: {type: object, properties: {attachmentId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'}, assetId: {$ref: '#/$defs/Id'},
        mediaType: {type: string, minLength: 1}, contentHash: {$ref: '#/$defs/Hash'}, readHandle: {$ref: '#/$defs/Id'}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [attachmentId, contextId, assetId, mediaType, contentHash, readHandle, policy], additionalProperties: false}
  DraftRef: {type: object, properties: {draftId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'}},
      required: [draftId, revision, contentHash], additionalProperties: false}
  DraftWrite: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contextId: {$ref: '#/$defs/Id'}, draftId: {$ref: '#/$defs/Id'},
        kind: {type: string, enum: [research-question, novelty-topic, novelty-manuscript, novelty-discussion]}, baseRevision: {anyOf: [
            {$ref: '#/$defs/Revision'}, {type: 'null'}]}, text: {type: string, x-policy-limit: Resolved owner draft text bounds.},
        policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, contextId, draftId, kind, baseRevision, text, policy], additionalProperties: false}
  DraftRevision: {type: object, properties: {draft: {$ref: '#/$defs/DraftRef'}, ownerId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'},
        kind: {type: string, enum: [research-question, novelty-topic, novelty-manuscript, novelty-discussion]}, parentRevision: {anyOf: [
            {$ref: '#/$defs/Revision'}, {type: 'null'}]}, text: {type: string}, acknowledgedAt: {$ref: '#/$defs/Time'}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [draft, ownerId, contextId, kind, parentRevision, text, acknowledgedAt, policy], additionalProperties: false}
  DraftWriteResult: {oneOf: [{type: object, properties: {outcome: {const: saved}, acknowledged: {$ref: '#/$defs/DraftRevision'}}, required: [outcome,
            acknowledged], additionalProperties: false}, {type: object, properties: {outcome: {const: conflict}, current: {$ref: '#/$defs/DraftRevision'},
            proposedText: {type: string}, proposedBaseRevision: {anyOf: [{$ref: '#/$defs/Revision'}, {type: 'null'}]}}, required: [
            outcome, current, proposedText, proposedBaseRevision], additionalProperties: false}]}
  DraftRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contextId: {$ref: '#/$defs/Id'}, draftId: {$ref: '#/$defs/Id'}},
      required: [context, contextId, draftId], additionalProperties: false}
  DraftRecovery: {oneOf: [{type: object, properties: {state: {const: recoverable}, acknowledged: {$ref: '#/$defs/DraftRevision'}}, required: [state,
            acknowledged], additionalProperties: false}, {type: object, properties: {state: {type: string, enum: [missing, consumed,
                discarded, expired, deleted]}, draftId: {$ref: '#/$defs/Id'}, reasonKey: {type: string, minLength: 1}}, required: [
            state, draftId, reasonKey], additionalProperties: false}]}
  DraftDiscard: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, contextId: {$ref: '#/$defs/Id'}, draft: {$ref: '#/$defs/DraftRef'},
        confirmed: {const: true}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, contextId, draft, confirmed, policy], additionalProperties: false}
  ResearchTurnRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, sessionId: {$ref: '#/$defs/Id'}, scope: {$ref: '#/$defs/ResearchScope'},
        mode: {type: string, enum: [question, compare, quote]}, text: {type: string, minLength: 1, x-policy-limit: Resolve content/input
            byte and character limits before enabling this operation.}, submittedDraft: {$ref: '#/$defs/DraftRef'}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [context, sessionId, scope, mode, text, policy], additionalProperties: false}
  ResearchNoveltyRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, scope: {$ref: '#/$defs/ResearchScope'}, inputMode: {type: string,
          enum: [topic, manuscript]}, text: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits
            before enabling this operation.}, submittedDraft: {$ref: '#/$defs/DraftRef'}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [
        context, scope, inputMode, text, policy], additionalProperties: false}
  ResearchJobRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, kind: {type: string, enum: [research-turn, novelty-analysis,
            novelty-discussion]}, jobId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'}}, required: [context, kind, jobId, contextId],
      additionalProperties: false}
  ResearchTurn: {type: object, properties: {turnId: {$ref: '#/$defs/Id'}, sessionId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, revision: {
          $ref: '#/$defs/Revision'}, inputMode: {type: string, enum: [question, compare, quote]}, committedText: {type: string, minLength: 1,
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}, submittedDraft: {anyOf: [
            {$ref: '#/$defs/DraftRef'}, {type: 'null'}]}, job: {$ref: '#/$defs/JobSnapshot'}, artifact: {anyOf: [{$ref: '#/$defs/ResearchArtifactRef'},
            {type: 'null'}]}}, required: [turnId, sessionId, ownerId, revision, inputMode, committedText, submittedDraft, job, artifact],
      additionalProperties: false}
  ResearchTurnRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, sessionId: {$ref: '#/$defs/Id'}, turnId: {$ref: '#/$defs/Id'}},
      required: [context, sessionId, turnId], additionalProperties: false}
  ResearchArtifactRef: {type: object, properties: {artifactId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'}},
      required: [artifactId, revision, contentHash], additionalProperties: false}
  ResearchEvidence: {type: object, properties: {evidenceId: {$ref: '#/$defs/Id'}, sourceKind: {type: string, enum: [public-paper, private-attachment,
            retrieved-web, unread-reference]}, sourceId: {$ref: '#/$defs/Id'}, sourceVersion: {$ref: '#/$defs/Revision'}, sourceContentHash: {
          anyOf: [{$ref: '#/$defs/Hash'}, {type: 'null'}]}, location: {type: string, minLength: 1, x-policy-limit: Resolve content/input
            byte and character limits before enabling this operation.}, readCoverage: {type: string, enum: [read, partial, not-read]},
        quote: {anyOf: [{type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling
                this operation.}, {type: 'null'}]}, claim: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte
            and character limits before enabling this operation.}, stance: {type: string, enum: [supports, contradicts, uncertain]},
        sourceUrl: {anyOf: [{type: string, minLength: 1, format: uri}, {type: 'null'}]}}, required: [evidenceId, sourceKind, sourceId,
        sourceVersion, sourceContentHash, location, readCoverage, quote, claim, stance, sourceUrl], additionalProperties: false}
  ResearchOutput: {type: object, properties: {summary: {type: string}, evidence: {type: array, items: {$ref: '#/$defs/ResearchEvidence'}}, coverage: {
          type: string, enum: [complete, partial, abstained]}, limitations: {type: array, items: {type: string, minLength: 1, x-policy-limit: Resolve
              content/input byte and character limits before enabling this operation.}}, methodRevision: {$ref: '#/$defs/Revision'},
        assessments: {type: array, items: {$ref: '#/$defs/ResearchAssessment'}}}, required: [summary, evidence, coverage, limitations,
        methodRevision], additionalProperties: false}
  ResearchAssessment: {type: object, properties: {criterionId: {$ref: '#/$defs/Id'}, label: {type: string, minLength: 1, x-policy-limit: Resolve content/input
            byte and character limits before enabling this operation.}, score: {type: number}, scaleMinimum: {type: number}, scaleMaximum: {
          type: number}, evidenceIds: {type: array, items: {$ref: '#/$defs/Id'}}, limitations: {type: array, items: {type: string,
            minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}}}, required: [
        criterionId, label, evidenceIds, limitations], additionalProperties: false, dependentRequired: {score: [scaleMinimum, scaleMaximum],
        scaleMinimum: [score, scaleMaximum], scaleMaximum: [score, scaleMinimum]}}
  ResearchArtifact: {type: object, properties: {artifact: {$ref: '#/$defs/ResearchArtifactRef'}, ownerId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'},
        operationId: {$ref: '#/$defs/Id'}, kind: {type: string, enum: [research-answer, novelty-result, novelty-discussion]}, output: {
          $ref: '#/$defs/ResearchOutput'}, currentEligibilityRevision: {$ref: '#/$defs/Revision'}, mediaType: {const: application/json},
        policy: {$ref: '#/$defs/PolicyRef'}}, required: [artifact, ownerId, contextId, operationId, kind, output, currentEligibilityRevision,
        mediaType, policy], additionalProperties: false}
  ResearchArtifactRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, artifact: {$ref: '#/$defs/ResearchArtifactRef'}}, required: [
        context, artifact], additionalProperties: false}
  ResearchArtifactResponse: {oneOf: [{type: object, properties: {availability: {const: ready}, prepared: {$ref: '#/$defs/ResearchArtifact'}}, required: [availability,
            prepared], additionalProperties: false}, {type: object, properties: {availability: {type: string, enum: [pending, failed,
                expired, deleted, restricted]}, artifactId: {$ref: '#/$defs/Id'}, reasonKey: {type: string, minLength: 1}}, required: [
            availability, artifactId, reasonKey], additionalProperties: false}]}
  ResearchNoveltyDiscussion: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, source: {$ref: '#/$defs/ResearchArtifactRef'}, text: {type: string,
          minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}, submittedDraft: {
          $ref: '#/$defs/DraftRef'}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, source, text, policy], additionalProperties: false}
  ResearchCompletion: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, kind: {type: string, enum: [research-turn, novelty-analysis,
            novelty-discussion]}, jobId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'}, leaseId: {$ref: '#/$defs/Id'}, expectedJobRevision: {
          $ref: '#/$defs/Revision'}, inputHash: {$ref: '#/$defs/Hash'}, prepared: {$ref: '#/$defs/ResearchArtifact'}, usageRecordId: {
          $ref: '#/$defs/Id'}}, required: [context, kind, jobId, contextId, leaseId, expectedJobRevision, inputHash, prepared, usageRecordId],
      additionalProperties: false}
  DigestSchedule: {type: object, properties: {cadenceId: {$ref: '#/$defs/Id'}, timeZone: {type: string, minLength: 1}, windowPolicy: {$ref: '#/$defs/PolicyRef'}},
      required: [cadenceId, timeZone, windowPolicy], additionalProperties: false}
  DigestSubscriptionWrite: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, topic: {type: string, minLength: 1, x-policy-limit: Resolve
            content/input byte and character limits before enabling this operation.}, enabled: {type: boolean}, schedule: {$ref: '#/$defs/DigestSchedule'},
        expectedRevision: {anyOf: [{$ref: '#/$defs/Revision'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [
        context, topic, enabled, schedule, expectedRevision, policy], additionalProperties: false}
  DigestSubscription: {type: object, properties: {subscriptionId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, topic: {type: string, minLength: 1,
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}, revision: {$ref: '#/$defs/Revision'},
        enabled: {type: boolean}, schedule: {$ref: '#/$defs/DigestSchedule'}, unsubscribeBoundary: {anyOf: [{$ref: '#/$defs/Revision'},
            {type: 'null'}]}}, required: [subscriptionId, ownerId, topic, revision, enabled, schedule, unsubscribeBoundary], additionalProperties: false}
  DigestSubscriptionRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, subscriptionId: {$ref: '#/$defs/Id'}}, required: [context,
        subscriptionId], additionalProperties: false}
  DigestSubscriptionsRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, page: {$ref: '#/$defs/PageRequest'}}, required: [context,
        page], additionalProperties: false}
  DigestSubscriptions: {type: object, properties: {subscriptions: {type: array, items: {$ref: '#/$defs/DigestSubscription'}}, page: {$ref: '#/$defs/PageInfo'}},
      required: [subscriptions, page], additionalProperties: false}
  DigestWindow: {type: object, properties: {startInclusive: {$ref: '#/$defs/Time'}, endExclusive: {$ref: '#/$defs/Time'}, timeZone: {type: string,
          minLength: 1}, windowPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [startInclusive, endExclusive, timeZone, windowPolicy],
      additionalProperties: false}
  DigestPrepare: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, subscriptionId: {$ref: '#/$defs/Id'}, subscriptionRevision: {
          $ref: '#/$defs/Revision'}, window: {$ref: '#/$defs/DigestWindow'}, consentRevision: {$ref: '#/$defs/Revision'}, policy: {
          $ref: '#/$defs/PolicyRef'}}, required: [context, subscriptionId, subscriptionRevision, window, consentRevision, policy],
      additionalProperties: false}
  DigestDeliveryRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, deliveryId: {$ref: '#/$defs/Id'}}, required: [context, deliveryId],
      additionalProperties: false}
  DigestDelivery: {type: object, properties: {deliveryId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, subscriptionId: {$ref: '#/$defs/Id'},
        revision: {$ref: '#/$defs/Revision'}, window: {$ref: '#/$defs/DigestWindow'}, papers: {type: array, items: {$ref: '#/$defs/PaperRef'}},
        state: {type: string, enum: [prepared, no-content, queued, sending, sent, failed, unknown, suppressed]}, effectKey: {$ref: '#/$defs/Id'},
        remoteReference: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, limitations: {type: array, items: {type: string, minLength: 1,
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.}}}, required: [deliveryId,
        ownerId, subscriptionId, revision, window, papers, state, effectKey, remoteReference, limitations], additionalProperties: false}
  DigestSend: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, deliveryId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'},
        effectKey: {$ref: '#/$defs/Id'}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [context, deliveryId, expectedRevision, effectKey,
        policy], additionalProperties: false}
  DigestUnsubscribe: {type: object, properties: {signedToken: {type: string, minLength: 1}, confirmed: {const: true}}, required: [signedToken, confirmed],
      additionalProperties: false}
  DigestUnsubscribeResult: {type: object, properties: {outcome: {const: acknowledged}, requestId: {$ref: '#/$defs/Id'}}, required: [outcome, requestId], additionalProperties: false}
  ExportConnectionConfigure: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, token: {type: string, minLength: 1, writeOnly: true, x-policy-limit: Resolved
            credential input bounds; reject and redact invalid credentials.}, expectedRevision: {anyOf: [{$ref: '#/$defs/Revision'},
            {type: 'null'}]}, credentialPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [context, token, expectedRevision, credentialPolicy],
      additionalProperties: false}
  ExportConnectionRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, connectionId: {$ref: '#/$defs/Id'}}, required: [context],
      additionalProperties: false, description: 'Internal envelope; an absent connectionId names the owner''s single connection (C09 2.1.0, A7).'}
  ExportConnection: {type: object, properties: {connectionId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        provider: {const: notion}, state: {type: string, enum: [connected, disconnected, revoked, unavailable]}, destinationScopeIds: {
          type: array, items: {$ref: '#/$defs/Id'}}, limitations: {type: array, items: {type: string, minLength: 1, x-policy-limit: Resolve
              content/input byte and character limits before enabling this operation.}}, workspaceName: {type: string, minLength: 1, maxLength: 2000}},
      required: [connectionId, ownerId, revision, provider, state, destinationScopeIds, limitations], additionalProperties: false}
  ExportDestination: {type: object, properties: {connectionId: {$ref: '#/$defs/Id'}, workspaceId: {$ref: '#/$defs/Id'}, parentPageId: {$ref: '#/$defs/Id'},
        formatRevision: {$ref: '#/$defs/Revision'}, destinationId: {$ref: '#/$defs/Id'}, title: {type: string, minLength: 1, maxLength: 2000},
        context: {type: string, minLength: 1, maxLength: 2000}}, required: [connectionId, workspaceId, parentPageId, formatRevision],
      additionalProperties: false}
  ExportDestinationEntry: {type: object, properties: {connectionId: {$ref: '#/$defs/Id'}, workspaceId: {$ref: '#/$defs/Id'}, parentPageId: {$ref: '#/$defs/Id'},
        formatRevision: {$ref: '#/$defs/Revision'}, destinationId: {$ref: '#/$defs/Id'}, title: {type: string, minLength: 1, maxLength: 2000},
        context: {type: string, minLength: 1, maxLength: 2000}, readable: {type: boolean}, creationCapability: {$ref: '#/$defs/ExportCreationCapability'},
        writable: {type: boolean}}, required: [connectionId, workspaceId, parentPageId, formatRevision, destinationId, title], additionalProperties: false}
  ExportCreationCapability: {type: string, enum: [unknown, confirmed, refused]}
  ExportDestinations: {type: object, properties: {connectionId: {$ref: '#/$defs/Id'}, connectionRevision: {$ref: '#/$defs/Revision'}, destinations: {
          type: array, items: {$ref: '#/$defs/ExportDestinationEntry'}}, listingComplete: {type: boolean}, lastDestinationId: {$ref: '#/$defs/Id'}},
      required: [connectionId, connectionRevision, destinations], additionalProperties: false}
  ExportPreviewRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, source: {$ref: '#/$defs/ResearchArtifactRef'}, destination: {
          $ref: '#/$defs/ExportDestination'}, renderPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [context, source, destination,
        renderPolicy], additionalProperties: false}
  ExportPreview: {type: object, properties: {previewId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'},
        source: {$ref: '#/$defs/ResearchArtifactRef'}, sourceEligibilityRevision: {$ref: '#/$defs/Revision'}, connectionRevision: {
          $ref: '#/$defs/Revision'}, destination: {$ref: '#/$defs/ExportDestinationEntry'}, renderedText: {type: string}, renderedContentHash: {
          $ref: '#/$defs/Hash'}, bindingHash: {$ref: '#/$defs/Hash'}, renderPolicy: {$ref: '#/$defs/PolicyRef'}, earlierExports: {type: array,
          items: {$ref: '#/$defs/ExportEarlierExport'}, maxItems: 20}, marker: {type: string, minLength: 1, maxLength: 200}, sourceTitle: {
          type: string, minLength: 1, maxLength: 2000}}, required: [previewId,
        ownerId, revision, source, sourceEligibilityRevision, connectionRevision, destination, renderedText, renderedContentHash, bindingHash,
        renderPolicy], additionalProperties: false}
  ExportEarlierExport: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, disposition: {$ref: '#/$defs/ExportEarlierExportDisposition'},
        endedAt: {$ref: '#/$defs/Time'}, remoteUrl: {type: string, minLength: 1, format: uri}, outcomeReason: {$ref: '#/$defs/ExportOutcomeReason'}},
      required: [effectId, disposition, endedAt], additionalProperties: false}
  ExportEarlierExportDisposition: {type: string, enum: [exported, may-exist]}
  ExportApprovalRequest: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, previewId: {$ref: '#/$defs/Id'}, previewRevision: {$ref: '#/$defs/Revision'},
        bindingHash: {$ref: '#/$defs/Hash'}, explicitApproval: {const: true}}, required: [context, previewId, previewRevision, bindingHash,
        explicitApproval], additionalProperties: false}
  ExportApproval: {type: object, properties: {approvalId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, previewId: {$ref: '#/$defs/Id'}, previewRevision: {
          $ref: '#/$defs/Revision'}, bindingHash: {$ref: '#/$defs/Hash'}, approvedAt: {$ref: '#/$defs/Time'}, expiresAt: {anyOf: [
            {$ref: '#/$defs/Time'}, {type: 'null'}]}, state: {type: string, enum: [approved, invalidated, consumed, cancelled, expired]},
        policy: {$ref: '#/$defs/PolicyRef'}, invalidationReason: {$ref: '#/$defs/ExportInvalidationReason'}}, required: [approvalId, ownerId,
        previewId, previewRevision, bindingHash, approvedAt, expiresAt, state, policy], additionalProperties: false}
  ExportInvalidationReason: {type: string, enum: [source-changed, destination-changed, connection-changed, authority-revoked, account-withdrawn]}
  ExportExecute: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, approvalId: {$ref: '#/$defs/Id'}, bindingHash: {$ref: '#/$defs/Hash'}},
      required: [context, approvalId, bindingHash], additionalProperties: false}
  ExportEffect: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, approvalId: {$ref: '#/$defs/Id'}, ownerId: {$ref: '#/$defs/Id'}, revision: {
          $ref: '#/$defs/Revision'}, bindingHash: {$ref: '#/$defs/Hash'}, state: {type: string, enum: [accepted, executing, succeeded,
            failed, unknown, cancelled, invalidated]}, remoteReference: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, remoteUrl: {
          anyOf: [{type: string, minLength: 1, format: uri}, {type: 'null'}]}, reconciliationEvidenceHash: {anyOf: [{$ref: '#/$defs/Hash'},
            {type: 'null'}]}, limitations: {type: array, items: {type: string, minLength: 1, x-policy-limit: Resolve content/input
              byte and character limits before enabling this operation.}}, outcomeReason: {$ref: '#/$defs/ExportOutcomeReason'}, settledBy: {
          $ref: '#/$defs/ExportSettledBy'}, nextCheckAt: {$ref: '#/$defs/Time'}, settlementOffered: {type: boolean}}, required: [effectId,
        approvalId, ownerId, revision, bindingHash, state, remoteReference, remoteUrl, reconciliationEvidenceHash, limitations], additionalProperties: false}
  ExportOutcomeReason: {type: string, enum: [token-invalid, no-access, destination-missing, content-rejected, workspace-block-limit, provider-blocked,
      rate-limit-budget-spent, not-found-after-checks, owner-settled-delivered, owner-settled-not-delivered, dependency-unavailable, policy-unresolved,
      source-changed, destination-changed, connection-changed, authority-revoked, account-withdrawn, owner-cancelled]}
  ExportSettledBy: {type: string, enum: [provider, reconciliation, owner]}
  ExportEffectRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, effectId: {$ref: '#/$defs/Id'}}, required: [context, effectId],
      additionalProperties: false}
  ExportCancel: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, approvalId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [context, approvalId, expectedRevision], additionalProperties: false}
  ExportHistoryList: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, limit: {type: integer, minimum: 1, maximum: 20}, cursor: {
          anyOf: [{type: string, minLength: 1, maxLength: 512}, {type: 'null'}]}}, required: [context], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  ExportHistoryPage: {type: object, properties: {entries: {type: array, items: {$ref: '#/$defs/ExportHistoryEntry'}, maxItems: 20}, nextCursor: {
          anyOf: [{type: string, minLength: 1, maxLength: 512}, {type: 'null'}]}}, required: [entries, nextCursor], additionalProperties: false}
  ExportHistoryEntry: {type: object, properties: {approvalId: {$ref: '#/$defs/Id'}, previewId: {$ref: '#/$defs/Id'}, previewRevision: {$ref: '#/$defs/Revision'},
        bindingHash: {$ref: '#/$defs/Hash'}, state: {$ref: '#/$defs/ExportApprovalState'}, invalidationReason: {$ref: '#/$defs/ExportInvalidationReason'},
        approvedAt: {$ref: '#/$defs/Time'}, endedAt: {$ref: '#/$defs/Time'}, sourceTitle: {type: string, minLength: 1, maxLength: 2000}, destinationTitle: {
          type: string, minLength: 1, maxLength: 2000}, continuable: {type: boolean}, effect: {$ref: '#/$defs/ExportHistoryEffect'}}, required: [
        approvalId, previewId, previewRevision, bindingHash, state, approvedAt, sourceTitle, destinationTitle, continuable], additionalProperties: false}
  ExportHistoryEffect: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, state: {$ref: '#/$defs/ExportEffectState'}, revision: {$ref: '#/$defs/Revision'},
        remoteUrl: {type: string, minLength: 1, format: uri}, outcomeReason: {$ref: '#/$defs/ExportOutcomeReason'}, settledBy: {$ref: '#/$defs/ExportSettledBy'},
        nextCheckAt: {$ref: '#/$defs/Time'}, possibleDuplicates: {type: array, items: {$ref: '#/$defs/ExportPossibleDuplicate'}, maxItems: 10},
        settlementOffered: {type: boolean}}, required: [effectId, state, revision, possibleDuplicates, settlementOffered], additionalProperties: false}
  ExportPossibleDuplicate: {type: object, properties: {remoteReference: {$ref: '#/$defs/Id'}, remoteUrl: {type: string, minLength: 1, format: uri}},
      required: [remoteReference], additionalProperties: false}
  ExportApprovalState: {type: string, enum: [approved, invalidated, consumed, cancelled, expired]}
  ExportEffectState: {type: string, enum: [accepted, executing, succeeded, failed, unknown, cancelled, invalidated]}
  ExportSettle: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, effectId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'},
        disposition: {$ref: '#/$defs/ExportSettleDisposition'}, assumptionAccepted: {const: true}, remoteUrl: {type: string, minLength: 1, format: uri}},
      required: [context, effectId, expectedRevision, disposition, assumptionAccepted], additionalProperties: false, description: 'Internal envelope;
        context is derived by the trusted boundary, never accepted from a public body.'}
  ExportSettleDisposition: {type: string, enum: [delivered, not-delivered]}
  SessionBootstrap: {type: object, properties: {signedIn: {type: boolean}, accountId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, authorityRevision: {
          anyOf: [{$ref: '#/$defs/Revision'}, {type: 'null'}]}, csrfToken: {type: string, minLength: 1, x-limit-policy: AdmissionPolicy
            bounds bytes and characters before persistence/processing.}}, required: [signedIn, accountId, authorityRevision, csrfToken],
      additionalProperties: false}
  CapabilityCatalog: {type: object, properties: {revision: {$ref: '#/$defs/Revision'}, capabilities: {type: array, items: {type: object, properties: {
              id: {$ref: '#/$defs/Id'}, state: {type: string, enum: [available, degraded, unavailable, policy_pending]}, modeIds: {
                type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.},
              languageIds: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy
                  blocks admission.}, levelIds: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length;
                  unresolved policy blocks admission.}, formatIds: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy
                  bounds length; unresolved policy blocks admission.}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [id, state,
              modeIds, languageIds, levelIds, formatIds, policy], additionalProperties: false}, x-limit-policy: AdmissionPolicy bounds
            length; unresolved policy blocks admission.}}, required: [revision, capabilities], additionalProperties: false}
  UploadAck: {type: object, properties: {uploadId: {$ref: '#/$defs/Id'}, contentHash: {$ref: '#/$defs/Hash'}, receivedBytes: {type: integer,
          minimum: 0}, revision: {$ref: '#/$defs/Revision'}}, required: [uploadId, contentHash, receivedBytes, revision], additionalProperties: false}
  ProcessLiveness: {type: object, properties: {status: {const: alive}}, required: [status], additionalProperties: false}
  ControlledReadiness: {type: object, properties: {status: {type: string, enum: [ready, not_ready, unknown]}, generation: {$ref: '#/$defs/Revision'},
        reasonKeys: {type: array, items: {$ref: '#/$defs/Id'}, x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks
            admission.}}, required: [status, generation, reasonKeys], additionalProperties: false}
  HostNavigationInputHttp: {type: object, properties: {routeId: {$ref: '#/$defs/Id'}, returnContext: {$ref: '#/$defs/HostReturnContext'}}, required: [routeId],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  AccessSessionInputHttp: {type: object, properties: {}, required: [], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  AccessRegisterInputHttp: {type: object, properties: {email: {$ref: '#/$defs/AccessEmail'}, password: {$ref: '#/$defs/AccessSecret'}, displayName: {type: string,
          minLength: 1, x-policy-bound: profile display-name policy, description: Bound by the named approved policy before processing.},
        policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [email, password, policyRef], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessEmailRequestInputHttp: {type: object, properties: {email: {$ref: '#/$defs/AccessEmail'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [email, policyRef],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  AccessVerifyEmailInputHttp: {type: object, properties: {verification: {$ref: '#/$defs/AccessChallengeProof'}}, required: [verification], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessLoginInputHttp: {type: object, properties: {email: {$ref: '#/$defs/AccessEmail'}, password: {$ref: '#/$defs/AccessSecret'}, policyRef: {$ref: '#/$defs/PolicyRef'}},
      required: [email, password, policyRef], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  AccessLogoutInputHttp: {type: object, properties: {}, required: [], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  AccessPasswordResetInputHttp: {type: object, properties: {verification: {$ref: '#/$defs/AccessChallengeProof'}, newPassword: {$ref: '#/$defs/AccessSecret'}},
      required: [verification, newPassword], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  AccessPasswordChangeInputHttp: {type: object, properties: {currentPassword: {$ref: '#/$defs/AccessSecret'}, newPassword: {$ref: '#/$defs/AccessSecret'}}, required: [
        currentPassword, newPassword], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted
        boundary, never accepted from a public body.'}
  AccessEmailChangeInputHttp: {type: object, properties: {currentProof: {$ref: '#/$defs/AccessSecret'}, newEmail: {$ref: '#/$defs/AccessEmail'}, policyRef: {
          $ref: '#/$defs/PolicyRef'}}, required: [currentProof, newEmail, policyRef], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessEmailChangeCompleteInputHttp: {type: object, properties: {verification: {$ref: '#/$defs/AccessChallengeProof'}}, required: [verification], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessBeginIdentityInputHttp: {type: object, properties: {provider: {type: string, enum: [google, orcid]}, intent: {type: string, enum: [sign_in, link]}, returnRouteId: {
          $ref: '#/$defs/Id'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [provider, intent, returnRouteId, policyRef], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessIdentityListInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessUnlinkIdentityInputHttp: {type: object, properties: {identityLinkId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [identityLinkId, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessOrcidProfileInputHttp: {type: object, properties: {identityLinkId: {$ref: '#/$defs/Id'}}, required: [identityLinkId], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessMfaEnrollmentInputHttp: {type: object, properties: {currentProof: {$ref: '#/$defs/AccessSecret'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [
        currentProof, policyRef], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  AccessMfaMaterialInputHttp: {type: object, properties: {enrollmentId: {$ref: '#/$defs/Id'}, deliveryReference: {$ref: '#/$defs/Id'}, currentProof: {$ref: '#/$defs/AccessSecret'}},
      required: [enrollmentId, deliveryReference, currentProof], additionalProperties: false, description: 'Internal envelope; context
        is derived by the trusted boundary, never accepted from a public body.'}
  AccessMfaConfirmInputHttp: {type: object, properties: {enrollmentId: {$ref: '#/$defs/Id'}, verification: {$ref: '#/$defs/AccessChallengeProof'}}, required: [
        enrollmentId, verification], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted
        boundary, never accepted from a public body.'}
  AccessMfaVerifyInputHttp: {type: object, properties: {verification: {$ref: '#/$defs/AccessChallengeProof'}, factorKind: {type: string, enum: [totp, recovery_proof]}},
      required: [verification, factorKind], additionalProperties: false, description: 'Pre-authentication request: context may contain
        an anonymous principal. The trusted transport separately validates the protected primary-authentication continuation cookie,
        binds it to verification.challengeId/flowBinding and the server-owned primary-authentication record, and passes only a verified
        invocation. The factor proof is untrusted until checked; neither a full session nor a caller-claimed account is required.'}
  AccessMfaRecoveryInputHttp: {type: object, properties: {verification: {$ref: '#/$defs/AccessChallengeProof'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [
        verification, policyRef], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.'}
  AccessProfileInputHttp: {type: object, properties: {}, required: [], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  AccessProfileUpdateInputHttp: {type: object, properties: {fieldVocabularyRevision: {$ref: '#/$defs/Revision'}, changes: {type: array, items: {$ref: '#/$defs/AccessProfileField'},
          x-policy-bound: retained mutable-profile field vocabulary}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [fieldVocabularyRevision, changes, policyRef, expectedRevision], additionalProperties: false, description: 'Internal envelope; context
        is derived by the trusted boundary, never accepted from a public body.'}
  AccessConsentListInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  AccessConsentUpdateInputHttp: {type: object, properties: {purposeId: {$ref: '#/$defs/Id'}, decision: {type: string, enum: [granted, revoked]}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [purposeId, decision, policyRef, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived
        by the trusted boundary, never accepted from a public body.'}
  LifecycleRequestInputHttp: {type: object, properties: {action: {type: string, enum: [withdraw, erase]}, policyRef: {$ref: '#/$defs/PolicyRef'}, confirmationRef: {
          $ref: '#/$defs/Id'}}, required: [action, policyRef, confirmationRef], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LifecycleReactivationInputHttp: {type: object, properties: {verification: {$ref: '#/$defs/AccessChallengeProof'}, policyRef: {$ref: '#/$defs/PolicyRef'}, confirmationRef: {
          $ref: '#/$defs/Id'}}, required: [verification, policyRef, confirmationRef], additionalProperties: false, description: Public
        pre-authentication envelope; no caller account ID or active session is required. Account and withdrawn lifecycle identity are
        resolved exclusively from the verified purpose-bound reactivation proof. Trusted transport context may remain anonymous until
        this limited recovery authority is verified.}
  LifecycleStatusInputHttp: {type: object, properties: {lifecycleRequestId: {$ref: '#/$defs/Id'}}, required: [lifecycleRequestId], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibrarySavePaperInputHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, policyRef: {$ref: '#/$defs/PolicyRef'}}, required: [paper, policyRef],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from
        a public body.'}
  LibrarySavedPaperInputHttp: {type: object, properties: {savedPaperId: {$ref: '#/$defs/Id'}}, required: [savedPaperId], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibraryPaperListInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibrarySaveSearchInputHttp: {type: object, properties: {queryContext: {$ref: '#/$defs/LibraryQueryContext'}, label: {type: string, minLength: 1, x-policy-bound: saved-search
            label policy, description: Bound by the named approved policy before processing.}}, required: [queryContext], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibrarySavedSearchInputHttp: {type: object, properties: {savedSearchId: {$ref: '#/$defs/Id'}}, required: [savedSearchId], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibrarySearchListInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibraryHistoryListInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibraryHistoryInputHttp: {type: object, properties: {historyId: {$ref: '#/$defs/Id'}}, required: [historyId], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibraryClearHistoryInputHttp: {type: object, properties: {policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [policyRef, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  SettingsReadInputHttp: {type: object, properties: {}, required: [], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  SettingsUpdateInputHttp: {type: object, properties: {searchDefaults: {$ref: '#/$defs/SettingsSearchDefaults'}, assistanceDefaults: {$ref: '#/$defs/SettingsAssistanceDefaults'},
        timeZone: {type: string, minLength: 1, maxLength: 100}, appearance: {type: string, enum: [light, dark, system]}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [policyRef, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary,
        never accepted from a public body.', anyOf: [{required: [searchDefaults]}, {required: [assistanceDefaults]}, {required: [appearance]}, {required: [timeZone]}]}
  SettingsOnboardingInputHttp: {type: object, properties: {action: {type: string, enum: [save_interests, complete, skip]}, interestIds: {type: array, items: {$ref: '#/$defs/Id'},
          x-policy-bound: retained interest vocabulary and onboarding policy, uniqueItems: true}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {
          $ref: '#/$defs/Revision'}}, required: [action, interestIds, policyRef, expectedRevision], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  SettingsSuggestionInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}, identityLinkId: {$ref: '#/$defs/Id'}}, required: [page], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  SettingsRecentInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  SettingsResetPrepareInputHttp: {type: object, properties: {action: {type: string, enum: [delete_behavior, reset_profile]}, currentProof: {$ref: '#/$defs/AccessSecret'}, policyRef: {$ref: '#/$defs/PolicyRef'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [action, currentProof, policyRef, expectedRevision], additionalProperties: false}
  SettingsResetInputHttp: {type: object, properties: {action: {type: string, enum: [delete_behavior, reset_profile]}, policyRef: {$ref: '#/$defs/PolicyRef'}, confirmationRef: {
          $ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [action, policyRef, confirmationRef, expectedRevision], additionalProperties: false,
      description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsageInspectInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsagePlanInputHttp: {type: object, properties: {}, required: [], additionalProperties: false, description: 'Internal envelope; context is derived by
        the trusted boundary, never accepted from a public body.'}
  UsageGrantInputHttp: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, tierId: {$ref: '#/$defs/Id'}, policyRef: {$ref: '#/$defs/PolicyRef'}, reasonKey: {
          $ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [accountId, tierId, policyRef, reasonKey, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsageRevokeInputHttp: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, entitlementId: {$ref: '#/$defs/Id'}, policyRef: {$ref: '#/$defs/PolicyRef'}, reasonKey: {
          $ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [accountId, entitlementId, policyRef, reasonKey, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsageRecordsInputHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false, description: 'Internal
        envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  CorpusResolveHttp: {type: object, properties: {identifier: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits
            before enabling this operation.}, versionLabel: {type: string, minLength: 1}}, required: [identifier], additionalProperties: false}
  CorpusReadHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, purpose: {type: string, enum: [metadata, read, assistance, research,
            citation, saved-reference]}}, required: [paper, purpose], additionalProperties: false}
  CorpusAssetReadHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'}, assetId: {$ref: '#/$defs/Id'}},
      required: [paper, contentRevision, assetId], additionalProperties: false}
  CorpusRunRequestHttp: {type: object, properties: {operation: {type: string, enum: [ingest, incremental-refresh, rebuild, reprocess]}, sourceScopeIds: {
          type: array, items: {$ref: '#/$defs/Id'}, minItems: 1, uniqueItems: true}, authoritativeInputRevision: {$ref: '#/$defs/Revision'},
        inputManifestHash: {$ref: '#/$defs/Hash'}, sourcePolicy: {$ref: '#/$defs/PolicyRef'}, compatibilityRevision: {$ref: '#/$defs/Revision'}},
      required: [operation, sourceScopeIds, authoritativeInputRevision, inputManifestHash, sourcePolicy, compatibilityRevision], additionalProperties: false}
  CorpusRunReadHttp: {type: object, properties: {runId: {$ref: '#/$defs/Id'}}, required: [runId], additionalProperties: false}
  CorpusEligibilityChangeHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, disposition: {type: string, enum: [eligible, withdrawn, restricted,
            unavailable]}, reasonKey: {type: string, minLength: 1}, sourceEvidenceHash: {$ref: '#/$defs/Hash'}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [paper, disposition, reasonKey, sourceEvidenceHash, policy], additionalProperties: false}
  SearchRequestHttp: {type: object, properties: {query: {$ref: '#/$defs/LibraryQueryContext'}, page: {$ref: '#/$defs/PageRequest'}, snapshotRevision: {
          $ref: '#/$defs/Revision'}}, required: [query, page], additionalProperties: false}
  CitationRequestHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, direction: {type: string, enum: [cited, citing, both]}, page: {
          $ref: '#/$defs/PageRequest'}, traversalPolicy: {$ref: '#/$defs/PolicyRef'}, snapshotRevision: {$ref: '#/$defs/Revision'}},
      required: [paper, direction, page, traversalPolicy], additionalProperties: false}
  AssistanceOptionsReadHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}}, required: [paper], additionalProperties: false}
  AssistanceRequestHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'},
        operation: {type: string, enum: [summary, translation]}, optionId: {$ref: '#/$defs/Id'}, optionsRevision: {$ref: '#/$defs/Revision'},
        glossaryRevision: {$ref: '#/$defs/Revision'}, processingPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [paper, contentRevision,
        contentHash, operation, optionId, optionsRevision, glossaryRevision, processingPolicy], additionalProperties: false}
  AssistanceJobReadHttp: {type: object, properties: {jobId: {$ref: '#/$defs/Id'}}, required: [jobId], additionalProperties: false}
  AssistanceResultRequestHttp: {type: object, properties: {jobId: {$ref: '#/$defs/Id'}, result: {$ref: '#/$defs/ResultRef'}}, required: [jobId], additionalProperties: false}
  AssistanceGlossaryReadHttp: {type: object, properties: {}, required: [], additionalProperties: false}
  AssistanceGlossaryWriteHttp: {type: object, properties: {expectedRevision: {$ref: '#/$defs/Revision'}, normalizationPolicy: {$ref: '#/$defs/PolicyRef'}, terms: {
          type: array, items: {$ref: '#/$defs/AssistanceGlossaryTerm'}}}, required: [expectedRevision, normalizationPolicy, terms],
      additionalProperties: false}
  ResearchContextCreateHttp: {type: object, properties: {purpose: {type: string, enum: [research, novelty]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [
        purpose, policy], additionalProperties: false}
  ResearchSessionCreateHttp: {type: object, properties: {title: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits
            before enabling this operation.}, scope: {$ref: '#/$defs/ResearchScope'}}, required: [title, scope], additionalProperties: false}
  ResearchSessionReadHttp: {type: object, properties: {sessionId: {$ref: '#/$defs/Id'}}, required: [sessionId], additionalProperties: false}
  ResearchSessionListHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false}
  ResearchDeleteHttp: {type: object, properties: {scope: {type: string, enum: [one-session, all-sessions]}, sessionId: {$ref: '#/$defs/Id'}, expectedRevision: {
          $ref: '#/$defs/Revision'}, confirmed: {const: true}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [scope, expectedRevision,
        confirmed, policy], additionalProperties: false, allOf: [{if: {properties: {scope: {const: one-session}}}, then: {required: [
              sessionId]}, else: {not: {required: [sessionId]}}}]}
  ResearchAttachmentStartHttp: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, fileName: {type: string, minLength: 1, x-policy-limit: Resolve content/input
            byte and character limits before enabling this operation.}, mediaType: {type: string, enum: [application/pdf, text/plain]},
        byteLength: {type: integer, minimum: 1, x-policy-limit: Maximum permitted attachment bytes; unresolved means refuse.}, contentHash: {
          $ref: '#/$defs/Hash'}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [contextId, fileName, mediaType, byteLength, contentHash,
        policy], additionalProperties: false}
  ResearchAttachmentFinishHttp: {type: object, properties: {uploadId: {$ref: '#/$defs/Id'}, contextId: {$ref: '#/$defs/Id'}, contentHash: {$ref: '#/$defs/Hash'}},
      required: [uploadId, contextId, contentHash], additionalProperties: false}
  ResearchAttachmentReadHttp: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, attachmentId: {$ref: '#/$defs/Id'}}, required: [contextId, attachmentId],
      additionalProperties: false}
  ResearchPrivateAssetReadHttp: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, attachmentId: {$ref: '#/$defs/Id'}, assetId: {$ref: '#/$defs/Id'}},
      required: [contextId, attachmentId, assetId], additionalProperties: false}
  DraftWriteHttp: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, draftId: {$ref: '#/$defs/Id'}, kind: {type: string, enum: [research-question,
            novelty-topic, novelty-manuscript, novelty-discussion]}, baseRevision: {anyOf: [{$ref: '#/$defs/Revision'}, {type: 'null'}]},
        text: {type: string, x-policy-limit: Resolved owner draft text bounds.}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [
        contextId, draftId, kind, baseRevision, text, policy], additionalProperties: false}
  DraftReadHttp: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, draftId: {$ref: '#/$defs/Id'}}, required: [contextId, draftId], additionalProperties: false}
  DraftDiscardHttp: {type: object, properties: {contextId: {$ref: '#/$defs/Id'}, draft: {$ref: '#/$defs/DraftRef'}, confirmed: {const: true}, policy: {
          $ref: '#/$defs/PolicyRef'}}, required: [contextId, draft, confirmed, policy], additionalProperties: false}
  ResearchTurnRequestHttp: {type: object, properties: {sessionId: {$ref: '#/$defs/Id'}, scope: {$ref: '#/$defs/ResearchScope'}, mode: {type: string, enum: [
            question, compare, quote]}, text: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character
            limits before enabling this operation.}, submittedDraft: {$ref: '#/$defs/DraftRef'}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [sessionId, scope, mode, text, policy], additionalProperties: false}
  ResearchTurnReadHttp: {type: object, properties: {sessionId: {$ref: '#/$defs/Id'}, turnId: {$ref: '#/$defs/Id'}}, required: [sessionId, turnId], additionalProperties: false}
  ResearchNoveltyRequestHttp: {type: object, properties: {scope: {$ref: '#/$defs/ResearchScope'}, inputMode: {type: string, enum: [topic, manuscript]}, text: {
          type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits before enabling this operation.},
        submittedDraft: {$ref: '#/$defs/DraftRef'}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [scope, inputMode, text, policy],
      additionalProperties: false}
  ResearchNoveltyDiscussionHttp: {type: object, properties: {source: {$ref: '#/$defs/ResearchArtifactRef'}, text: {type: string, minLength: 1, x-policy-limit: Resolve
            content/input byte and character limits before enabling this operation.}, submittedDraft: {$ref: '#/$defs/DraftRef'}, policy: {
          $ref: '#/$defs/PolicyRef'}}, required: [source, text, policy], additionalProperties: false}
  ResearchJobReadHttp: {type: object, properties: {kind: {type: string, enum: [research-turn, novelty-analysis, novelty-discussion]}, jobId: {$ref: '#/$defs/Id'},
        contextId: {$ref: '#/$defs/Id'}}, required: [kind, jobId, contextId], additionalProperties: false}
  ResearchArtifactReadHttp: {type: object, properties: {artifact: {$ref: '#/$defs/ResearchArtifactRef'}}, required: [artifact], additionalProperties: false}
  DigestSubscriptionWriteHttp: {type: object, properties: {topic: {type: string, minLength: 1, x-policy-limit: Resolve content/input byte and character limits
            before enabling this operation.}, enabled: {type: boolean}, schedule: {$ref: '#/$defs/DigestSchedule'}, expectedRevision: {
          anyOf: [{$ref: '#/$defs/Revision'}, {type: 'null'}]}, policy: {$ref: '#/$defs/PolicyRef'}}, required: [topic, enabled, schedule,
        expectedRevision, policy], additionalProperties: false}
  DigestSubscriptionsReadHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}}, required: [page], additionalProperties: false}
  DigestSubscriptionReadHttp: {type: object, properties: {subscriptionId: {$ref: '#/$defs/Id'}}, required: [subscriptionId], additionalProperties: false}
  DigestDeliveryReadHttp: {type: object, properties: {deliveryId: {$ref: '#/$defs/Id'}}, required: [deliveryId], additionalProperties: false}
  DigestUnsubscribeHttp: {type: object, properties: {signedToken: {type: string, minLength: 1}, confirmed: {const: true}}, required: [signedToken, confirmed],
      additionalProperties: false}
  ExportConnectionConfigureHttp: {type: object, properties: {token: {type: string, minLength: 1, writeOnly: true, x-policy-limit: Resolved credential input bounds;
            reject and redact invalid credentials.}, expectedRevision: {anyOf: [{$ref: '#/$defs/Revision'}, {type: 'null'}]}, credentialPolicy: {
          $ref: '#/$defs/PolicyRef'}}, required: [token, expectedRevision, credentialPolicy], additionalProperties: false}
  ExportConnectionReadHttp: {type: object, properties: {connectionId: {$ref: '#/$defs/Id'}}, required: [], additionalProperties: false}
  ExportPreviewRequestHttp: {type: object, properties: {source: {$ref: '#/$defs/ResearchArtifactRef'}, destination: {$ref: '#/$defs/ExportDestination'}, renderPolicy: {
          $ref: '#/$defs/PolicyRef'}}, required: [source, destination, renderPolicy], additionalProperties: false}
  ExportApprovalRequestHttp: {type: object, properties: {previewId: {$ref: '#/$defs/Id'}, previewRevision: {$ref: '#/$defs/Revision'}, bindingHash: {$ref: '#/$defs/Hash'},
        explicitApproval: {const: true}}, required: [previewId, previewRevision, bindingHash, explicitApproval], additionalProperties: false}
  ExportExecuteHttp: {type: object, properties: {approvalId: {$ref: '#/$defs/Id'}, bindingHash: {$ref: '#/$defs/Hash'}}, required: [approvalId, bindingHash],
      additionalProperties: false}
  ExportEffectReadHttp: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}}, required: [effectId], additionalProperties: false}
  ExportCancelHttp: {type: object, properties: {approvalId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [approvalId,
        expectedRevision], additionalProperties: false}
  ExportHistoryListHttp: {type: object, properties: {limit: {type: integer, minimum: 1, maximum: 20}, cursor: {anyOf: [{type: string, minLength: 1,
            maxLength: 512}, {type: 'null'}]}}, required: [], additionalProperties: false}
  ExportSettleHttp: {type: object, properties: {effectId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}, disposition: {
          $ref: '#/$defs/ExportSettleDisposition'}, assumptionAccepted: {const: true}, remoteUrl: {type: string, minLength: 1, format: uri}}, required: [
        effectId, expectedRevision, disposition, assumptionAccepted], additionalProperties: false}
  OpsQueryHttp: {type: object, properties: {page: {$ref: '#/$defs/PageRequest'}, capability: {$ref: '#/$defs/Id'}}, required: [page], additionalProperties: false}
  OpsRecoveryRequestHttp: {type: object, properties: {incidentId: {$ref: '#/$defs/Id'}, ownerComponent: {$ref: '#/$defs/Id'}, operation: {$ref: '#/$defs/Id'},
        targetId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}, evidenceRefs: {type: array, items: {$ref: '#/$defs/Id'},
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.}, policy: {$ref: '#/$defs/PolicyRef'}},
      required: [incidentId, ownerComponent, operation, targetId, expectedRevision, evidenceRefs, policy], additionalProperties: false}
  PreparedJobRead: {oneOf: [{$ref: '#/$defs/AssistanceResultRead'}, {$ref: '#/$defs/ResearchArtifactResponse'}]}
  LibraryRemoveSavedPaperInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, savedPaperId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [context, savedPaperId, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  LibraryRemoveSavedPaperInputHttp: {type: object, properties: {savedPaperId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [savedPaperId, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  LibraryRemoveSavedSearchInput: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, savedSearchId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}},
      required: [context, savedSearchId, expectedRevision], additionalProperties: false, description: 'Internal envelope; context is derived by the
        trusted boundary, never accepted from a public body.'}
  LibraryRemoveSavedSearchInputHttp: {type: object, properties: {savedSearchId: {$ref: '#/$defs/Id'}, expectedRevision: {$ref: '#/$defs/Revision'}}, required: [savedSearchId, expectedRevision],
      additionalProperties: false, description: 'Internal envelope; context is derived by the trusted boundary, never accepted from a public body.'}
  UsageAssignmentRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, accountId: {$ref: '#/$defs/Id'}}, required: [context, accountId], additionalProperties: false}
  UsageAssignmentReadHttp: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}}, required: [accountId], additionalProperties: false}
  UsageAssignmentSnapshot: {type: object, properties: {accountId: {$ref: '#/$defs/Id'}, revision: {$ref: '#/$defs/Revision'}, entitlement: {anyOf: [{$ref: '#/$defs/UsageEntitlement'},
            {type: 'null'}]}}, required: [accountId, revision, entitlement], additionalProperties: false}
  AssistanceHistoryRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, paper: {$ref: '#/$defs/PaperRef'}, page: {$ref: '#/$defs/PageRequest'}},
      required: [context, paper, page], additionalProperties: false}
  AssistanceHistoryReadHttp: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, page: {$ref: '#/$defs/PageRequest'}}, required: [paper, page], additionalProperties: false}
  AssistanceHistoryRow: {type: object, properties: {jobId: {$ref: '#/$defs/Id'}, paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'}, contentHash: {
          $ref: '#/$defs/Hash'}, operation: {enum: [summary, translation]}, optionId: {$ref: '#/$defs/Id'}, optionsRevision: {$ref: '#/$defs/Revision'},
        glossaryRevision: {$ref: '#/$defs/Revision'}, state: {enum: [accepted, running, succeeded, failed]}, revision: {$ref: '#/$defs/Revision'},
        seq: {type: integer, minimum: 0}, createdAt: {$ref: '#/$defs/Time'}, availability: {enum: [ready, pending, failed, expired, withdrawn, restricted]},
        result: {anyOf: [{$ref: '#/$defs/ResultRef'}, {type: 'null'}]}}, required: [jobId, paper, contentRevision, contentHash, operation, optionId,
        optionsRevision, glossaryRevision, state, revision, seq, createdAt, availability, result], additionalProperties: false, allOf: [{if: {properties: {
              availability: {const: ready}}}, then: {properties: {state: {const: succeeded}, result: {$ref: '#/$defs/ResultRef'}}}, else: {properties: {
              result: {type: 'null'}}}}]}
  AssistanceHistoryPage: {type: object, properties: {items: {type: array, items: {$ref: '#/$defs/AssistanceHistoryRow'}, x-policy-bound: accepted PageRequest.limit}, page: {
          $ref: '#/$defs/PageInfo'}}, required: [items, page], additionalProperties: false}
  ExecutionBinding: {type: object, properties: {ownerComponent: {$ref: '#/$defs/Id'}, operationId: {$ref: '#/$defs/Id'}, inputRevision: {$ref: '#/$defs/Revision'},
        inputHash: {$ref: '#/$defs/Hash'}, payloadRef: {$ref: '#/$defs/Id'}}, required: [ownerComponent, operationId, inputRevision, inputHash, payloadRef],
      additionalProperties: false}
  ExecutionClaim: {type: object, properties: {binding: {$ref: '#/$defs/ExecutionBinding'}, workerId: {$ref: '#/$defs/Id'}, leaseId: {$ref: '#/$defs/Id'}, fence: {
          type: integer, minimum: 1}, leaseRevision: {$ref: '#/$defs/Revision'}, expiresAt: {$ref: '#/$defs/Time'}}, required: [binding, workerId,
        leaseId, fence, leaseRevision, expiresAt], additionalProperties: false}
  ExecutionAcquire: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, binding: {$ref: '#/$defs/ExecutionBinding'}, deliveryId: {$ref: '#/$defs/Id'}},
      required: [context, binding, deliveryId], additionalProperties: false}
  ExecutionRenew: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, claim: {$ref: '#/$defs/ExecutionClaim'}, expectedLeaseRevision: {$ref: '#/$defs/Revision'}},
      required: [context, claim, expectedLeaseRevision], additionalProperties: false}
  ExecutionReclaim: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, binding: {$ref: '#/$defs/ExecutionBinding'}, previousFence: {type: integer,
          minimum: 1}, deliveryId: {$ref: '#/$defs/Id'}}, required: [context, binding, previousFence, deliveryId], additionalProperties: false}
  ExecutionClaimRead: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, claim: {$ref: '#/$defs/ExecutionClaim'}}, required: [context, claim], additionalProperties: false}
  ExecutionClaimResult: {type: object, properties: {claim: {$ref: '#/$defs/ExecutionClaim'}, jobRevision: {$ref: '#/$defs/Revision'}, acceptedAt: {$ref: '#/$defs/Time'}},
      required: [claim, jobRevision, acceptedAt], additionalProperties: false}
  AssistanceAcceptedInput: {type: object, properties: {paper: {$ref: '#/$defs/PaperRef'}, contentRevision: {$ref: '#/$defs/Revision'}, contentHash: {$ref: '#/$defs/Hash'},
        operation: {type: string, enum: [summary, translation]}, optionId: {$ref: '#/$defs/Id'}, optionsRevision: {$ref: '#/$defs/Revision'}, glossaryRevision: {
          $ref: '#/$defs/Revision'}, processingPolicy: {$ref: '#/$defs/PolicyRef'}, glossary: {$ref: '#/$defs/AssistanceGlossary'}}, required: [paper,
        contentRevision, contentHash, operation, optionId, optionsRevision, glossaryRevision, processingPolicy, glossary], additionalProperties: false}
  AssistanceExecutionPayload: {type: object, properties: {binding: {$ref: '#/$defs/ExecutionBinding'}, acceptedAt: {$ref: '#/$defs/Time'}, input: {$ref: '#/$defs/AssistanceAcceptedInput'},
        sections: {type: array, items: {$ref: '#/$defs/CorpusSection'}, x-policy-bound: accepted input and context policy}, usageRecordId: {$ref: '#/$defs/Id'}},
      required: [binding, acceptedAt, input, sections, usageRecordId], additionalProperties: false}
  ResearchAcceptedInput: {type: object, properties: {kind: {type: string, enum: [research-turn, novelty-analysis, novelty-discussion]},
        contextId: {$ref: '#/$defs/Id'}, sessionId: {anyOf: [{$ref: '#/$defs/Id'}, {type: 'null'}]}, inputSnapshot: {type: object,
          x-policy-bound: the frozen owner input for the accepted operation, immutable after acceptance}, inputHash: {$ref: '#/$defs/Hash'},
        sourceScope: {type: array, items: {$ref: '#/$defs/Id'}}, attachmentReferences: {type: array, items: {$ref: '#/$defs/Id'}},
        draftRevision: {anyOf: [{$ref: '#/$defs/Revision'}, {type: 'null'}]}, processingPolicy: {$ref: '#/$defs/PolicyRef'}}, required: [kind,
        contextId, sessionId, inputSnapshot, inputHash, sourceScope, attachmentReferences, draftRevision, processingPolicy], additionalProperties: false}
  ResearchExecutionPayload: {type: object, properties: {binding: {$ref: '#/$defs/ExecutionBinding'}, acceptedAt: {$ref: '#/$defs/Time'},
        input: {$ref: '#/$defs/ResearchAcceptedInput'}, evidenceScope: {type: array, items: {$ref: '#/$defs/Id'},
          x-policy-bound: eligible evidence the owner may read at execution time; the prepare/untrusted-content rules still apply}, usageRecordId: {$ref: '#/$defs/Id'}},
      required: [binding, acceptedAt, input, evidenceScope, usageRecordId], additionalProperties: false}
  AssistanceProgress: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, jobId: {$ref: '#/$defs/Id'}, factId: {$ref: '#/$defs/Id'}, claim: {$ref: '#/$defs/ExecutionClaim'},
        expectedJobRevision: {$ref: '#/$defs/Revision'}, inputHash: {$ref: '#/$defs/Hash'}, progress: {$ref: '#/$defs/Progress'}}, required: [context,
        jobId, factId, claim, expectedJobRevision, inputHash, progress], additionalProperties: false}
  AssistanceFailure: {type: object, properties: {context: {$ref: '#/$defs/CommandContext'}, jobId: {$ref: '#/$defs/Id'}, factId: {$ref: '#/$defs/Id'}, claim: {$ref: '#/$defs/ExecutionClaim'},
        expectedJobRevision: {$ref: '#/$defs/Revision'}, inputHash: {$ref: '#/$defs/Hash'}, error: {$ref: '#/$defs/Error'}, usageRecordId: {$ref: '#/$defs/Id'}},
      required: [context, jobId, factId, claim, expectedJobRevision, inputHash, error, usageRecordId], additionalProperties: false}
```

## C01 — Trusted host composition and coherent web context

```yaml contract
id: C01
title: Trusted host composition and coherent web context
owner:
- WebWorkspace
providers:
- U1
consumers:
- U2
- U3
- U4
- U5
- U6
- U8
mechanism: typed-module
requirements:
- FR1
- FR2
- FR3
- FR5
- FR6
- FR13
- FR14
- FR15
- FR16
- FR19
- FR19.2
operations:
- name: host.registerContribution
  input: HostRegisterInput
  output: HostManifestResult
  auth: Trusted application-composition authority; never a browser or ordinary administrator request.
  errors:
  - INVALID_INPUT
  - FORBIDDEN
  - CONFLICT
  - INCOMPATIBLE
  - POLICY_UNRESOLVED
  semantics: Compare manifest revision and schema digests before activation. Unknown/incompatible bindings and missing required participants keep
    the contribution unavailable; no domain data is written by registration.
  surface: internal
- name: host.inspectManifest
  input: HostInspectInput
  output: HostManifestResult
  auth: Trusted composition or authorized diagnostic caller.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read current registration evidence without activating features or implying journey readiness.
  surface: internal
- name: host.listCapabilities
  input: HostCapabilitiesInput
  output: HostCapabilitiesPage
  auth: Authorized diagnostic caller; any public projection is explicitly filtered by its separate access rule.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Paginate capability evidence and label unknown/stale observations. Missing modules cannot produce healthy defaults.
  surface: internal
- name: host.resolveNavigation
  input: HostNavigationInput
  output: HostNavigationResult
  auth: Validated session or anonymous context according to each registered route's verified access rule.
  errors:
  - INVALID_INPUT
  - FORBIDDEN
  - NOT_FOUND
  - INCOMPATIBLE
  - DEPENDENCY_UNAVAILABLE
  semantics: Return only permitted navigation. Owner changes invalidate prior private rendering state; navigation never submits work. Preserve
    authorized paper/query context without private drafts in URLs or telemetry.
  surface: browser
- name: host.recordObservation
  input: HostObservationInput
  output: Ack
  auth: Registered trusted producer with its own capability identity.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Admit only registered non-sensitive outcome codes and safe opaque correlation references; duplicate observation identity is reconciled.
    Observation failure never changes a domain job into success.
  surface: internal
invariants:
- U1's executable host starts without importing future unit implementations. Contributions have their own mounted integration assemblies; U8 supplies
  final composition, not another business-state owner.
- Principal, component identity and composition authority come from trusted transport/runtime bindings, never user-submitted context fields.
- The required contribution/capability/lifecycle manifests are finite trusted build inputs. Policy-dependent string/list limits must be loaded
  and enforced before allocation; unresolved bounds prevent activation.
- Shared UI retains Korean labels, approved colors/HIG web adaptations, responsive behavior, Light/Dark/System, focus and status semantics. This
  contract does not choose a frontend framework.
- Private drafts, tokens, manuscripts and secret provider data never enter observation fields, route templates, query return-context substitutes
  or other-account caches. A route being visible is never the sole authorization check.
- Schemas are producer-owned. Initial and complete implementations honor the same named contract or an explicitly negotiated revision; unknown
  authorization states are denied, not treated as ordinary additive fields.
checks:
- Reject incompatible schema digest, absent required contribution and absent lifecycle participant.
- Boot the U1 assembly with no future modules, then each real contribution assembly and U8's full assembly.
- Account switch/expiry clears private DOM, accessibility and transient cache state; valid search/paper return context remains coherent.
- A missing execution path is unavailable and a failed observation cannot fabricate success.
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C02 — Account access, consent and owner-acknowledged lifecycle

```yaml contract
id: C02
title: Account access, consent and owner-acknowledged lifecycle
owner:
- AccountAccess
providers:
- U1
- U2
consumers:
- U3
- U4
- U5
- U6
- U8
- 'External: public web'
mechanism: typed-module
requirements:
- FR6
- FR6.1
- FR6.2
- FR6.3
- FR6.4
- FR7
- FR7.1
- FR7.2
- FR8
- FR8.1
- FR10
- FR10.2
- FR11
- FR11.2
- FR12
- FR12.2
- FR14
- FR14.2
- FR16
- FR16.2
- FR17
- FR17.1
operations:
- name: access.inspectSession
  input: AccessSessionInput
  output: AccessSessionStatus
  auth: Anonymous or validated current session; no caller-selected account.
  errors:
  - INVALID_INPUT
  - DEPENDENCY_UNAVAILABLE
  semantics: Return only the current session's safe state. Invalid/revoked credentials do not create an account principal.
  surface: browser
- name: access.register
  input: AccessRegisterInput
  output: AccessChallengeDelivery
  auth: Public registration with abuse admission and configured input/data policy.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Durably reconcile one intended registration; duplicate/existing email responses are existence-neutral. Issue bound verification through
    the approved delivery path; never claim verification or public email delivery from local-sink success.
  surface: browser
- name: access.requestVerification
  input: AccessEmailRequestInput
  output: AccessChallengeDelivery
  auth: Public, abuse-limited request; existence-neutral outcome.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Request/reconcile permitted verification delivery without revealing whether another account exists.
  surface: browser
- name: access.verifyEmail
  input: AccessVerifyEmailInput
  output: Ack
  auth: Holder of valid unexpired single-use proof bound to the intended verification flow.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Verify the bound account only; stale, replayed or purpose-mismatched proof cannot change another identity.
  surface: browser
- name: access.login
  input: AccessLoginInput
  output: AccessLoginResult
  auth: Public credential verification with configured abuse policy.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Issue current principal only after verification and required MFA. Session cookie/token issuance travels through trusted transport
    Set-Cookie handling, never JSON token fields. Failures do not enumerate accounts.
  surface: browser
- name: access.logout
  input: AccessLogoutInput
  output: Ack
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Revoke the current session before acknowledging. Browser clearing alone is insufficient; replay cannot recover access. Protected
    retained data is not silently erased.
  surface: browser
- name: access.requestPasswordReset
  input: AccessEmailRequestInput
  output: AccessChallengeDelivery
  auth: Public, abuse-limited; existence-neutral response.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Deliver a purpose-bound recovery challenge only through the approved path; reveal no other account's existence or delivery state.
  surface: browser
- name: access.completePasswordReset
  input: AccessPasswordResetInput
  output: Ack
  auth: Valid unused purpose-bound recovery proof.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - UNKNOWN_OUTCOME
  semantics: Atomically reconcile password change, proof consumption and policy-defined session revocation; uncertain outcomes are read/reconciled,
    not blindly repeated.
  surface: browser
- name: access.changePassword
  input: AccessPasswordChangeInput
  output: Ack
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect. Required current
    credential/reauthentication proof.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - UNKNOWN_OUTCOME
  semantics: Preserve authoritative identity through failure; apply configured session revocation and never drop committed library/research work.
  surface: browser
- name: access.requestEmailChange
  input: AccessEmailChangeInput
  output: AccessChallengeDelivery
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect. Required reauthentication
    proof.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Bind intended old/new identity and delivery challenge; no identity switch before verified completion.
  surface: browser
- name: access.completeEmailChange
  input: AccessEmailChangeCompleteInput
  output: Ack
  auth: Valid purpose-bound email-change proof and the required current authority.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - UNKNOWN_OUTCOME
  semantics: Reconcile challenge consumption, intended identity update and revocation policy; collisions cannot bind a different account.
  surface: browser
- name: access.beginIdentityFlow
  input: AccessBeginIdentityInput
  output: AccessProviderRedirect
  auth: Public for sign-in; current authenticated owner for linking.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Generate allowlisted provider/callback state with purpose and owner binding; caller returnRouteId must resolve to a registered local
    route.
  surface: browser
- name: access.completeIdentityFlow
  input: AccessCompleteIdentityInput
  output: AccessIdentityResult
  auth: Trusted validated provider callback flow; linking additionally rechecks original owner.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - MFA_REQUIRED
  semantics: Validate callback state, issuer, audience, nonce/PKCE where applicable, purpose and single use before exchange/link. Collision or
    denied consent never silently creates a different owner. Credential material stays protected.
  surface: internal
- name: access.listIdentityLinks
  input: AccessIdentityListInput
  output: AccessIdentityPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: List only current owner's safe provider link state; tokens and secret handles are never returned.
  surface: browser
- name: access.unlinkIdentity
  input: AccessUnlinkIdentityInput
  output: Ack
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect. Required reauthentication.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Apply retained unlink/account-recovery policy and expected revision; do not invent a lockout bypass or remove other identities. Required
    top-level expectedRevision is the original observed control token; trusted mapping sets context.expectedRevision to the identical value and
    rejects disagreement. Current authorization then exact normalized-intent receipt replay precede fresh CAS. Missing, empty or null existing-state
    tokens reject; conflict uses an authorized fresh named read, never latestRevision in Error.details.
  surface: browser
- name: access.readOrcidProfile
  input: AccessOrcidProfileInput
  output: AccessOrcidProfile
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Read permitted linked profile with provenance/coverage. Unavailable profile is optional enrichment, not permission to block account/core
    paper use.
  surface: browser
- name: access.beginMfaEnrollment
  input: AccessMfaEnrollmentInput
  output: AccessMfaEnrollment
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect. Currently verified
    administrator enrollment authority and reauthentication.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - MFA_REQUIRED
  semantics: Create a bounded single-use enrollment. Seed/recovery material is delivered by a separately protected one-time channel, not this
    ordinary result schema.
  surface: admin
- name: access.retrieveMfaEnrollmentMaterial
  input: AccessMfaMaterialInput
  output: AccessMfaMaterial
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect. Bound enrollment
    owner, current administrator enrollment authority, valid current reauthentication proof and unused delivery reference.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - MFA_REQUIRED
  - UNKNOWN_OUTCOME
  semantics: 'Consume the delivery reference exactly once and return the typed secret material only through the dedicated protected response.
    Set Cache-Control: no-store; exclude request/response secrets from logs, traces, generic idempotency/result caches, service-worker caches
    and persisted browser storage. Render QR locally; clear transient material on exit, expiry, logout or account switch. Lost response never
    permits replay of secret material: return EXPIRED on repeated retrieval and require a replacement enrollment, invalidating prior seed/codes
    before activation. Confirmation alone activates the bound verified enrollment.'
  surface: admin
- name: access.confirmMfaEnrollment
  input: AccessMfaConfirmInput
  output: Ack
  auth: Bound enrollment owner with verified primary authentication and valid new factor proof.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Complete enrollment only after factor verification; interrupted enrollment cannot grant administrator access.
  surface: admin
- name: access.verifyMfa
  input: AccessMfaVerifyInput
  output: AccessLoginResult
  auth: Valid protected primary-authentication continuation and second-factor proof; an active full session is not required and anonymous context
    is permitted.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - MFA_REQUIRED
  semantics: Login/provider sign-in issues the primary-authentication continuation via protected trusted cookie transport, never as a full session
    or browser-asserted principal. Validate that cookie against the challengeId/flowBinding, server-owned primary-authentication success, intended
    account and current revocation state before checking the factor. Reject expired/replayed factors; only then issue the full session through
    trusted Set-Cookie transport for the existing role. Missing continuation cannot be replaced with caller account/context claims.
  surface: browser
- name: access.recoverMfa
  input: AccessMfaRecoveryInput
  output: Ack
  auth: Configured controlled administrator recovery authority/proof; no production bypass.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - MFA_REQUIRED
  semantics: Require the approved recovery policy and auditable proof; if the procedure is unresolved, deny with POLICY_UNRESOLVED rather than
    disabling MFA.
  surface: admin
- name: access.readProfile
  input: AccessProfileInput
  output: AccessProfile
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read owner profile and retained mutable-field vocabulary; email/roles/identity cannot be patched through generic profile fields.
  surface: browser
- name: access.updateProfile
  input: AccessProfileUpdateInput
  output: AccessProfile
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Require expected revision and current field vocabulary. Reject duplicate/unknown/read-only fields and value-kind violations. Preserve
    committed values on failed/conflicting writes. Required top-level expectedRevision is the original observed control token; trusted mapping
    sets context.expectedRevision to the identical value and rejects disagreement. Current authorization then exact normalized-intent receipt
    replay precede fresh CAS. Missing, empty or null existing-state tokens reject; conflict uses an authorized fresh named read, never latestRevision
    in Error.details.
  surface: browser
- name: access.listConsents
  input: AccessConsentListInput
  output: AccessConsentPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read authoritative consent decisions by registered purpose with their policy/revision.
  surface: browser
- name: access.updateConsent
  input: AccessConsentUpdateInput
  output: AccessConsentRecord
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Persist one intended purpose decision and revision. Current revocation controls future effects even while participant cleanup is
    incomplete; never report revoked before durable acknowledgement.
  surface: browser
- name: access.evaluateAuthority
  input: AccessAuthorityInput
  output: AccessAuthorityDecision
  auth: Registered trusted component; verify producer identity separately from context and recheck the affected owner's current authority.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Evaluate current session/account/role/MFA/owner/purpose policy. A decision is a checked revision, not an indefinitely valid bearer
    grant; effect/read boundaries must recheck or enforce a version guard.
  surface: internal
- name: lifecycle.configureManifest
  input: LifecycleManifestInput
  output: Ack
  auth: Trusted application-composition authority, not browser/admin payload privilege.
  errors:
  - INVALID_INPUT
  - FORBIDDEN
  - CONFLICT
  - INCOMPATIBLE
  - POLICY_UNRESOLVED
  semantics: Register complete required owners and scope obligations before their data can persist; reject duplicates, missing participants, incompatible
    contracts or unresolved policy.
  surface: internal
- name: lifecycle.request
  input: LifecycleRequestInput
  output: LifecycleRequest
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect. Required recent
    reauthentication and explicit action/scope confirmation.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - MFA_REQUIRED
  - UNKNOWN_OUTCOME
  semantics: Accept only an action permitted by the current approved retention/reactivation/erasure policy. If policy, participant or restore/derived-data
    obligations are unresolved, fail closed; revocation and cleanup completion remain distinct.
  surface: browser
- name: access.prepareLifecycle
  input: AccessLifecyclePrepareInput
  output: AccessLifecycleConfirmation
  auth: Current authenticated owner with recent reauthentication; derive owner from the protected full session.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, CONFLICT, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE]
  semantics: Verify current proof and exact lifecycle revision, then persist a finite one-use confirmation bound to owner, session authority, action, revision and policy. Ordinary output contains no credential or factor secret. Matching command replay returns the original reference without extending expiry. lifecycle.request consumes only this authoritative reference; a caller-invented reference never authorizes withdrawal or erasure.
  surface: browser
- name: access.requestReactivation
  input: AccessEmailRequestInput
  output: AccessChallengeDelivery
  auth: Public pre-authentication request under current abuse and reactivation-delivery policy; no active session or caller account authority.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  semantics: Return the same existence-neutral acknowledgement for unknown, active, withdrawn or erased accounts. For an eligible withdrawn account
    only, deliver a single-use proof bound to that account, withdrawn lifecycle revision, reactivation purpose, flow and current policy through
    the approved verified recovery path. Do not reveal eligibility or delivery state and do not issue a full session. Unresolved policy cannot
    authorize delivery or recovery.
  surface: browser
- name: lifecycle.reactivate
  input: LifecycleReactivationInput
  output: LifecycleReactivationResult
  auth: Valid unused purpose-bound reactivation proof and bound scope confirmation; no active full session is required. Resolve the account from
    the proof, never from caller principal or account identifiers.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - RATE_LIMITED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - EXPIRED
  - MFA_REQUIRED
  - UNKNOWN_OUTCOME
  semantics: Atomically reconcile proof consumption and one reactivation request against the current withdrawn-account authority, policy and participant
    manifest. Apply policy-required additional verification before restoration. Reject erased, superseded, expired, purpose-mismatched or ineligible
    states. Restore only demonstrably retained permissible data; never recreate erased records or reverse erasure tombstones. A lost-response
    retry may return only the same safe recorded result under the same validated bound flow/idempotency identity, not repeat effects or grant
    broad access. Trusted transport can issue a limited protected recovery cookie for lifecycle.inspect of this request only; completion requires
    normal sign-in and any required MFA before a full session.
  surface: browser
- name: lifecycle.inspect
  input: LifecycleStatusInput
  output: LifecycleRequest
  auth: Current owner or separately authorized lifecycle auditor; withdrawn-account recovery uses only the configured bound recovery authority.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Return honest participant/scope progress. Do not infer complete erasure from account status or message delivery; hide private operational
    evidence from unauthorized callers.
  surface: browser
- name: lifecycle.listPendingWork
  input: LifecyclePendingInput
  output: LifecycleWorkPage
  auth: Registered trusted participant identity; participantId must match runtime capability.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read only that participant's current required work. Poll/event delivery choice is open; recoverable redelivery does not transfer
    data ownership.
  surface: internal
- name: lifecycle.acknowledge
  input: LifecycleAcknowledgeInput
  output: LifecycleRequest
  auth: Registered participant acting only on its own required scopes.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Validate ticket, policy/manifest/request revision and evidence. Reject conflicting/stale acknowledgements; duplicate same evidence
    is safe. Complete only when every current required scope has policy-valid evidence, including restore/backup dispositions.
  surface: internal
- name: lifecycle.evaluateRestore
  input: LifecycleRestoreInput
  output: LifecycleRestoreDecision
  auth: Separately authorized restoration executor and registered participant; never a browser restore bypass.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Compare current authority/tombstones and approved restore policy against snapshot records. Deny revival of erased/prohibited data;
    policy uncertainty blocks restoration. Any allow decision requires a current version guard at actual restore.
  surface: internal
invariants:
- U1 seeds safe initial account contracts; U2 completes the same AccountAccess authority. No second account/session/consent store or shared cross-owner
  writer is created.
- Read and effect authorization uses current authority and owner context. UserId headers, submitted Principal objects and stale consent snapshots
  are not authority.
- Local C02 authority guard participates in the caller's owner transaction through the trusted OwnerTransactions/guard seam. AccountAccess owns its SECURITY DEFINER guard functions and exposes no writer. Hold shared account/session/current consent locks until owner commit; revocation takes the competing exclusive lock. Lock order is authority, owner control, receipt/admission, sorted child keys. Full-session, primary-MFA and reactivation-status purposes are distinct. Administrator operations additionally require current role and nonexpired completed MFA. Separate-owner commits reauthorize independently; a prior guard is not transferable authority. Retry a serialization rollback only with unchanged command identity within finite deadline; commit transport loss remains UNKNOWN_OUTCOME.
- Passwords, proof tokens, factor seeds, provider codes and session credentials are excluded from normal logs, errors and ordinary public output
  DTOs. The explicit single-use AccessMfaMaterial protected response is the only enrollment seed/recovery-code output; no-store, local-only QR
  rendering, client clearing and runtime redaction are mandatory. Secret schema annotations alone do not enforce any of these rules.
- Account-existence privacy applies to public registration/recovery acknowledgements and error mapping; internal resource identifiers must not
  be reflected for another account.
- Identity-provider and MFA callbacks bind purpose, intended owner, current flow and use disposition. Safe return routes are registry identifiers,
  never caller-controlled redirect URLs.
- Primary-authentication and reactivation recovery cookies are limited purpose-bound transport credentials, not full account sessions. Their server-verified
  invocation cannot be synthesized from an anonymous principal's body fields. MFA verification and withdrawn-account recovery must remain reachable
  without an active full session.
- Mutable profile fields are finite retained vocabulary entries; value kinds, limits and clear/null behavior are validated under the vocabulary
  revision. This is not arbitrary account-field assignment or new profile feature scope.
- The policy references must resolve to explicit approved rules before relevant changes. No retention duration, automatic erasure, resurrection,
  draft-storage rule, abuse threshold or public-service capacity is selected by these schemas.
- Lifecycle participant acknowledgements prove only their declared scope. Complete requires all required current participants, owned/derived/pending/cache
  and backup/restore dispositions; stale events and restored snapshots cannot recreate erased or prohibited data.
- An accepted lifecycle action records policy and manifest revisions. Changes during execution require reconciliation; reactivation can restore
  only data lawfully and technically retained, never erased data.
- Anonymous session inspection and verified guest search are retained; this contract does not grant anonymous private work or unverified additional
  public capability.
checks:
- Registration/verification/login/logout, lost response and email-delivery failure against real host boundaries with synthetic accounts.
- Cross-owner/session replay, OAuth state/collision/denial, MFA expiry/replay and controlled recovery denial when policy is unresolved.
- A primary-authenticated MFA continuation succeeds without a full session, while absent/mismatched continuation and another account's challenge
  fail; no administrator role is created by factor verification.
- Retrieve enrollment seed/local-QR payload and recovery codes exactly once with current reauthentication; verify no-store/redaction/client clearing,
  reject retrieval replay and invalidate replaced enrollment material after response loss.
- Withdrawn-account recovery accepts the bound reactivation proof without an active session; active/erased/unknown accounts remain existence-neutral
  at request, stale/purpose-mismatched proof fails, and erased data never returns. Completion still requires sign-in/MFA.
- Password/email changes reconcile interrupted writes and preserve acknowledged saved work.
- Reject profile role/email mutation through unknown fields and contradictory/duplicate field patches.
- Lifecycle request with missing participant/policy fails closed; lost/duplicate/stale ack never fabricates completion.
- Queued effect after consent revocation and restore after deletion cannot resurrect prohibited owner work.
version: 3.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C03 — Personal library, controlled personalization and consistent entitlements

```yaml contract
id: C03
title: Personal library, controlled personalization and consistent entitlements
owner:
- Library
- Personalization
- UsageEntitlements
providers:
- U1
- U2
consumers:
- U3
- U4
- U8
- 'External: public web'
mechanism: typed-module
requirements:
- FR5
- FR5.1
- FR5.2
- FR5.3
- FR8
- FR8.2
- FR9
- FR9.1
- FR10
- FR10.1
- FR10.2
- FR11
- FR11.1
- FR11.2
- FR17
- FR17.1
- FR17.2
operations:
- name: library.savePaper
  input: LibrarySavePaperInput
  output: LibrarySavedPaper
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Resolve the intended eligible public paper/version through its owner. Repeated intended saves reconcile one record; do not trust
    caller-supplied metadata or silently redirect identity.
  surface: browser
- name: library.readSavedPaper
  input: LibrarySavedPaperInput
  output: LibrarySavedPaper
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Preserve original saved identity and report current source/canonical disposition; read cannot substitute unrelated content.
  surface: browser
- name: library.listSavedPapers
  input: LibraryPaperListInput
  output: LibraryPaperPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read a stable owner-bound page; unavailable storage is an error, never a successful empty list.
  surface: browser
- name: library.removeSavedPaper
  input: LibraryRemoveSavedPaperInput
  output: Ack
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Remove only the acknowledged owner's saved reference using expected revision/idempotency; never remove public corpus content. Required
    top-level expectedRevision is the original observed control token; trusted mapping sets context.expectedRevision to the identical value and
    rejects disagreement. Current authorization then exact normalized-intent receipt replay precede fresh CAS. Missing, empty or null existing-state
    tokens reject; conflict uses an authorized fresh named read, never latestRevision in Error.details.
  surface: browser
- name: library.saveSearch
  input: LibrarySaveSearchInput
  output: LibrarySavedSearch
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Persist canonical query/refinement context under the declared retained vocabulary; duplicate intended saves reconcile without losing
    prior committed values.
  surface: browser
- name: library.readSavedSearch
  input: LibrarySavedSearchInput
  output: LibrarySavedSearch
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Return exact saved query context for a separate explicit Discovery rerun. Reading does not run a new query or add history.
  surface: browser
- name: library.listSavedSearches
  input: LibrarySearchListInput
  output: LibrarySearchPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Paginate confirmed records and stable ordering; errors and changed snapshots remain distinct.
  surface: browser
- name: library.removeSavedSearch
  input: LibraryRemoveSavedSearchInput
  output: Ack
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Remove the intended saved query only; history and saved papers are separate owners' records within Library. Required top-level expectedRevision
    is the original observed control token; trusted mapping sets context.expectedRevision to the identical value and rejects disagreement. Current
    authorization then exact normalized-intent receipt replay precede fresh CAS. Missing, empty or null existing-state tokens reject; conflict
    uses an authorized fresh named read, never latestRevision in Error.details.
  surface: browser
- name: library.listHistory
  input: LibraryHistoryListInput
  output: LibraryHistoryPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: List only qualifying recorded owner searches above the current clear boundary; expired or changed page snapshots are explicit. Return
    non-null clearBoundary even for virtual empty history, without allocating a row; page.snapshotRevision and Discovery admission cutoff are
    different values.
  surface: browser
- name: library.readHistory
  input: LibraryHistoryInput
  output: LibraryHistoryRecord
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read the historical submitted context for an explicit Discovery rerun. Cleared/deleted records cannot reappear through direct IDs.
  surface: browser
- name: library.recordSearchCompletion
  input: LibraryHistoryFactInput
  output: LibraryHistoryFactResult
  auth: Trusted Discovery fact producer with validated owner and fact identity; never a browser-writable history API.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Check the current lifecycle/clear boundary and deduplicate by execution/fact identity. A fact whose admissionSequence is at or below
    the captured clear cutoff is suppressed even if completionSequence is later; current consent/history policy also applies.
  surface: internal
- name: library.clearHistory
  input: LibraryClearHistoryInput
  output: LibraryClearHistoryResult
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Capture current owner's SearchHistoryCheckpoint from Discovery through the declared U1 interface, then durably record the clear boundary
    and clear included records. Never accept a browser-supplied cutoff. Lost acknowledgement reconciles the same boundary; a failed checkpoint/write
    cannot claim successful clear. Required top-level expectedRevision is the original observed control token; trusted mapping sets context.expectedRevision
    to the identical value and rejects disagreement. Current authorization then exact normalized-intent receipt replay precede fresh CAS. Missing,
    empty or null existing-state tokens reject; conflict uses an authorized fresh named read, never latestRevision in Error.details. Compare the
    supplied clearBoundary control token and capture Discovery cutoff on the server. Atomically advance boundary/receipt; delayed facts at or
    before cutoff remain suppressed.
  surface: browser
- name: settings.read
  input: SettingsReadInput
  output: SettingsSnapshot
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read explicit settings and onboarding state; a missing derived profile cannot erase explicit preferences.
  surface: browser
- name: settings.update
  input: SettingsUpdateInput
  output: SettingsSnapshot
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Require at least one settings change and expected revision; resolve all choices in retained vocabularies and preserve committed values
    on conflict/failure. Required top-level expectedRevision is the original observed control token; trusted mapping sets context.expectedRevision
    to the identical value and rejects disagreement. Current authorization then exact normalized-intent receipt replay precede fresh CAS. Missing,
    empty or null existing-state tokens reject; conflict uses an authorized fresh named read, never latestRevision in Error.details. settings.read
    supplies the shared SettingsSnapshot control revision; each change advances it. Reset also advances a distinct inputBoundary; current consent
    is independent.
  surface: browser
- name: settings.updateOnboarding
  input: SettingsOnboardingInput
  output: SettingsSnapshot
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Persist selection/progress/complete/skip explicitly and idempotently; skip does not overwrite established preferences, and resume
    does not create redirect loops. Required top-level expectedRevision is the original observed control token; trusted mapping sets context.expectedRevision
    to the identical value and rejects disagreement. Current authorization then exact normalized-intent receipt replay precede fresh CAS. Missing,
    empty or null existing-state tokens reject; conflict uses an authorized fresh named read, never latestRevision in Error.details. settings.read
    supplies the shared SettingsSnapshot control revision; each change advances it. Reset also advances a distinct inputBoundary; current consent
    is independent.
  surface: browser
- name: settings.listSuggestions
  input: SettingsSuggestionInput
  output: SettingsSuggestionPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Use only permitted linked ORCID data and declare source/coverage. Provider absence permits retained manual selection/skip, not an
    account gate.
  surface: browser
- name: settings.listRecentPapers
  input: SettingsRecentInput
  output: SettingsRecentPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Use permitted activity and current corpus eligibility with truthful ordering/dispositions; no activity or enrichment is a disclosed
    empty/cold-start outcome.
  surface: browser
- name: settings.recordBehavior
  input: SettingsBehaviorInput
  output: SettingsBehaviorResult
  auth: Registered trusted component; verify producer identity separately from context and recheck the affected owner's current authority.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Recheck consent and authority, require matching current input/reset boundary and deduplicate eventId. Stale events cannot recreate
    deleted/opted-out behavior or profiles.
  surface: internal
- name: settings.readProjection
  input: SettingsProjectionInput
  output: SettingsProfileProjection
  auth: Registered trusted component; verify producer identity separately from context and recheck the affected owner's current authority.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Return only the authorized purpose-specific projection and input boundary. Disabled/unavailable/cold-start is explicit; consumers
    must use their documented safe behavior.
  surface: internal
- name: settings.prepareReset
  input: SettingsResetPrepareInput
  output: SettingsResetConfirmation
  auth: Current full-session owner with reauthentication; no administrator shortcut.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, CONFLICT, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE]
  semantics: Verify current proof and persist a finite confirmation bound to owner, session authority, exact reset action, observed settings revision and policy. Matching command replay returns the original reference without extending expiry. Reset acceptance consumes this reference atomically with the settings boundary and receipt; a forged reference cannot authorize cleanup.
  surface: browser
- name: settings.reset
  input: SettingsResetInput
  output: SettingsResetResult
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect. Explicit scope
    confirmation and resolved deletion policy.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Advance the input boundary before accepting later events and reconcile policy-defined event/profile removal. Never delete Library
    work. Pending derived/restore disposition is not complete reset. Required top-level expectedRevision is the original observed control token;
    trusted mapping sets context.expectedRevision to the identical value and rejects disagreement. Current authorization then exact normalized-intent
    receipt replay precede fresh CAS. Missing, empty or null existing-state tokens reject; conflict uses an authorized fresh named read, never
    latestRevision in Error.details. settings.read supplies the shared SettingsSnapshot control revision; each change advances it. Reset also
    advances a distinct inputBoundary; current consent is independent.
  surface: browser
- name: settings.listResets
  input: SettingsResetListInput
  output: SettingsResetPage
  auth: Current full-session owner only; no app-admin shortcut, browser owner field or mutation key.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, CONFLICT, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE]
  semantics: Read only. Order acceptedAt/resetId descending. Cursor binds owner, current authority generation, view, last/high-water tuples, policy and expiry. Reapply current disposition filtering; outstanding includes all pending/blocked responsibilities irrespective of age and history includes retained complete responsibilities. A page is a traversal bound, not a frozen status snapshot. Expired cursor requires refresh; unavailable never means empty. No allocation, boundary change, worker claim or settlement is allowed. Outstanding obligations and suppression evidence cannot expire; completed history requires an explicit permitted retention policy.
  surface: browser
- name: settings.inspectReset
  input: SettingsResetInspectInput
  output: SettingsResetStatus
  auth: Current full-session owner; foreign and absent IDs have the same safe NOT_FOUND result.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, NOT_FOUND, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE]
  semantics: Read only. Acceptance fields remain immutable; statusRevision is a per-reset monotonic decimal-string revision. Return every required scope from the accepted finite manifest, never a truncated subset. Complete requires current matching evidence for every scope. Missing/stale evidence is pending or blocked. Evidence invalidation reopens the same responsibility with increased statusRevision. UI rejects earlier revisions within the same reset and former owner generation; never compares unrelated settings revisions. Reads cannot create work, claim leases or advance the input boundary.
  surface: browser
- name: admission.allocate
  input: AdmissionAllocateInput
  output: AdmissionIntent
  auth: Registered accepting owner only, current account authority and trusted operation identity/quantity/policy.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, CONFLICT, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE, UNKNOWN_OUTCOME]
  semantics: Before reserve, durably allocate one open intent under accepting-owner storage. Same owner/operation/generation/digest replays original state; changed identity conflicts. Closed identity never reopens. This is a protocol implemented by each registered accepting owner, not Usage ownership of their work.
  surface: internal
- name: admission.inspect
  input: AdmissionInspectInput
  output: AdmissionIntent
  auth: Registered accepting owner or specifically registered Usage reconciliation port; current purpose-limited authority.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, NOT_FOUND, CONFLICT, DEPENDENCY_UNAVAILABLE]
  semantics: Read original intent without mutation. Missing row, timeout or open observation is never proof authorizing reservation release.
  surface: internal
- name: admission.accept
  input: AdmissionAcceptInput
  output: AdmissionIntent
  auth: Registered accepting owner only with current effect authority and matching authoritative reservation.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, CONFLICT, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE, UNKNOWN_OUTCOME]
  semantics: Under authority then admission-row lock, atomically open-to-accepted with effect/responsibility, reservation reference and immutable receipt. Validate reservation account/operation/generation/digest/period/quantity/policy. No effect before this commit. Same accepted request replays; closed forbids delayed acceptance. No remote call inside the locked transaction.
  surface: internal
- name: admission.close
  input: AdmissionCloseInput
  output: AdmissionClosedEvidence
  auth: Registered accepting owner only; independently authorized reconciliation purpose and exact original identity.
  errors: [INVALID_INPUT, UNAUTHENTICATED, FORBIDDEN, NOT_FOUND, CONFLICT, POLICY_UNRESOLVED, DEPENDENCY_UNAVAILABLE, UNKNOWN_OUTCOME]
  semantics: Atomically compete with accept on the same owner admission row. Open-to-terminal-closed records immutable identity/revision/reason/time/evidence. Matching closed replay returns the original proof; accepted cannot close for nonacceptance. Usage obtains and verifies the proof through the trusted owner port before releasing exactly its original reservation. A client JSON proof, negative lookup, timeout, lease expiry or log is never sufficient. Retain terminal fences while delayed work or restore could occur. Refund after acceptance is a separate expressly permitted transition.
  surface: internal
- name: settings.applyConsentBoundary
  input: SettingsConsentBoundaryInput
  output: SettingsBehaviorResult
  auth: Trusted AccountAccess fact/participant contract; verify current consent from its owner.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Apply the confirmed consent revision to Personalization's own processing boundary. This operation cannot write authoritative consent;
    user opt-out is access.updateConsent, and failed projection cleanup never re-enables revoked processing.
  surface: internal
- name: usage.inspect
  input: UsageInspectInput
  output: UsageMeasurePage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Return known balances with explicit period/policy or unknown measures. Unknown never becomes zero and a display cache cannot authorize
    resource use.
  surface: browser
- name: usage.readPlan
  input: UsagePlanInput
  output: UsagePlanPresentation
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Present retained mock/administrative assignment truthfully; never claim payment or an automatically purchased resource.
  surface: browser
- name: usage.grantEntitlement
  input: UsageGrantInput
  output: UsageEntitlement
  auth: Current authorized application administrator with required MFA; target account is independently checked.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - MFA_REQUIRED
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Assign only configured retained tiers under $0 policy, record actor/target/reason and expected revision, and reconcile duplicate
    grant. Browser role/tier claims cannot self-authorize. Required top-level expectedRevision is the original observed control token; trusted
    mapping sets context.expectedRevision to the identical value and rejects disagreement. Current authorization then exact normalized-intent
    receipt replay precede fresh CAS. Missing, empty or null existing-state tokens reject; conflict uses an authorized fresh named read, never
    latestRevision in Error.details.
  surface: admin
- name: usage.revokeEntitlement
  input: UsageRevokeInput
  output: UsageEntitlement
  auth: Current authorized application administrator with required MFA.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - MFA_REQUIRED
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Revoke the intended assignment with audit and policy-defined effects on accepted work. Do not silently cancel acknowledged operations
    or activate a different paid tier. Required top-level expectedRevision is the original observed control token; trusted mapping sets context.expectedRevision
    to the identical value and rejects disagreement. Current authorization then exact normalized-intent receipt replay precede fresh CAS. Missing,
    empty or null existing-state tokens reject; conflict uses an authorized fresh named read, never latestRevision in Error.details.
  surface: admin
- name: usage.reserve
  input: UsageReserveInput
  output: UsageRecord
  auth: Trusted accepting operation owner acting for the current authenticated account; resource quantities are server-derived.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - QUOTA_EXCEEDED
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Atomically admit/reserve against current entitlement and server-derived period. Same owner/operation/input identity returns the same
    record; different fingerprint with reused idempotency key is CONFLICT. Unknown balance/policy fails closed before new work is accepted.
  surface: internal
- name: usage.settle
  input: UsageSettleInput
  output: UsageRecord
  auth: The trusted operation owner bound to the existing reservation and its current execution evidence.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Reconcile one commit/release/refund with expected revision, operation identity and policy. Concurrent retries cannot double-debit/refund.
    Actual quantities and release of uncertain work require resolved policy; no automatic refund/reset/release semantics are invented.
  surface: internal
- name: usage.reconcile
  input: UsageReconcileInput
  output: UsageRecord
  auth: Trusted operation owner or explicitly authorized diagnostic caller for the same account/effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read recorded accounting for the original operation, including unknown disposition; never reserve or debit anew as a read side effect.
  surface: internal
- name: usage.listRecords
  input: UsageRecordsInput
  output: UsageRecordsPage
  auth: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read only the current owner's bounded accounting evidence; operator-wide inspection requires a separate explicit administrative projection.
  surface: browser
- name: personalControls.applyLifecycle
  input: LifecycleApplyInput
  output: LifecycleParticipantDisposition
  auth: Trusted registered Library, Personalization or UsageEntitlements participant, restricted to its own component ticket.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Apply only current policy/manifest/request work to the component's own data and derived/restore scopes; reject stale tickets, prevent
    late resurrection and return scoped evidence for lifecycle.acknowledge. One component cannot acknowledge another's records.
  surface: internal
- name: usage.readAssignment
  input: UsageAssignmentRead
  output: UsageAssignmentSnapshot
  auth: Current administrator and required MFA; target account scope independently validated.
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - INCOMPATIBLE
  semantics: Administrator with current MFA reads the target assignment control revision. Absent assignment returns a non-null owner-defined initial
    token and null entitlement without allocating state. Grant CAS compares this token; revoke compares the current entitlement revision; both
    advance the same assignment control boundary. No ordinary self-plan lookup substitutes for this read.
  surface: admin
invariants:
- Library owns saved references/history, Personalization owns explicit settings/permitted projections, and UsageEntitlements owns balances. A
  single C03 bundle does not permit cross-owner data writes.
- Commands require current owner and expectedRevision where modifying an existing revision. Durable acknowledgement is the only successful write
  signal; same intended effect is reconciled after lost response.
- LibraryQueryContext is shared with Discovery; its vocabulary revision defines permitted retained modes/orders/filter operators/value kinds.
  Unsupported values fail rather than reaching provider query syntax unchecked.
- Search-history clear linearizes at the server-captured admission checkpoint. The durable clear boundary suppresses facts admitted at/before
  it, including queries finishing later; facts genuinely admitted after it may appear. A failed checkpoint cannot be treated as an empty history.
- Behavior reset/erasure advances an authoritative input boundary; producer events from prior generations cannot rebuild erased projections. Consent
  authority remains AccountAccess and is checked at processing, not merely when an event was emitted.
- Array sizes and user text bounds resolve through an approved policy or PageRequest.limit and are checked before work allocation. Pagination
  is owner/snapshot bound. Schema annotations alone do not enforce these dynamic bounds; unresolved admission policy returns POLICY_UNRESOLVED.
- Quota allocation, period/reset, refund/release rules and protected-action membership must be explicitly configured from approved evidence before
  enforcement. Times are server-derived; a period transition does not lose reconciliation for an earlier accepted operation.
- Reservation and operation acceptance coordinate by stable operation/input references, not an assumed cross-store atomic transaction. Capacity/accounting
  uncertainty blocks new acceptance until reconciled; accepted work keeps recoverable ownership.
- No tier or reset may activate paid resources. Public inputs never choose administrator authority, reserved quantities, history cutoffs or consent
  snapshots as facts.
- U2's bounded contribution can be verified against the initial contracts before U3's full corpus writer exists. Full saved-reference/corpus/lifecycle
  acceptance still requires real combined U3/U8 evidence; this contract adds no reverse construction dependency.
checks:
- Save/list/remove/revisit papers and queries across restart, failed writes, duplicate submission, two tabs and cross-owner attempts.
- Search admitted before history clear but completed/delivered after it never recreates a history row; newer admitted work is not erased by retrying
  the old clear.
- Canonical/withdrawn source produces explicit saved-reference disposition without unrelated redirection or deletion.
- Profile reset/opt-out followed by delayed events cannot recreate forbidden projections, while explicit library records remain.
- Onboarding select/skip/resume and ORCID failure remain usable; explicit defaults affect the real next action.
- Concurrent reserve, duplicate settle, unknown usage, grant/revoke and period rollover reconcile one intended effect without free/zero assumptions.
- Library, Personalization and UsageEntitlements each acknowledge only their own lifecycle scopes; unresolved backup/restore scope remains incomplete.
version: 3.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C04 — Canonical corpus, eligible content and projection publication

```yaml contract
id: C04
title: Canonical corpus, eligible content and projection publication
owner:
- CorpusContent
providers:
- U1
- U3
consumers:
- U1
- U2
- U3
- U4
- U8
mechanism: durable-command-fact
requirements:
- FR1
- FR1.1
- FR1.2
- FR2
- FR2.1
- FR2.2
- FR5
- FR5.3
- FR9
- FR9.1
- FR18
- FR18.1
- FR18.2
- FR18.3
operations:
- name: resolvePaper
  input: CorpusResolve
  output: CorpusIdentity
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Resolve exact canonical identity/version for metadata/headers; never substitute an unrelated paper for an obsolete identifier. Guest
    search receives metadata only through its separately authorized search response.
  surface: browser
- name: readContent
  input: CorpusRead
  output: CorpusContentRead
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SOURCE_INELIGIBLE
  semantics: Current eligibility and purpose permission dominate cached/indexed representations. Reading cannot start ingestion or model work.
  surface: browser
- name: readAsset
  input: CorpusAssetRead
  output: CorpusAsset
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SOURCE_INELIGIBLE
  semantics: Opaque readHandle is resolved only by an authorized delivery adapter; never accept arbitrary paths, URLs or private-attachment identifiers.
  surface: browser
- name: acceptCorpusRun
  input: CorpusRunRequest
  output: JobReceipt
  auth: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - IDEMPOTENCY_CONFLICT
  - CAPACITY_EXHAUSTED
  semantics: Durably record input snapshot and recoverable dispatch responsibility before acknowledgement; same idempotency key+input returns
    same run.
  surface: admin
- name: readCorpusRun
  input: CorpusRunRead
  output: CorpusRun
  auth: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Expose committed watermark and individual object/control/index outcomes; unknown effects cannot count as completed.
  surface: admin
- name: retryCorpusRun
  input: CorpusRunRead
  output: JobReceipt
  auth: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - OUTCOME_UNKNOWN
  semantics: Retry only reconciled retryable stages of the original intended run; retain committed stages and original authoritative inputs.
  surface: admin
- name: writeProjectionBatch
  input: CorpusProjectionBatch
  output: Ack
  auth: CorpusContent-owned writer with run/generation-scoped authority.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - IDEMPOTENCY_CONFLICT
  - SOURCE_INELIGIBLE
  - INCOMPATIBLE_VERSION
  semantics: Only CorpusContent writes derived projection batches; duplicate batchId+hash acknowledges once, changed hash conflicts.
  surface: internal
- name: publishProjectionGeneration
  input: CorpusPublicationRequest
  output: CorpusPublication
  auth: CorpusContent-owned publisher with current run authority.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - INCOMPATIBLE_VERSION
  - SOURCE_INELIGIBLE
  semantics: CAS published generation only after manifest completeness, all batch receipts, current source eligibility and compatibility verification.
    Failure preserves old publication and does not advance watermark.
  surface: internal
- name: readPublishedProjection
  input: CorpusProjectionRead
  output: CorpusPublication
  auth: Trusted Discovery reader; read-only projection access.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - INCOMPATIBLE_VERSION
  semantics: Return only a complete compatible publication; Discovery cannot write/rebuild/publish or treat its stale generation as eligibility
    authority.
  surface: internal
- name: changeSourceEligibility
  input: CorpusEligibilityChange
  output: Ack
  auth: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  semantics: Persist authoritative eligibility revision and recoverable source-change fact; reads enforce it immediately even before projection/cache
    repair.
  surface: admin
- name: readSourceChanges
  input: CorpusChangeRead
  output: CorpusChangePage
  auth: Trusted owner-domain consumer with declared source scope.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Ordered replayable facts; duplicate delivery is harmless. Facts inform saved-reference dispositions and reconciliation without granting
    direct cross-owner writes.
  surface: internal
invariants:
- 'R-01: CorpusContent is the sole logical projection writer and publication/rebuild completion authority; storage adapters act only under that
  owner. Discovery holds no writer capability.'
- U1 implements a permitted fixture generation; U3 completes every retained source/rebuild behavior with the same owner and contracts. No future
  U3 import is needed by U1.
- A publication is not a source-of-truth backup. Rebuild identifies authoritative inputs and verifies durable control/content/index receipts;
  no successful watermark for a partial run.
- Policy resolution is compulsory before source copying, storage, parsing, embedding or use. Unresolved permissions/capacity/continuity return
  POLICY_UNRESOLVED for affected effects.
- Withdrawal and permission changes are checked at every content/asset/model boundary. Delayed projection generations cannot restore prohibited
  content. Restore must replay current withdrawal boundaries before serving.
checks:
- Inject interruption at control/object/projection/publication writes; verify no false completion/watermark.
- 'Property: duplicate/reordered batches preserve canonical identity and one published generation; CAS rejects competing publication.'
- 'Property: withdrawal wins over stale cache/index/restore; Discovery cannot invoke projection mutations.'
state_machines:
- name: CorpusPublication
  initial: building
  transitions:
    building:
    - verified
    - failed
    verified:
    - published
    - failed
    published: []
    failed: []
  authority: CorpusContent
  rule: A new generation is distinct from the currently published generation; only complete verified manifests publish under CAS. Eligibility
    revocation remains independently authoritative.
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C05 — Discovery, citations and completed-search facts

```yaml contract
id: C05
title: Discovery, citations and completed-search facts
owner:
- Discovery
providers:
- U1
- U3
consumers:
- U1
- U2
- U3
- U4
- U5
- U8
mechanism: durable-command-fact
requirements:
- FR1
- FR1.1
- FR1.2
- FR1.3
- FR5
- FR5.2
- FR9
- FR9.1
- FR9.2
- FR12
- FR12.2
- FR13
- FR13.1
operations:
- name: search
  input: SearchRequest
  output: SearchResponse
  auth: Existing guest-search authority or current authenticated account; no private material, AI-job authority or personal history for guests.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SNAPSHOT_EXPIRED
  - CAPACITY_EXHAUSTED
  - INCOMPATIBLE_VERSION
  semantics: Validate canonical query vocabulary and policy bounds; use compatible published generation plus current eligibility. Snapshot-bound
    pagination or explicit SNAPSHOT_EXPIRED; empty matches only after successful retrieval.
  surface: browser
- name: readCitations
  input: CitationRequest
  output: CitationResponse
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SNAPSHOT_EXPIRED
  - SOURCE_INELIGIBLE
  - CAPACITY_EXHAUSTED
  semantics: Bound distinct nodes/depth/requests by resolved traversal policy; identify unknown/stale/partial sources without fabricated edges.
    Saving calls Library separately.
  surface: browser
- name: readHistoryCheckpoint
  input: SearchHistoryCheckpointRead
  output: SearchHistoryCheckpoint
  auth: Trusted Library consumer for current owner.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Linearizable producer admission fence for the owner's searches; Library records this boundary when clearing history to suppress already
    admitted delayed searches.
  surface: internal
- name: readCompletedSearchFacts
  input: SearchFactsRead
  output: SearchFactsPage
  auth: Trusted Library consumer, scoped to authenticated owner.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Only qualifying authenticated completed searches yield durable facts. Admission/completion sequence is producer-assigned; read/replay
    neither executes search nor writes Library.
  surface: internal
- name: ackCompletedSearchFact
  input: SearchFactAck
  output: Ack
  auth: Trusted Library consumer reporting its own persisted disposition.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  semantics: Record only after durable Library handling; lost acknowledgement permits duplicate replay, not duplicate history. Never treat delivery
    itself as saved-history success.
  surface: internal
invariants:
- LibraryQueryContext is the sole query shape shared by current search, saved query and history; mode/filter/order vocabularies are versioned
  and reconciled against retained behavior before readiness.
- Guest search never accepts an ownerId and produces no personal history/behavior. Authenticated personalization uses current consent and defaults;
  failed search is not a successful empty response.
- Discovery reads CorpusContent publication and eligibility contracts; it cannot publish generations, override withdrawal or interpret a private
  attachment ID as public content.
- History facts are at-least-once, owner-scoped and immutable. Library suppresses facts admitted at/before its acknowledged clear fence and facts
  prohibited by account lifecycle; consumption does not create a reverse Discovery-to-Library import.
- Configured input/page/traversal limits and compatibility rules must be resolved; unknown policy blocks the affected request instead of silently
  selecting numerical defaults.
checks:
- 'Property: same snapshot/cursor yields stable nonduplicated page identities; changed/expired snapshot is explicit.'
- 'Property: no guest/private history leak; duplicate facts and clear-before-delivery cannot recreate cleared history.'
- Verify lexical/semantic fixture relevance, disclosed fallback, source withdrawal and bounded cyclic citation graphs through mounted UI.
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C06 — Paper assistance, glossary and prepared-result boundary

```yaml contract
id: C06
title: Paper assistance, glossary and prepared-result boundary
owner:
- PaperAssistance
providers:
- U1
- U3
consumers:
- U1
- U3
- U8
mechanism: durable-command-fact
requirements:
- FR3
- FR3.1
- FR3.2
- FR3.3
- FR3.4
- FR4
- FR4.1
- FR4.2
- FR10
- FR10.1
- FR17
- FR17.2
operations:
- name: readAssistanceOptions
  input: AssistanceOptionsRead
  output: AssistanceOptions
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Expose reconciled supported actions/languages/presentation choices with vocabulary revision; readiness cannot imply parity from an
    empty options list.
  surface: browser
- name: acceptAssistance
  input: AssistanceRequest
  output: JobReceipt
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - IDEMPOTENCY_CONFLICT
  - CONFLICT
  - SOURCE_INELIGIBLE
  - CAPACITY_EXHAUSTED
  - OUTCOME_UNKNOWN
  semantics: Bind owner/paper/version/content/options/glossary snapshot, quota reservation and recoverable dispatch. Acknowledge only durable
    acceptance. Same key+input returns original job, changed input conflicts. Commit original acceptedAt once with immutable input/glossary, receipt
    and dispatch obligation. Replays/replacements never reset it; history createdAt maps to it.
  surface: browser
- name: readAssistanceJob
  input: AssistanceJobRead
  output: JobSnapshot
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read authoritative revision/sequence; snapshot recovery and C14 ordered progress refer to this same job. No execution from polling/reconnect.
  surface: browser
- name: readPreparedAssistance
  input: AssistanceResultRequest
  output: AssistanceResultRead
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SOURCE_INELIGIBLE
  semantics: Read retained prepared content bound to the job and exact source. Expired results remain expired; requesting another result requires
    explicit acceptAssistance.
  surface: browser
- name: readGlossary
  input: AssistanceGlossaryRead
  output: AssistanceGlossary
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Return acknowledged normalized terms and policy/revision. PaperAssistance returns a side-effect-free virtual empty snapshot with
    non-null owner/normalization-policy-bound initial revision when absent. Acceptance stores exact terms/revision; first U3 edit atomically compares
    absent plus initial token.
  surface: browser
- name: replaceGlossary
  input: AssistanceGlossaryWrite
  output: AssistanceGlossary
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  semantics: CAS replace after normalization, uniqueness and policy-bound checks; failed/conflicting writes preserve prior committed terms.
  surface: browser
- name: completeAssistance
  input: AssistanceComplete
  output: JobSnapshot
  auth: Trusted worker with current domain-scoped execution lease; recheck account/source policy before publishing outcomes.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - SOURCE_INELIGIBLE
  - OUTCOME_UNKNOWN
  semantics: Authenticate current authority before exact factId/content receipt replay. New facts require current trusted worker, unexpired lease/fence,
    immutable binding/input and expectedJobRevision. Validate prepared bytes and accepted source/options/glossary. In one PaperAssistance transaction
    commit result binding, terminal revision/sequence, fact receipt and durable settlement obligation. UsageEntitlements settles separately and
    idempotently; unknown stays reconcilable. C14 routes to this identical validator. Late replaced-worker progress, failure and success are rejected.
  surface: internal
- name: readAssistanceHistory
  input: AssistanceHistoryRead
  output: AssistanceHistoryPage
  auth: Current authenticated owner; current account/session/consent and exact source read authority.
  errors: &id002
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - INCOMPATIBLE
  semantics: Read current owner exact-paper/version retained jobs in descending immutable acceptedAt then jobId order. createdAt equals original
    acceptedAt. Cursor binds owner, exact paper/version, query/schema, stable membership and finite expiry. Every page rechecks current authority
    and present result availability. Expired/invalid cursor conflicts. Empty is distinct from dependency failure. Reads create no job, claim,
    glossary row, history fact or debit.
  surface: browser
- name: acquireExecutionClaim
  input: ExecutionAcquire
  output: ExecutionClaimResult
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: &id001
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - INCOMPATIBLE
  semantics: Compare immutable accepted binding and eligible nonterminal state, issue one worker-bound lease/fence atomically using owner time.
    Duplicate delivery to the same worker recovers the same still-current claim; another active claimant conflicts. Delivery attempt grants no
    authority.
  surface: internal
- name: renewExecutionClaim
  input: ExecutionRenew
  output: ExecutionClaimResult
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id001
  semantics: Compare trusted worker, current lease/fence, immutable binding, unexpired owner time and expectedLeaseRevision matching claim.leaseRevision.
    Advance lease revision only. Expired/replaced claims cannot renew; business revision/seq and original acceptedAt do not change.
  surface: internal
- name: reclaimExecution
  input: ExecutionReclaim
  output: ExecutionClaimResult
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id001
  semantics: Owner validates previousFence and expired/revoked prior claim atomically, grants replacement a strictly larger fence and preserves
    original input, acceptedAt and reservation. No timeout on the caller clock grants replacement authority.
  surface: internal
- name: readExecutionPayload
  input: ExecutionClaimRead
  output: AssistanceExecutionPayload
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id001
  semantics: U1 supports only PaperAssistance; other owner payload codecs remain INCOMPATIBLE until coordinated by their unit. Authenticate current
    worker/claim, verify exact accepted binding/hash and current source/account permission before releasing immutable input and permitted sections.
    Locator, owner ID and expired/replaced claim grant no access.
  surface: internal
- name: recordAssistanceProgress
  input: AssistanceProgress
  output: JobSnapshot
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id002
  semantics: Authenticate current authority, reconcile exact factId and normalized content before fresh CAS; otherwise validate current unexpired
    claim, expected job revision and input binding. Owner allocates seq/revision; terminal state never regresses.
  surface: internal
- name: failAssistance
  input: AssistanceFailure
  output: JobSnapshot
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id002
  semantics: Use the same fact authentication/replay/fence/CAS path as completion. Current claim may fail eligible work with a safe error and
    durable policy-bound settlement obligation; an old replaced worker cannot fail a newer attempt.
  surface: internal
invariants:
- PaperAssistance owns its job and result; shared dispatch/progress is a mechanism, not another outcome owner. JobReceipt is not produced by a
  no-op dispatch path.
- Assistance transitions accepted→running→succeeded|failed; generic cancellation states are not exposed as a new product capability. Owner lifecycle
  revocation may suppress execution/results under resolved policy.
- Terminal state/revision/sequence never regress. Progress is not proof of completion; succeeded requires a verified prepared result. Loss of
  a stream uses authoritative snapshot and ordered replay.
- Resolve permitted model/content use, supported option parity, workload bounds and accounting policy before affected execution. Missing model
  or invalid output yields explicit failure/abstention, not invented success.
- Current account/session/consent and source guard locks remain held on the target owner transaction connection through protected commit. Only
  AccountAccess/CorpusContent mutate their barriers; narrow owner-controlled guard functions expose no general foreign DML. Long inference holds
  no guard transaction.
- Exact committed fact replay can recover its safe receipt after lease expiry only under current permission; it never creates a new effect. New
  facts use owner time, current fence and a separate expected business revision.
checks:
- Crash after acceptance before dispatch; verify recoverable execution responsibility and no abandoned acknowledgement.
- 'Property: duplicate command/delivery/completion preserves one job/result/debit; stale events cannot regress terminal state.'
- Mounted stream framing/reconnect/poll/result tests exercise all four recorded legacy job defects; read-result must not invoke execution.
state_machines:
- name: AssistanceJob
  initial: accepted
  transitions:
    accepted:
    - running
    - failed
    running:
    - succeeded
    - failed
    succeeded: []
    failed: []
  rule: Recovering delivery of accepted/running work keeps original job identity; success requires durable prepared result. Retrying failed work
    is explicit and uses a new intended command only when policy allows.
bindings:
- prepared.ownerId == job.ownerId == trusted accountId
- prepared.jobId == accepted jobId
- prepared.paper == accepted paper/version/eligibility binding
- prepared.sourceContentHash == accepted source content hash
- prepared.operation/optionId/glossaryRevision == accepted immutable request
- completion.claim.binding and inputHash equal immutable accepted input; trusted worker and lease/fence equal current unexpired owner claim
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C07 — Private research, durable drafts and immutable novelty artifacts

```yaml contract
id: C07
title: Private research, durable drafts and immutable novelty artifacts
owner:
- ResearchWorkspace
providers:
- U4
consumers:
- U4
- U6
- U8
mechanism: durable-command-fact
requirements:
- FR2
- FR2.3
- FR13
- FR13.1
- FR13.2
- FR13.3
- FR14
- FR14.1
- FR14.2
- FR15
- FR15.1
- FR15.2
- FR16
- FR16.1
- FR16.2
- FR17
- FR17.2
operations:
- name: createResearchContext
  input: ResearchContextCreate
  output: ResearchContext
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - IDEMPOTENCY_CONFLICT
  semantics: Allocate server-owned private context before draft/upload/session/novelty steps; this protocol resource is not a separate product
    feature or job. Owner and context identity are server-assigned.
  surface: browser
- name: createResearchSession
  input: ResearchSessionCreate
  output: ResearchSession
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - IDEMPOTENCY_CONFLICT
  semantics: Commit one owner/context-bound session; scope references must be authorized independently.
  surface: browser
- name: readResearchSession
  input: ResearchSessionRead
  output: ResearchSession
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Reopen committed turn references and authoritative pending states; never submit work by opening a session.
  surface: browser
- name: listResearchSessions
  input: ResearchSessionList
  output: ResearchSessions
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SNAPSHOT_EXPIRED
  semantics: Owner-only snapshot pagination; deleted/tombstoned sessions cannot reappear through stale lists.
  surface: browser
- name: deleteResearchSessions
  input: ResearchDelete
  output: ResearchDeletion
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - OUTCOME_UNKNOWN
  semantics: CAS session/account-session-set boundary with explicit confirmation; durable tombstone precedes cleanup. Completion requires policy-defined
    pending-work, drafts/assets/derived-data dispositions.
  surface: browser
- name: beginPrivateAttachment
  input: ResearchAttachmentStart
  output: ResearchUploadPermit
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CAPACITY_EXHAUSTED
  semantics: Issue protected context-specific bounded upload handle only after resolved file/storage/privacy/capacity policy; this is not accepted
    research work.
  surface: browser
- name: finishPrivateAttachment
  input: ResearchAttachmentFinish
  output: ResearchAttachment
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - INVALID_CONTENT
  semantics: Verify bytes/hash/media before recoverable extraction; classify malformed/protected/truncated content truthfully; no public corpus
    publication.
  surface: browser
- name: readPrivateAttachment
  input: ResearchAttachmentRead
  output: ResearchAttachment
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Enforce account, exact research context and current lifecycle for direct reads.
  surface: browser
- name: readPrivateAsset
  input: ResearchPrivateAssetRead
  output: ResearchPrivateAsset
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Authorize each asset/readHandle; reject arbitrary paths and cross-context attachment reuse.
  surface: browser
- name: saveDraft
  input: DraftWrite
  output: DraftWriteResult
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  semantics: CAS baseRevision (null only for new draft). Durable acknowledgement includes exact revision/hash; conflict returns authorized current
    revision and proposed text without silently overwriting either.
  surface: browser
- name: restoreDraft
  input: DraftRead
  output: DraftRecovery
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Return only retained acknowledged unconsumed revision after same-owner authentication; restore has no submission/external effect.
  surface: browser
- name: discardDraft
  input: DraftDiscard
  output: Ack
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  semantics: Discard exact acknowledged revision under CAS and durable deletion boundary; a stale discard cannot erase newer edits.
  surface: browser
- name: acceptResearchTurn
  input: ResearchTurnRequest
  output: JobReceipt
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  - CAPACITY_EXHAUSTED
  - OUTCOME_UNKNOWN
  semantics: Commit one turn/input/scope snapshot and recoverable dispatch. If submittedDraft supplied, verify matching owner/context/kind/text
    hash and consume only that exact revision with accepted operation; newer edits survive.
  surface: browser
- name: readResearchTurn
  input: ResearchTurnRead
  output: ResearchTurn
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read committed input, pending/terminal state and prepared artifact reference without regeneration.
  surface: browser
- name: acceptNoveltyAnalysis
  input: ResearchNoveltyRequest
  output: JobReceipt
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  - CAPACITY_EXHAUSTED
  - OUTCOME_UNKNOWN
  semantics: Distinct topic/manuscript novelty job; immutable input and scope snapshot with exact optional draft consumption and recoverable dispatch.
  surface: browser
- name: acceptNoveltyDiscussion
  input: ResearchNoveltyDiscussion
  output: JobReceipt
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  - SOURCE_INELIGIBLE
  - CAPACITY_EXHAUSTED
  semantics: Accept a separate discussion job bound to the same owner's eligible immutable novelty result; neither reruns analysis nor approves
    export.
  surface: browser
- name: readResearchJob
  input: ResearchJobRead
  output: JobSnapshot
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Check job kind and context as well as owner; authoritative ordered snapshot for C14 progress recovery.
  surface: browser
- name: cancelNoveltyAnalysis
  input: ResearchJobRead
  output: JobSnapshot
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  semantics: Only kind novelty-analysis; cancellation request may return cancel_requested. Return cancelled only after authoritative cancellation
    wins; completed result stays succeeded if completion won. Never imply remote export cancellation.
  surface: browser
- name: readResearchArtifact
  input: ResearchArtifactRead
  output: ResearchArtifactResponse
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SOURCE_INELIGIBLE
  semantics: Fetch exact immutable revision/hash, with current eligibility; unavailable/expired/deleted result reads never regenerate work.
  surface: browser
- name: readNoveltyArtifactForExport
  input: ResearchArtifactRead
  output: ResearchArtifact
  auth: Trusted ApprovedExport consumer on behalf of current owner.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SOURCE_INELIGIBLE
  - CONFLICT
  semantics: 'R-02: only ready novelty-result, exact artifactId/revision/contentHash and current eligibility; changed bytes require new revision.
    Return typed immutable content plus eligibility revision.'
  surface: internal
- name: completeResearchWork
  input: ResearchCompletion
  output: JobSnapshot
  auth: Trusted worker with current domain-scoped execution lease; recheck account/source policy before publishing outcomes.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - SOURCE_INELIGIBLE
  - OUTCOME_UNKNOWN
  semantics: Match operation kind/context/lease/input; validate grounding and artifact hash; tombstone/cancellation dominates late publication.
    Persist artifact+terminal outcome recoverably and reconcile one usage record.
  surface: internal
invariants:
- 'R-02: artifactId/revision/contentHash identifies immutable canonical serialized prepared output. New content never overwrites that tuple; eligibility
  can change independently and is rechecked before export.'
- Private attachment identity never resolves through CorpusContent/public routes. Context scope is enforced within an owner, not merely between
  accounts. Source instructions are untrusted data.
- Research-turn and novelty-analysis/discussion retain distinct identities, allowed inputs and result kinds. Novelty cancellation cannot resurrect
  through late completion or authorize publication.
- Durable draft persistence/restore/discard/consumption is blocked with POLICY_UNRESOLVED until retention, erasure, storage and shared-device
  policy is resolved. Browser account tagging is not secure isolation.
- Only acknowledged draft revisions are recoverable. Saving/failed UI states cannot promise recovery; an accepted submission consumes its exact
  draft revision and preserves a concurrent newer one. Session tombstones reject late draft saves.
- Literal quotes require source text/hash/location actually read; unread web references cannot support claims. Partial extraction/model context
  and abstention are explicit, not false successful grounding. Optional assessments use the recorded method scale with minimum<=score<=maximum
  and existing evidence IDs; a score is not proof of scientific novelty.
- Deletion acknowledgement is not blanket erasure proof. Deleted/session-scoped results, drafts and attachments cannot reappear on replay/restore;
  backup and externally exported-copy treatment require resolved policy.
checks:
- 'Property: owner/context swaps fail on lists, direct IDs, assets, drafts, progress and results.'
- Interleave draft save/submit/new edit/conflict/discard/session-delete/restart; exact accepted revision is consumed and newer acknowledged edit
  survives.
- 'Property: immutable artifact tuple never returns different bytes; eligibility revocation prevents pending export.'
- Race novelty cancellation/completion and duplicate turn delivery; one authoritative outcome and no duplicate accounting.
- Controlled evidence fixtures include support, contradiction, insufficient evidence, unread references, corrupt extraction and malformed model
  output.
state_machines:
- name: ResearchTurnOrDiscussion
  initial: accepted
  transitions:
    accepted:
    - running
    - failed
    running:
    - succeeded
    - failed
    succeeded: []
    failed: []
  rule: Distinct kind/context and immutable input per accepted turn/discussion; deleted context prevents late result publication.
- name: NoveltyAnalysis
  initial: accepted
  transitions:
    accepted:
    - running
    - cancel_requested
    - failed
    running:
    - cancel_requested
    - succeeded
    - failed
    cancel_requested:
    - cancelled
    - succeeded
    - failed
    cancelled: []
    succeeded: []
    failed: []
  rule: Cancellation request is not cancellation completion; CAS determines the one winning terminal result. No terminal resurrection.
- name: DraftRevision
  initial: acknowledged
  transitions:
    acknowledged:
    - consumed
    - discarded
    - expired
    - deleted
    consumed: []
    discarded: []
    expired: []
    deleted: []
  rule: Editing creates another immutable acknowledged revision; consumption/discard targets exact revision and cannot consume newer edits. Conflict
    does not commit an overwrite.
bindings:
- artifact.ownerId/contextId/operationId == accepted owner/context/job
- artifact.kind matches research-turn, novelty-analysis or novelty-discussion job kind
- artifact.artifact.contentHash == hash of versioned canonical artifact.output
- submitted draft owner/context/kind/contentHash == accepted input
- completion lease/input/revision matches active claim and live context tombstone boundary
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C08 — Topics, content windows and recoverable digest delivery

```yaml contract
id: C08
title: Topics, content windows and recoverable digest delivery
owner:
- TopicsDigests
providers:
- U5
consumers:
- U5
- U8
- Email delivery adapter
mechanism: durable-command-fact
requirements:
- FR8
- FR8.1
- FR12
- FR12.1
- FR12.2
- FR19
- FR19.1
operations:
- name: upsertTopicSubscription
  input: DigestSubscriptionWrite
  output: DigestSubscription
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  semantics: CAS normalized owner/topic identity and settings; preserve one subscription for repeated follow. Resolve IANA time-zone, cadence
    and topic validation vocabulary before enabling.
  surface: browser
- name: listTopicSubscriptions
  input: DigestSubscriptionsRead
  output: DigestSubscriptions
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SNAPSHOT_EXPIRED
  semantics: Owner-only paginated current subscription state.
  surface: browser
- name: unfollowTopic
  input: DigestSubscriptionRead
  output: DigestSubscription
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  semantics: Durably disable subscription and advance unsubscribe boundary; queued work checks that boundary before sending.
  surface: browser
- name: prepareDigest
  input: DigestPrepare
  output: DigestDelivery
  auth: Trusted TopicsDigests scheduler for current eligible subscription.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Deduplicate owner/subscription/window/policy intention; resolve eligible Discovery inputs. startInclusive<endExclusive and schedule/time-zone
    policy govern boundaries. No-content is a recorded outcome, not a retrieval failure.
  surface: internal
- name: dispatchDigest
  input: DigestSend
  output: DigestDelivery
  auth: Trusted delivery worker for this TopicsDigests effect.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - OUTCOME_UNKNOWN
  - CAPACITY_EXHAUSTED
  semantics: Before external send recheck current owner, verified destination, consent, enabled subscription, unsubscribe fence, paper eligibility
    and free-delivery policy. Persist intent before adapter call; timeout may yield unknown.
  surface: internal
- name: readDigestDelivery
  input: DigestDeliveryRead
  output: DigestDelivery
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: Read authoritative delivery disposition; sent requires remote acceptance evidence, not an attempt.
  surface: browser
- name: reconcileDigestDelivery
  input: DigestDeliveryRead
  output: DigestDelivery
  auth: Trusted domain recovery worker; authorized operations can request reconciliation.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - OUTCOME_UNKNOWN
  semantics: Resolve original effectKey/remote receipt. Unknown outcomes never blindly resend; a retry requires affirmative proof that original
    effect did not occur.
  surface: internal
- name: unsubscribeDigestToken
  input: DigestUnsubscribe
  output: DigestUnsubscribeResult
  auth: Valid purpose-scoped signed unsubscribe token; no broader account authority.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - INVALID_TOKEN
  semantics: POST/explicit confirmation only; verify target/purpose and persist unsubscribe boundary. Repeated already-applied token is harmless;
    response discloses no account enumeration.
  surface: browser
invariants:
- Delivery is distinct from preparation and transport acknowledgement. States sent, failed, unknown, no-content and suppressed are not interchangeable.
- Unsubscribe/current consent wins over queued retries. One immutable effectKey binds subscription/window/content; stale scheduled work cannot
  create an additional send.
- The configured free delivery path, retention, consent and schedule policy must be resolved before public delivery. A local sink proves only
  synthetic delivery, not public parity.
- Provider acknowledgements and reconciliation facts are replayable without changing the intended effect. Unknown remote success remains unknown
  if the provider cannot resolve it.
checks:
- 'Property: clock/time-zone/DST schedule occurrences are unique; rolling 7/30-day content lookbacks may overlap with delivery watermarks suppressing repeated items, and duplicate scheduling retains one
  effect.'
- Race unsubscribe/revocation against queued dispatch; no ineligible send.
- Inject timeout after remote send; reconciliation cannot duplicate delivery or report false success.
state_machines:
- name: DigestDelivery
  initial: prepared
  transitions:
    prepared:
    - queued
    - no-content
    - suppressed
    - failed
    queued:
    - sending
    - suppressed
    - failed
    sending:
    - sent
    - failed
    - unknown
    unknown:
    - sent
    - failed
    - suppressed
    failed:
    - queued
    - suppressed
    sent: []
    no-content: []
    suppressed: []
  rule: failed→queued requires proven non-occurrence, resolved retry policy and current consent/subscription; unknown must reconcile first. Initial
    no-content outcome creates no send.
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C09 — Owner-approved Notion export and uncertain-effect reconciliation

```yaml contract
id: C09
title: Owner-approved Notion export and uncertain-effect reconciliation
owner:
- ApprovedExport
providers:
- U6
consumers:
- U6
- U8
- Notion adapter
mechanism: durable-command-fact
requirements:
- FR6
- FR6.3
- FR14
- FR14.2
- FR15
- FR15.1
- FR16
- FR16.1
- FR16.2
operations:
- name: configureNotionConnection
  input: ExportConnectionConfigure
  output: ExportConnection
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - INVALID_TOKEN
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  semantics: 'Preserve retained owner-token configuration: protected same-origin write-only token input, current-owner binding and CAS credential
    replacement. Validate with provider then store through resolved credential protection; never echo token to response, browser persistence or
    normal logs. Token replacement invalidates approvals using prior connection revision. C09 2.1.0 (A7): the response carries workspaceName
    when Notion reports one for the accepted token.'
  surface: browser
- name: readNotionConnection
  input: ExportConnectionRead
  output: ExportConnection
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: 'Return safe connection disposition/scope, never credential material. C09 2.1.0 (A7): connectionId is optional; when it is absent
    the server reads the current owner''s single connection. workspaceName, when present, is the Notion workspace name reported for the stored
    token. destinationScopeIds holds the activation destination in the real composition and is empty otherwise. An internal pre-connection
    reservation is never returned; while one exists the connection reads exactly as when no connection exists, and state stays one of the four
    listed values.'
  surface: browser
- name: disconnectNotion
  input: ExportConnectionRead
  output: ExportConnection
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - OUTCOME_UNKNOWN
  semantics: 'Persist revoked/disconnected authority boundary; pending previews/approvals/effects cannot reuse it. Remote published content is
    not claimed deleted. C09 2.1.0 (A7): connectionId is optional; when it is absent the current owner''s single connection is disconnected.'
  surface: browser
- name: listExportDestinations
  input: ExportConnectionRead
  output: ExportDestinations
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: 'List only currently permitted destinations from owner''s connection; partial/unavailable provider scope is explicit. C09 2.1.0
    (A1, A6, A7): connectionId is optional as for readNotionConnection. Notion grants access per shared page but enforces the connection-wide
    content-creation permission only when writing, so "currently permitted destinations" is read as pages shared with the connection that are
    readable and not known to be refused. Each entry carries required destinationId (the parent page id) and title (a placeholder when the page
    is untitled), an optional location context, and, as far as known, readable, creationCapability (unknown, confirmed or refused) and writable
    (false when the page is unreadable or the connection''s creation capability is refused, true otherwise). listingComplete false marks a partial
    or unavailable listing. lastDestinationId names the destination of the owner''s most recent succeeded export; it is only a preselection hint,
    used when that page is listed and readable.'
  surface: browser
- name: prepareExportPreview
  input: ExportPreviewRequest
  output: ExportPreview
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - SOURCE_INELIGIBLE
  - CONFLICT
  semantics: 'Read C07 exact eligible novelty artifact; freeze source tuple, owner, destination, connection revision and rendered content in canonical
    bindingHash. Preparing preview performs no Notion write. C09 2.1.0 (A1, A5): in the request, destinationId, title and context are optional
    and never trusted; the server derives destinationId from parentPageId and reads title and context from Notion. The response destination
    is an ExportDestinationEntry. sourceTitle, marker (the export marker, the text of the last top-level block) and earlierExports (bounded;
    earlier exports of the same source and destination that succeeded or may exist in Notion) are optional. Hash rule (NFR4.2): renderedContentHash
    is the SHA-256 of the canonical page-creation body tree {"properties": {"title": ...}, "children": [...]}, exactly as it is sent, serialized
    as JSON with sorted keys, compact separators and UTF-8 without escaping (the form ResearchWorkspace uses for its content hashes, with no domain
    prefix). For C09 2.1.0 this supersedes the rule in Canonical identity that hashes the renderedText bytes; renderedText is the read-only plain-text
    projection of that tree. bindingHash keeps the canonical rule: SHA-256 of the prefix docsuri:export-binding:v1 and a newline, followed by
    the JCS bytes of the object containing exactly ownerId, previewId, revision, source, sourceEligibilityRevision, connectionRevision, destination,
    renderedContentHash and renderPolicy, where destination holds only destinationId, connectionId, workspaceId, parentPageId and formatRevision
    (never title or context, so renaming a page does not void an approval). Golden byte vectors for both hashes: shared/export-hash-vectors.json.'
  surface: browser
- name: approveExportPreview
  input: ExportApprovalRequest
  output: ExportApproval
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - SOURCE_INELIGIBLE
  - IDEMPOTENCY_CONFLICT
  semantics: 'Require deliberate explicit approval of exact previewRevision/bindingHash. Revalidate source/destination/connection/current owner;
    a changed binding requires a new preview and approval. C09 2.1.0 (A9): every returned approval carries invalidationReason (source-changed,
    destination-changed, connection-changed, authority-revoked or account-withdrawn) when, and only when, it is invalidated.'
  surface: browser
- name: executeApprovedExport
  input: ExportExecute
  output: ExportEffect
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - SOURCE_INELIGIBLE
  - APPROVAL_REQUIRED
  - OUTCOME_UNKNOWN
  - CAPACITY_EXHAUSTED
  semantics: 'Before any external effect recheck exact immutable source revision/hash, current eligibility, destination, connection, owner and
    approval policy. Durably bind one effect to approval then dispatch; identical retry returns original effect. C09 2.1.0 (A6 extension): the
    notion.write message carries contentHash (the bound renderedContentHash) and marker, and the adapter writes only when the body it sends recomputes
    to contentHash. A write result adds providerRequestId and, for disposition rejected, refusalClass. A rate-limited answer is the provider outcome
    retry_later with the stated wait in the provider outcome''s retryAfterSeconds and no committed disposition.'
  surface: browser
- name: readExportEffect
  input: ExportEffectRead
  output: ExportEffect
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: 'Read outcome only. Unknown is not failed or success; refresh never creates or repeats a publication. C09 2.1.0 (A4): an effect
    may carry outcomeReason (why it ended failed, invalidated or cancelled, or how the owner settled it), settledBy, nextCheckAt (for an unknown
    effect, when the next reconciliation check runs) and settlementOffered (whether the owner may now settle it).'
  surface: browser
- name: cancelExportApproval
  input: ExportCancel
  output: ExportApproval
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - OUTCOME_UNKNOWN
  semantics: 'CAS invalidate unconsumed approval before dispatch; in-flight/existing external effect cannot be promised undone and returns conflict/unknown
    for explicit reconciliation. C09 2.1.0 (A10): expectedRevision is the preview revision while the approval is approved and unconsumed, and
    the approval becomes cancelled; it is the effect revision when the approval is consumed and its effect is still accepted, and the effect
    becomes cancelled with outcomeReason owner-cancelled while the approval stays consumed. Cancel returns the approval in both cases; the client
    reads the effect to see its cancelled state. An effect that has left accepted is never promised undone.'
  surface: browser
- name: listExportHistory
  input: ExportHistoryList
  output: ExportHistoryPage
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  semantics: 'C09 2.1.0 (A2): page the current owner''s exports keyed by approval, newest first, with limit 1 to 20 and an opaque cursor. Each
    entry carries the approval state, invalidationReason, approvedAt and endedAt (when the export ended: the approval was cancelled or invalidated,
    or its bound effect reached a terminal state), the source and destination titles, previewId, previewRevision and bindingHash for continue
    and cancel, and continuable (the approving session is still current). When an effect is bound, the entry carries its state, revision, remoteUrl,
    outcomeReason, settledBy, nextCheckAt, bounded possibleDuplicates (further pages carrying the same marker) and settlementOffered. Reading history
    never exports and never changes a record.'
  surface: browser
- name: settleExportEffect
  input: ExportSettle
  output: ExportEffect
  auth: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - CONFLICT
  - IDEMPOTENCY_CONFLICT
  semantics: 'C09 2.1.0 (A3): the owner settles an unknown effect as delivered or not-delivered under expectedRevision (the effect revision),
    with assumptionAccepted true, only once settlement is offered (the settling wait has passed and checks cannot decide, the connection cannot
    read the destination, or scanning has stopped). delivered moves the effect to succeeded and not-delivered to failed, with settledBy owner and
    outcomeReason owner-settled-delivered or owner-settled-not-delivered. The optional remoteUrl must be a Notion page link and is shown only,
    never used as identity. Settling never writes to Notion. A changed revision or an effect not offered for settlement answers CONFLICT; the
    same key with a changed request answers IDEMPOTENCY_CONFLICT.'
  surface: browser
- name: reconcileExportEffect
  input: ExportEffectRead
  output: ExportEffect
  auth: Trusted domain recovery worker or authorized recovery request for this owner/effect.
  errors:
  - INVALID_ARGUMENT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - OUTCOME_UNKNOWN
  semantics: 'Query evidence for original effect identity/remote reference; do not blindly repeat write. Another write is permitted only after
    proven non-occurrence and still-valid approval/current authority. C09 2.1.0 (A6 extension): the effect.reconcile message adds marker (the
    search key), destinationId, firstAttemptStartedAt and writerIdentity. Scan evidence maps marker found to committed and every other result
    to unknown, with scanComplete; a scan never yields definitely_not_committed.'
  surface: internal
invariants:
- 'R-02: the same ResearchArtifactRef tuple appears in C07 source read and C09 preview; bindingHash additionally fixes rendered content, destination,
  owner, connection revision and render policy. Canonical serialization/hashing is versioned and shared by preview/approval/execution.'
- Analysis completion, prepared-result read, draft restore, preview, approval cancellation and status polling never authorize an export. Only
  explicit current approval permits the bound effect.
- Unresolved credential protection, allowed external-copy handling, provider terms/free capacity, approval-validity or source policy blocks the
  affected connection/storage/export operation with POLICY_UNRESOLVED. No default duration or paid fallback is chosen.
- Approval and effect are distinct records. Duplicate idempotency key with changed payload conflicts. Lost remote response remains unknown until
  reconciled; provider inability to reconcile cannot be disguised as retry safety.
- 'Retained connection uses owner token configuration/read/disconnect, not a new OAuth feature. writeOnly is documentation/validation metadata,
  not sufficient secret handling: transport, redaction, storage and browser clearing require executable verification.'
- Revocation/deletion after a remote write does not prove deletion of external copies; report recorded local/remote dispositions separately under
  the resolved policy.
checks:
- 'Property: change any source bytes/revision/hash, owner, connection revision or destination after preview; stale approval cannot authorize effect.'
- 'Property: preview/read/cancel has zero external writes; duplicate execution has one intended effect.'
- Inject timeout immediately after remote success and restart before receipt; reconciliation identifies the original publication without blind
  duplicate send.
- Verify cross-owner credentials/results/approval/effect isolation and current-source eligibility immediately before write.
state_machines:
- name: ExportApproval
  initial: approved
  transitions:
    approved:
    - consumed
    - cancelled
    - invalidated
    - expired
    consumed: []
    cancelled: []
    invalidated: []
    expired: []
  rule: A preview is not an approval. Consumed approval binds one durable intended effect, not proof of its remote success.
- name: ExportEffect
  initial: accepted
  transitions:
    accepted:
    - executing
    - cancelled
    - invalidated
    - failed
    executing:
    - succeeded
    - failed
    - unknown
    unknown:
    - succeeded
    - failed
    failed:
    - accepted
    - invalidated
    succeeded: []
    cancelled: []
    invalidated: []
  rule: failed retry preserves same effect identity, needs proof remote effect did not occur and still-valid bound authorization; unknown never
    directly transitions to execution. Approval consumption does not manufacture a new approval for retry.
bindings:
- approval.ownerId == effect.ownerId == current accountId
- preview.source == C07 immutable artifactId/revision/contentHash
- approval.bindingHash == effect.bindingHash == current verified preview binding
- current connection/source eligibility/destination authority is checked at dispatch authorization point
- revocation concurrent with an already-dispatched remote effect is reported/reconciled rather than falsely claimed undone
version: 2.1.0
typeRegistry: urn:docsuri:v2:schemas
```

## C10 — Controlled platform evidence and effects

```yaml contract
id: C10
title: Controlled platform evidence and effects
owner:
- PlatformControl
providers:
- U7
consumers:
- U8
- 'External: authorized operator'
mechanism: typed-module / controlled executable
requirements:
- FR20
- FR20.1
- FR20.2
operations:
- name: inspectEvidence
  input: OperatorEvidenceRequest
  output: OperatorEvidence
  auth: operator authority for exact target or separately granted bounded evidence reader
  surface: internal
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Read verified target/input/generation bindings; app administrator alone never grants operator privileges.
- name: executeControlled
  input: OperatorExecuteRequest
  output: OperatorReceipt
  auth: current independent operator authority
  surface: internal
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Bind actor, operation, target, input hash, evidence generation and policy atomically to receipt before effects; recheck preconditions
    before each effect.
- name: readReceipt
  input: OperatorReceiptRequest
  output: OperatorReceipt
  auth: same target-scoped authority
  surface: internal
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Read/reconcile without repeating effects; unknown remains unknown until evidence establishes disposition.
invariants:
- The executable transport is local stdin/stdout JSON; dedicated authenticated evidence HTTP bindings remain compatibility-dependent rather than
  a public admin bypass.
- Operation vocabulary comes from the retained protocol inventory; unsupported or unverified native semantics fail closed. No generic arbitrary
  command, path or shell execution is admitted.
- Receipts preserve actor/target/effect binding across restart. A replay with changed input under the same key conflicts. Readiness is not inferred
  from a receipt alone.
checks:
- Wrong actor/target and changed inputs cannot cause effects.
- Interrupted effect with unknown outcome is reconciled without duplicate execution.
- Native filesystem/keyring behavior and every retained command still require actual fixture execution.
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C11 — Privacy-aware operations and domain recovery

```yaml contract
id: C11
title: Privacy-aware operations and domain recovery
owner:
- ServiceOperations
providers:
- U1
- U8
consumers:
- U8
- 'External: authorized administrator'
mechanism: typed-module
requirements:
- FR19
- FR19.1
- FR19.2
- FR19.3
operations:
- name: readDashboard
  input: OpsQuery
  output: OpsObservationPage
  auth: administrator with current MFA
  surface: admin
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Return evidence timestamps and unknown/stale conditions; pagination is stable for its snapshot.
- name: listIncidents
  input: OpsQuery
  output: OpsIncidentPage
  auth: administrator with current MFA
  surface: admin
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Return authorized incident/correlation references without private source text or secrets.
- name: requestRecovery
  input: OpsRecoveryRequest
  output: JobReceipt
  auth: administrator with current MFA plus operation-specific grant
  surface: admin
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Domain owner validates and performs recovery. Platform effects additionally require independent operator authority.
- name: recordObservation
  input: OpsObservation
  output: Ack
  auth: trusted producer identity bound by composition
  surface: internal
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Observation transport failure never changes a domain outcome; bounded buffering/dropping policy reports missing evidence.
invariants:
- Liveness, component readiness and complete-journey readiness are distinct. Unknown or stale observations cannot be upgraded to available.
- Recovery preserves current ownership, deletion, consent, source restrictions and idempotency; ServiceOperations never writes domain records
  directly.
- Logging excludes credentials and unnecessary private input; access and retention policy must be approved before storage.
checks:
- Inject a job failure, correlate to an incident and verify actual domain recovery.
- Restore cannot resurrect erased data or bypass current authority.
- Fail observation sink and assert bounded behavior plus truthful unknown indicators.
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C12 — Retained provider adapter boundary

```yaml contract
id: C12
title: Retained provider adapter boundary
owner:
- AccountAccess
- CorpusContent
- Discovery
- PaperAssistance
- ResearchWorkspace
- TopicsDigests
- ApprovedExport
providers:
- U1
- U2
- U3
- U4
- U5
- U6
consumers:
- 'External: Google / ORCID / source and citation APIs / approved model and extraction / email / Notion'
mechanism: typed adapter envelope; provider wire profile required
requirements: []
operations:
- name: invokeProvider
  input: ProviderRequest
  output: ProviderOutcome
  auth: trusted component plus current operation-specific authority
  surface: internal
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: Validate payload against the registered requestSchemaId and adapterRevision; only the registered operation allowlist is callable.
    Unknown adapter/profile/schema is POLICY_UNRESOLVED or INCOMPATIBLE, never permissive passthrough.
invariants:
- This is a dispatch envelope, not a claim that arbitrary JSON is a complete provider API. Each enabled adapter MUST register concrete request/response
  schemas, provider API version, allowed hosts, callback/credential rules and free-limit evidence before admission; unresolved profiles are blocked
  below.
- Owner component retains state authority. Credentials are references resolved server-side; adapter credentials never enter browser responses,
  observations or untrusted document prompts. Explicit owner token-configuration input and one-time MFA material have the separately documented
  protected treatment.
- Retry reads only within the selected deadline/attempt budget. Reconcile any possibly committed write before retry. Obey provider rate-limit
  responses and Retry-After; free-plan exhaustion cannot trigger paid fallback.
- Validate outbound URL/redirect/address targets before fetch, including private-address restrictions and per-source permission. Provider output
  and document content are untrusted data.
- 'The invokeProvider operation selects one of eleven typed profiles: identity.exchange, identity.profile, source.search, source.read, citation.read,
  model.generate, attachment.extract, email.send, notion.inspect, notion.write, effect.reconcile. responseSchemaId and non-null validatedPayload
  MUST match the selected profile; succeeded requires a non-null conforming payload. A nullable unknown outcome never proves a write was absent.'
checks:
- Reject unknown operation/schema/profile and outbound SSRF attempts.
- Verify Google/ORCID state, nonce/issuer/audience where applicable and link binding without account takeover.
- Exercise actual allowed email/model/Notion operation under verified free limits; mocks and a local mail sink do not establish public feasibility.
version: 2.0.0
typeRegistry: urn:docsuri:v2:schemas
```

## C14 — Durable accepted-work delivery and completion facts

```yaml contract
id: C14
title: Durable accepted-work delivery and completion facts
owner:
- CorpusContent
- PaperAssistance
- ResearchWorkspace
- TopicsDigests
- ApprovedExport
providers:
- U1
- U3
- U4
- U5
- U6
consumers:
- U1
- U3
- U4
- U5
- U6
- U8
- 'External: configured execution adapter'
mechanism: durable-command-fact
requirements: []
operations:
- name: deliverAccepted
  input: DispatchCommand
  output: DispatchAck
  auth: trusted executor binding plus rechecked current domain authority
  surface: internal
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: The domain commits operation and recoverable dispatch obligation in one atomic unit, or an equivalent proven recovery protocol, before
    acknowledging acceptance. Delivery is at least once; a consumer durably deduplicates messageId/operationId and validates input hash/revision.
    Delivery invokes acquireExecutionClaim then readExecutionPayload through the owner. DispatchAck only records transport disposition and owner
    recordedRevision, never a lease or completed result.
- name: recordCompletion
  input: DispatchFact
  output: DispatchAck
  auth: trusted executor for exact operation; authoritative owner validates transition
  surface: internal
  errors:
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - UNKNOWN_OUTCOME
  semantics: 'Only the operation owner commits state/seq/result visibility; stale worker generations, revoked authority and terminal/deleted-operation
    facts cannot overwrite or resurrect work. DispatchFact is a proposal, not an owner event: no worker seq/revision authority. messageId is the
    factId for the same normalized-intent replay. PaperAssistance progress/failure/success map to recordAssistanceProgress/failAssistance/completeAssistance
    using identical claim, CAS and settlement rules. For PaperAssistance, prepared.result must equal resultRef. ResearchWorkspace success carries
    a ResearchArtifact and maps to C07 completeResearchWork: resultRef.resultId equals prepared.artifact.artifactId, resultRef.revision and
    contentHash equal prepared.artifact.revision and contentHash, and resultRef.mediaType equals prepared.mediaType. The owning transaction verifies
    prepared.operationId, ownerId, contextId and artifact kind against the accepted operation, along with current account/source authority,
    unexpired lease/fence, expected job revision and exactly one usage settlement. Research non-success outcomes carry no prepared result.
    Claim binding must match operationId, ownerComponent and inputHash. A ResearchArtifact is never accepted for another owner. Other owners retain
    their own terminal/external-effect semantics and require a compatible payload codec before enablement.'
- name: acquireExecutionClaim
  input: ExecutionAcquire
  output: ExecutionClaimResult
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: &id001
  - INVALID_INPUT
  - UNAUTHENTICATED
  - FORBIDDEN
  - NOT_FOUND
  - CONFLICT
  - POLICY_UNRESOLVED
  - DEPENDENCY_UNAVAILABLE
  - INCOMPATIBLE
  semantics: Compare immutable accepted binding and eligible nonterminal state, issue one worker-bound lease/fence atomically using owner time.
    Duplicate delivery to the same worker recovers the same still-current claim; another active claimant conflicts. Delivery attempt grants no
    authority.
  surface: internal
- name: renewExecutionClaim
  input: ExecutionRenew
  output: ExecutionClaimResult
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id001
  semantics: Compare trusted worker, current lease/fence, immutable binding, unexpired owner time and expectedLeaseRevision matching claim.leaseRevision.
    Advance lease revision only. Expired/replaced claims cannot renew; business revision/seq and original acceptedAt do not change.
  surface: internal
- name: reclaimExecution
  input: ExecutionReclaim
  output: ExecutionClaimResult
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id001
  semantics: Owner validates previousFence and expired/revoked prior claim atomically, grants replacement a strictly larger fence and preserves
    original input, acceptedAt and reservation. No timeout on the caller clock grants replacement authority.
  surface: internal
- name: readExecutionPayload
  input: ExecutionClaimRead
  output: AssistanceExecutionPayload | ResearchExecutionPayload
  auth: Trusted authenticated executor for the exact owner operation; current account/session/source authority is rechecked on the same protected
    transaction.
  errors: *id001
  semantics: The payload type is owner-scoped. PaperAssistance releases `AssistanceExecutionPayload`; ResearchWorkspace releases
    `ResearchExecutionPayload` for its accepted kinds (`research-turn`, `novelty-analysis`, `novelty-discussion`). Every other owner payload codec remains
    INCOMPATIBLE until coordinated by its unit. Authenticate current worker/claim, verify exact accepted binding/hash and current source/account permission
    before releasing immutable input and permitted evidence/sections. Locator, owner ID and expired/replaced claim grant no access. The released input and
    evidence are untrusted data and never authorize an external action.
  surface: internal
invariants:
- A transport acknowledgement is not business completion. Retry_later leaves a durable redelivery obligation; committed/duplicate means the owning
  transaction recorded the disposition.
- Retry budgets/deadlines/capacity settings require an approved policy. No unbounded queue, retries, shared at-most-once claim or detached fire-and-forget
  acceptance.
- An outbox or alternative durable acceptance protocol is required behavior, not a selected database/broker. Reconcile usage reservations by operation
  identity, never count deliveries as separate work.
- Cancellation request is distinct from acknowledged cancellation; cancellation and completion compete at a single owner-controlled revision.
  Successful cancellation bars later effects.
checks:
- Crash before/after acceptance, delivery, effect and completion acknowledgement; recover exactly one logical operation.
- Duplicate/out-of-order events, lost stream and polling recovery preserve monotone seq/current snapshot.
- Revocation/deletion/cancellation races reject late work and prevent private-data resurrection.
- The released payload type is owner-scoped — an executor receives only its own owner's accepted input type, and an unknown or unregistered codec refuses
  INCOMPATIBLE rather than falling back to a generic envelope.
version: 2.2.0
typeRegistry: urn:docsuri:v2:schemas
```

## C13 — Browser and application HTTP contract

Only the operations explicitly listed here are externally mounted. A surface tag is not permission to expose internal callbacks, lifecycle acknowledgements, provider dispatch or projection writers. Account inputs and retained token configuration are redacted from logs; request credentials marked writeOnly are never echoed.

```yaml openapi
openapi: 3.1.1
info:
  title: DocSuri application v2 boundary
  version: 3.1.0
  description: Proposed browser/application contracts; legacy removal requires consumer evidence and approved transition.
servers:
- url: /
security:
- sessionCookie: []
paths:
  /api/v2/c01/host-resolve-navigation:
    post:
      operationId: C01_host.resolveNavigation
      summary: 'Trusted host composition and coherent web context: host.resolveNavigation'
      x-contract-operation: C01.host.resolveNavigation
      x-authorization: Validated session or anonymous context according to each registered route's verified access rule.
      description: Apply C01.host.resolveNavigation semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/HostNavigationInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HostNavigationResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-inspect-session:
    post:
      operationId: C02_access.inspectSession
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.inspectSession'
      x-contract-operation: C02.access.inspectSession
      x-authorization: Anonymous or validated current session; no caller-selected account.
      description: Apply C02.access.inspectSession semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessSessionInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessSessionStatus'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-register:
    post:
      operationId: C02_access.register
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.register'
      x-contract-operation: C02.access.register
      x-authorization: Public registration with abuse admission and configured input/data policy.
      description: Apply C02.access.register semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessRegisterInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessChallengeDelivery'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-request-verification:
    post:
      operationId: C02_access.requestVerification
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.requestVerification'
      x-contract-operation: C02.access.requestVerification
      x-authorization: Public, abuse-limited request; existence-neutral outcome.
      description: Apply C02.access.requestVerification semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessEmailRequestInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessChallengeDelivery'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-verify-email:
    post:
      operationId: C02_access.verifyEmail
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.verifyEmail'
      x-contract-operation: C02.access.verifyEmail
      x-authorization: Holder of valid unexpired single-use proof bound to the intended verification flow.
      description: Apply C02.access.verifyEmail semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessVerifyEmailInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-login:
    post:
      operationId: C02_access.login
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.login'
      x-contract-operation: C02.access.login
      x-authorization: Public credential verification with configured abuse policy.
      description: Apply C02.access.login semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessLoginInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessLoginResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-logout:
    post:
      operationId: C02_access.logout
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.logout'
      x-contract-operation: C02.access.logout
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C02.access.logout semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessLogoutInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-request-password-reset:
    post:
      operationId: C02_access.requestPasswordReset
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.requestPasswordReset'
      x-contract-operation: C02.access.requestPasswordReset
      x-authorization: Public, abuse-limited; existence-neutral response.
      description: Apply C02.access.requestPasswordReset semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessEmailRequestInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessChallengeDelivery'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-complete-password-reset:
    post:
      operationId: C02_access.completePasswordReset
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.completePasswordReset'
      x-contract-operation: C02.access.completePasswordReset
      x-authorization: Valid unused purpose-bound recovery proof.
      description: Apply C02.access.completePasswordReset semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessPasswordResetInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-change-password:
    post:
      operationId: C02_access.changePassword
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.changePassword'
      x-contract-operation: C02.access.changePassword
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
        Required current credential/reauthentication proof.
      description: Apply C02.access.changePassword semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessPasswordChangeInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-request-email-change:
    post:
      operationId: C02_access.requestEmailChange
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.requestEmailChange'
      x-contract-operation: C02.access.requestEmailChange
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
        Required reauthentication proof.
      description: Apply C02.access.requestEmailChange semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessEmailChangeInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessChallengeDelivery'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-complete-email-change:
    post:
      operationId: C02_access.completeEmailChange
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.completeEmailChange'
      x-contract-operation: C02.access.completeEmailChange
      x-authorization: Valid purpose-bound email-change proof and the required current authority.
      description: Apply C02.access.completeEmailChange semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessEmailChangeCompleteInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-begin-identity-flow:
    post:
      operationId: C02_access.beginIdentityFlow
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.beginIdentityFlow'
      x-contract-operation: C02.access.beginIdentityFlow
      x-authorization: Public for sign-in; current authenticated owner for linking.
      description: Apply C02.access.beginIdentityFlow semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessBeginIdentityInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessProviderRedirect'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-list-identity-links:
    post:
      operationId: C02_access.listIdentityLinks
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.listIdentityLinks'
      x-contract-operation: C02.access.listIdentityLinks
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C02.access.listIdentityLinks semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessIdentityListInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessIdentityPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-unlink-identity:
    post:
      operationId: C02_access.unlinkIdentity
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.unlinkIdentity'
      x-contract-operation: C02.access.unlinkIdentity
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
        Required reauthentication.
      description: Apply C02.access.unlinkIdentity semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessUnlinkIdentityInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-read-orcid-profile:
    post:
      operationId: C02_access.readOrcidProfile
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.readOrcidProfile'
      x-contract-operation: C02.access.readOrcidProfile
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C02.access.readOrcidProfile semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessOrcidProfileInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessOrcidProfile'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-begin-mfa-enrollment:
    post:
      operationId: C02_access.beginMfaEnrollment
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.beginMfaEnrollment'
      x-contract-operation: C02.access.beginMfaEnrollment
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
        Currently verified administrator enrollment authority and reauthentication.
      description: Apply C02.access.beginMfaEnrollment semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessMfaEnrollmentInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessMfaEnrollment'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-retrieve-mfa-enrollment-material:
    post:
      operationId: C02_access.retrieveMfaEnrollmentMaterial
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.retrieveMfaEnrollmentMaterial'
      x-contract-operation: C02.access.retrieveMfaEnrollmentMaterial
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
        Bound enrollment owner, current administrator enrollment authority, valid current reauthentication proof and unused delivery reference.
      description: Apply C02.access.retrieveMfaEnrollmentMaterial semantic rules. Derive internal context server-side; never accept it in this
        body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessMfaMaterialInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessMfaMaterial'
          headers:
            Cache-Control:
              schema:
                const: no-store
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-confirm-mfa-enrollment:
    post:
      operationId: C02_access.confirmMfaEnrollment
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.confirmMfaEnrollment'
      x-contract-operation: C02.access.confirmMfaEnrollment
      x-authorization: Bound enrollment owner with verified primary authentication and valid new factor proof.
      description: Apply C02.access.confirmMfaEnrollment semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessMfaConfirmInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-verify-mfa:
    post:
      operationId: C02_access.verifyMfa
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.verifyMfa'
      x-contract-operation: C02.access.verifyMfa
      x-authorization: Valid protected primary-authentication continuation and second-factor proof; an active full session is not required and
        anonymous context is permitted.
      description: Apply C02.access.verifyMfa semantic rules. Derive internal context server-side; never accept it in this body. Validate the
        purpose-bound continuation or recovery proof/cookie independently of a full session; anonymous context alone has no recovery/MFA authority.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessMfaVerifyInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessLoginResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-recover-mfa:
    post:
      operationId: C02_access.recoverMfa
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.recoverMfa'
      x-contract-operation: C02.access.recoverMfa
      x-authorization: Configured controlled administrator recovery authority/proof; no production bypass.
      description: Apply C02.access.recoverMfa semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessMfaRecoveryInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-read-profile:
    post:
      operationId: C02_access.readProfile
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.readProfile'
      x-contract-operation: C02.access.readProfile
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C02.access.readProfile semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessProfileInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessProfile'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-prepare-lifecycle:
    post:
      operationId: C02_access.prepareLifecycle
      x-contract-operation: C02.access.prepareLifecycle
      summary: Prepare a current-owner reauthenticated lifecycle confirmation
      security: [{sessionCookie: []}]
      parameters:
      - {name: X-CSRF-Token, in: header, required: true, schema: {type: string, minLength: 1}}
      - {name: Idempotency-Key, in: header, required: true, schema: {$ref: '#/components/schemas/Id'}}
      requestBody:
        required: true
        content:
          application/json:
            schema: {$ref: '#/components/schemas/AccessLifecyclePrepareInputHttp'}
      responses:
        '200':
          description: Bound one-use confirmation without private proof material
          content:
            application/json:
              schema: {$ref: '#/components/schemas/AccessLifecycleConfirmation'}
        default: {$ref: '#/components/responses/Edefault'}
  /api/v2/c02/access-update-profile:
    post:
      operationId: C02_access.updateProfile
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.updateProfile'
      x-contract-operation: C02.access.updateProfile
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C02.access.updateProfile semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessProfileUpdateInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessProfile'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-list-consents:
    post:
      operationId: C02_access.listConsents
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.listConsents'
      x-contract-operation: C02.access.listConsents
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C02.access.listConsents semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessConsentListInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessConsentPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-update-consent:
    post:
      operationId: C02_access.updateConsent
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.updateConsent'
      x-contract-operation: C02.access.updateConsent
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C02.access.updateConsent semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessConsentUpdateInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessConsentRecord'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/lifecycle-request:
    post:
      operationId: C02_lifecycle.request
      summary: 'Account access, consent and owner-acknowledged lifecycle: lifecycle.request'
      x-contract-operation: C02.lifecycle.request
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
        Required recent reauthentication and explicit action/scope confirmation.
      description: Apply C02.lifecycle.request semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LifecycleRequestInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LifecycleRequest'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/access-request-reactivation:
    post:
      operationId: C02_access.requestReactivation
      summary: 'Account access, consent and owner-acknowledged lifecycle: access.requestReactivation'
      x-contract-operation: C02.access.requestReactivation
      x-authorization: Public pre-authentication request under current abuse and reactivation-delivery policy; no active session or caller account
        authority.
      description: Apply C02.access.requestReactivation semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AccessEmailRequestInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AccessChallengeDelivery'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/lifecycle-reactivate:
    post:
      operationId: C02_lifecycle.reactivate
      summary: 'Account access, consent and owner-acknowledged lifecycle: lifecycle.reactivate'
      x-contract-operation: C02.lifecycle.reactivate
      x-authorization: Valid unused purpose-bound reactivation proof and bound scope confirmation; no active full session is required. Resolve
        the account from the proof, never from caller principal or account identifiers.
      description: Apply C02.lifecycle.reactivate semantic rules. Derive internal context server-side; never accept it in this body. Validate
        the purpose-bound continuation or recovery proof/cookie independently of a full session; anonymous context alone has no recovery/MFA authority.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LifecycleReactivationInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LifecycleReactivationResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c02/lifecycle-inspect:
    post:
      operationId: C02_lifecycle.inspect
      summary: 'Account access, consent and owner-acknowledged lifecycle: lifecycle.inspect'
      x-contract-operation: C02.lifecycle.inspect
      x-authorization: Current owner or separately authorized lifecycle auditor; withdrawn-account recovery uses only the configured bound recovery
        authority.
      description: Apply C02.lifecycle.inspect semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LifecycleStatusInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LifecycleRequest'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-save-paper:
    post:
      operationId: C03_library.savePaper
      summary: 'Personal library, controlled personalization and consistent entitlements: library.savePaper'
      x-contract-operation: C03.library.savePaper
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.savePaper semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibrarySavePaperInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibrarySavedPaper'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-read-saved-paper:
    post:
      operationId: C03_library.readSavedPaper
      summary: 'Personal library, controlled personalization and consistent entitlements: library.readSavedPaper'
      x-contract-operation: C03.library.readSavedPaper
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.readSavedPaper semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibrarySavedPaperInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibrarySavedPaper'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-list-saved-papers:
    post:
      operationId: C03_library.listSavedPapers
      summary: 'Personal library, controlled personalization and consistent entitlements: library.listSavedPapers'
      x-contract-operation: C03.library.listSavedPapers
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.listSavedPapers semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibraryPaperListInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibraryPaperPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-remove-saved-paper:
    post:
      operationId: C03_library.removeSavedPaper
      summary: 'Personal library, controlled personalization and consistent entitlements: library.removeSavedPaper'
      x-contract-operation: C03.library.removeSavedPaper
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.removeSavedPaper semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibraryRemoveSavedPaperInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-save-search:
    post:
      operationId: C03_library.saveSearch
      summary: 'Personal library, controlled personalization and consistent entitlements: library.saveSearch'
      x-contract-operation: C03.library.saveSearch
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.saveSearch semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibrarySaveSearchInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibrarySavedSearch'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-read-saved-search:
    post:
      operationId: C03_library.readSavedSearch
      summary: 'Personal library, controlled personalization and consistent entitlements: library.readSavedSearch'
      x-contract-operation: C03.library.readSavedSearch
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.readSavedSearch semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibrarySavedSearchInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibrarySavedSearch'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-list-saved-searches:
    post:
      operationId: C03_library.listSavedSearches
      summary: 'Personal library, controlled personalization and consistent entitlements: library.listSavedSearches'
      x-contract-operation: C03.library.listSavedSearches
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.listSavedSearches semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibrarySearchListInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibrarySearchPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-remove-saved-search:
    post:
      operationId: C03_library.removeSavedSearch
      summary: 'Personal library, controlled personalization and consistent entitlements: library.removeSavedSearch'
      x-contract-operation: C03.library.removeSavedSearch
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.removeSavedSearch semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibraryRemoveSavedSearchInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-list-history:
    post:
      operationId: C03_library.listHistory
      summary: 'Personal library, controlled personalization and consistent entitlements: library.listHistory'
      x-contract-operation: C03.library.listHistory
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.listHistory semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibraryHistoryListInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibraryHistoryPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-read-history:
    post:
      operationId: C03_library.readHistory
      summary: 'Personal library, controlled personalization and consistent entitlements: library.readHistory'
      x-contract-operation: C03.library.readHistory
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.readHistory semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibraryHistoryInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibraryHistoryRecord'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/library-clear-history:
    post:
      operationId: C03_library.clearHistory
      summary: 'Personal library, controlled personalization and consistent entitlements: library.clearHistory'
      x-contract-operation: C03.library.clearHistory
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.library.clearHistory semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LibraryClearHistoryInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LibraryClearHistoryResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/settings-read:
    post:
      operationId: C03_settings.read
      summary: 'Personal library, controlled personalization and consistent entitlements: settings.read'
      x-contract-operation: C03.settings.read
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.settings.read semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SettingsReadInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SettingsSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/settings-update:
    post:
      operationId: C03_settings.update
      summary: 'Personal library, controlled personalization and consistent entitlements: settings.update'
      x-contract-operation: C03.settings.update
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.settings.update semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SettingsUpdateInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SettingsSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/settings-update-onboarding:
    post:
      operationId: C03_settings.updateOnboarding
      summary: 'Personal library, controlled personalization and consistent entitlements: settings.updateOnboarding'
      x-contract-operation: C03.settings.updateOnboarding
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.settings.updateOnboarding semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SettingsOnboardingInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SettingsSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/settings-list-suggestions:
    post:
      operationId: C03_settings.listSuggestions
      summary: 'Personal library, controlled personalization and consistent entitlements: settings.listSuggestions'
      x-contract-operation: C03.settings.listSuggestions
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.settings.listSuggestions semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SettingsSuggestionInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SettingsSuggestionPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/settings-list-recent-papers:
    post:
      operationId: C03_settings.listRecentPapers
      summary: 'Personal library, controlled personalization and consistent entitlements: settings.listRecentPapers'
      x-contract-operation: C03.settings.listRecentPapers
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.settings.listRecentPapers semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SettingsRecentInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SettingsRecentPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/settings-resets:
    get:
      operationId: C03_settings.listResets
      x-contract-operation: C03.settings.listResets
      x-authorization: Current full-session owner only.
      security: [{sessionCookie: []}]
      parameters:
      - {name: view, in: query, required: true, schema: {type: string, enum: [outstanding, history]}}
      - {name: limit, in: query, required: true, schema: {type: integer, minimum: 1, maximum: 50}}
      - {name: cursor, in: query, required: false, schema: {type: string, minLength: 1, maxLength: 4096}}
      responses:
        '200': {description: Authoritative bounded read, content: {application/json: {schema: {$ref: '#/components/schemas/SettingsResetPage'}}}}
        '401': {$ref: '#/components/responses/E401'}
        '403': {$ref: '#/components/responses/E403'}
        '409': {$ref: '#/components/responses/E409'}
        '422': {$ref: '#/components/responses/E422'}
        '503': {$ref: '#/components/responses/E503'}
        default: {$ref: '#/components/responses/Edefault'}
  /api/v2/c03/settings-resets/{resetId}:
    get:
      operationId: C03_settings.inspectReset
      x-contract-operation: C03.settings.inspectReset
      x-authorization: Current full-session owner only; foreign and absent are indistinguishable.
      security: [{sessionCookie: []}]
      parameters:
      - {name: resetId, in: path, required: true, schema: {$ref: '#/components/schemas/Id'}}
      responses:
        '200': {description: Authoritative status without new work, content: {application/json: {schema: {$ref: '#/components/schemas/SettingsResetStatus'}}}}
        '401': {$ref: '#/components/responses/E401'}
        '403': {$ref: '#/components/responses/E403'}
        '404': {$ref: '#/components/responses/E404'}
        '422': {$ref: '#/components/responses/E422'}
        '503': {$ref: '#/components/responses/E503'}
        default: {$ref: '#/components/responses/Edefault'}
  /api/v2/c03/settings-prepare-reset:
    post:
      operationId: C03_settings.prepareReset
      x-contract-operation: C03.settings.prepareReset
      summary: Prepare a reauthenticated owner reset confirmation
      security: [{sessionCookie: []}]
      parameters:
      - {name: X-CSRF-Token, in: header, required: true, schema: {type: string, minLength: 1}}
      - {name: Idempotency-Key, in: header, required: true, schema: {$ref: '#/components/schemas/Id'}}
      requestBody:
        required: true
        content:
          application/json:
            schema: {$ref: '#/components/schemas/SettingsResetPrepareInputHttp'}
      responses:
        '200':
          description: Finite owner-bound confirmation without credential material
          content:
            application/json:
              schema: {$ref: '#/components/schemas/SettingsResetConfirmation'}
        default: {$ref: '#/components/responses/Edefault'}
  /api/v2/c03/settings-reset:
    post:
      operationId: C03_settings.reset
      summary: 'Personal library, controlled personalization and consistent entitlements: settings.reset'
      x-contract-operation: C03.settings.reset
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
        Explicit scope confirmation and resolved deletion policy.
      description: Apply C03.settings.reset semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SettingsResetInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SettingsResetResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/usage-inspect:
    post:
      operationId: C03_usage.inspect
      summary: 'Personal library, controlled personalization and consistent entitlements: usage.inspect'
      x-contract-operation: C03.usage.inspect
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.usage.inspect semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UsageInspectInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UsageMeasurePage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/usage-read-plan:
    post:
      operationId: C03_usage.readPlan
      summary: 'Personal library, controlled personalization and consistent entitlements: usage.readPlan'
      x-contract-operation: C03.usage.readPlan
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.usage.readPlan semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UsagePlanInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UsagePlanPresentation'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/usage-grant-entitlement:
    post:
      operationId: C03_usage.grantEntitlement
      summary: 'Personal library, controlled personalization and consistent entitlements: usage.grantEntitlement'
      x-contract-operation: C03.usage.grantEntitlement
      x-authorization: Current authorized application administrator with required MFA; target account is independently checked.
      description: Apply C03.usage.grantEntitlement semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UsageGrantInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UsageEntitlement'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/usage-revoke-entitlement:
    post:
      operationId: C03_usage.revokeEntitlement
      summary: 'Personal library, controlled personalization and consistent entitlements: usage.revokeEntitlement'
      x-contract-operation: C03.usage.revokeEntitlement
      x-authorization: Current authorized application administrator with required MFA.
      description: Apply C03.usage.revokeEntitlement semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UsageRevokeInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UsageEntitlement'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/usage-list-records:
    post:
      operationId: C03_usage.listRecords
      summary: 'Personal library, controlled personalization and consistent entitlements: usage.listRecords'
      x-contract-operation: C03.usage.listRecords
      x-authorization: Current authenticated owner from trusted context; enforce resource ownership and current revocation again at the effect.
      description: Apply C03.usage.listRecords semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UsageRecordsInputHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UsageRecordsPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c04/resolve-paper:
    post:
      operationId: C04_resolvePaper
      summary: 'Canonical corpus, eligible content and projection publication: resolvePaper'
      x-contract-operation: C04.resolvePaper
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C04.resolvePaper semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CorpusResolveHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CorpusIdentity'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c04/read-content:
    post:
      operationId: C04_readContent
      summary: 'Canonical corpus, eligible content and projection publication: readContent'
      x-contract-operation: C04.readContent
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C04.readContent semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CorpusReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CorpusContentRead'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c04/read-asset:
    post:
      operationId: C04_readAsset
      summary: 'Canonical corpus, eligible content and projection publication: readAsset'
      x-contract-operation: C04.readAsset
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C04.readAsset semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CorpusAssetReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CorpusAsset'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c04/accept-corpus-run:
    post:
      operationId: C04_acceptCorpusRun
      summary: 'Canonical corpus, eligible content and projection publication: acceptCorpusRun'
      x-contract-operation: C04.acceptCorpusRun
      x-authorization: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
      description: Apply C04.acceptCorpusRun semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CorpusRunRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '202':
          description: Durably accepted with recoverable dispatch responsibility
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
  /api/v2/c04/read-corpus-run:
    post:
      operationId: C04_readCorpusRun
      summary: 'Canonical corpus, eligible content and projection publication: readCorpusRun'
      x-contract-operation: C04.readCorpusRun
      x-authorization: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
      description: Apply C04.readCorpusRun semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CorpusRunReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CorpusRun'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c04/retry-corpus-run:
    post:
      operationId: C04_retryCorpusRun
      summary: 'Canonical corpus, eligible content and projection publication: retryCorpusRun'
      x-contract-operation: C04.retryCorpusRun
      x-authorization: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
      description: Apply C04.retryCorpusRun semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CorpusRunReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '202':
          description: Durably accepted with recoverable dispatch responsibility
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
  /api/v2/c04/change-source-eligibility:
    post:
      operationId: C04_changeSourceEligibility
      summary: 'Canonical corpus, eligible content and projection publication: changeSourceEligibility'
      x-contract-operation: C04.changeSourceEligibility
      x-authorization: Current authorized corpus-maintenance actor and explicit operation scope; account membership alone is insufficient.
      description: Apply C04.changeSourceEligibility semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CorpusEligibilityChangeHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c05/search:
    post:
      operationId: C05_search
      summary: 'Discovery, citations and completed-search facts: search'
      x-contract-operation: C05.search
      x-authorization: Existing guest-search authority or current authenticated account; no private material, AI-job authority or personal history
        for guests.
      description: Apply C05.search semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SearchRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResponse'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c05/read-citations:
    post:
      operationId: C05_readCitations
      summary: 'Discovery, citations and completed-search facts: readCitations'
      x-contract-operation: C05.readCitations
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C05.readCitations semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CitationRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CitationResponse'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c06/read-assistance-options:
    post:
      operationId: C06_readAssistanceOptions
      summary: 'Paper assistance, glossary and prepared-result boundary: readAssistanceOptions'
      x-contract-operation: C06.readAssistanceOptions
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C06.readAssistanceOptions semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistanceOptionsReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssistanceOptions'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c06/accept-assistance:
    post:
      operationId: C06_acceptAssistance
      summary: 'Paper assistance, glossary and prepared-result boundary: acceptAssistance'
      x-contract-operation: C06.acceptAssistance
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C06.acceptAssistance semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistanceRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '202':
          description: Durably accepted with recoverable dispatch responsibility
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
  /api/v2/c06/read-assistance-job:
    post:
      operationId: C06_readAssistanceJob
      summary: 'Paper assistance, glossary and prepared-result boundary: readAssistanceJob'
      x-contract-operation: C06.readAssistanceJob
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C06.readAssistanceJob semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistanceJobReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c06/read-prepared-assistance:
    post:
      operationId: C06_readPreparedAssistance
      summary: 'Paper assistance, glossary and prepared-result boundary: readPreparedAssistance'
      x-contract-operation: C06.readPreparedAssistance
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C06.readPreparedAssistance semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistanceResultRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssistanceResultRead'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c06/read-glossary:
    post:
      operationId: C06_readGlossary
      summary: 'Paper assistance, glossary and prepared-result boundary: readGlossary'
      x-contract-operation: C06.readGlossary
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C06.readGlossary semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistanceGlossaryReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssistanceGlossary'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c06/replace-glossary:
    post:
      operationId: C06_replaceGlossary
      summary: 'Paper assistance, glossary and prepared-result boundary: replaceGlossary'
      x-contract-operation: C06.replaceGlossary
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C06.replaceGlossary semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistanceGlossaryWriteHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssistanceGlossary'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/create-research-context:
    post:
      operationId: C07_createResearchContext
      summary: 'Private research, durable drafts and immutable novelty artifacts: createResearchContext'
      x-contract-operation: C07.createResearchContext
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.createResearchContext semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchContextCreateHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchContext'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/create-research-session:
    post:
      operationId: C07_createResearchSession
      summary: 'Private research, durable drafts and immutable novelty artifacts: createResearchSession'
      x-contract-operation: C07.createResearchSession
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.createResearchSession semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchSessionCreateHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchSession'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/read-research-session:
    post:
      operationId: C07_readResearchSession
      summary: 'Private research, durable drafts and immutable novelty artifacts: readResearchSession'
      x-contract-operation: C07.readResearchSession
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.readResearchSession semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchSessionReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchSession'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/list-research-sessions:
    post:
      operationId: C07_listResearchSessions
      summary: 'Private research, durable drafts and immutable novelty artifacts: listResearchSessions'
      x-contract-operation: C07.listResearchSessions
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.listResearchSessions semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchSessionListHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchSessions'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/delete-research-sessions:
    post:
      operationId: C07_deleteResearchSessions
      summary: 'Private research, durable drafts and immutable novelty artifacts: deleteResearchSessions'
      x-contract-operation: C07.deleteResearchSessions
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.deleteResearchSessions semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchDeleteHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchDeletion'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/begin-private-attachment:
    post:
      operationId: C07_beginPrivateAttachment
      summary: 'Private research, durable drafts and immutable novelty artifacts: beginPrivateAttachment'
      x-contract-operation: C07.beginPrivateAttachment
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.beginPrivateAttachment semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchAttachmentStartHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchUploadPermit'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/finish-private-attachment:
    post:
      operationId: C07_finishPrivateAttachment
      summary: 'Private research, durable drafts and immutable novelty artifacts: finishPrivateAttachment'
      x-contract-operation: C07.finishPrivateAttachment
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.finishPrivateAttachment semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchAttachmentFinishHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchAttachment'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/read-private-attachment:
    post:
      operationId: C07_readPrivateAttachment
      summary: 'Private research, durable drafts and immutable novelty artifacts: readPrivateAttachment'
      x-contract-operation: C07.readPrivateAttachment
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.readPrivateAttachment semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchAttachmentReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchAttachment'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/read-private-asset:
    post:
      operationId: C07_readPrivateAsset
      summary: 'Private research, durable drafts and immutable novelty artifacts: readPrivateAsset'
      x-contract-operation: C07.readPrivateAsset
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.readPrivateAsset semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchPrivateAssetReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchPrivateAsset'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/save-draft:
    post:
      operationId: C07_saveDraft
      summary: 'Private research, durable drafts and immutable novelty artifacts: saveDraft'
      x-contract-operation: C07.saveDraft
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.saveDraft semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DraftWriteHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DraftWriteResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/restore-draft:
    post:
      operationId: C07_restoreDraft
      summary: 'Private research, durable drafts and immutable novelty artifacts: restoreDraft'
      x-contract-operation: C07.restoreDraft
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.restoreDraft semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DraftReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DraftRecovery'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/discard-draft:
    post:
      operationId: C07_discardDraft
      summary: 'Private research, durable drafts and immutable novelty artifacts: discardDraft'
      x-contract-operation: C07.discardDraft
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.discardDraft semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DraftDiscardHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Ack'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/accept-research-turn:
    post:
      operationId: C07_acceptResearchTurn
      summary: 'Private research, durable drafts and immutable novelty artifacts: acceptResearchTurn'
      x-contract-operation: C07.acceptResearchTurn
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.acceptResearchTurn semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchTurnRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '202':
          description: Durably accepted with recoverable dispatch responsibility
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
  /api/v2/c07/read-research-turn:
    post:
      operationId: C07_readResearchTurn
      summary: 'Private research, durable drafts and immutable novelty artifacts: readResearchTurn'
      x-contract-operation: C07.readResearchTurn
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.readResearchTurn semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchTurnReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchTurn'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/accept-novelty-analysis:
    post:
      operationId: C07_acceptNoveltyAnalysis
      summary: 'Private research, durable drafts and immutable novelty artifacts: acceptNoveltyAnalysis'
      x-contract-operation: C07.acceptNoveltyAnalysis
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.acceptNoveltyAnalysis semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchNoveltyRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '202':
          description: Durably accepted with recoverable dispatch responsibility
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
  /api/v2/c07/accept-novelty-discussion:
    post:
      operationId: C07_acceptNoveltyDiscussion
      summary: 'Private research, durable drafts and immutable novelty artifacts: acceptNoveltyDiscussion'
      x-contract-operation: C07.acceptNoveltyDiscussion
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.acceptNoveltyDiscussion semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchNoveltyDiscussionHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '202':
          description: Durably accepted with recoverable dispatch responsibility
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
  /api/v2/c07/read-research-job:
    post:
      operationId: C07_readResearchJob
      summary: 'Private research, durable drafts and immutable novelty artifacts: readResearchJob'
      x-contract-operation: C07.readResearchJob
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.readResearchJob semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchJobReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/cancel-novelty-analysis:
    post:
      operationId: C07_cancelNoveltyAnalysis
      summary: 'Private research, durable drafts and immutable novelty artifacts: cancelNoveltyAnalysis'
      x-contract-operation: C07.cancelNoveltyAnalysis
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.cancelNoveltyAnalysis semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchJobReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c07/read-research-artifact:
    post:
      operationId: C07_readResearchArtifact
      summary: 'Private research, durable drafts and immutable novelty artifacts: readResearchArtifact'
      x-contract-operation: C07.readResearchArtifact
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C07.readResearchArtifact semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResearchArtifactReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResearchArtifactResponse'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c08/upsert-topic-subscription:
    post:
      operationId: C08_upsertTopicSubscription
      summary: 'Topics, content windows and recoverable digest delivery: upsertTopicSubscription'
      x-contract-operation: C08.upsertTopicSubscription
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C08.upsertTopicSubscription semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DigestSubscriptionWriteHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DigestSubscription'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c08/list-topic-subscriptions:
    post:
      operationId: C08_listTopicSubscriptions
      summary: 'Topics, content windows and recoverable digest delivery: listTopicSubscriptions'
      x-contract-operation: C08.listTopicSubscriptions
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C08.listTopicSubscriptions semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DigestSubscriptionsReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DigestSubscriptions'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c08/unfollow-topic:
    post:
      operationId: C08_unfollowTopic
      summary: 'Topics, content windows and recoverable digest delivery: unfollowTopic'
      x-contract-operation: C08.unfollowTopic
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C08.unfollowTopic semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DigestSubscriptionReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DigestSubscription'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c08/read-digest-delivery:
    post:
      operationId: C08_readDigestDelivery
      summary: 'Topics, content windows and recoverable digest delivery: readDigestDelivery'
      x-contract-operation: C08.readDigestDelivery
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C08.readDigestDelivery semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DigestDeliveryReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DigestDelivery'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c08/unsubscribe-digest-token:
    post:
      operationId: C08_unsubscribeDigestToken
      summary: 'Topics, content windows and recoverable digest delivery: unsubscribeDigestToken'
      x-contract-operation: C08.unsubscribeDigestToken
      x-authorization: Valid purpose-scoped signed unsubscribe token; no broader account authority.
      description: Apply C08.unsubscribeDigestToken semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - {}
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DigestUnsubscribeHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DigestUnsubscribeResult'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/configure-notion-connection:
    post:
      operationId: C09_configureNotionConnection
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: configureNotionConnection'
      x-contract-operation: C09.configureNotionConnection
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.configureNotionConnection semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportConnectionConfigureHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportConnection'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/read-notion-connection:
    post:
      operationId: C09_readNotionConnection
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: readNotionConnection'
      x-contract-operation: C09.readNotionConnection
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.readNotionConnection semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportConnectionReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportConnection'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/disconnect-notion:
    post:
      operationId: C09_disconnectNotion
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: disconnectNotion'
      x-contract-operation: C09.disconnectNotion
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.disconnectNotion semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportConnectionReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportConnection'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/list-export-destinations:
    post:
      operationId: C09_listExportDestinations
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: listExportDestinations'
      x-contract-operation: C09.listExportDestinations
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.listExportDestinations semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportConnectionReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportDestinations'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/prepare-export-preview:
    post:
      operationId: C09_prepareExportPreview
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: prepareExportPreview'
      x-contract-operation: C09.prepareExportPreview
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.prepareExportPreview semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportPreviewRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportPreview'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/approve-export-preview:
    post:
      operationId: C09_approveExportPreview
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: approveExportPreview'
      x-contract-operation: C09.approveExportPreview
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.approveExportPreview semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportApprovalRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportApproval'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/execute-approved-export:
    post:
      operationId: C09_executeApprovedExport
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: executeApprovedExport'
      x-contract-operation: C09.executeApprovedExport
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.executeApprovedExport semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportExecuteHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportEffect'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/read-export-effect:
    post:
      operationId: C09_readExportEffect
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: readExportEffect'
      x-contract-operation: C09.readExportEffect
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.readExportEffect semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportEffectReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportEffect'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/cancel-export-approval:
    post:
      operationId: C09_cancelExportApproval
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: cancelExportApproval'
      x-contract-operation: C09.cancelExportApproval
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.cancelExportApproval semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportCancelHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportApproval'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/list-export-history:
    post:
      operationId: C09_listExportHistory
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: listExportHistory'
      x-contract-operation: C09.listExportHistory
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.listExportHistory semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportHistoryListHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportHistoryPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c09/settle-export-effect:
    post:
      operationId: C09_settleExportEffect
      summary: 'Owner-approved Notion export and uncertain-effect reconciliation: settleExportEffect'
      x-contract-operation: C09.settleExportEffect
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C09.settleExportEffect semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportSettleHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportEffect'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c11/read-dashboard:
    post:
      operationId: C11_readDashboard
      summary: 'Privacy-aware operations and domain recovery: readDashboard'
      x-contract-operation: C11.readDashboard
      x-authorization: administrator with current MFA
      description: Apply C11.readDashboard semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OpsQueryHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OpsObservationPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c11/list-incidents:
    post:
      operationId: C11_listIncidents
      summary: 'Privacy-aware operations and domain recovery: listIncidents'
      x-contract-operation: C11.listIncidents
      x-authorization: administrator with current MFA
      description: Apply C11.listIncidents semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OpsQueryHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OpsIncidentPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c11/request-recovery:
    post:
      operationId: C11_requestRecovery
      summary: 'Privacy-aware operations and domain recovery: requestRecovery'
      x-contract-operation: C11.requestRecovery
      x-authorization: administrator with current MFA plus operation-specific grant
      description: Apply C11.requestRecovery semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OpsRecoveryRequestHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '202':
          description: Durably accepted with recoverable dispatch responsibility
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobReceipt'
  /api/v2/session:
    get:
      operationId: sessionBootstrap
      description: Optional authentication inspection and CSRF bootstrap; anonymous cannot obtain another account identity.
      parameters: []
      responses:
        '200':
          description: Optional authentication inspection and CSRF bootstrap; anonymous cannot obtain another account identity.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SessionBootstrap'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
      security:
      - {}
      - sessionCookie: []
  /api/v2/capabilities:
    get:
      operationId: capabilityCatalog
      description: Public safe retained-choice vocabulary; no private operational evidence or new capabilities.
      parameters: []
      responses:
        '200':
          description: Public safe retained-choice vocabulary; no private operational evidence or new capabilities.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CapabilityCatalog'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
      security: []
  /api/v2/jobs/{jobId}:
    get:
      operationId: jobSnapshot
      description: Current owner-authorized operation snapshot; registry resolves the actual operation owner; never starts work.
      parameters:
      - name: jobId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      responses:
        '200':
          description: Current owner-authorized operation snapshot; registry resolves the actual operation owner; never starts work.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/jobs/{jobId}/result:
    get:
      operationId: preparedJobRead
      description: Dispatch to the recorded operation owner; full prepared result read. Pending/failed/expired dispositions are typed; no new
        work.
      parameters:
      - name: jobId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      responses:
        '200':
          description: Dispatch to the recorded operation owner; full prepared result read. Pending/failed/expired dispositions are typed; no
            new work.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PreparedJobRead'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/jobs/{jobId}/events:
    get:
      operationId: jobEvents
      description: SSE snapshot/reset events. Current owner authorization at admission and during delivery. Replay semantics above.
      parameters:
      - name: jobId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      - name: Last-Event-ID
        in: header
        required: false
        schema:
          type: string
          pattern: ^[0-9]+$
      - name: afterSeq
        in: query
        required: false
        schema:
          type: integer
          minimum: 0
      responses:
        '200':
          description: UTF-8 SSE, id=seq, event=snapshot/reset, data=JobSnapshot; real newlines and blank event terminator.
          headers:
            Cache-Control:
              schema:
                const: no-store
          content:
            text/event-stream:
              schema:
                type: string
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/papers/{paperId}/versions/{versionId}/assets/{assetId}:
    get:
      operationId: deliverPaperidAsset
      description: Authorized byte delivery; public corpus and private attachment namespaces never interchange. Validate source/owner on every
        delivery.
      parameters:
      - name: paperId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      - name: versionId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      - name: assetId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      responses:
        '200':
          description: Validated media bytes; MIME is derived from approved metadata; unsafe types forced attachment, nosniff; bounded/range behavior
            follows approved profile.
          headers:
            Cache-Control:
              schema:
                const: no-store
            X-Content-Type-Options:
              schema:
                const: nosniff
          content:
            application/octet-stream:
              schema:
                type: string
                format: binary
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/attachments/{attachmentId}/assets/{assetId}:
    get:
      operationId: deliverAttachmentidAsset
      description: Authorized byte delivery; public corpus and private attachment namespaces never interchange. Validate source/owner on every
        delivery.
      parameters:
      - name: attachmentId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      - name: assetId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      responses:
        '200':
          description: Validated media bytes; MIME is derived from approved metadata; unsafe types forced attachment, nosniff; bounded/range behavior
            follows approved profile.
          headers:
            Cache-Control:
              schema:
                const: no-store
            X-Content-Type-Options:
              schema:
                const: nosniff
          content:
            application/octet-stream:
              schema:
                type: string
                format: binary
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/private-uploads/{uploadId}/content:
    put:
      operationId: uploadPrivateBytes
      description: Use the current owner-bound upload permit, expected digest and expiry. Stream into quarantined private storage under finite
        policy limits; never public. Repeat same bytes/digest recovers same upload; changed bytes conflict. Finalization validates before extraction.
      parameters:
      - name: uploadId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      - name: Content-Length
        in: header
        required: true
        schema:
          type: integer
          minimum: 0
      requestBody:
        required: true
        content:
          application/octet-stream:
            schema:
              type: string
              format: binary
      responses:
        '200':
          description: Bytes acknowledged privately; finalization still required
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UploadAck'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/identity/{provider}/callback:
    get:
      operationId: identityCallback
      description: Google/ORCID one-use callback. Verify pre-established state, redirect binding, issuer/audience/nonce and PKCE as the approved
        provider profile requires; never trust callback email as an account link. Redirect only to stored allowed return target; do not log codes.
        Exactly one of code/error is required. An error callback is never authenticated success.
      parameters:
      - name: provider
        in: path
        required: true
        schema:
          type: string
          enum:
          - google
          - orcid
      - name: state
        in: query
        required: true
        schema:
          type: string
          minLength: 1
          x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.
      - name: code
        in: query
        required: false
        schema:
          type: string
          minLength: 1
          x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.
      - name: error
        in: query
        required: false
        schema:
          type: string
          minLength: 1
          x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.
      responses:
        '200':
          description: Google/ORCID one-use callback. Verify pre-established state, redirect binding, issuer/audience/nonce and PKCE as the approved
            provider profile requires; never trust callback email as an account link. Redirect only to stored allowed return target; do not log
            codes.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SessionBootstrap'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
        '303':
          description: Verified callback outcome and rotated session cookie or safe unresolved-link challenge; allowed local return target only.
          headers:
            Location:
              schema:
                type: string
      security: []
  /api/v2/c06/read-assistance-history:
    post:
      operationId: C06_readAssistanceHistory
      summary: C06.readAssistanceHistory
      x-contract-operation: C06.readAssistanceHistory
      x-authorization: Current authenticated account; server derives owner from trusted context and checks every referenced resource/context.
      description: Apply C06.readAssistanceJob semantic rules. Derive internal context server-side; never accept it in this body.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AssistanceHistoryReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AssistanceHistoryPage'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /api/v2/c03/usage-read-assignment:
    post:
      operationId: C03_usage_readAssignment
      summary: C03.usage.readAssignment
      x-contract-operation: C03.usage.readAssignment
      x-authorization: Current authorized application administrator with required MFA; target account is independently checked.
      description: Current administrator with required MFA; accountId is target, never caller authority. Ordinary self-plan read grants no access.
      security:
      - sessionCookie: []
      parameters:
      - name: X-CSRF-Token
        in: header
        required: true
        schema:
          type: string
          minLength: 1
        description: Bound to current session or anonymous bootstrap; verify Origin too.
      - name: Idempotency-Key
        in: header
        required: true
        schema:
          $ref: '#/components/schemas/Id'
        description: Required for mutations; on pure queries it does not create a persistent mutation.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UsageAssignmentReadHttp'
      responses:
        '200':
          description: Committed outcome or explicitly discriminated pending/conflict/unavailable result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UsageAssignmentSnapshot'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
components:
  securitySchemes:
    sessionCookie:
      type: apiKey
      in: cookie
      name: session_id
  schemas:
    Id:
      type: string
      minLength: 1
      maxLength: 128
    Revision:
      type: string
      minLength: 1
      maxLength: 128
    Time:
      type: string
      format: date-time
    Hash:
      type: string
      pattern: ^[a-f0-9]{64}$
    PolicyRef:
      type: object
      properties:
        policyId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
      required:
      - policyId
      - revision
      additionalProperties: false
    Error:
      type: object
      properties:
        code:
          type: string
          enum:
          - APPROVAL_REQUIRED
          - CANCELLED
          - CAPACITY_EXHAUSTED
          - CONFLICT
          - CONSENT_REVOKED
          - DEADLINE_EXCEEDED
          - DEPENDENCY_UNAVAILABLE
          - EXPIRED
          - FORBIDDEN
          - IDEMPOTENCY_CONFLICT
          - INCOMPATIBLE
          - INCOMPATIBLE_VERSION
          - INTERNAL_ERROR
          - INVALID_ARGUMENT
          - INVALID_CONTENT
          - INVALID_INPUT
          - INVALID_TOKEN
          - MFA_REQUIRED
          - NOT_FOUND
          - NOT_READY
          - OUTCOME_UNKNOWN
          - POLICY_DENIED
          - POLICY_UNRESOLVED
          - QUOTA_EXCEEDED
          - RATE_LIMITED
          - SNAPSHOT_EXPIRED
          - SOURCE_INELIGIBLE
          - STALE_REVISION
          - UNAUTHENTICATED
          - UNKNOWN_OUTCOME
        requestId:
          $ref: '#/components/schemas/Id'
        retryable:
          type: boolean
        messageKey:
          $ref: '#/components/schemas/Id'
        retryAfterSeconds:
          type: integer
          minimum: 0
        details:
          type: object
          properties:
            fieldNames:
              type: array
              items:
                $ref: '#/components/schemas/Id'
              x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
          required:
          - fieldNames
          additionalProperties: false
      required:
      - code
      - requestId
      - retryable
      - messageKey
      additionalProperties: false
    PaperRef:
      type: object
      properties:
        paperId:
          $ref: '#/components/schemas/Id'
        versionId:
          $ref: '#/components/schemas/Id'
        eligibilityRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - paperId
      - versionId
      - eligibilityRevision
      additionalProperties: false
    ResultRef:
      type: object
      properties:
        resultId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        contentHash:
          $ref: '#/components/schemas/Hash'
        mediaType:
          type: string
          minLength: 1
          x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.
      required:
      - resultId
      - revision
      - contentHash
      - mediaType
      additionalProperties: false
    PageRequest:
      type: object
      properties:
        cursor:
          anyOf:
          - type: string
            minLength: 1
            x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.
          - type: 'null'
        limit:
          type: integer
          minimum: 1
          x-limit-policy: bounded by selected admission policy
      required: []
      additionalProperties: false
    PageInfo:
      type: object
      properties:
        nextCursor:
          anyOf:
          - type: string
            minLength: 1
            x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.
          - type: 'null'
        snapshotRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - nextCursor
      - snapshotRevision
      additionalProperties: false
    Ack:
      type: object
      properties:
        resourceId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        requestId:
          $ref: '#/components/schemas/Id'
      required:
      - resourceId
      - revision
      - requestId
      additionalProperties: false
    Progress:
      oneOf:
      - type: object
        properties:
          mode:
            const: indeterminate
        required:
        - mode
        additionalProperties: false
      - type: object
        properties:
          mode:
            const: determinate
          current:
            type: integer
            minimum: 0
          total:
            type: integer
            minimum: 1
        required:
        - mode
        - current
        - total
        additionalProperties: false
    JobReceipt:
      type: object
      properties:
        jobId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        seq:
          type: integer
          minimum: 0
        state:
          type: string
          enum:
          - accepted
          - running
          - cancel_requested
          - succeeded
          - failed
          - cancelled
        requestId:
          $ref: '#/components/schemas/Id'
        acceptedAt:
          $ref: '#/components/schemas/Time'
      required:
      - jobId
      - revision
      - seq
      - state
      - requestId
      - acceptedAt
      additionalProperties: false
    JobSnapshot:
      type: object
      properties:
        jobId:
          $ref: '#/components/schemas/Id'
        kind:
          $ref: '#/components/schemas/Id'
        state:
          type: string
          enum:
          - accepted
          - running
          - cancel_requested
          - succeeded
          - failed
          - cancelled
        revision:
          $ref: '#/components/schemas/Revision'
        seq:
          type: integer
          minimum: 0
        ownerId:
          $ref: '#/components/schemas/Id'
        progress:
          $ref: '#/components/schemas/Progress'
        result:
          anyOf:
          - $ref: '#/components/schemas/ResultRef'
          - type: 'null'
        error:
          anyOf:
          - $ref: '#/components/schemas/Error'
          - type: 'null'
        acceptedAt:
          $ref: '#/components/schemas/Time'
      required:
      - jobId
      - kind
      - state
      - revision
      - seq
      - ownerId
      - progress
      - result
      - error
      - acceptedAt
      additionalProperties: false
      allOf:
      - if:
          properties:
            state:
              const: succeeded
        then:
          properties:
            result:
              $ref: '#/components/schemas/ResultRef'
            error:
              type: 'null'
      - if:
          properties:
            state:
              const: failed
        then:
          properties:
            error:
              $ref: '#/components/schemas/Error'
            result:
              type: 'null'
      - if:
          properties:
            state:
              enum:
              - accepted
              - running
              - cancel_requested
              - cancelled
        then:
          properties:
            result:
              type: 'null'
    OpsObservation:
      type: object
      properties:
        observationId:
          $ref: '#/components/schemas/Id'
        capability:
          $ref: '#/components/schemas/Id'
        component:
          $ref: '#/components/schemas/Id'
        observedAt:
          $ref: '#/components/schemas/Time'
        revision:
          $ref: '#/components/schemas/Revision'
        status:
          type: string
          enum:
          - available
          - degraded
          - unavailable
          - unknown
        evidenceRef:
          $ref: '#/components/schemas/Id'
        limitations:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
      required:
      - observationId
      - capability
      - component
      - observedAt
      - revision
      - status
      - evidenceRef
      - limitations
      additionalProperties: false
    OpsObservationPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/OpsObservation'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
        page:
          $ref: '#/components/schemas/PageInfo'
      required:
      - items
      - page
      additionalProperties: false
    OpsIncident:
      type: object
      properties:
        incidentId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        capabilities:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
        correlationIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
        state:
          type: string
          enum:
          - open
          - investigating
          - recovering
          - resolved
        evidenceRefs:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
      required:
      - incidentId
      - revision
      - capabilities
      - correlationIds
      - state
      - evidenceRefs
      additionalProperties: false
    OpsIncidentPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/OpsIncident'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
        page:
          $ref: '#/components/schemas/PageInfo'
      required:
      - items
      - page
      additionalProperties: false
    LibraryFilter:
      type: object
      properties:
        filterId:
          $ref: '#/components/schemas/Id'
        operatorId:
          $ref: '#/components/schemas/Id'
        values:
          type: array
          items:
            oneOf:
            - type: string
              x-policy-bound: search filter value
            - type: integer
            - type: boolean
          x-policy-bound: search vocabulary entry and approved input policy
      required:
      - filterId
      - operatorId
      - values
      additionalProperties: false
    LibraryQueryContext:
      type: object
      properties:
        query:
          type: string
          minLength: 1
          x-policy-bound: search query size/input policy
          description: Bound by the named approved policy before processing.
        modeId:
          $ref: '#/components/schemas/Id'
        orderId:
          $ref: '#/components/schemas/Id'
        filters:
          type: array
          items:
            $ref: '#/components/schemas/LibraryFilter'
          x-policy-bound: retained filter vocabulary and search policy
        vocabularyRevision:
          $ref: '#/components/schemas/Revision'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - query
      - modeId
      - orderId
      - filters
      - vocabularyRevision
      - policyRef
      additionalProperties: false
      description: Canonical submitted query/refinement context shared by search, saved queries and history. Unknown or unsupported vocabulary
        IDs are rejected; no arbitrary query-engine syntax is accepted through filters.
    HostPaperReturnContext:
      type: object
      properties:
        kind:
          const: paper
        paper:
          $ref: '#/components/schemas/PaperRef'
        anchorId:
          $ref: '#/components/schemas/Id'
      required:
      - kind
      - paper
      additionalProperties: false
    HostSearchReturnContext:
      type: object
      properties:
        kind:
          const: search
        queryContext:
          $ref: '#/components/schemas/LibraryQueryContext'
        resultWindowId:
          $ref: '#/components/schemas/Id'
        resultPosition:
          type: integer
          minimum: 0
      required:
      - kind
      - queryContext
      - resultWindowId
      additionalProperties: false
    HostRouteReturnContext:
      type: object
      properties:
        kind:
          const: route
        routeId:
          $ref: '#/components/schemas/Id'
      required:
      - kind
      - routeId
      additionalProperties: false
    HostReturnContext:
      oneOf:
      - $ref: '#/components/schemas/HostPaperReturnContext'
      - $ref: '#/components/schemas/HostSearchReturnContext'
      - $ref: '#/components/schemas/HostRouteReturnContext'
    HostNavigationItem:
      type: object
      properties:
        routeId:
          $ref: '#/components/schemas/Id'
        titleKey:
          $ref: '#/components/schemas/Id'
        path:
          type: string
          minLength: 1
          x-policy-bound: registered relative route policy
          description: Bound by the named approved policy before processing.
        capabilityId:
          $ref: '#/components/schemas/Id'
        available:
          type: boolean
        reasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - routeId
      - titleKey
      - path
      - capabilityId
      - available
      additionalProperties: false
    HostNavigationResult:
      type: object
      properties:
        manifestRevision:
          $ref: '#/components/schemas/Revision'
        authorityRevision:
          $ref: '#/components/schemas/Revision'
        items:
          type: array
          items:
            $ref: '#/components/schemas/HostNavigationItem'
          x-policy-bound: authorized compiled navigation manifest
        resolvedRouteId:
          $ref: '#/components/schemas/Id'
        returnContext:
          $ref: '#/components/schemas/HostReturnContext'
        clearPriorOwnerState:
          type: boolean
      required:
      - manifestRevision
      - authorityRevision
      - items
      - resolvedRouteId
      - clearPriorOwnerState
      additionalProperties: false
    AccessSecret:
      type: string
      minLength: 1
      x-policy-bound: credential input policy
      description: Sensitive proof/credential; never logged, reflected or placed in a URL.
      writeOnly: true
      x-sensitive: true
    AccessEmail:
      type: string
      format: email
      x-policy-bound: email normalization and size policy
    AccessPublicSession:
      type: object
      properties:
        sessionId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        authorityRevision:
          $ref: '#/components/schemas/Revision'
        verified:
          type: boolean
        authenticationLevel:
          type: string
          enum:
          - primary
          - mfa
        expiresAt:
          $ref: '#/components/schemas/Time'
      required:
      - sessionId
      - accountId
      - authorityRevision
      - verified
      - authenticationLevel
      additionalProperties: false
    AccessAnonymousSession:
      type: object
      properties:
        state:
          const: anonymous
        requestId:
          $ref: '#/components/schemas/Id'
      required:
      - state
      - requestId
      additionalProperties: false
    AccessKnownSession:
      type: object
      properties:
        state:
          const: authenticated
        session:
          $ref: '#/components/schemas/AccessPublicSession'
      required:
      - state
      - session
      additionalProperties: false
    AccessSessionStatus:
      oneOf:
      - $ref: '#/components/schemas/AccessAnonymousSession'
      - $ref: '#/components/schemas/AccessKnownSession'
      - $ref: '#/components/schemas/AccessMfaContinuation'
    AccessChallengeDelivery:
      type: object
      properties:
        requestId:
          $ref: '#/components/schemas/Id'
        acknowledgement:
          const: accepted
        messageKey:
          $ref: '#/components/schemas/Id'
      required:
      - requestId
      - acknowledgement
      - messageKey
      additionalProperties: false
      description: Existence-neutral public acknowledgement. It does not expose account existence, challenge secrets or recipient-specific delivery
        facts.
    AccessChallengeProof:
      type: object
      properties:
        challengeId:
          $ref: '#/components/schemas/Id'
        proof:
          $ref: '#/components/schemas/AccessSecret'
        flowBinding:
          $ref: '#/components/schemas/Id'
      required:
      - challengeId
      - proof
      - flowBinding
      additionalProperties: false
    AccessMfaContinuation:
      type: object
      properties:
        state:
          const: mfa_required
        challengeId:
          $ref: '#/components/schemas/Id'
        flowBinding:
          $ref: '#/components/schemas/Id'
        expiresAt:
          $ref: '#/components/schemas/Time'
      required:
      - state
      - challengeId
      - flowBinding
      - expiresAt
      additionalProperties: false
    AccessLoginResult:
      oneOf:
      - $ref: '#/components/schemas/AccessKnownSession'
      - $ref: '#/components/schemas/AccessMfaContinuation'
    AccessProviderRedirect:
      type: object
      properties:
        flowId:
          $ref: '#/components/schemas/Id'
        provider:
          type: string
          enum:
          - google
          - orcid
        authorizationUrl:
          type: string
          format: uri
          x-policy-bound: allowlisted provider redirect length
        expiresAt:
          $ref: '#/components/schemas/Time'
      required:
      - flowId
      - provider
      - authorizationUrl
      - expiresAt
      additionalProperties: false
      description: URL generated from configured provider and registered callback binding; never copied from a caller-controlled destination.
    AccessIdentityLink:
      type: object
      properties:
        identityLinkId:
          $ref: '#/components/schemas/Id'
        provider:
          type: string
          enum:
          - google
          - orcid
        providerSubject:
          type: string
          minLength: 1
          x-policy-bound: provider subject policy
          description: Bound by the named approved policy before processing.
        revision:
          $ref: '#/components/schemas/Revision'
        profileAvailable:
          type: boolean
      required:
      - identityLinkId
      - provider
      - providerSubject
      - revision
      - profileAvailable
      additionalProperties: false
    AccessIdentityPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/AccessIdentityLink'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    AccessOrcidWork:
      type: object
      properties:
        sourceId:
          $ref: '#/components/schemas/Id'
        title:
          type: string
          minLength: 1
          x-policy-bound: ORCID work-title policy
          description: Bound by the named approved policy before processing.
        externalIdentifiers:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-bound: ORCID external identifier policy
            description: Bound by the named approved policy before processing.
          x-policy-bound: ORCID work identifier policy
        sourceUrl:
          type: string
          format: uri
          x-policy-bound: eligible profile source URL policy
      required:
      - sourceId
      - title
      - externalIdentifiers
      additionalProperties: false
    AccessOrcidProfile:
      type: object
      properties:
        identityLinkId:
          $ref: '#/components/schemas/Id'
        subject:
          type: string
          minLength: 1
          x-policy-bound: ORCID subject policy
          description: Bound by the named approved policy before processing.
        revision:
          $ref: '#/components/schemas/Revision'
        provenance:
          type: string
          minLength: 1
          x-policy-bound: profile provenance policy
          description: Bound by the named approved policy before processing.
        displayName:
          type: string
          minLength: 1
          x-policy-bound: profile display-name policy
          description: Bound by the named approved policy before processing.
        works:
          type: array
          items:
            $ref: '#/components/schemas/AccessOrcidWork'
          x-policy-bound: approved ORCID enrichment count policy
        coverage:
          type: string
          enum:
          - complete
          - partial
          - unavailable
      required:
      - identityLinkId
      - subject
      - revision
      - provenance
      - works
      - coverage
      additionalProperties: false
    AccessMfaEnrollment:
      type: object
      properties:
        enrollmentId:
          $ref: '#/components/schemas/Id'
        deliveryReference:
          $ref: '#/components/schemas/Id'
        expiresAt:
          $ref: '#/components/schemas/Time'
        nextAction:
          const: confirm_factor
      required:
      - enrollmentId
      - deliveryReference
      - expiresAt
      - nextAction
      additionalProperties: false
      description: Protected one-time enrollment delivery is separate from ordinary JSON/log output; no factor seed or recovery code is returned
        here.
    AccessEnrollmentSecret:
      type: string
      minLength: 1
      x-policy-bound: protected MFA enrollment-material policy
      description: Secret output permitted only by the protected single-use enrollment-material response; redact entirely from diagnostics and
        do not cache or persist in the client.
      readOnly: true
      x-sensitive: true
      x-protected-one-time: true
    AccessMfaMaterial:
      type: object
      properties:
        enrollmentId:
          $ref: '#/components/schemas/Id'
        seed:
          $ref: '#/components/schemas/AccessEnrollmentSecret'
        provisioningUri:
          $ref: '#/components/schemas/AccessEnrollmentSecret'
        recoveryCodes:
          type: array
          items:
            $ref: '#/components/schemas/AccessEnrollmentSecret'
          x-policy-bound: approved MFA recovery-code count/size policy
          uniqueItems: true
        expiresAt:
          $ref: '#/components/schemas/Time'
      required:
      - enrollmentId
      - seed
      - provisioningUri
      - recoveryCodes
      - expiresAt
      additionalProperties: false
      description: 'Dedicated protected response only. provisioningUri encodes this enrollment''s seed and account/issuer binding and may be rendered
        as a QR locally, without an external QR service. Recovery codes remain unusable before successful enrollment confirmation. The trusted
        HTTP adapter applies Cache-Control: no-store and excludes the response from logging, tracing, generic result caches and persisted client
        storage.'
    AccessProfileValue:
      oneOf:
      - type: string
        x-policy-bound: declared profile field policy
      - type: boolean
      - type: array
        items:
          $ref: '#/components/schemas/Id'
        x-policy-bound: declared profile multi-choice policy
        uniqueItems: true
      - type: 'null'
    AccessProfileFieldDefinition:
      type: object
      properties:
        fieldId:
          $ref: '#/components/schemas/Id'
        labelKey:
          $ref: '#/components/schemas/Id'
        valueKind:
          type: string
          enum:
          - text
          - boolean
          - single_choice
          - multi_choice
        mutable:
          type: boolean
        nullable:
          type: boolean
        choiceIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-policy-bound: retained profile choice vocabulary
          uniqueItems: true
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - fieldId
      - labelKey
      - valueKind
      - mutable
      - nullable
      - choiceIds
      - policyRef
      additionalProperties: false
    AccessProfileField:
      type: object
      properties:
        fieldId:
          $ref: '#/components/schemas/Id'
        value:
          $ref: '#/components/schemas/AccessProfileValue'
      required:
      - fieldId
      - value
      additionalProperties: false
    AccessLifecyclePrepareInputHttp:
      type: object
      properties:
        currentProof: {$ref: '#/components/schemas/AccessSecret'}
        action: {type: string, enum: [withdraw, erase]}
        expectedRevision: {$ref: '#/components/schemas/Revision'}
        policyRef: {$ref: '#/components/schemas/PolicyRef'}
      required: [currentProof, action, expectedRevision, policyRef]
      additionalProperties: false
    AccessLifecycleConfirmation:
      type: object
      properties:
        confirmationRef: {$ref: '#/components/schemas/Id'}
        action: {type: string, enum: [withdraw, erase]}
        revision: {$ref: '#/components/schemas/Revision'}
        expiresAt: {$ref: '#/components/schemas/Time'}
      required: [confirmationRef, action, revision, expiresAt]
      additionalProperties: false
    AccessProfile:
      type: object
      properties:
        lifecycleRevision:
          $ref: '#/components/schemas/Revision'
        accountId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        email:
          $ref: '#/components/schemas/AccessEmail'
        emailVerified:
          type: boolean
        fieldVocabularyRevision:
          $ref: '#/components/schemas/Revision'
        definitions:
          type: array
          items:
            $ref: '#/components/schemas/AccessProfileFieldDefinition'
          x-policy-bound: retained editable-profile field vocabulary
        fields:
          type: array
          items:
            $ref: '#/components/schemas/AccessProfileField'
          x-policy-bound: retained editable-profile field vocabulary
      required:
      - accountId
      - revision
      - email
      - emailVerified
      - fieldVocabularyRevision
      - definitions
      - fields
      - lifecycleRevision
      additionalProperties: false
    AccessConsentRecord:
      type: object
      properties:
        consentId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        purposeId:
          $ref: '#/components/schemas/Id'
        decision:
          type: string
          enum:
          - granted
          - revoked
        revision:
          $ref: '#/components/schemas/Revision'
        effectiveAt:
          $ref: '#/components/schemas/Time'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - consentId
      - accountId
      - purposeId
      - decision
      - revision
      - effectiveAt
      - policyRef
      additionalProperties: false
    AccessConsentPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/AccessConsentRecord'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    LifecycleAction:
      type: string
      enum:
      - withdraw
      - reactivate
      - erase
    LifecycleScope:
      type: string
      enum:
      - live_records
      - derived_artifacts
      - pending_work
      - caches
      - backups
      - restore_enforcement
      - external_copies
    LifecycleReactivationResult:
      type: object
      properties:
        lifecycleRequestId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        state:
          type: string
          enum:
          - accepted
          - running
          - complete
          - blocked
          - failed
        access:
          type: string
          enum:
          - reactivation_pending
          - sign_in_required
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        requestId:
          $ref: '#/components/schemas/Id'
        reasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - lifecycleRequestId
      - revision
      - state
      - access
      - policyRef
      - requestId
      - reasonKey
      additionalProperties: false
      description: Safe status after valid reactivation proof; never a full session or a promise that erased data was restored. A protected limited
        recovery binding, issued through trusted cookie transport, permits lifecycle.inspect for this request alone while normal account authority
        remains unavailable.
      allOf:
      - if:
          properties:
            state:
              const: complete
        then:
          properties:
            access:
              const: sign_in_required
      - if:
          properties:
            state:
              type: string
              enum:
              - accepted
              - running
              - blocked
              - failed
        then:
          properties:
            access:
              const: reactivation_pending
    LifecycleScopeDisposition:
      type: object
      properties:
        scope:
          $ref: '#/components/schemas/LifecycleScope'
        disposition:
          type: string
          enum:
          - erased
          - retained_by_policy
          - revoked
          - not_applicable
          - pending
          - blocked
        evidenceReference:
          $ref: '#/components/schemas/Id'
        reasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - scope
      - disposition
      - reasonKey
      additionalProperties: false
      allOf:
      - if:
          properties:
            disposition:
              type: string
              enum:
              - erased
              - retained_by_policy
              - revoked
              - not_applicable
        then:
          required:
          - evidenceReference
    LifecycleParticipantDisposition:
      type: object
      properties:
        participantId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        state:
          type: string
          enum:
          - pending
          - running
          - acknowledged
          - failed
          - blocked
        scopes:
          type: array
          items:
            $ref: '#/components/schemas/LifecycleScopeDisposition'
          maxItems: 7
        observedAt:
          $ref: '#/components/schemas/Time'
      required:
      - participantId
      - revision
      - state
      - scopes
      - observedAt
      additionalProperties: false
    LifecycleRequest:
      type: object
      properties:
        lifecycleRequestId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        action:
          $ref: '#/components/schemas/LifecycleAction'
        revision:
          $ref: '#/components/schemas/Revision'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        manifestRevision:
          $ref: '#/components/schemas/Revision'
        authorityRevision:
          $ref: '#/components/schemas/Revision'
        revocation:
          type: string
          enum:
          - not_required
          - pending
          - effective
        state:
          type: string
          enum:
          - accepted
          - running
          - complete
          - blocked
          - failed
        participants:
          type: array
          items:
            $ref: '#/components/schemas/LifecycleParticipantDisposition'
          maxItems: 13
        completionEvidenceRef:
          $ref: '#/components/schemas/Id'
      required:
      - lifecycleRequestId
      - accountId
      - action
      - revision
      - policyRef
      - manifestRevision
      - authorityRevision
      - revocation
      - state
      - participants
      additionalProperties: false
      allOf:
      - if:
          properties:
            state:
              const: complete
        then:
          required:
          - completionEvidenceRef
          properties:
            revocation:
              type: string
              enum:
              - not_required
              - effective
    LibrarySavedPaper:
      type: object
      properties:
        savedPaperId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        savedPaper:
          $ref: '#/components/schemas/PaperRef'
        resolvedPaper:
          $ref: '#/components/schemas/PaperRef'
        savedTitle:
          type: string
          minLength: 1
          x-policy-bound: paper metadata display policy
          description: Bound by the named approved policy before processing.
        sourceDisposition:
          type: string
          enum:
          - available
          - source_only
          - canonicalized
          - withdrawn
          - unavailable
          - restricted
        reasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - savedPaperId
      - accountId
      - revision
      - savedPaper
      - sourceDisposition
      - reasonKey
      additionalProperties: false
    LibraryPaperPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/LibrarySavedPaper'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    LibrarySavedSearch:
      type: object
      properties:
        savedSearchId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        queryContext:
          $ref: '#/components/schemas/LibraryQueryContext'
        label:
          type: string
          minLength: 1
          x-policy-bound: saved-search label policy
          description: Bound by the named approved policy before processing.
      required:
      - savedSearchId
      - accountId
      - revision
      - queryContext
      additionalProperties: false
    LibrarySearchPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/LibrarySavedSearch'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    LibraryHistoryRecord:
      type: object
      properties:
        historyId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        searchExecutionId:
          $ref: '#/components/schemas/Id'
        queryContext:
          $ref: '#/components/schemas/LibraryQueryContext'
        recordedAt:
          $ref: '#/components/schemas/Time'
        admissionSequence:
          type: integer
          minimum: 0
        completionSequence:
          type: integer
          minimum: 0
        clearBoundary:
          $ref: '#/components/schemas/Revision'
      required:
      - historyId
      - accountId
      - searchExecutionId
      - queryContext
      - recordedAt
      - admissionSequence
      - completionSequence
      - clearBoundary
      additionalProperties: false
    LibraryHistoryPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/LibraryHistoryRecord'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        clearBoundary:
          $ref: '#/components/schemas/Revision'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      - clearBoundary
      additionalProperties: false
    LibraryClearHistoryResult:
      type: object
      properties:
        ack:
          $ref: '#/components/schemas/Ack'
        checkpoint:
          $ref: '#/components/schemas/SearchHistoryCheckpoint'
        clearBoundary:
          $ref: '#/components/schemas/Revision'
      required:
      - ack
      - checkpoint
      - clearBoundary
      additionalProperties: false
      description: Server-captured Discovery admission checkpoint, not a caller-selected cutoff. Facts admitted at/before the cutoff remain suppressed
        even if they finish after clear.
    SettingsSearchDefaults:
      type: object
      properties:
        modeId:
          $ref: '#/components/schemas/Id'
        orderId:
          $ref: '#/components/schemas/Id'
        filters:
          type: array
          items:
            $ref: '#/components/schemas/LibraryFilter'
          x-policy-bound: retained filter vocabulary and search policy
        vocabularyRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - modeId
      - orderId
      - filters
      - vocabularyRevision
      additionalProperties: false
    SettingsAssistanceDefaults:
      type: object
      properties:
        actionId:
          $ref: '#/components/schemas/Id'
        languageId:
          $ref: '#/components/schemas/Id'
        presentationLevelId:
          $ref: '#/components/schemas/Id'
        vocabularyRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - actionId
      - languageId
      - presentationLevelId
      - vocabularyRevision
      additionalProperties: false
    SettingsSnapshot:
      type: object
      properties:
        timeZone:
          type: [string, 'null']
          minLength: 1
          maxLength: 100
          description: 'Explicit owner IANA timezone; null means unconfigured.'
        accountId:
          $ref: '#/components/schemas/Id'
        settingsId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        searchDefaults:
          $ref: '#/components/schemas/SettingsSearchDefaults'
        assistanceDefaults:
          $ref: '#/components/schemas/SettingsAssistanceDefaults'
        appearance:
          type: string
          enum:
          - light
          - dark
          - system
        onboarding:
          type: string
          enum:
          - not_started
          - in_progress
          - completed
          - skipped
        interestIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-policy-bound: retained interest vocabulary and profile policy
          uniqueItems: true
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - accountId
      - settingsId
      - revision
      - searchDefaults
      - assistanceDefaults
      - appearance
      - onboarding
      - interestIds
      - policyRef
      additionalProperties: false
    SettingsSuggestion:
      type: object
      properties:
        interestId:
          $ref: '#/components/schemas/Id'
        labelKey:
          $ref: '#/components/schemas/Id'
        source:
          type: string
          enum:
          - orcid
          - retained_manual_vocabulary
        sourceRevision:
          $ref: '#/components/schemas/Revision'
        reasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - interestId
      - labelKey
      - source
      - sourceRevision
      - reasonKey
      additionalProperties: false
    SettingsSuggestionPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/SettingsSuggestion'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    SettingsRecentPaper:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        lastActivityAt:
          $ref: '#/components/schemas/Time'
        activityReference:
          $ref: '#/components/schemas/Id'
        sourceDisposition:
          type: string
          enum:
          - available
          - source_only
          - withdrawn
          - unavailable
          - restricted
      required:
      - paper
      - lastActivityAt
      - activityReference
      - sourceDisposition
      additionalProperties: false
    SettingsRecentPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/SettingsRecentPaper'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    SettingsResetResult:
      type: object
      properties:
        resetId:
          $ref: '#/components/schemas/Id'
        ack:
          $ref: '#/components/schemas/Ack'
        inputBoundary:
          $ref: '#/components/schemas/Revision'
        consentRevision:
          $ref: '#/components/schemas/Revision'
        disposition:
          type: string
          enum:
          - complete
          - pending
          - blocked
        remainingScopeReasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - resetId
      - ack
      - inputBoundary
      - consentRevision
      - disposition
      additionalProperties: false
    SettingsResetSummary:
      type: object
      properties:
        resetId: {$ref: '#/components/schemas/Id'}
        action: {type: string, enum: [delete_behavior, reset_profile]}
        acceptedAt: {$ref: '#/components/schemas/Time'}
        acceptedSettingsRevision: {$ref: '#/components/schemas/Revision'}
        inputBoundary: {$ref: '#/components/schemas/Revision'}
        policyRef: {$ref: '#/components/schemas/PolicyRef'}
        manifestRevision: {$ref: '#/components/schemas/Revision'}
        statusRevision: {$ref: '#/components/schemas/Revision'}
        observedAt: {$ref: '#/components/schemas/Time'}
        disposition: {type: string, enum: [pending, blocked, complete]}
        reasonKey: {$ref: '#/components/schemas/Id'}
      required: [resetId, action, acceptedAt, acceptedSettingsRevision, inputBoundary, policyRef, manifestRevision, statusRevision, observedAt, disposition, reasonKey]
      additionalProperties: false
    SettingsResetScopeStatus:
      type: object
      properties:
        participantId: {$ref: '#/components/schemas/Id'}
        scopeId: {$ref: '#/components/schemas/Id'}
        manifestRevision: {$ref: '#/components/schemas/Revision'}
        workGeneration: {$ref: '#/components/schemas/Revision'}
        disposition: {type: string, enum: [pending, blocked, complete]}
        reasonKey: {$ref: '#/components/schemas/Id'}
        evidenceRef: {oneOf: [{$ref: '#/components/schemas/Id'}, {type: 'null'}]}
        updatedAt: {$ref: '#/components/schemas/Time'}
      required: [participantId, scopeId, manifestRevision, workGeneration, disposition, reasonKey, evidenceRef, updatedAt]
      additionalProperties: false
    SettingsResetStatus:
      type: object
      properties:
        reset: {$ref: '#/components/schemas/SettingsResetSummary'}
        scopes: {type: array, minItems: 1, maxItems: 32, items: {$ref: '#/components/schemas/SettingsResetScopeStatus'}}
      required: [reset, scopes]
      additionalProperties: false
    SettingsResetPage:
      type: object
      properties:
        items: {type: array, maxItems: 50, items: {$ref: '#/components/schemas/SettingsResetSummary'}}
        page: {$ref: '#/components/schemas/PageInfo'}
        appliedLimit: {type: integer, minimum: 1, maximum: 50}
        policyRef: {$ref: '#/components/schemas/PolicyRef'}
      required: [items, page, appliedLimit, policyRef]
      additionalProperties: false
    UsageOperation:
      type: object
      properties:
        operationOwner:
          type: string
          enum:
          - AccountAccess
          - CorpusContent
          - Discovery
          - Library
          - PaperAssistance
          - ResearchWorkspace
          - Personalization
          - TopicsDigests
          - ApprovedExport
          - UsageEntitlements
          - ServiceOperations
          - PlatformControl
          - WebWorkspace
        operationId:
          $ref: '#/components/schemas/Id'
        inputRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - operationOwner
      - operationId
      - inputRevision
      additionalProperties: false
    UsageQuantity:
      type: object
      properties:
        metricId:
          $ref: '#/components/schemas/Id'
        quantity:
          type: integer
          minimum: 0
      required:
      - metricId
      - quantity
      additionalProperties: false
    UsageKnownMeasure:
      type: object
      properties:
        state:
          const: known
        metricId:
          $ref: '#/components/schemas/Id'
        allocated:
          type: integer
          minimum: 0
        used:
          type: integer
          minimum: 0
        reserved:
          type: integer
          minimum: 0
        remaining:
          type: integer
          minimum: 0
        periodId:
          $ref: '#/components/schemas/Id'
        periodStart:
          $ref: '#/components/schemas/Time'
        periodEnd:
          $ref: '#/components/schemas/Time'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - state
      - metricId
      - allocated
      - used
      - reserved
      - remaining
      - periodId
      - periodStart
      - periodEnd
      - policyRef
      additionalProperties: false
    UsageUnknownMeasure:
      type: object
      properties:
        state:
          const: unknown
        metricId:
          $ref: '#/components/schemas/Id'
        reasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - state
      - metricId
      - reasonKey
      additionalProperties: false
    UsageMeasure:
      oneOf:
      - $ref: '#/components/schemas/UsageKnownMeasure'
      - $ref: '#/components/schemas/UsageUnknownMeasure'
    UsageMeasurePage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/UsageMeasure'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    UsagePlanPresentation:
      type: object
      properties:
        accountId:
          $ref: '#/components/schemas/Id'
        tierId:
          $ref: '#/components/schemas/Id'
        labelKey:
          $ref: '#/components/schemas/Id'
        source:
          type: string
          enum:
          - mock
          - administrative_assignment
        revision:
          $ref: '#/components/schemas/Revision'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        paymentOccurred:
          const: false
      required:
      - accountId
      - tierId
      - labelKey
      - source
      - revision
      - policyRef
      - paymentOccurred
      additionalProperties: false
    UsageEntitlement:
      type: object
      properties:
        entitlementId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        tierId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        assignmentSource:
          type: string
          enum:
          - mock
          - administrative_assignment
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        effectiveAt:
          $ref: '#/components/schemas/Time'
        disposition:
          type: string
          enum:
          - active
          - revoked
      required:
      - entitlementId
      - accountId
      - tierId
      - revision
      - assignmentSource
      - policyRef
      - effectiveAt
      - disposition
      additionalProperties: false
    UsageRecord:
      type: object
      properties:
        usageRecordId:
          $ref: '#/components/schemas/Id'
        accountId:
          $ref: '#/components/schemas/Id'
        operation:
          $ref: '#/components/schemas/UsageOperation'
        revision:
          $ref: '#/components/schemas/Revision'
        periodId:
          $ref: '#/components/schemas/Id'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        disposition:
          type: string
          enum:
          - reserved
          - committed
          - released
          - refunded
          - unknown
        quantities:
          type: array
          items:
            $ref: '#/components/schemas/UsageQuantity'
          x-policy-bound: registered operation accounting metrics
        effectReference:
          $ref: '#/components/schemas/Id'
        reasonKey:
          $ref: '#/components/schemas/Id'
      required:
      - usageRecordId
      - accountId
      - operation
      - revision
      - periodId
      - policyRef
      - disposition
      - quantities
      - reasonKey
      additionalProperties: false
    UsageRecordsPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/UsageRecord'
          x-policy-bound: accepted PageRequest.limit and approved list policy
        page:
          $ref: '#/components/schemas/PageInfo'
        appliedLimit:
          type: integer
          minimum: 1
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - items
      - page
      - appliedLimit
      - policyRef
      additionalProperties: false
    CorpusIdentity:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        requestedIdentifier:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        canonicalDisposition:
          type: string
          enum:
          - same
          - alias
          - withdrawn
          - unavailable
          - restricted
        metadataRevision:
          $ref: '#/components/schemas/Revision'
        title:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        sourceUrls:
          type: array
          items:
            type: string
            minLength: 1
            format: uri
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - paper
      - requestedIdentifier
      - canonicalDisposition
      - metadataRevision
      - title
      - sourceUrls
      - policy
      additionalProperties: false
    CorpusSection:
      type: object
      properties:
        sectionId:
          $ref: '#/components/schemas/Id'
        heading:
          type: string
        text:
          type: string
        anchor:
          $ref: '#/components/schemas/Id'
      required:
      - sectionId
      - heading
      - text
      - anchor
      additionalProperties: false
    CorpusAssetRef:
      type: object
      properties:
        assetId:
          $ref: '#/components/schemas/Id'
        mediaType:
          type: string
          minLength: 1
        contentHash:
          $ref: '#/components/schemas/Hash'
        altText:
          type: string
        sectionId:
          $ref: '#/components/schemas/Id'
      required:
      - assetId
      - mediaType
      - contentHash
      - altText
      additionalProperties: false
    CorpusContent:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        contentRevision:
          $ref: '#/components/schemas/Revision'
        contentHash:
          $ref: '#/components/schemas/Hash'
        sections:
          type: array
          items:
            $ref: '#/components/schemas/CorpusSection'
        assets:
          type: array
          items:
            $ref: '#/components/schemas/CorpusAssetRef'
        sourceUrls:
          type: array
          items:
            type: string
            minLength: 1
            format: uri
        coverage:
          type: string
          enum:
          - complete
          - partial
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - paper
      - contentRevision
      - contentHash
      - sections
      - assets
      - sourceUrls
      - coverage
      - limitations
      - policy
      additionalProperties: false
    CorpusContentRead:
      oneOf:
      - type: object
        properties:
          availability:
            const: ready
          content:
            $ref: '#/components/schemas/CorpusContent'
        required:
        - availability
        - content
        additionalProperties: false
      - type: object
        properties:
          availability:
            type: string
            enum:
            - absent
            - building
            - unsupported
            - failed
            - withdrawn
            - restricted
          paper:
            $ref: '#/components/schemas/PaperRef'
          reasonKey:
            type: string
            minLength: 1
          retryable:
            type: boolean
        required:
        - availability
        - paper
        - reasonKey
        - retryable
        additionalProperties: false
    CorpusAsset:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        asset:
          $ref: '#/components/schemas/CorpusAssetRef'
        readHandle:
          $ref: '#/components/schemas/Id'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - paper
      - asset
      - readHandle
      - policy
      additionalProperties: false
    CorpusEffectDisposition:
      type: object
      properties:
        effectId:
          $ref: '#/components/schemas/Id'
        stage:
          type: string
          enum:
          - source
          - control
          - content
          - projection
          - publication
        state:
          type: string
          enum:
          - pending
          - committed
          - failed
          - unknown
        evidenceHash:
          anyOf:
          - $ref: '#/components/schemas/Hash'
          - type: 'null'
        error:
          anyOf:
          - $ref: '#/components/schemas/Error'
          - type: 'null'
      required:
      - effectId
      - stage
      - state
      - evidenceHash
      - error
      additionalProperties: false
    CorpusRun:
      type: object
      properties:
        runId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        job:
          $ref: '#/components/schemas/JobSnapshot'
        inputManifestHash:
          $ref: '#/components/schemas/Hash'
        effects:
          type: array
          items:
            $ref: '#/components/schemas/CorpusEffectDisposition'
        committedWatermark:
          anyOf:
          - type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
          - type: 'null'
        publicationGeneration:
          anyOf:
          - $ref: '#/components/schemas/Id'
          - type: 'null'
      required:
      - runId
      - revision
      - job
      - inputManifestHash
      - effects
      - committedWatermark
      - publicationGeneration
      additionalProperties: false
    CorpusPublication:
      type: object
      properties:
        generationId:
          $ref: '#/components/schemas/Id'
        publicationRevision:
          $ref: '#/components/schemas/Revision'
        manifestHash:
          $ref: '#/components/schemas/Hash'
        compatibilityRevision:
          $ref: '#/components/schemas/Revision'
        eligibilityRevision:
          $ref: '#/components/schemas/Revision'
        publishedAt:
          $ref: '#/components/schemas/Time'
        complete:
          const: true
      required:
      - generationId
      - publicationRevision
      - manifestHash
      - compatibilityRevision
      - eligibilityRevision
      - publishedAt
      - complete
      additionalProperties: false
    SearchHit:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        title:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        authors:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        publishedAt:
          anyOf:
          - $ref: '#/components/schemas/Time'
          - type: 'null'
        snippet:
          type: string
        sourceUrl:
          type: string
          minLength: 1
          format: uri
        availability:
          type: string
          enum:
          - readable
          - source-only
          - building
          - unavailable
          - restricted
        matchExplanation:
          type: string
      required:
      - paper
      - title
      - authors
      - publishedAt
      - snippet
      - sourceUrl
      - availability
      - matchExplanation
      additionalProperties: false
    SearchResponse:
      type: object
      properties:
        executionId:
          $ref: '#/components/schemas/Id'
        query:
          $ref: '#/components/schemas/LibraryQueryContext'
        hits:
          type: array
          items:
            $ref: '#/components/schemas/SearchHit'
        page:
          $ref: '#/components/schemas/PageInfo'
        publication:
          $ref: '#/components/schemas/CorpusPublication'
        outcome:
          type: string
          enum:
          - complete
          - partial
          - degraded
        effectiveModeId:
          $ref: '#/components/schemas/Id'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
      required:
      - executionId
      - query
      - hits
      - page
      - publication
      - outcome
      - effectiveModeId
      - limitations
      additionalProperties: false
    SearchHistoryCheckpoint:
      type: object
      properties:
        ownerId:
          $ref: '#/components/schemas/Id'
        admissionSequence:
          type: integer
          minimum: 0
        revision:
          $ref: '#/components/schemas/Revision'
      required:
      - ownerId
      - admissionSequence
      - revision
      additionalProperties: false
    CitationNode:
      type: object
      properties:
        nodeId:
          $ref: '#/components/schemas/Id'
        paper:
          anyOf:
          - $ref: '#/components/schemas/PaperRef'
          - type: 'null'
        title:
          anyOf:
          - type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
          - type: 'null'
        sourceUrl:
          anyOf:
          - type: string
            minLength: 1
            format: uri
          - type: 'null'
        disposition:
          type: string
          enum:
          - eligible
          - unknown
          - incomplete
          - restricted
          - withdrawn
      required:
      - nodeId
      - paper
      - title
      - sourceUrl
      - disposition
      additionalProperties: false
    CitationEdge:
      type: object
      properties:
        fromNodeId:
          $ref: '#/components/schemas/Id'
        toNodeId:
          $ref: '#/components/schemas/Id'
        sourceUrl:
          type: string
          minLength: 1
          format: uri
        observedAt:
          $ref: '#/components/schemas/Time'
      required:
      - fromNodeId
      - toNodeId
      - sourceUrl
      - observedAt
      additionalProperties: false
    CitationResponse:
      type: object
      properties:
        snapshotId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        root:
          $ref: '#/components/schemas/PaperRef'
        nodes:
          type: array
          items:
            $ref: '#/components/schemas/CitationNode'
        edges:
          type: array
          items:
            $ref: '#/components/schemas/CitationEdge'
        freshness:
          type: string
          enum:
          - current
          - stale
          - unknown
        coverage:
          type: string
          enum:
          - complete
          - partial
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        page:
          $ref: '#/components/schemas/PageInfo'
      required:
      - snapshotId
      - revision
      - root
      - nodes
      - edges
      - freshness
      - coverage
      - limitations
      - page
      additionalProperties: false
    AssistanceOption:
      type: object
      properties:
        optionId:
          $ref: '#/components/schemas/Id'
        operation:
          type: string
          enum:
          - summary
          - translation
        sourceLanguageId:
          $ref: '#/components/schemas/Id'
        targetLanguageId:
          $ref: '#/components/schemas/Id'
        presentationLevelId:
          $ref: '#/components/schemas/Id'
        labelKey:
          type: string
          minLength: 1
      required:
      - optionId
      - operation
      - sourceLanguageId
      - targetLanguageId
      - presentationLevelId
      - labelKey
      additionalProperties: false
    AssistanceOptions:
      type: object
      properties:
        revision:
          $ref: '#/components/schemas/Revision'
        options:
          type: array
          items:
            $ref: '#/components/schemas/AssistanceOption'
        policy:
          $ref: '#/components/schemas/PolicyRef'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
      required:
      - revision
      - options
      - policy
      - limitations
      additionalProperties: false
    AssistanceResult:
      type: object
      properties:
        result:
          $ref: '#/components/schemas/ResultRef'
        ownerId:
          $ref: '#/components/schemas/Id'
        jobId:
          $ref: '#/components/schemas/Id'
        paper:
          $ref: '#/components/schemas/PaperRef'
        sourceContentHash:
          $ref: '#/components/schemas/Hash'
        operation:
          type: string
          enum:
          - summary
          - translation
        optionId:
          $ref: '#/components/schemas/Id'
        glossaryRevision:
          $ref: '#/components/schemas/Revision'
        sections:
          type: array
          items:
            $ref: '#/components/schemas/CorpusSection'
        coverage:
          type: string
          enum:
          - complete
          - partial
          - abstained
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        methodRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - result
      - ownerId
      - jobId
      - paper
      - sourceContentHash
      - operation
      - optionId
      - glossaryRevision
      - sections
      - coverage
      - limitations
      - methodRevision
      additionalProperties: false
    AssistanceResultRead:
      oneOf:
      - type: object
        properties:
          availability:
            const: ready
          prepared:
            $ref: '#/components/schemas/AssistanceResult'
        required:
        - availability
        - prepared
        additionalProperties: false
      - type: object
        properties:
          availability:
            type: string
            enum:
            - pending
            - failed
            - expired
            - withdrawn
            - restricted
          jobId:
            $ref: '#/components/schemas/Id'
          reasonKey:
            type: string
            minLength: 1
        required:
        - availability
        - jobId
        - reasonKey
        additionalProperties: false
    AssistanceGlossaryTerm:
      type: object
      properties:
        termId:
          $ref: '#/components/schemas/Id'
        source:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        preferred:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        languageId:
          $ref: '#/components/schemas/Id'
      required:
      - termId
      - source
      - preferred
      - languageId
      additionalProperties: false
    AssistanceGlossary:
      type: object
      properties:
        ownerId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        normalizationPolicy:
          $ref: '#/components/schemas/PolicyRef'
        terms:
          type: array
          items:
            $ref: '#/components/schemas/AssistanceGlossaryTerm'
      required:
      - ownerId
      - revision
      - normalizationPolicy
      - terms
      additionalProperties: false
    ResearchScope:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        publicPapers:
          type: array
          items:
            $ref: '#/components/schemas/PaperRef'
        attachmentIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          uniqueItems: true
        webReferences:
          type: array
          items:
            type: string
            minLength: 1
            format: uri
        scopePolicy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - contextId
      - publicPapers
      - attachmentIds
      - webReferences
      - scopePolicy
      additionalProperties: false
    ResearchContext:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        purpose:
          type: string
          enum:
          - research
          - novelty
        lifecycle:
          type: string
          enum:
          - active
          - deleting
          - deleted
      required:
      - contextId
      - ownerId
      - revision
      - purpose
      - lifecycle
      additionalProperties: false
    ResearchSession:
      type: object
      properties:
        sessionId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        scope:
          $ref: '#/components/schemas/ResearchScope'
        lifecycle:
          type: string
          enum:
          - active
          - deleting
          - deleted
        turnIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
        pendingJobIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
        deletionBoundary:
          anyOf:
          - $ref: '#/components/schemas/Revision'
          - type: 'null'
      required:
      - sessionId
      - ownerId
      - revision
      - scope
      - lifecycle
      - turnIds
      - pendingJobIds
      - deletionBoundary
      additionalProperties: false
    ResearchSessions:
      type: object
      properties:
        sessions:
          type: array
          items:
            $ref: '#/components/schemas/ResearchSession'
        page:
          $ref: '#/components/schemas/PageInfo'
      required:
      - sessions
      - page
      additionalProperties: false
    ResearchDeletion:
      type: object
      properties:
        requestId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        state:
          type: string
          enum:
          - accepted
          - in-progress
          - complete
          - limited
          - failed
        tombstoneBoundary:
          $ref: '#/components/schemas/Revision'
        policy:
          $ref: '#/components/schemas/PolicyRef'
        remainingJobIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
      required:
      - requestId
      - revision
      - state
      - tombstoneBoundary
      - policy
      - remainingJobIds
      - limitations
      additionalProperties: false
    ResearchUploadPermit:
      type: object
      properties:
        uploadId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        contextId:
          $ref: '#/components/schemas/Id'
        contentHash:
          $ref: '#/components/schemas/Hash'
        writeHandle:
          $ref: '#/components/schemas/Id'
        expiresAt:
          $ref: '#/components/schemas/Time'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - uploadId
      - ownerId
      - contextId
      - contentHash
      - writeHandle
      - expiresAt
      - policy
      additionalProperties: false
    ResearchAttachment:
      type: object
      properties:
        attachmentId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        contextId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        contentHash:
          $ref: '#/components/schemas/Hash'
        state:
          type: string
          enum:
          - processing
          - ready
          - partial
          - unsupported
          - failed
          - deleted
        assetIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
      required:
      - attachmentId
      - ownerId
      - contextId
      - revision
      - contentHash
      - state
      - assetIds
      - limitations
      additionalProperties: false
    ResearchPrivateAsset:
      type: object
      properties:
        attachmentId:
          $ref: '#/components/schemas/Id'
        contextId:
          $ref: '#/components/schemas/Id'
        assetId:
          $ref: '#/components/schemas/Id'
        mediaType:
          type: string
          minLength: 1
        contentHash:
          $ref: '#/components/schemas/Hash'
        readHandle:
          $ref: '#/components/schemas/Id'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - attachmentId
      - contextId
      - assetId
      - mediaType
      - contentHash
      - readHandle
      - policy
      additionalProperties: false
    DraftRef:
      type: object
      properties:
        draftId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        contentHash:
          $ref: '#/components/schemas/Hash'
      required:
      - draftId
      - revision
      - contentHash
      additionalProperties: false
    DraftRevision:
      type: object
      properties:
        draft:
          $ref: '#/components/schemas/DraftRef'
        ownerId:
          $ref: '#/components/schemas/Id'
        contextId:
          $ref: '#/components/schemas/Id'
        kind:
          type: string
          enum:
          - research-question
          - novelty-topic
          - novelty-manuscript
          - novelty-discussion
        parentRevision:
          anyOf:
          - $ref: '#/components/schemas/Revision'
          - type: 'null'
        text:
          type: string
        acknowledgedAt:
          $ref: '#/components/schemas/Time'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - draft
      - ownerId
      - contextId
      - kind
      - parentRevision
      - text
      - acknowledgedAt
      - policy
      additionalProperties: false
    DraftWriteResult:
      oneOf:
      - type: object
        properties:
          outcome:
            const: saved
          acknowledged:
            $ref: '#/components/schemas/DraftRevision'
        required:
        - outcome
        - acknowledged
        additionalProperties: false
      - type: object
        properties:
          outcome:
            const: conflict
          current:
            $ref: '#/components/schemas/DraftRevision'
          proposedText:
            type: string
          proposedBaseRevision:
            anyOf:
            - $ref: '#/components/schemas/Revision'
            - type: 'null'
        required:
        - outcome
        - current
        - proposedText
        - proposedBaseRevision
        additionalProperties: false
    DraftRecovery:
      oneOf:
      - type: object
        properties:
          state:
            const: recoverable
          acknowledged:
            $ref: '#/components/schemas/DraftRevision'
        required:
        - state
        - acknowledged
        additionalProperties: false
      - type: object
        properties:
          state:
            type: string
            enum:
            - missing
            - consumed
            - discarded
            - expired
            - deleted
          draftId:
            $ref: '#/components/schemas/Id'
          reasonKey:
            type: string
            minLength: 1
        required:
        - state
        - draftId
        - reasonKey
        additionalProperties: false
    ResearchTurn:
      type: object
      properties:
        turnId:
          $ref: '#/components/schemas/Id'
        sessionId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        inputMode:
          type: string
          enum:
          - question
          - compare
          - quote
        committedText:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        submittedDraft:
          anyOf:
          - $ref: '#/components/schemas/DraftRef'
          - type: 'null'
        job:
          $ref: '#/components/schemas/JobSnapshot'
        artifact:
          anyOf:
          - $ref: '#/components/schemas/ResearchArtifactRef'
          - type: 'null'
      required:
      - turnId
      - sessionId
      - ownerId
      - revision
      - inputMode
      - committedText
      - submittedDraft
      - job
      - artifact
      additionalProperties: false
    ResearchArtifactRef:
      type: object
      properties:
        artifactId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        contentHash:
          $ref: '#/components/schemas/Hash'
      required:
      - artifactId
      - revision
      - contentHash
      additionalProperties: false
    ResearchEvidence:
      type: object
      properties:
        evidenceId:
          $ref: '#/components/schemas/Id'
        sourceKind:
          type: string
          enum:
          - public-paper
          - private-attachment
          - retrieved-web
          - unread-reference
        sourceId:
          $ref: '#/components/schemas/Id'
        sourceVersion:
          $ref: '#/components/schemas/Revision'
        sourceContentHash:
          anyOf:
          - $ref: '#/components/schemas/Hash'
          - type: 'null'
        location:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        readCoverage:
          type: string
          enum:
          - read
          - partial
          - not-read
        quote:
          anyOf:
          - type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
          - type: 'null'
        claim:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        stance:
          type: string
          enum:
          - supports
          - contradicts
          - uncertain
        sourceUrl:
          anyOf:
          - type: string
            minLength: 1
            format: uri
          - type: 'null'
      required:
      - evidenceId
      - sourceKind
      - sourceId
      - sourceVersion
      - sourceContentHash
      - location
      - readCoverage
      - quote
      - claim
      - stance
      - sourceUrl
      additionalProperties: false
    ResearchOutput:
      type: object
      properties:
        summary:
          type: string
        evidence:
          type: array
          items:
            $ref: '#/components/schemas/ResearchEvidence'
        coverage:
          type: string
          enum:
          - complete
          - partial
          - abstained
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        methodRevision:
          $ref: '#/components/schemas/Revision'
        assessments:
          type: array
          items:
            $ref: '#/components/schemas/ResearchAssessment'
      required:
      - summary
      - evidence
      - coverage
      - limitations
      - methodRevision
      additionalProperties: false
    ResearchAssessment:
      type: object
      properties:
        criterionId:
          $ref: '#/components/schemas/Id'
        label:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        score:
          type: number
        scaleMinimum:
          type: number
        scaleMaximum:
          type: number
        evidenceIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
      required:
      - criterionId
      - label
      - evidenceIds
      - limitations
      additionalProperties: false
      dependentRequired:
        score:
        - scaleMinimum
        - scaleMaximum
        scaleMinimum:
        - score
        - scaleMaximum
        scaleMaximum:
        - score
        - scaleMinimum
    ResearchArtifact:
      type: object
      properties:
        artifact:
          $ref: '#/components/schemas/ResearchArtifactRef'
        ownerId:
          $ref: '#/components/schemas/Id'
        contextId:
          $ref: '#/components/schemas/Id'
        operationId:
          $ref: '#/components/schemas/Id'
        kind:
          type: string
          enum:
          - research-answer
          - novelty-result
          - novelty-discussion
        output:
          $ref: '#/components/schemas/ResearchOutput'
        currentEligibilityRevision:
          $ref: '#/components/schemas/Revision'
        mediaType:
          const: application/json
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - artifact
      - ownerId
      - contextId
      - operationId
      - kind
      - output
      - currentEligibilityRevision
      - mediaType
      - policy
      additionalProperties: false
    ResearchArtifactResponse:
      oneOf:
      - type: object
        properties:
          availability:
            const: ready
          prepared:
            $ref: '#/components/schemas/ResearchArtifact'
        required:
        - availability
        - prepared
        additionalProperties: false
      - type: object
        properties:
          availability:
            type: string
            enum:
            - pending
            - failed
            - expired
            - deleted
            - restricted
          artifactId:
            $ref: '#/components/schemas/Id'
          reasonKey:
            type: string
            minLength: 1
        required:
        - availability
        - artifactId
        - reasonKey
        additionalProperties: false
    DigestSchedule:
      type: object
      properties:
        cadenceId:
          $ref: '#/components/schemas/Id'
        timeZone:
          type: string
          minLength: 1
        windowPolicy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - cadenceId
      - timeZone
      - windowPolicy
      additionalProperties: false
    DigestSubscription:
      type: object
      properties:
        subscriptionId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        topic:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        revision:
          $ref: '#/components/schemas/Revision'
        enabled:
          type: boolean
        schedule:
          $ref: '#/components/schemas/DigestSchedule'
        unsubscribeBoundary:
          anyOf:
          - $ref: '#/components/schemas/Revision'
          - type: 'null'
      required:
      - subscriptionId
      - ownerId
      - topic
      - revision
      - enabled
      - schedule
      - unsubscribeBoundary
      additionalProperties: false
    DigestSubscriptions:
      type: object
      properties:
        subscriptions:
          type: array
          items:
            $ref: '#/components/schemas/DigestSubscription'
        page:
          $ref: '#/components/schemas/PageInfo'
      required:
      - subscriptions
      - page
      additionalProperties: false
    DigestWindow:
      type: object
      properties:
        startInclusive:
          $ref: '#/components/schemas/Time'
        endExclusive:
          $ref: '#/components/schemas/Time'
        timeZone:
          type: string
          minLength: 1
        windowPolicy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - startInclusive
      - endExclusive
      - timeZone
      - windowPolicy
      additionalProperties: false
    DigestDelivery:
      type: object
      properties:
        deliveryId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        subscriptionId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        window:
          $ref: '#/components/schemas/DigestWindow'
        papers:
          type: array
          items:
            $ref: '#/components/schemas/PaperRef'
        state:
          type: string
          enum:
          - prepared
          - no-content
          - queued
          - sending
          - sent
          - failed
          - unknown
          - suppressed
        effectKey:
          $ref: '#/components/schemas/Id'
        remoteReference:
          anyOf:
          - $ref: '#/components/schemas/Id'
          - type: 'null'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
      required:
      - deliveryId
      - ownerId
      - subscriptionId
      - revision
      - window
      - papers
      - state
      - effectKey
      - remoteReference
      - limitations
      additionalProperties: false
    DigestUnsubscribeResult:
      type: object
      properties:
        outcome:
          const: acknowledged
        requestId:
          $ref: '#/components/schemas/Id'
      required:
      - outcome
      - requestId
      additionalProperties: false
    ExportConnection:
      type: object
      properties:
        connectionId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        provider:
          const: notion
        state:
          type: string
          enum:
          - connected
          - disconnected
          - revoked
          - unavailable
        destinationScopeIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        workspaceName:
          type: string
          minLength: 1
          maxLength: 2000
      required:
      - connectionId
      - ownerId
      - revision
      - provider
      - state
      - destinationScopeIds
      - limitations
      additionalProperties: false
    ExportDestination:
      type: object
      properties:
        connectionId:
          $ref: '#/components/schemas/Id'
        workspaceId:
          $ref: '#/components/schemas/Id'
        parentPageId:
          $ref: '#/components/schemas/Id'
        formatRevision:
          $ref: '#/components/schemas/Revision'
        destinationId:
          $ref: '#/components/schemas/Id'
        title:
          type: string
          minLength: 1
          maxLength: 2000
        context:
          type: string
          minLength: 1
          maxLength: 2000
      required:
      - connectionId
      - workspaceId
      - parentPageId
      - formatRevision
      additionalProperties: false
    ExportDestinationEntry:
      type: object
      properties:
        connectionId:
          $ref: '#/components/schemas/Id'
        workspaceId:
          $ref: '#/components/schemas/Id'
        parentPageId:
          $ref: '#/components/schemas/Id'
        formatRevision:
          $ref: '#/components/schemas/Revision'
        destinationId:
          $ref: '#/components/schemas/Id'
        title:
          type: string
          minLength: 1
          maxLength: 2000
        context:
          type: string
          minLength: 1
          maxLength: 2000
        readable:
          type: boolean
        creationCapability:
          $ref: '#/components/schemas/ExportCreationCapability'
        writable:
          type: boolean
      required:
      - connectionId
      - workspaceId
      - parentPageId
      - formatRevision
      - destinationId
      - title
      additionalProperties: false
    ExportCreationCapability:
      type: string
      enum:
      - unknown
      - confirmed
      - refused
    ExportDestinations:
      type: object
      properties:
        connectionId:
          $ref: '#/components/schemas/Id'
        connectionRevision:
          $ref: '#/components/schemas/Revision'
        destinations:
          type: array
          items:
            $ref: '#/components/schemas/ExportDestinationEntry'
        listingComplete:
          type: boolean
        lastDestinationId:
          $ref: '#/components/schemas/Id'
      required:
      - connectionId
      - connectionRevision
      - destinations
      additionalProperties: false
    ExportPreview:
      type: object
      properties:
        previewId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        source:
          $ref: '#/components/schemas/ResearchArtifactRef'
        sourceEligibilityRevision:
          $ref: '#/components/schemas/Revision'
        connectionRevision:
          $ref: '#/components/schemas/Revision'
        destination:
          $ref: '#/components/schemas/ExportDestinationEntry'
        renderedText:
          type: string
        renderedContentHash:
          $ref: '#/components/schemas/Hash'
        bindingHash:
          $ref: '#/components/schemas/Hash'
        renderPolicy:
          $ref: '#/components/schemas/PolicyRef'
        earlierExports:
          type: array
          items:
            $ref: '#/components/schemas/ExportEarlierExport'
          maxItems: 20
        marker:
          type: string
          minLength: 1
          maxLength: 200
        sourceTitle:
          type: string
          minLength: 1
          maxLength: 2000
      required:
      - previewId
      - ownerId
      - revision
      - source
      - sourceEligibilityRevision
      - connectionRevision
      - destination
      - renderedText
      - renderedContentHash
      - bindingHash
      - renderPolicy
      additionalProperties: false
    ExportEarlierExport:
      type: object
      properties:
        effectId:
          $ref: '#/components/schemas/Id'
        disposition:
          $ref: '#/components/schemas/ExportEarlierExportDisposition'
        endedAt:
          $ref: '#/components/schemas/Time'
        remoteUrl:
          type: string
          minLength: 1
          format: uri
        outcomeReason:
          $ref: '#/components/schemas/ExportOutcomeReason'
      required:
      - effectId
      - disposition
      - endedAt
      additionalProperties: false
    ExportEarlierExportDisposition:
      type: string
      enum:
      - exported
      - may-exist
    ExportApproval:
      type: object
      properties:
        approvalId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        previewId:
          $ref: '#/components/schemas/Id'
        previewRevision:
          $ref: '#/components/schemas/Revision'
        bindingHash:
          $ref: '#/components/schemas/Hash'
        approvedAt:
          $ref: '#/components/schemas/Time'
        expiresAt:
          anyOf:
          - $ref: '#/components/schemas/Time'
          - type: 'null'
        state:
          type: string
          enum:
          - approved
          - invalidated
          - consumed
          - cancelled
          - expired
        policy:
          $ref: '#/components/schemas/PolicyRef'
        invalidationReason:
          $ref: '#/components/schemas/ExportInvalidationReason'
      required:
      - approvalId
      - ownerId
      - previewId
      - previewRevision
      - bindingHash
      - approvedAt
      - expiresAt
      - state
      - policy
      additionalProperties: false
    ExportInvalidationReason:
      type: string
      enum:
      - source-changed
      - destination-changed
      - connection-changed
      - authority-revoked
      - account-withdrawn
    ExportEffect:
      type: object
      properties:
        effectId:
          $ref: '#/components/schemas/Id'
        approvalId:
          $ref: '#/components/schemas/Id'
        ownerId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        bindingHash:
          $ref: '#/components/schemas/Hash'
        state:
          type: string
          enum:
          - accepted
          - executing
          - succeeded
          - failed
          - unknown
          - cancelled
          - invalidated
        remoteReference:
          anyOf:
          - $ref: '#/components/schemas/Id'
          - type: 'null'
        remoteUrl:
          anyOf:
          - type: string
            minLength: 1
            format: uri
          - type: 'null'
        reconciliationEvidenceHash:
          anyOf:
          - $ref: '#/components/schemas/Hash'
          - type: 'null'
        limitations:
          type: array
          items:
            type: string
            minLength: 1
            x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        outcomeReason:
          $ref: '#/components/schemas/ExportOutcomeReason'
        settledBy:
          $ref: '#/components/schemas/ExportSettledBy'
        nextCheckAt:
          $ref: '#/components/schemas/Time'
        settlementOffered:
          type: boolean
      required:
      - effectId
      - approvalId
      - ownerId
      - revision
      - bindingHash
      - state
      - remoteReference
      - remoteUrl
      - reconciliationEvidenceHash
      - limitations
      additionalProperties: false
    ExportOutcomeReason:
      type: string
      enum:
      - token-invalid
      - no-access
      - destination-missing
      - content-rejected
      - workspace-block-limit
      - provider-blocked
      - rate-limit-budget-spent
      - not-found-after-checks
      - owner-settled-delivered
      - owner-settled-not-delivered
      - dependency-unavailable
      - policy-unresolved
      - source-changed
      - destination-changed
      - connection-changed
      - authority-revoked
      - account-withdrawn
      - owner-cancelled
    ExportSettledBy:
      type: string
      enum:
      - provider
      - reconciliation
      - owner
    ExportHistoryPage:
      type: object
      properties:
        entries:
          type: array
          items:
            $ref: '#/components/schemas/ExportHistoryEntry'
          maxItems: 20
        nextCursor:
          anyOf:
          - type: string
            minLength: 1
            maxLength: 512
          - type: 'null'
      required:
      - entries
      - nextCursor
      additionalProperties: false
    ExportHistoryEntry:
      type: object
      properties:
        approvalId:
          $ref: '#/components/schemas/Id'
        previewId:
          $ref: '#/components/schemas/Id'
        previewRevision:
          $ref: '#/components/schemas/Revision'
        bindingHash:
          $ref: '#/components/schemas/Hash'
        state:
          $ref: '#/components/schemas/ExportApprovalState'
        invalidationReason:
          $ref: '#/components/schemas/ExportInvalidationReason'
        approvedAt:
          $ref: '#/components/schemas/Time'
        endedAt:
          $ref: '#/components/schemas/Time'
        sourceTitle:
          type: string
          minLength: 1
          maxLength: 2000
        destinationTitle:
          type: string
          minLength: 1
          maxLength: 2000
        continuable:
          type: boolean
        effect:
          $ref: '#/components/schemas/ExportHistoryEffect'
      required:
      - approvalId
      - previewId
      - previewRevision
      - bindingHash
      - state
      - approvedAt
      - sourceTitle
      - destinationTitle
      - continuable
      additionalProperties: false
    ExportHistoryEffect:
      type: object
      properties:
        effectId:
          $ref: '#/components/schemas/Id'
        state:
          $ref: '#/components/schemas/ExportEffectState'
        revision:
          $ref: '#/components/schemas/Revision'
        remoteUrl:
          type: string
          minLength: 1
          format: uri
        outcomeReason:
          $ref: '#/components/schemas/ExportOutcomeReason'
        settledBy:
          $ref: '#/components/schemas/ExportSettledBy'
        nextCheckAt:
          $ref: '#/components/schemas/Time'
        possibleDuplicates:
          type: array
          items:
            $ref: '#/components/schemas/ExportPossibleDuplicate'
          maxItems: 10
        settlementOffered:
          type: boolean
      required:
      - effectId
      - state
      - revision
      - possibleDuplicates
      - settlementOffered
      additionalProperties: false
    ExportPossibleDuplicate:
      type: object
      properties:
        remoteReference:
          $ref: '#/components/schemas/Id'
        remoteUrl:
          type: string
          minLength: 1
          format: uri
      required:
      - remoteReference
      additionalProperties: false
    ExportApprovalState:
      type: string
      enum:
      - approved
      - invalidated
      - consumed
      - cancelled
      - expired
    ExportEffectState:
      type: string
      enum:
      - accepted
      - executing
      - succeeded
      - failed
      - unknown
      - cancelled
      - invalidated
    ExportSettleDisposition:
      type: string
      enum:
      - delivered
      - not-delivered
    SessionBootstrap:
      type: object
      properties:
        signedIn:
          type: boolean
        accountId:
          anyOf:
          - $ref: '#/components/schemas/Id'
          - type: 'null'
        authorityRevision:
          anyOf:
          - $ref: '#/components/schemas/Revision'
          - type: 'null'
        csrfToken:
          type: string
          minLength: 1
          x-limit-policy: AdmissionPolicy bounds bytes and characters before persistence/processing.
      required:
      - signedIn
      - accountId
      - authorityRevision
      - csrfToken
      additionalProperties: false
    CapabilityCatalog:
      type: object
      properties:
        revision:
          $ref: '#/components/schemas/Revision'
        capabilities:
          type: array
          items:
            type: object
            properties:
              id:
                $ref: '#/components/schemas/Id'
              state:
                type: string
                enum:
                - available
                - degraded
                - unavailable
                - policy_pending
              modeIds:
                type: array
                items:
                  $ref: '#/components/schemas/Id'
                x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
              languageIds:
                type: array
                items:
                  $ref: '#/components/schemas/Id'
                x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
              levelIds:
                type: array
                items:
                  $ref: '#/components/schemas/Id'
                x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
              formatIds:
                type: array
                items:
                  $ref: '#/components/schemas/Id'
                x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
              policy:
                $ref: '#/components/schemas/PolicyRef'
            required:
            - id
            - state
            - modeIds
            - languageIds
            - levelIds
            - formatIds
            - policy
            additionalProperties: false
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
      required:
      - revision
      - capabilities
      additionalProperties: false
    UploadAck:
      type: object
      properties:
        uploadId:
          $ref: '#/components/schemas/Id'
        contentHash:
          $ref: '#/components/schemas/Hash'
        receivedBytes:
          type: integer
          minimum: 0
        revision:
          $ref: '#/components/schemas/Revision'
      required:
      - uploadId
      - contentHash
      - receivedBytes
      - revision
      additionalProperties: false
    HostNavigationInputHttp:
      type: object
      properties:
        routeId:
          $ref: '#/components/schemas/Id'
        returnContext:
          $ref: '#/components/schemas/HostReturnContext'
      required:
      - routeId
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessSessionInputHttp:
      type: object
      properties: {}
      required: []
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessRegisterInputHttp:
      type: object
      properties:
        email:
          $ref: '#/components/schemas/AccessEmail'
        password:
          $ref: '#/components/schemas/AccessSecret'
        displayName:
          type: string
          minLength: 1
          x-policy-bound: profile display-name policy
          description: Bound by the named approved policy before processing.
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - email
      - password
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessEmailRequestInputHttp:
      type: object
      properties:
        email:
          $ref: '#/components/schemas/AccessEmail'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - email
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessVerifyEmailInputHttp:
      type: object
      properties:
        verification:
          $ref: '#/components/schemas/AccessChallengeProof'
      required:
      - verification
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessLoginInputHttp:
      type: object
      properties:
        email:
          $ref: '#/components/schemas/AccessEmail'
        password:
          $ref: '#/components/schemas/AccessSecret'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - email
      - password
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessLogoutInputHttp:
      type: object
      properties: {}
      required: []
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessPasswordResetInputHttp:
      type: object
      properties:
        verification:
          $ref: '#/components/schemas/AccessChallengeProof'
        newPassword:
          $ref: '#/components/schemas/AccessSecret'
      required:
      - verification
      - newPassword
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessPasswordChangeInputHttp:
      type: object
      properties:
        currentPassword:
          $ref: '#/components/schemas/AccessSecret'
        newPassword:
          $ref: '#/components/schemas/AccessSecret'
      required:
      - currentPassword
      - newPassword
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessEmailChangeInputHttp:
      type: object
      properties:
        currentProof:
          $ref: '#/components/schemas/AccessSecret'
        newEmail:
          $ref: '#/components/schemas/AccessEmail'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - currentProof
      - newEmail
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessEmailChangeCompleteInputHttp:
      type: object
      properties:
        verification:
          $ref: '#/components/schemas/AccessChallengeProof'
      required:
      - verification
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessBeginIdentityInputHttp:
      type: object
      properties:
        provider:
          type: string
          enum:
          - google
          - orcid
        intent:
          type: string
          enum:
          - sign_in
          - link
        returnRouteId:
          $ref: '#/components/schemas/Id'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - provider
      - intent
      - returnRouteId
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessIdentityListInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessUnlinkIdentityInputHttp:
      type: object
      properties:
        identityLinkId:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - identityLinkId
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessOrcidProfileInputHttp:
      type: object
      properties:
        identityLinkId:
          $ref: '#/components/schemas/Id'
      required:
      - identityLinkId
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessMfaEnrollmentInputHttp:
      type: object
      properties:
        currentProof:
          $ref: '#/components/schemas/AccessSecret'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - currentProof
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessMfaMaterialInputHttp:
      type: object
      properties:
        enrollmentId:
          $ref: '#/components/schemas/Id'
        deliveryReference:
          $ref: '#/components/schemas/Id'
        currentProof:
          $ref: '#/components/schemas/AccessSecret'
      required:
      - enrollmentId
      - deliveryReference
      - currentProof
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessMfaConfirmInputHttp:
      type: object
      properties:
        enrollmentId:
          $ref: '#/components/schemas/Id'
        verification:
          $ref: '#/components/schemas/AccessChallengeProof'
      required:
      - enrollmentId
      - verification
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessMfaVerifyInputHttp:
      type: object
      properties:
        verification:
          $ref: '#/components/schemas/AccessChallengeProof'
        factorKind:
          type: string
          enum:
          - totp
          - recovery_proof
      required:
      - verification
      - factorKind
      additionalProperties: false
      description: 'Pre-authentication request: context may contain an anonymous principal. The trusted transport separately validates the protected
        primary-authentication continuation cookie, binds it to verification.challengeId/flowBinding and the server-owned primary-authentication
        record, and passes only a verified invocation. The factor proof is untrusted until checked; neither a full session nor a caller-claimed
        account is required.'
    AccessMfaRecoveryInputHttp:
      type: object
      properties:
        verification:
          $ref: '#/components/schemas/AccessChallengeProof'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - verification
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessProfileInputHttp:
      type: object
      properties: {}
      required: []
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessProfileUpdateInputHttp:
      type: object
      properties:
        fieldVocabularyRevision:
          $ref: '#/components/schemas/Revision'
        changes:
          type: array
          items:
            $ref: '#/components/schemas/AccessProfileField'
          x-policy-bound: retained mutable-profile field vocabulary
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - fieldVocabularyRevision
      - changes
      - policyRef
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessConsentListInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    AccessConsentUpdateInputHttp:
      type: object
      properties:
        expectedRevision:
          $ref: '#/components/schemas/Revision'
        purposeId:
          $ref: '#/components/schemas/Id'
        decision:
          type: string
          enum:
          - granted
          - revoked
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - purposeId
      - decision
      - policyRef
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LifecycleRequestInputHttp:
      type: object
      properties:
        action:
          type: string
          enum:
          - withdraw
          - erase
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        confirmationRef:
          $ref: '#/components/schemas/Id'
      required:
      - action
      - policyRef
      - confirmationRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LifecycleReactivationInputHttp:
      type: object
      properties:
        verification:
          $ref: '#/components/schemas/AccessChallengeProof'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        confirmationRef:
          $ref: '#/components/schemas/Id'
      required:
      - verification
      - policyRef
      - confirmationRef
      additionalProperties: false
      description: Public pre-authentication envelope; no caller account ID or active session is required. Account and withdrawn lifecycle identity
        are resolved exclusively from the verified purpose-bound reactivation proof. Trusted transport context may remain anonymous until this
        limited recovery authority is verified.
    LifecycleStatusInputHttp:
      type: object
      properties:
        lifecycleRequestId:
          $ref: '#/components/schemas/Id'
      required:
      - lifecycleRequestId
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibrarySavePaperInputHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - paper
      - policyRef
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibrarySavedPaperInputHttp:
      type: object
      properties:
        savedPaperId:
          $ref: '#/components/schemas/Id'
      required:
      - savedPaperId
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibraryPaperListInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibrarySaveSearchInputHttp:
      type: object
      properties:
        queryContext:
          $ref: '#/components/schemas/LibraryQueryContext'
        label:
          type: string
          minLength: 1
          x-policy-bound: saved-search label policy
          description: Bound by the named approved policy before processing.
      required:
      - queryContext
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibrarySavedSearchInputHttp:
      type: object
      properties:
        savedSearchId:
          $ref: '#/components/schemas/Id'
      required:
      - savedSearchId
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibrarySearchListInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibraryHistoryListInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibraryHistoryInputHttp:
      type: object
      properties:
        historyId:
          $ref: '#/components/schemas/Id'
      required:
      - historyId
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibraryClearHistoryInputHttp:
      type: object
      properties:
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - policyRef
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    SettingsReadInputHttp:
      type: object
      properties: {}
      required: []
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    SettingsUpdateInputHttp:
      type: object
      properties:
        timeZone:
          type: string
          minLength: 1
          maxLength: 100
        searchDefaults:
          $ref: '#/components/schemas/SettingsSearchDefaults'
        assistanceDefaults:
          $ref: '#/components/schemas/SettingsAssistanceDefaults'
        appearance:
          type: string
          enum:
          - light
          - dark
          - system
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - policyRef
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
      anyOf:
      - required:
        - searchDefaults
      - required:
        - assistanceDefaults
      - required:
        - appearance
      - required:
        - timeZone
    SettingsOnboardingInputHttp:
      type: object
      properties:
        action:
          type: string
          enum:
          - save_interests
          - complete
          - skip
        interestIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-policy-bound: retained interest vocabulary and onboarding policy
          uniqueItems: true
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - action
      - interestIds
      - policyRef
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    SettingsSuggestionInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
        identityLinkId:
          $ref: '#/components/schemas/Id'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    SettingsRecentInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    SettingsResetPrepareInputHttp: {type: object, properties: {action: {type: string, enum: [delete_behavior, reset_profile]}, currentProof: {$ref: '#/components/schemas/AccessSecret'}, policyRef: {$ref: '#/components/schemas/PolicyRef'}, expectedRevision: {$ref: '#/components/schemas/Revision'}}, required: [action, currentProof, policyRef, expectedRevision], additionalProperties: false}
    SettingsResetConfirmation: {type: object, properties: {confirmationRef: {$ref: '#/components/schemas/Id'}, action: {type: string, enum: [delete_behavior, reset_profile]}, revision: {$ref: '#/components/schemas/Revision'}, expiresAt: {$ref: '#/components/schemas/Time'}}, required: [confirmationRef, action, revision, expiresAt], additionalProperties: false}
    SettingsResetInputHttp:
      type: object
      properties:
        action:
          type: string
          enum:
          - delete_behavior
          - reset_profile
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        confirmationRef:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - action
      - policyRef
      - confirmationRef
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    UsageInspectInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    UsagePlanInputHttp:
      type: object
      properties: {}
      required: []
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    UsageGrantInputHttp:
      type: object
      properties:
        accountId:
          $ref: '#/components/schemas/Id'
        tierId:
          $ref: '#/components/schemas/Id'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        reasonKey:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - accountId
      - tierId
      - policyRef
      - reasonKey
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    UsageRevokeInputHttp:
      type: object
      properties:
        accountId:
          $ref: '#/components/schemas/Id'
        entitlementId:
          $ref: '#/components/schemas/Id'
        policyRef:
          $ref: '#/components/schemas/PolicyRef'
        reasonKey:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - accountId
      - entitlementId
      - policyRef
      - reasonKey
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    UsageRecordsInputHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    CorpusResolveHttp:
      type: object
      properties:
        identifier:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        versionLabel:
          type: string
          minLength: 1
      required:
      - identifier
      additionalProperties: false
    CorpusReadHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        purpose:
          type: string
          enum:
          - metadata
          - read
          - assistance
          - research
          - citation
          - saved-reference
      required:
      - paper
      - purpose
      additionalProperties: false
    CorpusAssetReadHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        contentRevision:
          $ref: '#/components/schemas/Revision'
        assetId:
          $ref: '#/components/schemas/Id'
      required:
      - paper
      - contentRevision
      - assetId
      additionalProperties: false
    CorpusRunRequestHttp:
      type: object
      properties:
        operation:
          type: string
          enum:
          - ingest
          - incremental-refresh
          - rebuild
          - reprocess
        sourceScopeIds:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          minItems: 1
          uniqueItems: true
        authoritativeInputRevision:
          $ref: '#/components/schemas/Revision'
        inputManifestHash:
          $ref: '#/components/schemas/Hash'
        sourcePolicy:
          $ref: '#/components/schemas/PolicyRef'
        compatibilityRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - operation
      - sourceScopeIds
      - authoritativeInputRevision
      - inputManifestHash
      - sourcePolicy
      - compatibilityRevision
      additionalProperties: false
    CorpusRunReadHttp:
      type: object
      properties:
        runId:
          $ref: '#/components/schemas/Id'
      required:
      - runId
      additionalProperties: false
    CorpusEligibilityChangeHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        disposition:
          type: string
          enum:
          - eligible
          - withdrawn
          - restricted
          - unavailable
        reasonKey:
          type: string
          minLength: 1
        sourceEvidenceHash:
          $ref: '#/components/schemas/Hash'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - paper
      - disposition
      - reasonKey
      - sourceEvidenceHash
      - policy
      additionalProperties: false
    SearchRequestHttp:
      type: object
      properties:
        query:
          $ref: '#/components/schemas/LibraryQueryContext'
        page:
          $ref: '#/components/schemas/PageRequest'
        snapshotRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - query
      - page
      additionalProperties: false
    CitationRequestHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        direction:
          type: string
          enum:
          - cited
          - citing
          - both
        page:
          $ref: '#/components/schemas/PageRequest'
        traversalPolicy:
          $ref: '#/components/schemas/PolicyRef'
        snapshotRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - paper
      - direction
      - page
      - traversalPolicy
      additionalProperties: false
    AssistanceOptionsReadHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
      required:
      - paper
      additionalProperties: false
    AssistanceRequestHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        contentRevision:
          $ref: '#/components/schemas/Revision'
        contentHash:
          $ref: '#/components/schemas/Hash'
        operation:
          type: string
          enum:
          - summary
          - translation
        optionId:
          $ref: '#/components/schemas/Id'
        optionsRevision:
          $ref: '#/components/schemas/Revision'
        glossaryRevision:
          $ref: '#/components/schemas/Revision'
        processingPolicy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - paper
      - contentRevision
      - contentHash
      - operation
      - optionId
      - optionsRevision
      - glossaryRevision
      - processingPolicy
      additionalProperties: false
    AssistanceJobReadHttp:
      type: object
      properties:
        jobId:
          $ref: '#/components/schemas/Id'
      required:
      - jobId
      additionalProperties: false
    AssistanceResultRequestHttp:
      type: object
      properties:
        jobId:
          $ref: '#/components/schemas/Id'
        result:
          $ref: '#/components/schemas/ResultRef'
      required:
      - jobId
      additionalProperties: false
    AssistanceGlossaryReadHttp:
      type: object
      properties: {}
      required: []
      additionalProperties: false
    AssistanceGlossaryWriteHttp:
      type: object
      properties:
        expectedRevision:
          $ref: '#/components/schemas/Revision'
        normalizationPolicy:
          $ref: '#/components/schemas/PolicyRef'
        terms:
          type: array
          items:
            $ref: '#/components/schemas/AssistanceGlossaryTerm'
      required:
      - expectedRevision
      - normalizationPolicy
      - terms
      additionalProperties: false
    ResearchContextCreateHttp:
      type: object
      properties:
        purpose:
          type: string
          enum:
          - research
          - novelty
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - purpose
      - policy
      additionalProperties: false
    ResearchSessionCreateHttp:
      type: object
      properties:
        title:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        scope:
          $ref: '#/components/schemas/ResearchScope'
      required:
      - title
      - scope
      additionalProperties: false
    ResearchSessionReadHttp:
      type: object
      properties:
        sessionId:
          $ref: '#/components/schemas/Id'
      required:
      - sessionId
      additionalProperties: false
    ResearchSessionListHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
    ResearchDeleteHttp:
      type: object
      properties:
        scope:
          type: string
          enum:
          - one-session
          - all-sessions
        sessionId:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
        confirmed:
          const: true
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - scope
      - expectedRevision
      - confirmed
      - policy
      additionalProperties: false
      allOf:
      - if:
          properties:
            scope:
              const: one-session
        then:
          required:
          - sessionId
        else:
          not:
            required:
            - sessionId
    ResearchAttachmentStartHttp:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        fileName:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        mediaType:
          type: string
          enum:
          - application/pdf
          - text/plain
        byteLength:
          type: integer
          minimum: 1
          x-policy-limit: Maximum permitted attachment bytes; unresolved means refuse.
        contentHash:
          $ref: '#/components/schemas/Hash'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - contextId
      - fileName
      - mediaType
      - byteLength
      - contentHash
      - policy
      additionalProperties: false
    ResearchAttachmentFinishHttp:
      type: object
      properties:
        uploadId:
          $ref: '#/components/schemas/Id'
        contextId:
          $ref: '#/components/schemas/Id'
        contentHash:
          $ref: '#/components/schemas/Hash'
      required:
      - uploadId
      - contextId
      - contentHash
      additionalProperties: false
    ResearchAttachmentReadHttp:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        attachmentId:
          $ref: '#/components/schemas/Id'
      required:
      - contextId
      - attachmentId
      additionalProperties: false
    ResearchPrivateAssetReadHttp:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        attachmentId:
          $ref: '#/components/schemas/Id'
        assetId:
          $ref: '#/components/schemas/Id'
      required:
      - contextId
      - attachmentId
      - assetId
      additionalProperties: false
    DraftWriteHttp:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        draftId:
          $ref: '#/components/schemas/Id'
        kind:
          type: string
          enum:
          - research-question
          - novelty-topic
          - novelty-manuscript
          - novelty-discussion
        baseRevision:
          anyOf:
          - $ref: '#/components/schemas/Revision'
          - type: 'null'
        text:
          type: string
          x-policy-limit: Resolved owner draft text bounds.
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - contextId
      - draftId
      - kind
      - baseRevision
      - text
      - policy
      additionalProperties: false
    DraftReadHttp:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        draftId:
          $ref: '#/components/schemas/Id'
      required:
      - contextId
      - draftId
      additionalProperties: false
    DraftDiscardHttp:
      type: object
      properties:
        contextId:
          $ref: '#/components/schemas/Id'
        draft:
          $ref: '#/components/schemas/DraftRef'
        confirmed:
          const: true
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - contextId
      - draft
      - confirmed
      - policy
      additionalProperties: false
    ResearchTurnRequestHttp:
      type: object
      properties:
        sessionId:
          $ref: '#/components/schemas/Id'
        scope:
          $ref: '#/components/schemas/ResearchScope'
        mode:
          type: string
          enum:
          - question
          - compare
          - quote
        text:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        submittedDraft:
          $ref: '#/components/schemas/DraftRef'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - sessionId
      - scope
      - mode
      - text
      - policy
      additionalProperties: false
    ResearchTurnReadHttp:
      type: object
      properties:
        sessionId:
          $ref: '#/components/schemas/Id'
        turnId:
          $ref: '#/components/schemas/Id'
      required:
      - sessionId
      - turnId
      additionalProperties: false
    ResearchNoveltyRequestHttp:
      type: object
      properties:
        scope:
          $ref: '#/components/schemas/ResearchScope'
        inputMode:
          type: string
          enum:
          - topic
          - manuscript
        text:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        submittedDraft:
          $ref: '#/components/schemas/DraftRef'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - scope
      - inputMode
      - text
      - policy
      additionalProperties: false
    ResearchNoveltyDiscussionHttp:
      type: object
      properties:
        source:
          $ref: '#/components/schemas/ResearchArtifactRef'
        text:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        submittedDraft:
          $ref: '#/components/schemas/DraftRef'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - source
      - text
      - policy
      additionalProperties: false
    ResearchJobReadHttp:
      type: object
      properties:
        kind:
          type: string
          enum:
          - research-turn
          - novelty-analysis
          - novelty-discussion
        jobId:
          $ref: '#/components/schemas/Id'
        contextId:
          $ref: '#/components/schemas/Id'
      required:
      - kind
      - jobId
      - contextId
      additionalProperties: false
    ResearchArtifactReadHttp:
      type: object
      properties:
        artifact:
          $ref: '#/components/schemas/ResearchArtifactRef'
      required:
      - artifact
      additionalProperties: false
    DigestSubscriptionWriteHttp:
      type: object
      properties:
        topic:
          type: string
          minLength: 1
          x-policy-limit: Resolve content/input byte and character limits before enabling this operation.
        enabled:
          type: boolean
        schedule:
          $ref: '#/components/schemas/DigestSchedule'
        expectedRevision:
          anyOf:
          - $ref: '#/components/schemas/Revision'
          - type: 'null'
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - topic
      - enabled
      - schedule
      - expectedRevision
      - policy
      additionalProperties: false
    DigestSubscriptionsReadHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - page
      additionalProperties: false
    DigestSubscriptionReadHttp:
      type: object
      properties:
        subscriptionId:
          $ref: '#/components/schemas/Id'
      required:
      - subscriptionId
      additionalProperties: false
    DigestDeliveryReadHttp:
      type: object
      properties:
        deliveryId:
          $ref: '#/components/schemas/Id'
      required:
      - deliveryId
      additionalProperties: false
    DigestUnsubscribeHttp:
      type: object
      properties:
        signedToken:
          type: string
          minLength: 1
        confirmed:
          const: true
      required:
      - signedToken
      - confirmed
      additionalProperties: false
    ExportConnectionConfigureHttp:
      type: object
      properties:
        token:
          type: string
          minLength: 1
          writeOnly: true
          x-policy-limit: Resolved credential input bounds; reject and redact invalid credentials.
        expectedRevision:
          anyOf:
          - $ref: '#/components/schemas/Revision'
          - type: 'null'
        credentialPolicy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - token
      - expectedRevision
      - credentialPolicy
      additionalProperties: false
    ExportConnectionReadHttp:
      type: object
      properties:
        connectionId:
          $ref: '#/components/schemas/Id'
      required: []
      additionalProperties: false
    ExportPreviewRequestHttp:
      type: object
      properties:
        source:
          $ref: '#/components/schemas/ResearchArtifactRef'
        destination:
          $ref: '#/components/schemas/ExportDestination'
        renderPolicy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - source
      - destination
      - renderPolicy
      additionalProperties: false
    ExportApprovalRequestHttp:
      type: object
      properties:
        previewId:
          $ref: '#/components/schemas/Id'
        previewRevision:
          $ref: '#/components/schemas/Revision'
        bindingHash:
          $ref: '#/components/schemas/Hash'
        explicitApproval:
          const: true
      required:
      - previewId
      - previewRevision
      - bindingHash
      - explicitApproval
      additionalProperties: false
    ExportExecuteHttp:
      type: object
      properties:
        approvalId:
          $ref: '#/components/schemas/Id'
        bindingHash:
          $ref: '#/components/schemas/Hash'
      required:
      - approvalId
      - bindingHash
      additionalProperties: false
    ExportEffectReadHttp:
      type: object
      properties:
        effectId:
          $ref: '#/components/schemas/Id'
      required:
      - effectId
      additionalProperties: false
    ExportCancelHttp:
      type: object
      properties:
        approvalId:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - approvalId
      - expectedRevision
      additionalProperties: false
    ExportHistoryListHttp:
      type: object
      properties:
        limit:
          type: integer
          minimum: 1
          maximum: 20
        cursor:
          anyOf:
          - type: string
            minLength: 1
            maxLength: 512
          - type: 'null'
      required: []
      additionalProperties: false
    ExportSettleHttp:
      type: object
      properties:
        effectId:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
        disposition:
          $ref: '#/components/schemas/ExportSettleDisposition'
        assumptionAccepted:
          const: true
        remoteUrl:
          type: string
          minLength: 1
          format: uri
      required:
      - effectId
      - expectedRevision
      - disposition
      - assumptionAccepted
      additionalProperties: false
    OpsQueryHttp:
      type: object
      properties:
        page:
          $ref: '#/components/schemas/PageRequest'
        capability:
          $ref: '#/components/schemas/Id'
      required:
      - page
      additionalProperties: false
    OpsRecoveryRequestHttp:
      type: object
      properties:
        incidentId:
          $ref: '#/components/schemas/Id'
        ownerComponent:
          $ref: '#/components/schemas/Id'
        operation:
          $ref: '#/components/schemas/Id'
        targetId:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
        evidenceRefs:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
        policy:
          $ref: '#/components/schemas/PolicyRef'
      required:
      - incidentId
      - ownerComponent
      - operation
      - targetId
      - expectedRevision
      - evidenceRefs
      - policy
      additionalProperties: false
    PreparedJobRead:
      oneOf:
      - $ref: '#/components/schemas/AssistanceResultRead'
      - $ref: '#/components/schemas/ResearchArtifactResponse'
    LibraryRemoveSavedPaperInputHttp:
      type: object
      properties:
        savedPaperId:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - savedPaperId
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    LibraryRemoveSavedSearchInputHttp:
      type: object
      properties:
        savedSearchId:
          $ref: '#/components/schemas/Id'
        expectedRevision:
          $ref: '#/components/schemas/Revision'
      required:
      - savedSearchId
      - expectedRevision
      additionalProperties: false
      description: Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    UsageAssignmentReadHttp:
      type: object
      properties:
        accountId:
          $ref: '#/components/schemas/Id'
      required:
      - accountId
      additionalProperties: false
    UsageAssignmentSnapshot:
      type: object
      properties:
        accountId:
          $ref: '#/components/schemas/Id'
        revision:
          $ref: '#/components/schemas/Revision'
        entitlement:
          anyOf:
          - $ref: '#/components/schemas/UsageEntitlement'
          - type: 'null'
      required:
      - accountId
      - revision
      - entitlement
      additionalProperties: false
    AssistanceHistoryReadHttp:
      type: object
      properties:
        paper:
          $ref: '#/components/schemas/PaperRef'
        page:
          $ref: '#/components/schemas/PageRequest'
      required:
      - paper
      - page
      additionalProperties: false
    AssistanceHistoryRow:
      type: object
      properties:
        jobId:
          $ref: '#/components/schemas/Id'
        paper:
          $ref: '#/components/schemas/PaperRef'
        contentRevision:
          $ref: '#/components/schemas/Revision'
        contentHash:
          $ref: '#/components/schemas/Hash'
        operation:
          enum:
          - summary
          - translation
        optionId:
          $ref: '#/components/schemas/Id'
        optionsRevision:
          $ref: '#/components/schemas/Revision'
        glossaryRevision:
          $ref: '#/components/schemas/Revision'
        state:
          enum:
          - accepted
          - running
          - succeeded
          - failed
        revision:
          $ref: '#/components/schemas/Revision'
        seq:
          type: integer
          minimum: 0
        createdAt:
          $ref: '#/components/schemas/Time'
        availability:
          enum:
          - ready
          - pending
          - failed
          - expired
          - withdrawn
          - restricted
        result:
          anyOf:
          - $ref: '#/components/schemas/ResultRef'
          - type: 'null'
      required:
      - jobId
      - paper
      - contentRevision
      - contentHash
      - operation
      - optionId
      - optionsRevision
      - glossaryRevision
      - state
      - revision
      - seq
      - createdAt
      - availability
      - result
      additionalProperties: false
      allOf:
      - if:
          properties:
            availability:
              const: ready
        then:
          properties:
            state:
              const: succeeded
            result:
              $ref: '#/components/schemas/ResultRef'
        else:
          properties:
            result:
              type: 'null'
    AssistanceHistoryPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/AssistanceHistoryRow'
          x-policy-bound: accepted PageRequest.limit
        page:
          $ref: '#/components/schemas/PageInfo'
      required:
      - items
      - page
      additionalProperties: false
  responses:
    E400:
      description: Malformed input
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E401:
      description: Authentication required
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E403:
      description: Permission or current MFA required
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E404:
      description: Absent or unauthorized resource
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E409:
      description: Revision/identity conflict or unknown effect
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E410:
      description: Authorized result expired
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E422:
      description: Validation failed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E429:
      description: Admission/usage/rate limit
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E503:
      description: Dependency, compatibility or required policy unavailable
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E504:
      description: Deadline exceeded
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    Edefault:
      description: Typed safe failure
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
```

## C10 — Controlled evidence HTTP binding

This binding remains isolated from public application access. Its v2 wire revision does not remove the retained v1 interface before consumer and native-platform compatibility evidence is approved.

```yaml openapi
openapi: 3.1.1
info:
  title: DocSuri controlled evidence v2 binding
  version: 2.0.0
  description: Proposed separately controlled read-only evidence API; native membership and compatibility inventory remain prerequisites. Never
    reachable as an application admin mount.
security:
- verifiedPeer: []
paths:
  /healthz:
    get:
      operationId: controlledLiveness
      description: No request body; bounded verified-peer read. Reject non-loopback peers, wrong target scope and unverified peer identity. Current
        evidence is not mutation authority.
      parameters: []
      responses:
        '200':
          description: Authorized read
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessLiveness'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /readyz:
    get:
      operationId: controlledReadiness
      description: No request body; bounded verified-peer read. Reject non-loopback peers, wrong target scope and unverified peer identity. Current
        evidence is not mutation authority.
      parameters: []
      responses:
        '200':
          description: Authorized read
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ControlledReadiness'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /internal/v2/evidence/{targetId}:
    get:
      operationId: readControlledEvidence
      description: No request body; bounded verified-peer read. Reject non-loopback peers, wrong target scope and unverified peer identity. Current
        evidence is not mutation authority.
      parameters:
      - name: targetId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      responses:
        '200':
          description: Authorized read
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OperatorEvidence'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
  /internal/v2/compatibility/{targetId}:
    get:
      operationId: readControlledCompatibility
      description: No request body; bounded verified-peer read. Reject non-loopback peers, wrong target scope and unverified peer identity. Current
        evidence is not mutation authority.
      parameters:
      - name: targetId
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/Id'
      responses:
        '200':
          description: Authorized read
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OperatorEvidence'
        '400':
          $ref: '#/components/responses/E400'
        '401':
          $ref: '#/components/responses/E401'
        '403':
          $ref: '#/components/responses/E403'
        '404':
          $ref: '#/components/responses/E404'
        '409':
          $ref: '#/components/responses/E409'
        '410':
          $ref: '#/components/responses/E410'
        '422':
          $ref: '#/components/responses/E422'
        '429':
          $ref: '#/components/responses/E429'
        '503':
          $ref: '#/components/responses/E503'
        '504':
          $ref: '#/components/responses/E504'
        default:
          $ref: '#/components/responses/Edefault'
components:
  securitySchemes:
    verifiedPeer:
      type: mutualTLS
      description: Transport-verified peer identity and target-scoped read grant; loopback required; never an identity header.
  schemas:
    Id:
      type: string
      minLength: 1
      maxLength: 128
    Revision:
      type: string
      minLength: 1
      maxLength: 128
    Time:
      type: string
      format: date-time
    Hash:
      type: string
      pattern: ^[a-f0-9]{64}$
    Error:
      type: object
      properties:
        code:
          type: string
          enum:
          - APPROVAL_REQUIRED
          - CANCELLED
          - CAPACITY_EXHAUSTED
          - CONFLICT
          - CONSENT_REVOKED
          - DEADLINE_EXCEEDED
          - DEPENDENCY_UNAVAILABLE
          - EXPIRED
          - FORBIDDEN
          - IDEMPOTENCY_CONFLICT
          - INCOMPATIBLE
          - INCOMPATIBLE_VERSION
          - INTERNAL_ERROR
          - INVALID_ARGUMENT
          - INVALID_CONTENT
          - INVALID_INPUT
          - INVALID_TOKEN
          - MFA_REQUIRED
          - NOT_FOUND
          - NOT_READY
          - OUTCOME_UNKNOWN
          - POLICY_DENIED
          - POLICY_UNRESOLVED
          - QUOTA_EXCEEDED
          - RATE_LIMITED
          - SNAPSHOT_EXPIRED
          - SOURCE_INELIGIBLE
          - STALE_REVISION
          - UNAUTHENTICATED
          - UNKNOWN_OUTCOME
        requestId:
          $ref: '#/components/schemas/Id'
        retryable:
          type: boolean
        messageKey:
          $ref: '#/components/schemas/Id'
        retryAfterSeconds:
          type: integer
          minimum: 0
        details:
          type: object
          properties:
            fieldNames:
              type: array
              items:
                $ref: '#/components/schemas/Id'
              x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
          required:
          - fieldNames
          additionalProperties: false
      required:
      - code
      - requestId
      - retryable
      - messageKey
      additionalProperties: false
    OperatorEvidence:
      type: object
      properties:
        evidenceId:
          $ref: '#/components/schemas/Id'
        targetId:
          $ref: '#/components/schemas/Id'
        inputHash:
          $ref: '#/components/schemas/Hash'
        generation:
          $ref: '#/components/schemas/Revision'
        observedAt:
          $ref: '#/components/schemas/Time'
        compatibility:
          type: string
          enum:
          - compatible
          - incompatible
          - unknown
        checks:
          type: array
          items:
            type: object
            properties:
              name:
                $ref: '#/components/schemas/Id'
              outcome:
                type: string
                enum:
                - pass
                - fail
                - unknown
              evidenceRef:
                $ref: '#/components/schemas/Id'
            required:
            - name
            - outcome
            - evidenceRef
            additionalProperties: false
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
      required:
      - evidenceId
      - targetId
      - inputHash
      - generation
      - observedAt
      - compatibility
      - checks
      additionalProperties: false
    ProcessLiveness:
      type: object
      properties:
        status:
          const: alive
      required:
      - status
      additionalProperties: false
    ControlledReadiness:
      type: object
      properties:
        status:
          type: string
          enum:
          - ready
          - not_ready
          - unknown
        generation:
          $ref: '#/components/schemas/Revision'
        reasonKeys:
          type: array
          items:
            $ref: '#/components/schemas/Id'
          x-limit-policy: AdmissionPolicy bounds length; unresolved policy blocks admission.
      required:
      - status
      - generation
      - reasonKeys
      additionalProperties: false
  responses:
    E400:
      description: Malformed input
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E401:
      description: Authentication required
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E403:
      description: Permission or current MFA required
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E404:
      description: Absent or unauthorized resource
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E409:
      description: Revision/identity conflict or unknown effect
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E410:
      description: Authorized result expired
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E422:
      description: Validation failed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E429:
      description: Admission/usage/rate limit
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E503:
      description: Dependency, compatibility or required policy unavailable
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    E504:
      description: Deadline exceeded
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
    Edefault:
      description: Typed safe failure
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
```

## Canonical identity and immutable approval binding

`Hash` is lowercase hexadecimal SHA-256. Raw attachments and stored binary assets
hash their exact bytes. Structured prepared outputs hash UTF-8 bytes of RFC 8785
JSON Canonicalization Scheme (JCS), with the domain prefix
`docsuri:prepared-output:v1\n` prepended. Input validation rejects duplicate JSON
keys, non-finite numbers and malformed Unicode; JCS does not silently normalize
Unicode. Publish a new canonicalization version before changing these rules.

The export renderer owns the exact UTF-8 `renderedText` representation and hashes
those bytes without a trailing newline insertion. Its policy revision binds any
subsequent provider block conversion; the converted payload must have a stored
digest before dispatch. Preview `bindingHash` hashes the prefix
`docsuri:export-binding:v1\n` followed by JCS bytes of the object containing exactly
`ownerId`, `previewId`, `revision`, `source`, `sourceEligibilityRevision`,
`connectionRevision`, `destination`, `renderedContentHash` and `renderPolicy`
from `ExportPreview`. `bindingHash` is excluded from its own preimage.
The immutable source reference includes the exact artifact ID, revision and
content hash. Do not substitute the newest artifact or destination at dispatch.
Changes require a fresh preview and deliberate approval. Verification must use
shared golden byte vectors across every producer and consumer.

## Contract ownership rules

- The authoritative component named in each contract owns its semantic spec and
  data. The provider unit delivers the initial implementation; subsequent units
  extend that same owner. Consumers cannot directly write another owner's tables,
  projections, lifecycle acknowledgements or accounting balances.
- All local schema references resolve into C00. Contract `1.0.0` is the proposed
  initial v2 contract release. HTTP path `v2` distinguishes the application
  generation; it does not imply compatibility with existing routes or overwrite
  an existing published specification.
- Before changing a shared type, record affected operations and consumers,
  examples, compatibility tests, storage implications and a coordinated rollout
  or rollback. Safe additive response fields may be ignored after compatible
  publication; security, status and authority fields are never silently ignored.
  Breaking meaning, required input or enum changes need a major contract revision,
  migration evidence where applicable and approval from the affected owners.
- Existing consumers and retained native platform protocol membership must be
  inventoried before legacy behavior is removed. Do not invent a deprecation
  period or claim that no external consumers exist. One application permits
  coordinated local module releases; the controlled operator surface retains
  its separate compatibility and authority check.
- The project maintainer owns scope decisions. Follow CONVENTIONS.md: reviewable
  working branches merge through PRs into develop when their purpose is complete;
  release promotion to main is separate. The interim CI policy remains recorded
  in the [integration evidence](../../maintenance/develop-integration.md).

## Domain-review clarification disposition

| Accepted upstream finding | Contract decision | Later closure evidence |
|---|---|---|
| Domain R-01: search projection writes and withdrawal | C04 assigns authoritative corpus eligibility, projection build/publication and atomic generation switch to CorpusContent. C05 reads only published generations and rechecks current withdrawal eligibility; discovery owns query semantics, not corpus writes. | Race tests for duplicate batches, failed rebuild, concurrent withdrawal, stale generation/cursors and restoration. U1/U3 own implementation; U8 verifies integration. |
| Domain R-02: artifact revision approved for export | C07 produces an immutable research artifact reference. C09 binds owner, exact artifact revision/hash, current eligibility, connection, destination, renderer policy and preview revision/hash to explicit approval and one logical export effect. | Changed artifact/destination/connection, approval replay/cancellation, revocation race and unknown remote-outcome reconciliation tests. U4/U6 own implementation; U8 verifies integration. |

These decisions specify the intended behavior. They do not claim executed
runtime closure of the earlier findings or of the four paper-job defects.

## Open questions

These are evidence-dependent implementation conditions already carried by the
approved scope. A blocked affected operation is not an acceptable substitute for
full capability parity in the first v2 release. Synthetic isolated development
may proceed where its own data policy and limits are resolved; it cannot decide
existing-user continuity or demonstrate sustainable public-service operation.

| Contract | Question | Blocks |
|---|---|---|
| C02/C03/C07/C08/C09/C11/C14 | Which authoritative users, saved data, environments and recoverable backups exist? What continuity and restore policy does the maintainer choose after inventory and a restore drill? | IB-02; all affected units before migration, destructive continuity changes or claims of existing-data recovery. |
| C02/C03/C07/C09/C11 | What retention, deletion/reactivation, backup disposition and shared-device draft-storage policy applies to each data class? Which legal/content/consent conditions apply? | IB-03; affected sensitive persistence and lifecycle implementation, before choosing storage/location. Requires explicit policy revisions and owner/participant closure evidence. |
| C00/C03/C04/C06/C07/C08/C11/C12/C14 | Which free/local configuration supports the measured workload, finite input/list limits, deadlines, retry budgets, quota rules and queue/concurrency bounds without paid fallback? | IB-04/IB-05; enabling affected public work and selecting operating limits. U1 supplies baseline; each unit proves its path; U8 verifies complete fit. |
| C04/C05/C06/C07/C08/C09/C12 | Which current source/provider API versions, request/response fields, permission and free-service limits apply? What model/action/level/language/format and search-filter vocabularies are retained? | IB-01/IB-03/IB-05; affected adapter implementation and capability-parity closure. Each typed profile must be bound to a verified provider schema and fixtures, with no silent omitted mode. |
| C02/C12 | What email delivery, Google/ORCID integration, MFA recovery and abuse-admission policy can the public service sustain at $0? | U1/U2 public identity paths; no mock provider path counts as public registration/identity evidence. |
| C10 | What is the complete retained native command/evidence/compatibility protocol membership, authority model and existing-consumer matrix? | U7/U8 protocol replacement or removals. The generic typed envelope is not a completed per-command parity inventory. |
| C13/C10 | Which deployed clients and integrations rely on current routes, payloads, session behavior and platform v1 endpoints? Which transition is approved? | Any legacy API removal or breaking rollout. U8 reconciles evidence with affected owners before release. |
| All contracts | Which numeric correctness, responsiveness, recovery and repairability targets follow from the measured baseline and user agreement? | Delivery acceptance thresholds and operating SLAs; no numbers selected here. |

## Non-functional and backlog obligations

| Requirement | Contract responsibility and proof |
|---|---|
| NFR1 complete-task correctness | C01–C14: execute the two documented paper tasks through real browser, persistence, worker and adapter boundaries; then complete every retained capability's parity ledger. |
| NFR2 responsiveness | C01/C06/C07/C13/C14: bounded waits, truthful progress, retained context and actionable errors; measure cold/warm and interrupted paths before target agreement. |
| NFR3 durability | C02–C09/C14: atomic acceptance, owner receipts, conflict handling, crash recovery, idempotency and restore drills, including failed writes and delayed completion. |
| NFR4 multi-user security | C00/C02/all private boundaries: current owner checks, anonymous restrictions, CSRF, MFA, operator separation, safe content handling and abuse admission; verify every list/read/event/asset/effect. |
| NFR5 privacy/content | C02/C04/C07–C12: investigated permissions and policy revisions; account, private content, credentials, behavior and operational evidence remain separate; deletion/restore evidence includes derived work. |
| NFR6 accessibility | C01/C13 plus every UI contribution: coherent Korean states and error keys, preserved search/draft context, keyboard/focus and announced status; execute the approved WCAG 2.2 AA design checklist later. |
| NFR7 repairability | Named owners, schema references, reproducible validators and cross-boundary fixtures; demonstrate diagnosis, repair and affected regression checks from a clean setup. |
| NFR8 sustainable $0 capacity | C03/C11/C12/C14: verified finite local/free limits, backpressure, explicit unavailable states, bounded reconciliation; no auto-purchase or paid fallback. |
| NFR9 observability | C00/C11/C14: correlation/operation/effect identities and safe outcome categories; distinguish stale, unavailable and unknown evidence; exclude secrets/private text from routine logs. |
| NFR10 consistency | C00/C01/C10/C12/C13/C14: common revisions and schemas, compatible adapters, real SSE/reconnect/result/dispatch checks and coordinated consumer changes. |

IB-01 capability inventory, IB-02 continuity, IB-03 obligations, IB-04 baseline,
IB-05 free/local capacity, IB-06 repairable foundations, IB-07 anchor journey,
IB-08 full parity and IB-09 release/continuity proof remain the approved backlog
outcomes. Contract documentation alone closes none of their runtime evidence.

## Verification and implementation handoff

[verify.py](verify.py) extracts the inline YAML, checks JSON Schema 2020-12 and
OpenAPI documents, resolves references, compares canonical HTTP schema copies,
checks every declared browser operation has a binding, and reconciles all 70
functional IDs and the 19 unit edges against approved upstream files. It runs
positive and negative shape fixtures. The [verification record](verification.md)
names the exact environment, results and limits.

Later executable contract suites must include, at minimum:

1. Every operation's valid request and typed errors; unexpected identity fields,
   cross-owner references and unauthorized role/token contexts must be rejected.
2. Account expiry, role/consent revocation and source withdrawal during reads,
   streams, worker completion, attachment delivery and remote dispatch.
3. Lost acceptance responses, duplicate keys with same/different inputs, worker
   crash before/after acceptance and completion, stale leases and bounded retries.
4. Actual browser-to-service SSE bytes and snapshot/result shapes, reconnect
   gaps, duplicate sequence handling, terminal closure and polling fallback.
5. Two-window draft conflicts, save acknowledgement loss, browser restart,
   account switch/logout isolation, deletion and restore; unsaved text is never
   promised recoverable, and accepted committed messages remain separate.
6. History clear versus delayed search facts; preference opt-out versus delayed
   events; lifecycle manifests with absent/incompatible participants; restore
   against current tombstones rather than old backup authority.
7. Projection rebuild/publish/withdraw races, stale eligible-search pages,
   private attachment namespaces and unsafe asset/document input.
8. Preview changes, approval replay, cancelled approval, destination changes,
   external success with lost acknowledgement and provider quota exhaustion.
   Unknown outcomes must reconcile without duplicate export/email effects.
9. Independent operator peer/target authorization and every retained native
   command's preconditions, evidence, compatibility and restart behavior.
10. All required provider profiles against recorded primary specifications and
    real permitted free/local integration fixtures; a test double proves only its
    own contract compliance until checked against the real adapter.

No application tests, capacity measurements, data migration, live provider
calls, deployment or current-user validation are claimed by this specification.

## Sources and specification versions

- Approved inputs: [requirements](../requirements-analysis/requirements.md),
  [components](../domain-design/components.md), [domain decisions](../domain-design/decisions.md),
  [unit catalogue](../units-generation/unit-of-work.md), [dependency DAG](../units-generation/unit-of-work-dependency.md),
  [confirmed contract plan](contract-design-questions.md).
- Current-behavior evidence: [repository API inventory](../../../../codekb/DocSuri/api-documentation.md)
  and [code-quality findings](../../../../codekb/DocSuri/code-quality-assessment.md).
  Source checks in the confirmed plan establish guest search and owner authority;
  these documents are reference evidence, not proof that runtime behavior works.
- Schema/wire standards, consulted 2026-10-11:
  [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html),
  [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core),
  [HTTP semantics, RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html),
  [HTML Server-sent events](https://html.spec.whatwg.org/dev/server-sent-events.html),
  [JSON canonicalization, RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html).
- Provider references consulted for boundary risks; full adapter/free-limit
  verification remains open:
  [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect),
  [ORCID authenticated identity tutorial](https://info.orcid.org/documentation/api-tutorials/api-tutorial-get-and-authenticated-orcid-id/),
  [Notion request limits](https://developers.notion.com/reference/request-limits).
  Notion's documented timeout/overload outcomes reinforce reconciliation before
  retry; this does not establish that the proposed public service fits free limits.

## Executed schema cases

The verifier checks the positive and negative instances below. They are shape checks, not account-isolation, transactional or runtime tests.

```yaml schema-cases
cases:
- name: account principal
  schema: Principal
  instance:
    kind: account
    accountId: a1
    authorityRevision: r1
    roles:
    - user
    mfa: false
  valid: true
- name: anonymous lacks authority
  schema: Principal
  instance:
    kind: anonymous
    requestScope: x
  valid: true
- name: anonymous cannot claim account fields
  schema: Principal
  instance:
    kind: anonymous
    accountId: a1
    authorityRevision: r1
    roles:
    - user
    mfa: false
  valid: false
- name: negative page size
  schema: PageRequest
  instance:
    limit: -1
  valid: false
- name: running snapshot
  schema: JobSnapshot
  instance:
    jobId: j1
    kind: summarize
    state: running
    revision: r1
    seq: 1
    ownerId: a1
    progress:
      mode: indeterminate
    result: null
    error: null
    acceptedAt: '2026-10-11T00:00:00Z'
  valid: true
- name: negative sequence
  schema: JobSnapshot
  instance:
    jobId: j1
    kind: summarize
    state: running
    revision: r1
    seq: -1
    ownerId: a1
    progress:
      mode: indeterminate
    result: null
    error: null
    acceptedAt: '2026-10-11T00:00:00Z'
  valid: false
- name: success needs result
  schema: JobSnapshot
  instance:
    jobId: j1
    kind: summarize
    state: succeeded
    revision: r1
    seq: 1
    ownerId: a1
    progress:
      mode: indeterminate
    result: null
    error: null
    acceptedAt: '2026-10-11T00:00:00Z'
  valid: false
- name: prepared success
  schema: JobSnapshot
  instance:
    jobId: j1
    kind: summarize
    state: succeeded
    revision: r1
    seq: 1
    ownerId: a1
    progress:
      mode: indeterminate
    result:
      resultId: r
      revision: r1
      contentHash: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      mediaType: application/json
    error: null
    acceptedAt: '2026-10-11T00:00:00Z'
  valid: true
- name: invalid result digest
  schema: JobSnapshot
  instance:
    jobId: j1
    kind: summarize
    state: succeeded
    revision: r1
    seq: 1
    ownerId: a1
    progress:
      mode: indeterminate
    result:
      resultId: r
      revision: r1
      contentHash: oops
      mediaType: application/json
    error: null
    acceptedAt: '2026-10-11T00:00:00Z'
  valid: false
- name: unknown error code
  schema: Error
  instance:
    code: MADE_UP
    requestId: r
    retryable: false
    messageKey: e
  valid: false
- name: explicit unknown effect
  schema: Error
  instance:
    code: UNKNOWN_OUTCOME
    requestId: r
    retryable: false
    messageKey: outcome.unknown
  valid: true
- name: policy reference
  schema: PolicyRef
  instance:
    policyId: drafts
    revision: v1
  valid: true
- name: missing policy revision
  schema: PolicyRef
  instance:
    policyId: drafts
  valid: false
- name: unvalidated callback profile rejected
  schema: ProviderRequest
  instance:
    adapterId: random
    validatedPayload: {}
  valid: false
- name: event with missing identity
  schema: DispatchFact
  instance:
    kind: succeeded
  valid: false
- name: AccessUnlinkIdentityInputHttp-valid-precondition
  schema: AccessUnlinkIdentityInputHttp
  instance:
    identityLinkId: link1
    expectedRevision: r1
  valid: true
- name: AccessUnlinkIdentityInputHttp-missing-precondition
  schema: AccessUnlinkIdentityInputHttp
  instance:
    identityLinkId: link1
  valid: false
- name: AccessUnlinkIdentityInputHttp-null-precondition
  schema: AccessUnlinkIdentityInputHttp
  instance:
    identityLinkId: link1
    expectedRevision: null
  valid: false
- name: AccessUnlinkIdentityInputHttp-empty-precondition
  schema: AccessUnlinkIdentityInputHttp
  instance:
    identityLinkId: link1
    expectedRevision: ''
  valid: false
- name: AccessProfileUpdateInputHttp-valid-precondition
  schema: AccessProfileUpdateInputHttp
  instance:
    fieldVocabularyRevision: r1
    changes: &id001 []
    policyRef: &id002
      policyId: synthetic
      revision: r1
    expectedRevision: r1
  valid: true
- name: AccessProfileUpdateInputHttp-missing-precondition
  schema: AccessProfileUpdateInputHttp
  instance:
    fieldVocabularyRevision: r1
    changes: *id001
    policyRef: *id002
  valid: false
- name: AccessProfileUpdateInputHttp-null-precondition
  schema: AccessProfileUpdateInputHttp
  instance:
    fieldVocabularyRevision: r1
    changes: *id001
    policyRef: *id002
    expectedRevision: null
  valid: false
- name: AccessProfileUpdateInputHttp-empty-precondition
  schema: AccessProfileUpdateInputHttp
  instance:
    fieldVocabularyRevision: r1
    changes: *id001
    policyRef: *id002
    expectedRevision: ''
  valid: false
- name: LibraryClearHistoryInputHttp-valid-precondition
  schema: LibraryClearHistoryInputHttp
  instance:
    policyRef: *id002
    expectedRevision: r1
  valid: true
- name: LibraryClearHistoryInputHttp-missing-precondition
  schema: LibraryClearHistoryInputHttp
  instance:
    policyRef: *id002
  valid: false
- name: LibraryClearHistoryInputHttp-null-precondition
  schema: LibraryClearHistoryInputHttp
  instance:
    policyRef: *id002
    expectedRevision: null
  valid: false
- name: LibraryClearHistoryInputHttp-empty-precondition
  schema: LibraryClearHistoryInputHttp
  instance:
    policyRef: *id002
    expectedRevision: ''
  valid: false
- name: SettingsUpdateInputHttp-valid-precondition
  schema: SettingsUpdateInputHttp
  instance:
    appearance: system
    policyRef: *id002
    expectedRevision: r1
  valid: true
- name: SettingsUpdateInputHttp-missing-precondition
  schema: SettingsUpdateInputHttp
  instance:
    appearance: system
    policyRef: *id002
  valid: false
- name: SettingsUpdateInputHttp-null-precondition
  schema: SettingsUpdateInputHttp
  instance:
    appearance: system
    policyRef: *id002
    expectedRevision: null
  valid: false
- name: SettingsUpdateInputHttp-empty-precondition
  schema: SettingsUpdateInputHttp
  instance:
    appearance: system
    policyRef: *id002
    expectedRevision: ''
  valid: false
- name: SettingsOnboardingInputHttp-valid-precondition
  schema: SettingsOnboardingInputHttp
  instance:
    action: skip
    interestIds: &id003 []
    policyRef: *id002
    expectedRevision: r1
  valid: true
- name: SettingsOnboardingInputHttp-missing-precondition
  schema: SettingsOnboardingInputHttp
  instance:
    action: skip
    interestIds: *id003
    policyRef: *id002
  valid: false
- name: SettingsOnboardingInputHttp-null-precondition
  schema: SettingsOnboardingInputHttp
  instance:
    action: skip
    interestIds: *id003
    policyRef: *id002
    expectedRevision: null
  valid: false
- name: SettingsOnboardingInputHttp-empty-precondition
  schema: SettingsOnboardingInputHttp
  instance:
    action: skip
    interestIds: *id003
    policyRef: *id002
    expectedRevision: ''
  valid: false
- name: SettingsResetInputHttp-valid-precondition
  schema: SettingsResetInputHttp
  instance:
    action: delete_behavior
    confirmationRef: confirmation1
    policyRef: *id002
    expectedRevision: r1
  valid: true
- name: SettingsResetInputHttp-missing-precondition
  schema: SettingsResetInputHttp
  instance:
    action: delete_behavior
    confirmationRef: confirmation1
    policyRef: *id002
  valid: false
- name: SettingsResetInputHttp-null-precondition
  schema: SettingsResetInputHttp
  instance:
    action: delete_behavior
    confirmationRef: confirmation1
    policyRef: *id002
    expectedRevision: null
  valid: false
- name: SettingsResetInputHttp-empty-precondition
  schema: SettingsResetInputHttp
  instance:
    action: delete_behavior
    confirmationRef: confirmation1
    policyRef: *id002
    expectedRevision: ''
  valid: false
- name: UsageGrantInputHttp-valid-precondition
  schema: UsageGrantInputHttp
  instance:
    accountId: a1
    tierId: free
    reasonKey: test
    policyRef: *id002
    expectedRevision: r1
  valid: true
- name: UsageGrantInputHttp-missing-precondition
  schema: UsageGrantInputHttp
  instance:
    accountId: a1
    tierId: free
    reasonKey: test
    policyRef: *id002
  valid: false
- name: UsageGrantInputHttp-null-precondition
  schema: UsageGrantInputHttp
  instance:
    accountId: a1
    tierId: free
    reasonKey: test
    policyRef: *id002
    expectedRevision: null
  valid: false
- name: UsageGrantInputHttp-empty-precondition
  schema: UsageGrantInputHttp
  instance:
    accountId: a1
    tierId: free
    reasonKey: test
    policyRef: *id002
    expectedRevision: ''
  valid: false
- name: UsageRevokeInputHttp-valid-precondition
  schema: UsageRevokeInputHttp
  instance:
    accountId: a1
    entitlementId: e1
    reasonKey: test
    policyRef: *id002
    expectedRevision: r1
  valid: true
- name: UsageRevokeInputHttp-missing-precondition
  schema: UsageRevokeInputHttp
  instance:
    accountId: a1
    entitlementId: e1
    reasonKey: test
    policyRef: *id002
  valid: false
- name: UsageRevokeInputHttp-null-precondition
  schema: UsageRevokeInputHttp
  instance:
    accountId: a1
    entitlementId: e1
    reasonKey: test
    policyRef: *id002
    expectedRevision: null
  valid: false
- name: UsageRevokeInputHttp-empty-precondition
  schema: UsageRevokeInputHttp
  instance:
    accountId: a1
    entitlementId: e1
    reasonKey: test
    policyRef: *id002
    expectedRevision: ''
  valid: false
- name: LibraryRemoveSavedPaperInputHttp-valid-precondition
  schema: LibraryRemoveSavedPaperInputHttp
  instance:
    savedPaperId: saved1
    expectedRevision: r1
  valid: true
- name: LibraryRemoveSavedPaperInputHttp-missing-precondition
  schema: LibraryRemoveSavedPaperInputHttp
  instance:
    savedPaperId: saved1
  valid: false
- name: LibraryRemoveSavedPaperInputHttp-null-precondition
  schema: LibraryRemoveSavedPaperInputHttp
  instance:
    savedPaperId: saved1
    expectedRevision: null
  valid: false
- name: LibraryRemoveSavedPaperInputHttp-empty-precondition
  schema: LibraryRemoveSavedPaperInputHttp
  instance:
    savedPaperId: saved1
    expectedRevision: ''
  valid: false
- name: LibraryRemoveSavedSearchInputHttp-valid-precondition
  schema: LibraryRemoveSavedSearchInputHttp
  instance:
    savedSearchId: saved1
    expectedRevision: r1
  valid: true
- name: LibraryRemoveSavedSearchInputHttp-missing-precondition
  schema: LibraryRemoveSavedSearchInputHttp
  instance:
    savedSearchId: saved1
  valid: false
- name: LibraryRemoveSavedSearchInputHttp-null-precondition
  schema: LibraryRemoveSavedSearchInputHttp
  instance:
    savedSearchId: saved1
    expectedRevision: null
  valid: false
- name: LibraryRemoveSavedSearchInputHttp-empty-precondition
  schema: LibraryRemoveSavedSearchInputHttp
  instance:
    savedSearchId: saved1
    expectedRevision: ''
  valid: false
```
