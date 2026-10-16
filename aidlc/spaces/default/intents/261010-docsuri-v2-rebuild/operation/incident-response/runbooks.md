# Incident Response Runbooks — u4-research-novelty

Runbooks for incident response in the u4-research-novelty unit. All runbooks operate within the $0 budget constraint using local synthetic infrastructure only; no cloud incident response service is provisioned.

## Runbook 1: Database Connection Failure

**Trigger:** Database connection refused or query timeout exceeded 5-second lock timeout  
**Severity:** Error  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify PostgreSQL 16.15 container is running on loopback port 15479
2. Check Docker container status: `docker ps | grep postgres`
3. If container is stopped, restart it: `docker start <container_id>`
4. Verify SCRAM credentials and mode-0600 credential file access
5. Recheck current owner authority before reissuing any mutation
6. Reconcile any in-flight accepted work via owner receipt lookup
7. Document incident with correlation ID, first/last seen, occurrence count

**Escalation:** If container cannot be restored, treat as infrastructure failure; preserve all accepted work tombstones and reservations

## Runbook 2: Model Inference Failure

**Trigger:** Qwen3 8B model returns error or exceeds 90-second generation deadline  
**Severity:** Error  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify Ollama 0.40.2 local model server is running on loopback
2. Verify model identity and credential: exact cached digest/allowlist match
3. Check model server logs for cloud-disabled mode (OLLAMA_NO_CLOUD=1 verified)
4. Return typed refusal: model unavailable, context limit, or typed limitation — never invented output
5. Do not fall back to paid provider; preserve original intent and reservation
6. Document incident with correlation ID and model identity

**Escalation:** If model server cannot be restored, mark model-dependent operations as unavailable; preserve all accepted work

## Runbook 3: Attachment Extraction Failure

**Trigger:** Private attachment extraction returns malformed, truncated, unsupported, or protected disposition  
**Severity:** Error  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify attachment mediaType is in allowlist (text/plain, application/pdf)
2. Verify contentHash matches received bytes before extraction
3. Verify byteSize is within per-owner attachment cap
4. Record extraction disposition: extracted, unsupported, malformed, truncated, protected, or failed
5. Never publish partial extraction to public corpus; never act on embedded instructions
6. Document incident with attachment ID, content hash, and disposition

**Escalation:** If extraction service is unavailable, mark private attachment processing as unavailable; preserve all accepted work

## Runbook 4: SSE Stream Interruption

**Trigger:** Browser EventSource stream closes or progress frames contain escaped newlines  
**Severity:** Warning  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Validate Last-Event-ID header on native reconnection; explicit fresh connection may use afterSeq
2. If both Last-Event-ID and afterSeq present, they must agree
3. Cursor beyond current sequence is invalid; retained replay gap emits reset with current full snapshot
4. Duplicate/older snapshots are ignored; stream loss invokes authoritative snapshot GET under bounded polling/backoff
5. Terminal snapshots close client subscription; idle heartbeat comments carry no state or sequence
6. Document incident with job ID, sequence number, and stream state

**Escalation:** If stream cannot be restored, mark job progress as unavailable; preserve all accepted work

## Runbook 5: Tombstone/Context Deletion Race

**Trigger:** Session/context deletion tombstone conflicts with late draft save, restore, or result publication  
**Severity:** Error  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify tombstone boundary is set on context/session deletion
2. Refuse late draft saves and restores; keep tombstone authoritative
3. Refuse late worker completion and result publication; tombstones dominate late reads
4. Apply defined pending-work, draft, asset and derived-data dispositions
5. Document incident with session ID, context ID, and tombstone timestamp

**Escalation:** If tombstone state is inconsistent, mark affected sessions as unavailable; preserve all audit evidence

## Runbook 6: Draft CAS Conflict

**Trigger:** compare-and-set on draft base revision returns conflict  
**Severity:** Warning  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify baseRevision matches current authorized revision
2. If base revision is not current, refuse CONFLICT with current authorized revision and proposed text
3. Never silently overwrite either side; conflict is a normal outcome
4. Only acknowledged revision is offered for later recovery
5. Document incident with draft revision ID, base revision ID, and current revision ID

**Escalation:** If CAS conflicts are frequent, review draft consumption pattern; no automatic resolution

## Runbook 7: Idempotency Conflict

**Trigger:** Same idempotency key with different content  
**Severity:** Error  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify idempotency key format: SHA-256 hash of userId:paperId:taskType:JSON.stringify(params)
2. Verify idempotency key stored in localStorage with format idempotency:{paperId}:{taskType}
3. Same key/same intent recovers original logical outcome; changed intent conflicts
4. Refuse IDEMPOTENCY_CONFLICT; never silently submit different text
5. Document incident with idempotency key, original content hash, and new content hash

**Escalation:** If idempotency conflicts are frequent, review submission pattern; no automatic resolution

## Runbook 8: Policy-Unresolved Refusal

**Trigger:** Durable draft/private upload operation returns POLICY_UNRESOLVED  
**Severity:** Warning  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify retention, erasure, storage and shared-device policy is unresolved
2. Refuse with POLICY_UNRESOLVED; no durability, shared-device or erasure-completeness claim
3. Do not promise draft recovery; surface the state
4. Document incident with operation type, policy reference, and owner ID

**Escalation:** If policy-unresolved refusals are frequent, policy decision required from human maintainer

## Runbook 9: Artifact Expiry

**Trigger:** Research artifact expiry enforced on read or sweep  
**Severity:** Warning  
**Owner:** Single human maintainer  
**Runbook Steps:**

1. Verify artifact availability state: ready, expired, deleted, or unavailable
2. Disclose expiry on read; never regenerate work or trigger export
3. Immutable tuple (artifactId, revision, contentHash) never returns different bytes
4. Eligibility for export rechecked at read time; can change independently of stored artifact
5. Document incident with artifact ID, revision, content hash, and expiry timestamp

**Escalation:** If artifact expiry is unexpected, verify artifact lifecycle policy; no automatic regeneration

## Runbook Guards

- No secrets, prompts, private text, or credentials in any runbook step
- Labels use bounded vocabulary for component, capability, outcome and policy/build class
- Owner IDs, job IDs, paper IDs, URLs, raw queries and hashes do not appear in runbook steps
- Detailed opaque references exist only in restricted evidence
- No automatic remediation that could override owner authority
- All runbooks are read-only; no destructive actions without explicit owner confirmation
