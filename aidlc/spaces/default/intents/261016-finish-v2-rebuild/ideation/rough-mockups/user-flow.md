# User Flows — Finish the DocSuri v2 rebuild (new capabilities only)

Date: 2026-10-16 (Asia/Seoul)
Isolated run. Sources: [rough-mockups-questions.md](rough-mockups-questions.md), [wireframes.md](wireframes.md).

## Flow 1 — Follow a topic and manage digests (U5)

- Persona: the maintainer (sole user)
- Trigger: wants new content on a subject gathered and delivered periodically
- Steps:
  1. Topics view (empty or populated) -> activate "follow new topic" -> system records the follow and shows it in the followed list
  2. Topic row -> "digest settings" -> settings form opens bound to that topic
  3. Choose cadence, delivery time, content window -> save -> acknowledged settings shown (not silently assumed)
  4. Digest delivery time arrives -> system selects eligible content, prepares and delivers the digest -> outcome recorded and visible
- Success outcome: the topic appears in the followed list with its settings acknowledged; digests arrive as configured
- Error paths:
  - No eligible content in the window -> digest says so explicitly; not counted as a delivery failure
  - Delivery fails or outcome unknown -> status shows the uncertainty; reconciliation before any duplicate send
  - Unsubscribe after queueing -> consent honored despite the queued work; no send after unsubscribe

## Flow 2 — Inspect, approve and export an artifact (U6)

- Persona: the maintainer
- Trigger: wants a completed research/analysis artifact in their Notion workspace
- Steps:
  1. Export view (or artifact view) -> open the prepared artifact -> read-only preview (this never triggers an export)
  2. Choose the destination (owner's configured Notion workspace/page)
  3. Activate "approve and export" -> system binds the approval to the exact artifact revision and destination, then performs the export
  4. Outcome status shown: sent, failed, or unknown
- Success outcome: the artifact exists at the chosen destination exactly once, with the outcome reconciled
- Error paths:
  - Artifact or destination changed after approval -> old approval invalidated; re-approval required
  - Export response lost (timeout after remote success) -> status shows unknown; reconciliation resolves without a silent duplicate
  - Wrong owner / revoked authority -> denied; nothing exported

## Flow 3 — Assembled whole (U8)

- Persona: the maintainer
- Trigger: daily use of the finished service
- Steps:
  1. Open the workspace -> assembled navigation exposes search, library, topics, research, export, settings coherently
  2. Any journey (find -> understand -> save -> revisit, topics, research, export) runs through real boundaries
  3. Service runs continuously on this machine with real accounts and real papers [scope-definition Q6]
- Success outcome: every capability reachable and working as one experience
- Error paths:
  - Interruption/restart -> work resumes without half-applied results
  - Component failure -> the failing capability degrades with a plain explanation; the rest keeps working
