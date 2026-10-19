# Intent Backlog — Finish the DocSuri v2 rebuild

Date: 2026-10-16 (Asia/Seoul)
Isolated run feeding the approval-handoff brief. All items are Must-have for the finish release; there are no Should/Could/Won't items because no new features are in scope. [Q2]

| ID | Work package | Priority | Depends on | Completion evidence |
|---|---|---|---|---|
| IB-01 | Re-anchor the finish plan: reconcile the approved unit catalogue and 70-row capability map against current code and contracts before building on them | Must | — | Reconciliation notes; stale claims corrected or flagged |
| IB-02 | Select and get human approval for the construction verification command | Must | IB-01 | Approved exact command recorded before any unit checkpoint verifies |
| IB-03 | U5 — topics & digests: design, implement, verify, merge (persisted follow/unfollow, digest settings, content selection, delivery outcomes, unsubscribe, lifecycle participant) | Must | IB-02; U1–U3 merged | Real integration demo incl. scheduling, consent and delivery-failure paths |
| IB-04 | U6 — approved export: design, implement, verify, merge (owner connection, preview, explicit approval, reconciled Notion effect) | Must | IB-02; U4 merged (PR #51 done) | Real export effect to an authorized test destination with reconciliation |
| IB-05 | U8 — complete service integration: assemble all views and lifecycle participants; cumulative verification | Must | IB-03, IB-04 | Whole-application verification across real boundaries |
| IB-06 | Honest tail redo: build/CI and the seven operation stages over the complete application, covering the real operating mode (continuous local service on real data) | Must | IB-05 | Operation evidence that describes the finished application truthfully |

Sequence follows risk-first: re-anchor, gate on the verification command, build the two library units, assemble, then redo the tail. [Q3] [Q4] [Q5]
