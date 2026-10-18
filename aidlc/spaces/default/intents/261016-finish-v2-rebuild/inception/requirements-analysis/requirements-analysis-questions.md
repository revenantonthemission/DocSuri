# Requirements Analysis Questions — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Isolated run: produces this workflow's requirements record so Units Generation can trace U5/U6/U8. Inputs: [intent statement](../ideation/intent-capture/intent-statement.md), [scope document](../ideation/scope-definition/scope-document.md), and the reverse-engineering inventory (business overview, architecture, code structure) for the current capability surface.

## Q1. What should this requirements record cover?

A. The finish release's requirements: what U5, U6 and U8 must deliver, the honest tail/production-level bar, and retained capabilities recorded as already-delivered context — not a re-enumeration of all twenty capability rows
B. A full re-enumeration of every retained capability as if from scratch
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q2. What must U5 (topics & digests) deliver?

A. Persisted topic follow/unfollow; per-topic digest settings (cadence, delivery time in the owner's timezone, content window, inherited language/level); content selection from eligible corpus; recorded delivery outcomes with reconciliation of unknown outcomes; unsubscribe honored even with queued work (no send after unsubscribe); lifecycle-participant registration so account withdrawal stops digests
B. A different set (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q3. What must U6 (approved export) deliver?

A. Owner Notion connection (token-based, protected); read-only inspection and preview of a prepared artifact that never triggers an export; one explicit approve-and-export action bound to the exact artifact revision and chosen destination; outcome states sent/failed/unknown with reconciliation and no silent duplicate; invalidated approvals on artifact/destination change or revoked authority
B. A different set (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q4. What must U8 and the tail redo deliver?

A. U8: assemble all views and lifecycle participants into one application with cumulative whole-application verification through real boundaries. Tail redo: build/CI plus all seven operation stages produce real evidence over the complete application, covering its real operating mode — a continuously running local service on real accounts and real papers
B. A different set (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A

## Q5. Which non-functional requirements bind the new units?

A. Owner isolation on every read/write; consent honored for digests (late consent changes stop delivery); Notion tokens stored protected and never exposed; digest delivery and export effects idempotent with explicit reconciliation; Korean responsive UI and the established WCAG 2.2 AA target; $0 free/local operation with no paid fallback
B. A different set (say under Other)
C. Not applicable

X. Other (please specify)

[Answer]: A
