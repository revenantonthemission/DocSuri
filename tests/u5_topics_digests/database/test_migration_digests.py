"""Step 17 (e): U5's applied migration bytes and receipts never change.

Every file U5's chain appends to U4's is pinned with the SHA-256 the runner records
when it applies the file. An edit to an applied file fails here; the only legal change
is a new file appended to the runner's chain together with its pin. The realm's
receipts must equal the pins, and the runner refuses a file whose bytes differ from
its receipt before that file runs, rewriting nothing.

`u5_digest_read.sql` is pinned at its corrected bytes. The repair (ac55d423) corrected
its selection comment once, before this pin, so a realm that recorded the first bytes
is refused and preserved rather than upgraded (code summary, "Migration and remaining
evidence").
"""

import pytest

from scripts import verify_docsuri_u5 as runner
from tests.u5_topics_digests.realm_catalog import admin_connection

U5_CHAIN = (
    (
        "accounts",
        "backend/modules/accounts/u5_lifecycle_tables.sql",
        "fc19fd8852e001bcd211fcbcfe5753e6c2f00dd51c75120acd0b14a3e1425444",
    ),
    (
        "accounts",
        "backend/modules/accounts/u2_lifecycle_effect.sql",
        "1724aa567197a7a9453bda1635d65126afbaee6dccfb49d72c802469a3d86fe0",
    ),
    (
        "accounts",
        "backend/modules/accounts/u2_lifecycle_action.sql",
        "1d1b2b7e3bed153e5594e5b8f1a4da9cad02a7eaac3d471644a7dc5e1ab3d6d2",
    ),
    (
        "accounts",
        "backend/modules/accounts/u5_lifecycle_guard.sql",
        "619137c90a04b5e37ac4426e7861337ad93c5bf6ae7f2e46ac09b82cd659c626",
    ),
    (
        "corpus",
        "backend/modules/corpus/u5_digest_read.sql",
        "9c2f89bfe04ac21e98928264c2f79bf4f0493d9f39e3acc567eab2b5040bb4ab",
    ),
    (
        "accounts",
        "backend/modules/accounts/u5_digest_recipient.sql",
        "4fe8a2115123499e5d76f26956d5d51ca3fdca3e5af1e8c549d65eb418f84474",
    ),
    (
        "topics",
        "backend/modules/topics/u5_schema.sql",
        "c63aff0ab909c50d544f9d447f7a4c7875a454025867f8b463966ba5b9100ece",
    ),
    (
        "topics",
        "backend/modules/topics/u5_erasure.sql",
        "e115a2ff44ae4f2d04e5d22f9725b3564dbb55788de78771589a738e6872c7e1",
    ),
    (
        "topics",
        "backend/modules/topics/u5_run_guard.sql",
        "0e0fb81e5df91c185c6990eea00e7d99c1f0beb6ca74c50cd4e25b81b4fb389b",
    ),
    (
        "personalization",
        "backend/modules/personalization/u5_digest_preferences.sql",
        "a04bc33bff9e2e1a35211c3267815665850a3f5a2dd11090ca95d934d4907d3f",
    ),
    (
        "topics",
        "backend/modules/topics/u5_preference_snapshot.sql",
        "55123c39398396ba8c9109d2bcc71073638f2064c1427264b1c3e793c2f3c042",
    ),
    (
        "topics",
        "backend/modules/topics/u5_schedule.sql",
        "13d9c04a5b27fa7483f2858ee3819a7a784c9b9f4324af09fe1303c8cd2f2628",
    ),
    (
        "topics",
        "backend/modules/topics/u5_unsubscribe_capability.sql",
        "a2886a5457673666781c7ce2932315122f825319e2d23e7671c20019cd5d6a7d",
    ),
    (
        "topics",
        "backend/modules/topics/u5_real_send_retention.sql",
        "05b780de1dfc3a75aeced228f98cbabbc6a3e362e3ec4d8a53ccf724ed13bf29",
    ),
    (
        "topics",
        "backend/modules/topics/u5_refusal_detail.sql",
        "43ce96893b5aec57d79e8d23abd7402c060ab5bc728fba797a20a228fc6cd600",
    ),
    (
        "topics",
        "backend/modules/topics/u5_scheduled_instant.sql",
        "49982d27a43cad0bbc9c0e7cf03744bd3fa38ca97d53b9fff9eda38d0c639c12",
    ),
)
PINS = {relative: pinned for _, relative, pinned in U5_CHAIN}
DIGEST_READ = "backend/modules/corpus/u5_digest_read.sql"
# The bytes the first U5 build applied (8ba35b90), before the comment correction.
DIGEST_READ_FIRST_BYTES = "41c0ec322125996db4b40b9f081a74e3bf71d5e2750dc7bcd7fdc9104ffb3aaf"


def receipts(realm) -> dict:
    with admin_connection(realm) as conn:
        return conn.execute("SELECT schema_hashes FROM public.docsuri_local_identity").fetchone()[
            "schema_hashes"
        ]


def test_the_u5_chain_appends_exactly_the_pinned_files_in_order():
    appended = runner.MIGRATIONS[len(runner.U4_MIGRATIONS) :]
    assert runner.MIGRATIONS[: len(runner.U4_MIGRATIONS)] == runner.U4_MIGRATIONS
    assert appended == tuple((owner, relative) for owner, relative, _ in U5_CHAIN)


def test_every_applied_u5_file_keeps_its_pinned_bytes():
    current = {relative: runner.digest(runner.ROOT / relative) for relative in PINS}
    assert current == PINS
    assert current[DIGEST_READ] != DIGEST_READ_FIRST_BYTES


def test_the_realm_receipts_equal_the_pins_and_every_chain_file(realm):
    recorded = receipts(realm)
    assert {relative: recorded.get(relative) for relative in PINS} == PINS
    chain = {relative: runner.digest(runner.ROOT / relative) for _, relative in runner.MIGRATIONS}
    assert {relative: recorded.get(relative) for relative in chain} == chain


@pytest.mark.parametrize(
    ("relative", "differing_digest"),
    [
        (DIGEST_READ, DIGEST_READ_FIRST_BYTES),
        ("backend/modules/topics/u5_scheduled_instant.sql", "0" * 64),
    ],
    ids=["first-digest-read-bytes", "newest-repair"],
)
def test_the_runner_refuses_an_applied_file_whose_bytes_differ(
    realm, monkeypatch, relative, differing_digest
):
    """`migrate` compares each applied file with its receipt and rewrites nothing."""
    measure = runner.digest
    target = runner.ROOT / relative
    before = receipts(realm)
    assert before[relative] == measure(target) == PINS[relative]
    monkeypatch.setattr(
        runner, "digest", lambda path: differing_digest if path == target else measure(path)
    )
    with pytest.raises(runner.Refused, match="applied migration changed; append a new migration"):
        runner.migrate(realm.root / "environment.json")
    assert receipts(realm) == before


def test_the_chain_holds_one_lifecycle_definition(realm):
    """U5 composes U2's lifecycle tables once (u5_lifecycle_tables.sql) and leaves out
    u2_controls.sql, which would define them a second time."""
    assert "backend/modules/accounts/u2_controls.sql" not in {
        relative for _, relative in runner.MIGRATIONS
    }
    with admin_connection(realm) as conn:
        homes = conn.execute(
            "SELECT n.nspname AS schema, c.relname AS name FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.relname IN ('lifecycle_request','lifecycle_scope') AND c.relkind='r' "
            "ORDER BY 1,2"
        ).fetchall()
        revision = conn.execute(
            "SELECT format_type(atttypid,atttypmod) AS type, attnotnull AS required "
            "FROM pg_attribute WHERE attrelid='accounts.account'::regclass "
            "AND attname='lifecycle_revision' AND NOT attisdropped"
        ).fetchall()
        functions = conn.execute(
            "SELECT p.proname AS name, count(*) AS n FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='accounts' "
            "AND p.proname IN ('guard_lifecycle_effect','lifecycle_effect_action') GROUP BY 1 ORDER BY 1"
        ).fetchall()
    assert homes == [
        {"schema": "accounts", "name": "lifecycle_request"},
        {"schema": "accounts", "name": "lifecycle_scope"},
    ]
    assert revision == [{"type": "uuid", "required": True}]
    assert functions == [
        {"name": "guard_lifecycle_effect", "n": 1},
        {"name": "lifecycle_effect_action", "n": 1},
    ]
