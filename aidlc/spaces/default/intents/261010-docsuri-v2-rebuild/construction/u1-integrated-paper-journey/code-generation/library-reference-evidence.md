# Library reference behavior

Date: 2026-10-11. Code Generation Steps 7/8 remain in progress.

## Implemented

The existing Library owner repository now preserves a submitted query and its
refinements as durable saved work, reads saved queries directly or in stable
owner order, reads recorded history, and removes saved paper/query references.
Reading a saved query preserves its recorded vocabulary and performs no search
or model work. Query text is bounded to 2 KiB, the stored context to 16 KiB, an
optional label to 100 characters, and saved-query allocation to 100 per synthetic
account. These are local experiment bounds, not public-service product limits.
Allocation exhaustion rejects new writes; it never evicts saved work or receipts.

Mutations require current account/session authority before exact operation
receipt replay. Fresh removals then require the exact current reference revision.
The removal receipt survives deletion; replay after a later resave returns the
old receipt without deleting the new reference. A withdrawn paper may be removed
from the owner's library without deleting or regaining access to its corpus
source. Unknown commit replies reconcile the original operation identity.

Saved-query creation uses a server-allocated reference identity and stores its
original receipt. Existing canonical query shape is validated through generated
bindings; no handwritten parallel wire model was added. Storage uses only the
Library schema and its existing owner principal. No migration or service-data
reset was required. The current list seam has finite limits and stable ordering;
canonical page/cursor assembly remains part of the API layer, not claimed here.

## Executed verification

Scoped Ruff formatting and lint passed. The exact scoped development commands:

```text
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

- Component scope: **96 passed in 3.13 seconds**, including six Library context
  cases for exact submitted context, labels, older vocabularies and malformed or
  excessive inputs.
- First repository scope: **43 passed in 73.17 seconds**. Seven added cases cover
  fresh-repository rediscovery, changed intent, stale revision, deletion replay,
  later resave, withdrawal, revocation, clear preserving saved queries and a lost
  removal response.
- After adding a valid second-owner session and direct owner-bound query read:
  **44 passed in 77.40 seconds**, with zero skips/errors/failures. B can save,
  read and remove its own query, cannot directly read or remove A's query, and A
  retains its authorized read/removal. This supplements the earlier invalid
  session-substitution denial rather than treating it as equivalent evidence.

All database checks use the owned persistent PostgreSQL diagnostic realm and
real runtime grants. Test cleanup deletes only exact saved-query identities
created by that test helper, retains operation receipts, and revokes the exact
new B session. It never clears the journey database or unknown references.
No live model execution was required for these Library checks.

Trace: BR4.1–BR4.5, FR5.1–FR5.3, LC07/08/09, current-authority and recovery
obligations. API/browser integration, final per-module coverage, public capacity
and the full U1 journey remain pending. This is an intermediate component
checkpoint, not a completed unit or approved completion command.
