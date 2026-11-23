"""A6's effect kinds (U8 plan Step 27; the person's decision of 2026-10-25).

Each is run by one of PlatformControl's two drivers (`u8_platform/drivers/`): the
arrangement driver through the fixed programs on this Mac, the realm driver on the
composed realm. U7's three kinds stay in U7's `enums.EFFECT_KINDS`, as built, and U7's
bounded child refuses every kind here.
"""

from __future__ import annotations

EFFECT_DATABASE_BACKUP = "database-backup"
EFFECT_DATABASE_RESTORE = "database-restore"
EFFECT_DATABASE_RECREATE = "database-recreate"
EFFECT_DATABASE_REMOVE = "database-remove"
EFFECT_SERVICE_CONTROL = "service-control"
EFFECT_TUNNEL_ROUTE = "tunnel-route"
EFFECT_ISOLATION_CHECK = "isolation-check"
EFFECT_PROFILE_CHANGE = "profile-change"
EFFECT_COPY_DISPOSE = "copy-dispose"
EFFECT_V1_LIFECYCLE_APPLY = "v1-lifecycle-apply"
EFFECT_DECISION_RECORD = "decision-record"
# A lone ledger copy onto the backup volume (L1-5, Step 64(c)).
EFFECT_LEDGER_COPY = "ledger-copy"
U8_EFFECT_KINDS = (
    EFFECT_DATABASE_BACKUP,
    EFFECT_DATABASE_RESTORE,
    EFFECT_DATABASE_RECREATE,
    EFFECT_DATABASE_REMOVE,
    EFFECT_SERVICE_CONTROL,
    EFFECT_TUNNEL_ROUTE,
    EFFECT_ISOLATION_CHECK,
    EFFECT_PROFILE_CHANGE,
    EFFECT_COPY_DISPOSE,
    EFFECT_V1_LIFECYCLE_APPLY,
    EFFECT_DECISION_RECORD,
    EFFECT_LEDGER_COPY,
)
