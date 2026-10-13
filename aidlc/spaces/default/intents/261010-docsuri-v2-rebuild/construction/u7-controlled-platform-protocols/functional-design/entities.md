# U7 logical entity model

## Scope and source of truth

This model covers the four entities owned by the `PlatformControl` component
([component catalogue](../../../inception/domain-design/components.md)) for the
retained controlled operator executable. It elaborates types, requiredness,
validation and cardinality; it selects no storage technology, no host and no
process placement. The fenced `yaml` block below is the source of truth for the
entity set; the prose after it is a derived human-readable summary.

Decisions carried in from
[Functional Design questions](functional-design-questions.md): evidence binds
target, input and environment and carries a finite validity window (Q4);
operator authority is a locally provisioned, target-scoped grant (Q2); a
destructive/release effect needs a separately provisioned grant of its own
class (Q3); operations move through `authorized → executing → completed |
failed | unknown` and an unknown stays unknown until reconciled (Q7). The
controlled-operation vocabulary comes from the retained protocol inventory and
never admits an arbitrary command, path or shell (contract C10).

## Authoritative entity definitions

```yaml
entities:
  - name: "PlatformEvidence"
    description: "An immutable, privacy-safe observation of a platform target's state and compatibility, bound to the exact actor-relevant target, input and environment it was observed under."
    attributes:
      - name: "platformEvidenceId"
        type: "identifier"
        required: true
        unique: true
      - name: "targetReference"
        type: "reference"
        required: true
        references: "platform target identity (opaque; the authority domain the evidence is about)"
      - name: "inputBinding"
        type: "value-object"
        required: true
        description: "Digest plus canonical parameters of the inputs the evidence was observed under."
      - name: "environmentBinding"
        type: "value-object"
        required: true
        description: "Platform/runtime identity and version context the evidence is valid for (host class, native tool/runtime version, configuration identity)."
      - name: "generation"
        type: "integer"
        required: true
        description: "Monotonic generation for the target; a new observation produces a new generation, never a mutation of an old one."
      - name: "observations"
        type: "collection"
        required: true
        description: "Structured observed facts (compatibility assessment, capability presence, resource/limit facts). MUST exclude credentials, secrets and private content."
      - name: "compatibility"
        type: "enum"
        required: false
        allowedValues: ["current", "stale", "mismatched", "missing"]
        description: "DERIVED assessment computed at read/precondition time, not a stored value: the evidence against the requesting operation's target, input and environment bindings and its validity window. 'missing' denotes the absence of a required observation, not a stored row."
      - name: "observedAt"
        type: "timestamp"
        required: true
      - name: "maxAge"
        type: "duration"
        required: true
        description: "Finite, per-protocol validity window. Declared when the protocol is admitted; never unbounded."
      - name: "recordedAt"
        type: "timestamp"
        required: true
    constraints:
      - "Immutable once recorded; a later observation creates a new generation with its own id."
      - "Staleness is derived as observedAt + maxAge and is never written as a mutable flag on the record."
      - "Evidence never confers authority; it is an input to an authority-bound precondition check only."
      - "observations carries no credential, secret or private source text."
    relationships:
      - target: "ControlledOperation"
        cardinality: "one PlatformEvidence generation to many ControlledOperations"
        direction: "referenced by"
        description: "Each operation binds exactly the evidence id and generation it was authorized under."

  - name: "OperatorAuthority"
    description: "An independent, locally provisioned grant of a permitted operation set over an explicit target scope to a verified local actor. Three classes exist: routine execution, destructive-release execution, and read-only bounded evidence access. Application administrator status is not this authority."
    attributes:
      - name: "operatorAuthorityId"
        type: "identifier"
        required: true
        unique: true
      - name: "actorReference"
        type: "reference"
        required: true
        description: "Verified local OS user identity. A web application administrator identity can never satisfy this field."
      - name: "targetScope"
        type: "value-object"
        required: true
        description: "Non-empty, explicit set of targets the grant covers. Wildcard or implicit-all scope is invalid."
      - name: "permittedOperation"
        type: "collection"
        required: true
        description: "Allowlist of operation names drawn from the retained protocol inventory. For a routine or destructive-release grant these are executing protocol operations; for an evidence-reader grant they are the read operations (inspectEvidence, readReceipt) only."
        allowedValues: ["retained protocol inventory member (see protocols disposition)"]
      - name: "authorityClass"
        type: "enum"
        required: true
        allowedValues: ["routine", "destructive-release", "evidence-reader"]
        description: "routine and destructive-release grants authorize execution; an evidence-reader grant authorizes bounded read-only access to evidence and receipts for its target scope. A destructive-release grant is provisioned separately and never implied by a routine grant."
      - name: "authorityBinding"
        type: "value-object"
        required: true
        description: "Binds actor + target scope + operation + the provisioning evidence recorded by the controlled local procedure."
      - name: "provisionedAt"
        type: "timestamp"
        required: true
      - name: "revokedAt"
        type: "timestamp"
        required: false
      - name: "revocation"
        type: "enum"
        required: true
        allowedValues: ["active", "revoked"]
        description: "Evaluated at execution time; a revoked grant can never authorize an effect, and revocation takes effect immediately."
    constraints:
      - "targetScope MUST be explicit and non-empty."
      - "authorityClass destructive-release CANNOT be created by widening a routine grant; it requires its own provisioning record."
      - "An evidence-reader grant authorizes read-only access only and can never authorize an effect."
      - "The grant is provisioned only through the controlled local procedure; no network admin surface may mint one."
    relationships:
      - target: "ControlledOperation"
        cardinality: "one OperatorAuthority to many ControlledOperations"
        direction: "referenced by"
        description: "Each operation executes under exactly one current grant of the matching authority class."

  - name: "ControlledOperation"
    description: "A single authorized request to apply one retained operator protocol to one target, bound to its actor, operation, target, input hash, evidence generation and policy before any effect."
    attributes:
      - name: "controlledOperationId"
        type: "identifier"
        required: true
        unique: true
      - name: "operatorAuthorityId"
        type: "reference"
        required: true
        references: "OperatorAuthority"
      - name: "platformEvidenceId"
        type: "reference"
        required: true
        references: "PlatformEvidence (exact generation)"
      - name: "operationName"
        type: "enum"
        required: true
        description: "Must be a member of the retained protocol inventory allowlist for this build. No generic command, path or shell is admissible."
      - name: "authorityClass"
        type: "enum"
        required: true
        allowedValues: ["routine", "destructive-release"]
      - name: "targetReference"
        type: "reference"
        required: true
      - name: "inputBinding"
        type: "value-object"
        required: true
        description: "Canonical input digest plus exact parameters; any change produces a different binding."
      - name: "environmentBinding"
        type: "value-object"
        required: true
        description: "The platform/runtime identity and version context this operation targets; compared against the evidence's environment binding for the mismatch check (BR1.3)."
      - name: "idempotencyKey"
        type: "string"
        required: true
        description: "Caller-supplied key; the pair (idempotencyKey, inputBinding digest) is the replay identity."
      - name: "preconditions"
        type: "collection"
        required: true
        description: "Named precondition checks (evidence compatibility, target match, authority currency) that must hold immediately before the effect."
      - name: "state"
        type: "enum"
        required: true
        allowedValues: ["authorized", "executing", "completed", "failed", "unknown"]
      - name: "effectDisposition"
        type: "enum"
        required: true
        allowedValues: ["not-applied", "applied", "unknown"]
      - name: "requestedAt"
        type: "timestamp"
        required: true
      - name: "startedAt"
        type: "timestamp"
        required: false
      - name: "settledAt"
        type: "timestamp"
        required: false
    constraints:
      - "operationName is restricted to the admitted inventory; unsupported or unverified native semantics fail closed."
      - "Preconditions are re-checked against current authority and target state under the effect's exclusive target lock immediately before the effect; a failed recheck yields no effect."
      - "state transitions follow the operation state machine in functional-spec.md; terminal 'completed' requires effect evidence, never liveness alone."
    relationships:
      - target: "OperationReceipt"
        cardinality: "exactly one ControlledOperation to exactly one OperationReceipt"
        direction: "produces"
        description: "The durable record of the operation's outcome and reconciliation."

  - name: "OperationReceipt"
    description: "The durable, append-only record of one controlled operation: created with the operation at authorization (carrying the actor/target/effect binding), then carrying the outcome and reconciliation when the operation settles. It preserves the binding across restart. In-flight lifecycle state belongs to the operation, not the receipt."
    attributes:
      - name: "operationReceiptId"
        type: "identifier"
        required: true
        unique: true
      - name: "controlledOperationId"
        type: "reference"
        required: true
        unique: true
        references: "ControlledOperation"
      - name: "targetEffectReference"
        type: "reference"
        required: true
        description: "How a later reconciliation read can observe the effect's presence or absence on the target."
      - name: "outcome"
        type: "enum"
        required: false
        allowedValues: ["completed", "failed", "unknown"]
        description: "Recorded when the operation settles; absent while the operation is authorized or executing. The operation, not the receipt, owns the in-flight lifecycle state."
      - name: "reconciliationEvidence"
        type: "value-object"
        required: false
        description: "Structured evidence establishing the applied / not-applied disposition of a previously unknown effect."
      - name: "reconciliationState"
        type: "enum"
        required: true
        allowedValues: ["pending", "not-applicable", "unresolved", "reconciled-applied", "reconciled-not-applied"]
        description: "pending from authorization until the operation settles; not-applicable when the settled outcome is completed or failed; unresolved while the settled outcome is unknown and not yet reconciled; reconciled-applied or reconciled-not-applied once reconciliation evidence establishes disposition."
      - name: "recordedAt"
        type: "timestamp"
        required: true
      - name: "reconciledAt"
        type: "timestamp"
        required: false
    constraints:
      - "Append-only: an existing receipt is never overwritten; reconciliation adds evidence and moves reconciliationState."
      - "An 'unknown' receipt remains unknown until reconciliation evidence establishes disposition; it is never auto-promoted to completed or failed."
      - "A replay with the same idempotencyKey and the same input binding returns this receipt without repeating effects; a changed input under the same key is rejected."
    relationships:
      - target: "ControlledOperation"
        cardinality: "exactly one OperationReceipt to one ControlledOperation"
        direction: "belongs to"
        description: "The receipt is the operation's durable outcome; reads create no new operation."
```

## Entity summary

| Entity | Identity | Purpose | Key invariant |
|---|---|---|---|
| PlatformEvidence | `platformEvidenceId` | Immutable, bound observation of a platform target | Bound and finite-lived; never authority |
| OperatorAuthority | `operatorAuthorityId` | Independent, target-scoped local grant | App admin ≠ operator; destructive-release is separate |
| ControlledOperation | `controlledOperationId` | One authorized protocol application | Vocabulary-limited; preconditions rechecked before effect |
| OperationReceipt | `operationReceiptId` | Durable outcome + reconciliation | One per operation; unknown stays until reconciled |

## Ownership and consistency constraints

- `PlatformControl` is the single owner of all four entities; no other component writes them (U8 reads evidence and receipts only).
- `ControlledOperation` binds to an exact `PlatformEvidence` generation and an exact `OperatorAuthority` grant; a mismatch between the operation's target/input and its evidence binding is invalid.
- A `destructive-release` operation requires an `OperatorAuthority` whose `authorityClass` is `destructive-release`; a `routine` grant can never satisfy it.
- The four entities carry no cross-component reference; `ServiceOperations` consumes them through the read-only interface described in functional-spec.md.

## Deferred detail and evidence prerequisites

- The concrete members of `operationName` and each protocol's `maxAge` come from the retained-protocol reconciliation (Q1/Q5); this model fixes the shape and the admission rule, not the final membership list.
- Storage technology, retention duration and the unresolved-unknown review cadence stay open (Q7 fixes reconciliation semantics; retention policy belongs to operations/NFR design).
- No real destructive or release operation is authorized by this design; all validation uses synthetic targets and inputs.
