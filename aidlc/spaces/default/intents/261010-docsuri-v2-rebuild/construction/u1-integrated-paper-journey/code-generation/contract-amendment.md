# Coordinated U1 contract amendment

Date: 2026-10-11. Status: formal specification amendment during approved Code
Generation Step 1. Application implementation and executable closure are pending.

The approved functional design's contract revision plan is applied to the
canonical inception contract summary using ordinary guarded file edits. No stage
state, approval, historical review or freeze override is changed. The original
Contract Design review-01 describes release 1.0.0, not these amended bytes.

## Release and compatibility

Release 2.0.0 is coordinated across the shared C00 registry, typed contract blocks,
C13 browser OpenAPI and controlled evidence OpenAPI. The product namespace
`/api/v2` remains unchanged; the contract release version is a separate concept.
Required browser preconditions and worker claim evidence are breaking changes.
Shared JobReceipt/JobSnapshot now require immutable acceptedAt, affecting later
durable-work consumers too; each owner must preserve original acceptance time.
All contract blocks therefore carry the same coordinated release version.

No deployed consumer is assumed upgraded. Existing production routes and legacy
generated bindings remain untouched by this documentation change. U1's explicit
local assembly will consume generated bindings for these canonical shapes; later
U2–U8 contributions must adopt compatible bindings before their affected paths
are enabled. Existing generators and the shared schema catalogue remain the
single binding path; handwritten parallel wire models are not authorized.
Compatibility and real consumers must be verified before removing any old route.

## Changes

- Account unlink/profile, saved paper/query removal, history clear, settings,
  onboarding/reset and administrator entitlement changes transmit required
  expectedRevision. Reads retain distinct input shapes. Current authorization
  precedes exact original-intent receipt replay, which precedes fresh CAS.
- History reads expose a non-null clearBoundary, distinct from pagination
  snapshot and server-captured Discovery cutoff. Personalization settings share
  one control revision; reset advances a separate input boundary. Administrator
  assignment reads expose a safe initial control token without creating state.
- C06 retained-result history supports a fresh authenticated return by exact
  paper/version without retained job IDs. Present result availability is distinct
  from terminal job state. Reads create no work, claims, history facts or debit.
- C06/C14 specify worker-bound acquire, renewal, replacement and protected payload
  reads. Lease revision, job revision and fence are separate. Dispatch proposals
  cannot allocate owner sequence/revision. Direct and relayed completion use the
  same authority/fence/input/CAS validation and settlement obligations.
- Job receipts/snapshots preserve acceptedAt. History createdAt projects it.
  PaperAssistance's virtual empty glossary is owner/policy-bound, read-only and
  captured at acceptance; later editing must compare its initial token.
- Guarded effects hold current account/session/consent and source barriers on the
  target owner's transaction connection. Owner-controlled guard functions expose
  no arbitrary foreign writes. Long inference runs outside guard transactions.

U1 payload retrieval is explicitly typed for PaperAssistance. Other owners' codecs
remain unavailable until their unit coordinates and verifies them. This preserves
later novelty cancellation and export reconciliation semantics rather than
claiming the assistance payload can serve every job kind.

## Verification and open evidence

The existing standalone document validator checks references, OpenAPI consistency,
all 70 FR IDs and 19 dependency edges. Added positive controls and missing/null/
empty precondition cases exercise the changed browser shapes. Targeted semantic
checks verify browser bindings, claim operations and owner/job revision separation.

These checks verify the formal amendment only. Contract R-01 and R-03 remain open
until actual mounted browser and persistent worker tests demonstrate the behavior.
Contract R-02 (durable research draft rediscovery) remains U4 work. Infrastructure
R-01 remains open until real runtime roles and two-connection revocation ordering
pass on the selected persistent PostgreSQL volume. No review finding is declared
closed by a schema-only pass.

Reproduce document validation with the existing isolated validator environment:

```bash
/tmp/docsuri-contract-validation/bin/python aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/inception/contract-design/verify.py
```

This is not the Construction Verification Command, which remains unset.
