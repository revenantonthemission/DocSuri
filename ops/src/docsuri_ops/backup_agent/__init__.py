"""The backup agent: the one program that writes, reads back and disposes of backup
sets on the backup volume, run under the backup account through its fixed program
`docsuri-backup-agent <command>` (Workflow 19).

Unattended commands are accepted only from the scheduler account and in-person
commands only from the operator account; the sudo rules are the first gate and the
agent's own check the second (BR4.3). See the approved plan:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

__all__: list[str] = []
