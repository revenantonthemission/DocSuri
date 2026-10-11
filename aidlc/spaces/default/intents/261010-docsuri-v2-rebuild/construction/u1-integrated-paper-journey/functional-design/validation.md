# U1 functional design validation

Date: 2026-10-11. These checks validate documents, not a running v2 application.

- `python validate_design.py` (run with `/tmp/docsuri-contract-validation/bin/python`, PyYAML 6.0.3) passed: 21 unique entities match approved ownership; 39 unique rules; required attribute/rule fields, relationship targets, requirement references, 43 local links and content encoding/fence checks.
- The same check matched the exact upstream U1 assignment: 29 rows, including 21 inline acceptance criteria reproduced from their source. The release-wide table has 70 rows: 29 U1 design mappings and 41 explicit later-unit assignments. Nine workflows, 14 local checks, all ten NFRs and nine IB obligations are linked.
- `bun .codex/tools/aidlc.ts engine sensor-traceability --output-path aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/construction/u1-integrated-paper-journey/functional-design/traceability.json --stage-slug functional-design` passed with no gaps, orphans, missing IDs, invalid entries or invalid targets.
- Mermaid's parser validated the derived ER diagram. Its text fallback is present. Entity names were independently checked against the YAML model; cardinality interpretation still requires architectural review.
- The frontend writer checked all 38 documented existing API paths against the current canonical specification. Proposed assistance rediscovery and revision/worker changes are labeled as coordinated amendments, not existing endpoints.
- `git diff --check` passed for tracked changes. Python validation separately reads all newly generated documents.

Graph generation 2026-10-11T07:46:49Z reported no recorded gaps for the generated paths; metadata for recently edited spec, traceability and validator had changed. Checks therefore read the current files directly. This is bounded document validation, not an exhaustive source audit.

The canonical contracts still need their coordinated amendments before affected code. No model task, browser journey, persistence/worker recovery, accessibility conformance, operating capacity, data restore or application test is claimed to have passed here. The exact runnable v2 completion command remains unset pending separate approval when available.
