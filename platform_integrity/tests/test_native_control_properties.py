"""Independent Python/JCS oracle for the restricted SQL control codec and generated plans."""

import psycopg
import pytest
from hypothesis import HealthCheck, given, settings
from psycopg.types.json import Jsonb
from run_support import plans
from test_dispatch_postgres import (
    pipeline as pipeline,
)
from test_operator_roles_postgres import (
    native as native,
)
from test_scoped_run_postgres import (
    scoped as scoped,
)
from test_target_effects import DSN
from test_target_effects import (
    realm as realm,
)

from docsuri_platform_integrity.contracts.codec import canonical, digest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not DSN, reason="isolated DB required")]


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(plan=plans())
def test_sql_control_hash_matches_independent_jcs_oracle(scoped, plan):
    # Safe fixture reuse: this property only evaluates immutable codec functions, no writes.
    payload = plan.model_dump(mode="json")
    with psycopg.connect(DSN, autocommit=True) as owner:
        encoded, fingerprint = owner.execute(
            "SELECT r1_control.control_canonical(%s),r1_control.control_hash(%s)",
            (Jsonb(payload), Jsonb(payload)),
        ).fetchone()
    assert encoded.encode() == canonical(payload)
    assert fingerprint == digest(canonical(payload))
