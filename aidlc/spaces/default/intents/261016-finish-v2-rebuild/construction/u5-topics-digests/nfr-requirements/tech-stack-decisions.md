# Tech Stack Decisions — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests. Sources: confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q2), [technology stack](../../../../codekb/DocSuri/technology-stack.md) (brownfield constraint), constraint register (C-01 $0, C-06 stack retention).

## Decision

**No new technology choices.** U5 joins the built backend as a module using the established patterns, and adds no frameworks, providers or paid services. [Q2]

| Area | Choice | Rationale |
|---|---|---|
| Backend module | Python + FastAPI patterns of the built modules; repository-per-owned-aggregate against the shared PostgreSQL | Proven by the built units; keeps one writer per owned table; avoids a second store [Q2; C-06] |
| Scheduling | The application's existing scheduler/worker entry points (no new broker or scheduler dependency) | $0 constraint; the built application already runs workers [Q2; NFR6] |
| Delivery carrier | The built application's email delivery capability — local sink in test profiles; maintainer-configured free SMTP (or equivalent) in real operation (BR1.4) | $0/local only; real delivery evidence recorded via pathKind `real` [Q2; NFR6] |
| Frontend contribution | Established Next.js/SWR/CSS-Modules patterns of the built workspace | Consistency, accessibility conventions, no new UI stack [Q2; NFR5] |
| Persistence of digest state | The shared PostgreSQL through this module's own repositories (six owned entities) | Ownership model; no cross-module writes [Q2] |

## Rejected Alternatives

- **A separate scheduler/broker service** — rejected: adds operational burden and dependency risk under $0 with no capability gain over the existing worker path. [Q2]
- **A third-party digest-email SaaS** — ineligible by policy ($0, no paid services). [constraint C-01]
- **A second datastore** — rejected: violates the one-writer/single-store ownership model and adds migration surface. [Q2]

## Verification Notes

- The exact delivery configuration (which SMTP/free path) is operational configuration, not a stack choice; real-delivery evidence checks it at U5's verification and again cumulatively at U8. [Q2]
