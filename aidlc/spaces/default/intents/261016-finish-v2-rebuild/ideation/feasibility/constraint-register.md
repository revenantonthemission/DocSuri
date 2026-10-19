# Constraint Register — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Isolated run feeding the approval-handoff brief. Sources: [feasibility-questions.md](feasibility-questions.md), [intent statement](../intent-capture/intent-statement.md), [market trends](../market-research/market-trends.md), [build-vs-buy](../market-research/build-vs-buy.md).

| ID | Constraint | Type | Source |
|---|---|---|---|
| C-01 | $0 budget: free or local stacks only; no paid SaaS, APIs or subscriptions | Budget | [Q4] [build-vs-buy.md] |
| C-02 | No new product features beyond current capability parity in the first finished release | Scope | [intent-statement.md] |
| C-03 | Local-only operation: no cloud services or accounts in use | Technical | [Q6] |
| C-04 | Personal-data privacy and consent handling applies (accounts, drafts, digests); no PCI/HIPAA/SOC2 scope | Regulatory | [Q2] |
| C-05 | Content-licensing obligations apply to ingested material; terms may tighten over time | Regulatory | [Q2] [market-trends.md] |
| C-06 | Existing stack retained: Python backend, Next.js frontend, local model runtimes, synthetic realms | Technical | [Q3] |
| C-07 | Integration set fixed to the retained systems (Notion export, Google/ORCID, citation/content sources, local models, operator executable) | Technical | [Q1] |
| C-08 | Solo maintainer with coding agents; no other approval roles | Organizational | [Q5] |
| C-09 | No fixed deadline; maintainer review time is the scheduling resource | Organizational | [Q4] |
| C-10 | The construction verification command stays unset until a human approves the exact command; no checkpoint verifies before that | Process | [approval-handoff Q2, carried risk] |
