# Owned local HTTPS transport

The journey realm now binds `https://127.0.0.1:18039`; the historical diagnostic
HTTP profile remains available for its original mounted-slice evidence. No
system trust store was changed. This is isolated local transport, not public
hosting or browser-wide readiness.

Provisioning creates an owned P-256 key and short-lived self-signed certificate
with the exact loopback IP SAN, server-auth usage and environment expiry. A
private manifest pins run/database/origin, certificate and SPKI hashes. Reads
are bounded, regular-file, no-follow and single-link; provisioning is serialized
under an owned lock. Partial, changed or expired material refuses adoption.
Files and their parent directory are fsynced before acknowledgement. A complete
retry revalidates and fsyncs the directory without rotating the key.

The actual TLS component probe mounts Uvicorn on an ephemeral loopback socket.
An HTTPX client explicitly trusts only the generated certificate, checks the
served DER fingerprint and rejects a wrong hostname. Secure, HttpOnly,
SameSite=strict cookies round-trip over that connection. Other cases cover
invalid realms/origins/expiry, changed/partial records, FIFO and hard-link
custody, and a failed directory fsync followed by an unchanged-key retry.

## Executed checks

- `python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json`: 177 collected/passed in 3.47 seconds.
- `python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json`: 84 collected/passed in 22.94 seconds.
- Both have zero errors, failures or skips, exit 0 and unchanged tested source
  fingerprint `297d61d3023b02903e99ebed6d90ea7779fe056801b5d3478faad8606f5ccd0f`.
- Scoped Ruff format/check passed. Per-module cumulative coverage is deferred
  to the planned measured pass; these results do not establish that floor.
- `backend/.venv/bin/python scripts/prepare_docsuri_u1_transport.py --environment-file /tmp/docsuri-u1-run/environment.json` provisioned the actual owned journey certificate, SHA-256 `b8cf3c3d8406ff1dcc938f50b26fe81cda92e28e0a5795e58a0459b5f6d9f767`.

Protected result/source records and JUnit files are retained as
`/tmp/docsuri-u1-run/tls-final-{component,repository}-{result.json,junit.xml}`.
The preceding 176-case component attempt passed before the directory durability
addition; the 177-case run is the final source-bound evidence.

## Remaining boundaries

This does not yet prove the real account API, CSRF bootstrap, mounted browser
session, SSE or complete research journey. Browser verification will use an
isolated profile and narrowly scoped SPKI trust exception, with independent
exact certificate/host/expiry checks. A SPKI exception alone is not hostname or
expiry verification. Normal model assistance remains unready for the recorded
semantic failures; no new model experiment was run in this slice.
