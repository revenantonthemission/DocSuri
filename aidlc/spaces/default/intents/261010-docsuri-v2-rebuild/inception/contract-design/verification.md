# Contract Design — verification record

Date: 2026-10-11. This record covers the formal specification, not application behavior.

## Reproduction

Run from the repository root with Python and these isolated validation dependencies:
PyYAML 6.0.3, jsonschema 4.25.1, openapi-spec-validator 0.7.2.

```sh
python3 -m venv /tmp/docsuri-contract-validation
/tmp/docsuri-contract-validation/bin/python -m pip install PyYAML==6.0.3 jsonschema==4.25.1 openapi-spec-validator==0.7.2
/tmp/docsuri-contract-validation/bin/python aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/inception/contract-design/verify.py
```

The local environment uses Python 3.9.6. The validator performs no external effects
or application/provider calls. Installing validation packages requires network
access; no project runtime dependency or paid service was added.

## Limits

Specification validation cannot prove runtime authentication, transactionality,
recovery, concurrency, data continuity, provider compatibility or $0 capacity.
The contract's normative checks and open evidence conditions still require the
later implementation and integration evidence listed in the artifact.

The initial authoring checks caught and corrected a temporary generator's set
iteration error and duplicate YAML anchors. The final result is recorded below.

## Executed result

The validator passed: 14 boundary families, 415 schema definitions, 1,421 local
schema references, 141 typed operations, 115 HTTP operations across two valid
OpenAPI 3.1.1 documents, all 19 approved dependency edges and all 70 functional
requirement IDs. Six positive and nine negative schema cases passed.
All declared browser/admin operations have a corresponding external binding;
internal context is excluded from strict browser input schemas, schema copies
agree with the canonical registry, and local artifact links resolve.

The Python environment emits an urllib3/LibreSSL compatibility warning when the
OpenAPI package imports. Validation completed with exit 0 and used only local
references; this is not a verified network-TLS runtime configuration for DocSuri.

## Manual consistency checks

- Notion connection retains protected token configuration; OAuth was not added.
- Anonymous search is preserved, while private work requires current owner access.
- Primary-auth MFA continuation and withdrawn-account recovery do not require an
  already active full session; proof-specific authority is mandatory.
- Export approval binds an immutable artifact and destination; projection
  publication and withdrawal have an explicit authoritative owner.
- No stack, hosting, migration policy, retention duration, service quality target
  or paid fallback was selected. No application source or CI pipeline was changed.
