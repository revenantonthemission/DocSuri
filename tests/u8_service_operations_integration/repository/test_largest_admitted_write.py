"""S4: the largest write admission accepts (U8 plan Step 50(e); scalability-design § 1).

One paper at CorpusContent's production limits is imported into a rehearsal database of
this test's own, through CorpusContent's own `importPaper` under the complete realm's
3 s statement and 5 s transaction bounds, and its database growth and its WAL are
measured between two CHECKPOINTs on one administrator session. The paper: one section
of 200 paragraph blocks of exactly 8,192 bytes (the chunk limit your decision of
2026-11-08 lowered, L1-74, measured again by your answer of 2026-11-09, L1-81; Steps
50(g) and 50(i)), words drawn by a fixed seed from a
fixed vocabulary of 4,096 lowercase ASCII words, and `fullText` filled with the same
words until the document `paper_import` measures is within 4 KiB of the 16 MiB limit.

An overrun of the asserted bounds, or a refusal by the realm's own bounds, is a design
question for the person about the headroom or the per-paper limits: never answered by
raising a bound or importing a smaller paper. No account is made.
"""

from __future__ import annotations

import json
import random
import secrets
import time
import warnings

import pytest
from psycopg import sql

from backend.artifacts import PrivateArtifacts
from backend.modules.corpus.limits import BLOCK_BYTES, PRODUCTION_LIMITS
from backend.modules.corpus.paper_import import PaperSource, convert
from backend.u8_policy import PRODUCTION_OPERATIONS
from docsuri_ops.arrangement.paths import REALM_DATABASES
from docsuri_ops.migration.realm import RealmDatabases, owners_for

SEED = 20261101
BLOCKS = 200
DOCUMENT_LOW, DOCUMENT_HIGH = 16_773_120, 16_777_216

# 64 syllables, two per word: 4,096 distinct lowercase ASCII words, some with a suffix
# (the first four letters alone name the word, so the suffix keeps them distinct).
_SYLLABLES = [c + v for c in "bcdfghjklmnprstv" for v in "aeio"]
VOCABULARY = tuple(
    _SYLLABLES[i // 64] + _SYLLABLES[i % 64] + ("", "n", "ra", "lo")[i % 4]
    for i in range(4_096)
)


def words(rng: random.Random, length: int) -> str:
    """Exactly `length` ASCII bytes of vocabulary words, ending in a letter."""
    parts, size = [], 0
    # The joined text is `size - 1` bytes, so it must pass `length` before the cut: a
    # running size of exactly `length` would leave one byte short (review of 2026-11-09).
    while size <= length:
        word = rng.choice(VOCABULARY)
        parts.append(word)
        size += len(word) + 1
    text = " ".join(parts)[:length]
    return text[:-1] + "a" if text.endswith(" ") else text


def paper_document(token: str, rng: random.Random, full_text: str) -> dict:
    return {
        "meta": {"paperId": f"u8-s4-{token}", "version": 1,
                 "title": "S4 largest admitted paper",
                 "provenance": {"sourceTier": "native_html",
                                "parserVersion": "docmodel-parser@8",
                                "schemaVersion": "1.1.0",
                                "generatedAt": "2026-11-01T00:00:00Z"}},
        "fullText": full_text,
        "sections": [{"id": "s1", "title": "Body", "blocks": [
            {"id": f"s1.p{index}", "type": "paragraph", "text": words(rng, BLOCK_BYTES)}
            for index in range(BLOCKS)]}],
    }


def measured_bytes(document: dict) -> int:
    """The size `paper_import` measures: the validated, converted document, serialised as
    it serialises it (`paper_import.py:142-145`)."""
    converted = convert(document, PRODUCTION_LIMITS)["document"]
    return len(json.dumps(converted, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode())


def build_paper(token: str) -> dict:
    """The paragraphs, then `fullText` filled to land inside the 4 KiB window."""
    document = paper_document(token, random.Random(SEED), "")
    base = measured_bytes(document)
    target = (DOCUMENT_LOW + DOCUMENT_HIGH) // 2
    assert base < target, base
    document["fullText"] = words(random.Random(SEED + 1), target - base)
    assert len(document["fullText"]) == target - base  # `words` is exact (batch-1d fix d)
    size = measured_bytes(document)
    assert DOCUMENT_LOW <= size <= DOCUMENT_HIGH, size
    return document


def checkpoint(conn, name: str) -> tuple[int, str, str]:
    conn.execute("CHECKPOINT")
    size = conn.execute("SELECT pg_database_size(%s)", (name,)).fetchone()[0]
    lsn = conn.execute("SELECT pg_current_wal_lsn()::text").fetchone()[0]
    redo = conn.execute("SELECT redo_lsn::text FROM pg_control_checkpoint()").fetchone()[0]
    return int(size), lsn, redo


def blobs(files: PrivateArtifacts) -> set[str]:
    return {path.name for path in files.root.glob("*.blob")}


def test_one_paper_at_the_production_limits_fits_inside_the_headroom(realm):
    # A change to any value admission or the limits use fails here too.
    assert PRODUCTION_OPERATIONS.footprint_budget_bytes == 8_589_934_592
    assert PRODUCTION_OPERATIONS.footprint_headroom_bytes == 268_435_456
    assert PRODUCTION_LIMITS.max_source_bytes == 16_777_216
    assert PRODUCTION_LIMITS.max_chunks == 200
    assert BLOCK_BYTES == 8_192
    assert len(set(VOCABULARY)) == 4_096
    assert all(word.isascii() and word.islower() and word.isalpha() for word in VOCABULARY)
    token = secrets.token_hex(4)
    document = build_paper(token)
    # Every block is exactly the chunk limit, ending in a letter (batch-1d fix d).
    blocks = document["sections"][0]["blocks"]
    assert len(blocks) == BLOCKS
    assert all(len(block["text"].encode()) == BLOCK_BYTES and block["text"][-1].isalpha()
               for block in blocks)
    source = PaperSource(
        source_key=f"u8-s4-{token}", version=f"key:u8-s4-{token}@v1",
        title="S4 largest admitted paper", authors=("Synthetic Author",),
        source_url="https://example.invalid/u8-s4", published_on=None,
        document=document, metadata={},
    )
    del document
    databases = RealmDatabases.for_realm(realm.root)
    files = PrivateArtifacts.for_profile(realm, "corpus-files", maximum_bytes=16_777_216)
    name = REALM_DATABASES.new("rehearsal")
    before_blobs = blobs(files)
    private_path = None
    with databases.admin() as conn:
        try:
            # The realm bounds every statement at 3 s and `admin()` sets none of its own:
            # a CHECKPOINT after this much writing, or the drop, can take longer. The
            # import's own owner bounds (3 s, 5 s) stay unchanged.
            conn.execute("SET statement_timeout = '60s'")
            databases.create_rehearsal(name)
            start_size, start_lsn, start_redo = checkpoint(conn, name)
            owners, close = owners_for(realm)(name)
            started = time.monotonic()
            try:
                result = owners.papers.import_paper(source, re_embed=True)
            except Exception as error:  # the owner bounds' refusal, reported with its time
                seconds = time.monotonic() - started
                pytest.fail(f"the import was refused by {type(error).__name__} after "
                            f"{seconds:.2f} s: {error}")
            finally:
                close()
            seconds = time.monotonic() - started
            middle_redo = conn.execute(
                "SELECT redo_lsn::text FROM pg_control_checkpoint()").fetchone()[0]
            assert middle_redo == start_redo, (
                "measurement error: a checkpoint started inside the window "
                f"({start_redo} -> {middle_redo})")
            end_size, end_lsn, _ = checkpoint(conn, name)
            wal = int(conn.execute("SELECT pg_wal_lsn_diff(%s::pg_lsn, %s::pg_lsn)",
                                   (end_lsn, start_lsn)).fetchone()[0])
            growth = end_size - start_size
            with databases.admin(name) as target:
                vectors = target.execute(
                    "SELECT count(*) FROM corpus.projection "
                    "WHERE embedding_vector IS NOT NULL").fetchone()[0]
                row = target.execute("SELECT private_path FROM corpus.version WHERE id=%s",
                                     (source.version,)).fetchone()
                private_path = None if row is None else row[0]
            figures = (f"growth={growth} wal={wal} sum={growth + wal} "
                       f"import_seconds={seconds:.2f}")
            # The figures reach the phase's log on a pass too, for the code summary (S4).
            warnings.warn(f"S4 figures: {figures}", UserWarning, stacklevel=1)
            assert result["disposition"] == "imported", (result, figures)
            assert vectors == 200, (vectors, figures)
            assert growth < 100_000_000, figures
            assert growth + wal < 268_435_456, figures
            new_blobs = blobs(files) - before_blobs
            assert new_blobs == {private_path}, (sorted(new_blobs), private_path, figures)
        finally:
            for blob in sorted(blobs(files) - before_blobs):
                files.erase(blob)
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)))
    assert blobs(files) == before_blobs
