# U1 NFR design document validation

Date: 2026-10-11. Scope: six logical design documents and traceability. No application, model, infrastructure or load experiment ran.

## Executed checks

From the repository root:

```sh
python3 aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/construction/u1-integrated-paper-journey/nfr-design/validate_design.py
bun .codex/tools/aidlc.ts engine sensor-traceability --output-path aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/construction/u1-integrated-paper-journey/nfr-design/traceability.json --stage-slug nfr-design
bun .codex/tools/aidlc.ts engine sensor-upstream-coverage --output-path aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/construction/u1-integrated-paper-journey/nfr-design/security-design.md --stage-slug nfr-design --consumes performance-requirements,security-requirements,scalability-requirements,reliability-requirements,observability-requirements,tech-stack-decisions,functional-spec,contract-summary --deliverables performance-design,security-design,scalability-design,reliability-design,observability-design,logical-components
```

- Local checker passed: six documents, all 37 detailed upstream requirements mapped once to 37 named solutions, 80 local file links, nine exact functional references. It cross-checks the upstream requirement tables and their traceability rather than assuming the expected count.
- Traceability sensor passed with zero gaps, orphans, missing/invalid entries or targets.
- Upstream-coverage sensor scanned all six deliverables and found all eight declared consumed artifacts referenced, with zero findings.
- Required-sections sensor passed separately for all six documents (H2 counts 3, 7, 3, 3, 3 and 6 in performance/security/scalability/reliability/observability/logical order).
- No implementation snippets or Mermaid diagrams occur in the six deliverables; TS/JS snippet checks and diagram parsing have no applicable input. Encoding and local file existence checks passed; link fragments are outside the local validator's checks.
- `git diff --check` passed for tracked changes. The document validator read the new untracked documents directly.

The initial upstream sensor invocation omitted its explicit input list and returned a vacuous no-upstream result; that was not accepted as coverage evidence. A subsequent JSON-list invocation exposed that the CLI expects comma-separated values. The complete invocation above then passed over the intended inputs. Neither case required changing product content.

## Evidence and limits

Graph coverage at generation 2026-10-11T08:32:16Z reported no recorded gaps and matching metadata for the six design documents, upstream traceability/checker and CONVENTIONS.md. Subsequent integration edits were read and checked directly. This is a best-effort index signal, not proof of completeness.

The package selects owner-local durable receipts, bounded admission and reconciliation, fenced claims, current-authority ordering, safe rendering and source delivery, bounded observation and isolated restore mechanisms. PaperAssistance owns the initial empty glossary and immutable accepted snapshot; Personalization owns defaults. The shared authority guard and cross-owner accounting protocol have distinct boundaries.

These checks establish document structure and traceability only. Semantic adequacy requires independent review. Canonical contract amendments, concrete adapter guarantees, permitted handling, finite values, useful real-model results, recovery, public capacity and human-agreed numeric targets remain prerequisites for affected implementation or operation. The exact runnable unit-completion command remains unselected and requires the separately agreed human approval.
