"""The standing job: the scheduler account's one long-running program
(`docsuri-standing`), running one lane per task without overlapping a task with
itself: the availability heartbeat, the agent's status and isolation checks, the
scheduled backup and verification, and hourly housekeeping (reliability-design § 11).

See the approved plan:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

__all__: list[str] = []
