"""The realm's databases are UTF-8 with the C locale (U8 plan Step 48(e)-(f); the
tech-stack decision on database encoding and locale).

Read through the operations login on `docsuri_u8`: `pg_database` is a shared catalogue,
and a session on a template would block `CREATE DATABASE`.
"""

from __future__ import annotations

EXPECTED_DATABASES = {
    "docsuri_u8", "docsuri_u8_template", "docsuri_u8_platform", "postgres", "template0",
    "template1",
}
WORDS = ["하", "a", "가", "B", "é", "나", "Z", "각"]


def test_every_realm_database_is_utf8_with_the_c_locale(connect):
    with connect("operations") as conn:
        rows = conn.execute(
            "SELECT datname, pg_encoding_to_char(encoding) AS encoding, datcollate, datctype, "
            "datlocprovider::text AS provider FROM pg_database").fetchall()
    assert EXPECTED_DATABASES <= {row["datname"] for row in rows}
    for row in rows:
        assert (row["encoding"], row["datcollate"], row["datctype"], row["provider"]) == (
            "UTF8", "C", "C", "c"), row["datname"]


def test_text_sorts_by_code_point(connect):
    with connect("operations") as conn:
        ordered = [row["v"] for row in conn.execute(
            "SELECT v FROM unnest(%s::text[]) AS t(v) ORDER BY v", (WORDS,)).fetchall()]
    assert ordered == ["B", "Z", "a", "é", "가", "각", "나", "하"]
    assert ordered == sorted(WORDS)
